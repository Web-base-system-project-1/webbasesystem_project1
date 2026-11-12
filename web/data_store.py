"""서버가 켜질 때 한 번만 CSV를 읽어 메모리에 들고 있는다.

요청마다 파일을 다시 읽지 않는다. 읽는 폴더는 .env 의 DATA_DIR 로 바꿀 수 있고,
지정하지 않으면 Git 으로 공유하는 예시 데이터 폴더를 사용한다.
"""

import json
import math
import os
from pathlib import Path

import pandas as pd

from detectors import DETECTORS, build_panel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = "data/sample/example"

# 탐지 기본값. 명세의 필수 임계값 중 가운데 값을 기본으로 쓴다.
DEFAULT_K = 3
DEFAULT_MIN_COUNT = 3
DEFAULT_THRESHOLDS = {"zscore": 2.5, "growth": 1.0}

SHARE_COLUMNS = [
    "domestic_id", "foreign_id", "field", "year",
    "collab_count", "international_total", "share",
]


class DataError(Exception):
    """데이터 폴더나 파일 형식 문제."""


def _resolve(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _read_csv(path, required=True, columns=()):
    if not path.exists():
        if required:
            raise DataError(f"필수 파일이 없습니다: {path.name}")
        return pd.DataFrame(columns=columns)
    try:
        frame = pd.read_csv(path, encoding="utf-8")
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise DataError(f"CSV 파일을 읽을 수 없습니다: {path.name}") from error
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise DataError(f"{path.name} 에 없는 열: {', '.join(missing)}")
    return frame


def _numeric_columns(frame, filename, columns):
    for column in columns:
        if column not in frame.columns:
            continue
        try:
            values = pd.to_numeric(frame[column], errors="raise")
            if not values.dropna().map(math.isfinite).all():
                raise ValueError("non-finite number")
            if column == "year":
                if values.isna().any() or (values % 1 != 0).any():
                    raise ValueError("invalid year")
                values = values.astype(int)
        except (ValueError, TypeError, OverflowError) as error:
            raise DataError(f"{filename} 의 {column} 숫자 형식을 확인하세요.") from error
        frame[column] = values
    return frame


class DataStore:
    """한 데이터 폴더를 읽어 조회용으로 들고 있는 객체."""

    def __init__(self, data_dir=None):
        self.data_dir = _resolve(data_dir or os.environ.get("DATA_DIR") or DEFAULT_DATA_DIR)
        if not self.data_dir.is_dir():
            raise DataError(f"데이터 폴더가 없습니다: {self.data_dir}")

        self.manifest = self._read_manifest()
        self.shares = self._read_shares()
        self.domestic = _read_csv(
            self.data_dir / "institutions_kr.csv", columns=("domestic_id", "name", "type", "ror"),
        )
        self.foreign = _read_csv(
            self.data_dir / "institutions_foreign.csv", required=False,
            columns=("foreign_id", "name", "country_code"),
        )
        self.detections = _read_csv(
            self.data_dir / "detections.csv", required=False,
            columns=("domestic_id", "foreign_id", "field", "year", "detector", "threshold", "score"),
        )
        _numeric_columns(self.detections, "detections.csv", (
            "year", "threshold", "score", "baseline_mean", "baseline_std",
            "current_value", "previous_value", "collab_count", "min_count",
        ))
        self.injections = _read_csv(
            self.data_dir / "injections.csv", required=False,
            columns=("scenario_id", "domestic_id", "foreign_id", "field", "year"),
        )
        _numeric_columns(self.injections, "injections.csv", ("year",))

        # 탐지 함수에 넣을 원자료. 둘 다 있어야 패널을 만들 수 있다.
        self.counts = _read_csv(
            self.data_dir / "collab_counts.csv", required=False,
            columns=("domestic_id", "foreign_id", "field", "year", "collab_count"),
        )
        _numeric_columns(self.counts, "collab_counts.csv", ("year", "collab_count"))
        self.totals = _read_csv(
            self.data_dir / "kr_totals.csv", required=False,
            columns=("domestic_id", "field", "year", "international_total"),
        )
        _numeric_columns(self.totals, "kr_totals.csv", ("year", "international_total"))
        self._panel = None
        self._detector_cache = {}

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
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, ValueError) as error:
                    raise DataError(f"메타데이터 파일을 읽을 수 없습니다: {name}") from error
                if not isinstance(manifest, dict):
                    raise DataError(f"메타데이터는 JSON 객체여야 합니다: {name}")
                return manifest
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
            "years": {
                "min": int(years.min()) if len(years) else None,
                "max": int(years.max()) if len(years) else None,
            },
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
        if self.can_detect:
            return sorted(DETECTORS)
        if self.detections.empty:
            return []
        return sorted(self.detections["detector"].unique().tolist())

    # ------------------------------------------------------- 탐지 함수 호출

    @property
    def can_detect(self):
        """collab_counts 와 kr_totals 가 모두 있으면 탐지 함수를 직접 부를 수 있다."""
        return not self.counts.empty and not self.totals.empty

    @property
    def panel(self):
        """기관 쌍 x 연도 전체 패널. 건수가 0인 연도도 행으로 남는다."""
        if not self.can_detect:
            return None
        if self._panel is None:
            self._panel = build_panel(self.counts, self.totals)
        return self._panel

    def run_detector(self, detector, k=DEFAULT_K, threshold=None, min_count=DEFAULT_MIN_COUNT):
        """2번 담당자의 탐지 함수를 그대로 호출한다. 계산을 여기서 다시 구현하지 않는다.

        같은 설정으로 다시 물으면 계산하지 않고 보관한 결과를 돌려준다.
        캐시 키에 데이터 버전이 들어 있어 폴더가 바뀌면 섞이지 않는다.
        """
        if detector not in DETECTORS:
            raise DataError(f"알 수 없는 탐지기입니다: {detector}")
        if not self.can_detect:
            raise DataError("collab_counts.csv 와 kr_totals.csv 가 있어야 탐지를 실행할 수 있습니다.")
        if threshold is None:
            threshold = DEFAULT_THRESHOLDS[detector]

        key = (self.data_version, detector, int(k), float(threshold), int(min_count))
        if key not in self._detector_cache:
            params = {"k": int(k), "threshold": float(threshold), "min_count": int(min_count)}
            self._detector_cache[key] = DETECTORS[detector](self.panel, params)
        return self._detector_cache[key]

    # -------------------------------------------------------------- 읽기 보조

    def _read_shares(self):
        frame = _read_csv(self.data_dir / "collab_shares.csv", columns=SHARE_COLUMNS)
        return _numeric_columns(frame, "collab_shares.csv", (
            "year", "collab_count", "international_total", "share",
        ))

    def domestic_name(self, value):
        name = self._domestic_name.get(value, value)
        return value if pd.isna(name) else name

    def foreign_name(self, value):
        name = self._foreign_name.get(value, value)
        return value if pd.isna(name) else name

    def foreign_country(self, value):
        country = self._foreign_country.get(value)
        return None if pd.isna(country) else country

    # ------------------------------------------------------------------ 조회

    def institutions(self, role="domestic", query=None, type_=None, field=None, domestic_id=None, foreign_id=None):
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
        if field or domestic_id or foreign_id:
            # 0으로 채운 행만 있는 관계는 협력 기관으로 표시하지 않습니다.
            related = self.shares[self.shares["collab_count"] > 0]
            for column, value in (("field", field), ("domestic_id", domestic_id), ("foreign_id", foreign_id)):
                if value:
                    related = related[related[column] == value]
            frame = frame[frame["id"].isin(related[f"{role}_id"].unique())]
        if query:
            lowered = query.lower()
            mask = frame["name"].astype(str).str.lower().str.contains(lowered, na=False, regex=False)
            mask |= frame["id"].astype(str).str.lower().str.contains(lowered, na=False, regex=False)
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
