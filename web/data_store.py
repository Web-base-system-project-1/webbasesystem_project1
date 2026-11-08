"""서버가 켜질 때 한 번만 CSV를 읽어 메모리에 들고 있는다.

요청마다 파일을 다시 읽지 않는다. 읽는 폴더는 .env 의 DATA_DIR 로 바꿀 수 있고,
지정하지 않으면 Git 으로 공유하는 예시 데이터 폴더를 사용한다.
"""

import json
import os
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = "data/sample/example"

SHARE_COLUMNS = [
    "domestic_id", "foreign_id", "field", "year",
    "collab_count", "international_total", "share",
]


class DataError(Exception):
    """데이터 폴더나 파일 형식 문제."""


def _resolve(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _read_csv(path, required=True):
    if not path.exists():
        if required:
            raise DataError(f"필수 파일이 없습니다: {path.name}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8")


class DataStore:
    """한 데이터 폴더를 읽어 조회용으로 들고 있는 객체."""

    def __init__(self, data_dir=None):
        self.data_dir = _resolve(data_dir or os.environ.get("DATA_DIR") or DEFAULT_DATA_DIR)
        if not self.data_dir.is_dir():
            raise DataError(f"데이터 폴더가 없습니다: {self.data_dir}")

        self.manifest = self._read_manifest()
        self.shares = self._read_shares()
        self.domestic = _read_csv(self.data_dir / "institutions_kr.csv")
        self.foreign = _read_csv(self.data_dir / "institutions_foreign.csv", required=False)
        self.detections = _read_csv(self.data_dir / "detections.csv", required=False)
        self.injections = _read_csv(self.data_dir / "injections.csv", required=False)

        self._domestic_name = dict(zip(self.domestic["domestic_id"], self.domestic["name"]))
        if self.foreign.empty:
            self._foreign_name, self._foreign_country = {}, {}
        else:
            self._foreign_name = dict(zip(self.foreign["foreign_id"], self.foreign["name"]))
            self._foreign_country = dict(zip(self.foreign["foreign_id"], self.foreign["country_code"]))

    # ------------------------------------------------------------------ 메타

    def _read_manifest(self):
        for name in ("MANIFEST.json", "aggregation_manifest.json"):
            path = self.data_dir / name
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return {}

    @property
    def data_version(self):
        """캐시 키와 응답에 함께 실어 오래된 결과가 섞이지 않게 한다."""
        manifest = self.manifest
        return (
            manifest.get("data_version")
            or manifest.get("created_at")
            or f"dir:{self.data_dir.name}"
        )

    @property
    def is_real_data(self):
        if "is_real_data" in self.manifest:
            return bool(self.manifest["is_real_data"])
        return self.manifest.get("data_scope") not in (None, "example")

    def meta(self):
        years = self.shares["year"]
        return {
            "data_version": self.data_version,
            "data_scope": self.manifest.get("data_scope", "unknown"),
            "is_real_data": self.is_real_data,
            "data_dir": self.data_dir.name,
            "fields": sorted(self.shares["field"].unique().tolist()),
            "years": {"min": int(years.min()), "max": int(years.max())},
            "detectors": self._detector_list(),
            "counts": {
                "rows": int(len(self.shares)),
                "domestic_institutions": int(self.shares["domestic_id"].nunique()),
                "foreign_institutions": int(self.shares["foreign_id"].nunique()),
                "pairs": int(len(self.shares.groupby(["domestic_id", "foreign_id", "field"]))),
                "detections": int(len(self.detections)),
                "injections": int(len(self.injections)),
            },
        }

    def _detector_list(self):
        if self.detections.empty:
            return []
        return sorted(self.detections["detector"].unique().tolist())

    # -------------------------------------------------------------- 읽기 보조

    def _read_shares(self):
        frame = _read_csv(self.data_dir / "collab_shares.csv")
        missing = [c for c in SHARE_COLUMNS if c not in frame.columns]
        if missing:
            raise DataError(f"collab_shares.csv 에 없는 열: {', '.join(missing)}")
        frame["year"] = frame["year"].astype(int)
        return frame

    def domestic_name(self, value):
        return self._domestic_name.get(value, value)

    def foreign_name(self, value):
        return self._foreign_name.get(value, value)

    def foreign_country(self, value):
        return self._foreign_country.get(value)

    # ------------------------------------------------------------------ 조회

    def institutions(self, role="domestic", query=None, type_=None):
        if role == "domestic":
            frame = self.domestic.rename(columns={"domestic_id": "id"}).copy()
            frame["country_code"] = "KR"
        else:
            if self.foreign.empty:
                ids = sorted(self.shares["foreign_id"].unique())
                frame = pd.DataFrame({"id": ids, "name": ids, "country_code": None})
            else:
                frame = self.foreign.rename(columns={"foreign_id": "id"}).copy()
            frame["type"] = None
        if query:
            lowered = query.lower()
            mask = frame["name"].astype(str).str.lower().str.contains(lowered, na=False)
            mask |= frame["id"].astype(str).str.lower().str.contains(lowered, na=False)
            frame = frame[mask]
        if type_:
            frame = frame[frame["type"] == type_]
        return frame

    def pairs(self, field=None, domestic_id=None, min_count=None):
        frame = self.shares
        if field:
            frame = frame[frame["field"] == field]
        if domestic_id:
            frame = frame[frame["domestic_id"] == domestic_id]
        grouped = frame.groupby(["domestic_id", "foreign_id", "field"], as_index=False).agg(
            total_count=("collab_count", "sum"),
            year_min=("year", "min"),
            year_max=("year", "max"),
            max_share=("share", "max"),
        )
        if min_count is not None:
            grouped = grouped[grouped["total_count"] >= min_count]
        return grouped.sort_values("total_count", ascending=False)

    def timeline(self, domestic_id, foreign_id, field):
        keys = (
            (self.shares["domestic_id"] == domestic_id)
            & (self.shares["foreign_id"] == foreign_id)
            & (self.shares["field"] == field)
        )
        return self.shares[keys].sort_values("year")

    def detections_for(self, **filters):
        frame = self.detections
        if frame.empty:
            return frame
        for column, value in filters.items():
            if value is None or column not in frame.columns:
                continue
            frame = frame[frame[column] == value]
        return frame

    def injections_for(self, domestic_id=None, foreign_id=None, field=None, scenario_id=None):
        frame = self.injections
        if frame.empty:
            return frame
        for column, value in (
            ("domestic_id", domestic_id), ("foreign_id", foreign_id),
            ("field", field), ("scenario_id", scenario_id),
        ):
            if value is not None and column in frame.columns:
                frame = frame[frame[column] == value]
        return frame


_store = None


def get_store():
    """서버가 처음 요청을 받을 때 한 번만 만들고 이후에는 재사용한다."""
    global _store
    if _store is None:
        _store = DataStore()
    return _store


def reload_store():
    """DATA_DIR 를 바꾼 뒤 다시 읽을 때 사용한다."""
    global _store
    _store = None
    return get_store()
