"""조회 API. 모든 응답은 data_version 을 함께 돌려준다.

프론트엔드는 상대 주소 /api/... 로 부른다. 숫자가 아닌 입력, 없는 기관 쌍,
빈 결과는 모두 같은 모양의 오류 또는 빈 목록으로 응답한다.
"""

import math

import pandas as pd
from flask import Blueprint, jsonify, request

from web.data_store import (
    DEFAULT_K, DEFAULT_MIN_COUNT, DEFAULT_THRESHOLDS, DataError, get_store,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_LIMIT = 1000


# --------------------------------------------------------------------- 공통

class ApiError(Exception):
    """클라이언트에게 그대로 보여 줄 수 있는 오류."""

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@api_bp.errorhandler(ApiError)
def _handle_api_error(error):
    return jsonify({"error": {"code": error.code, "message": error.message}}), error.status


@api_bp.errorhandler(DataError)
def _handle_data_error(error):
    return jsonify({"error": {"code": "data_unavailable", "message": str(error)}}), 503


def clean(value):
    """NaN 과 numpy 숫자를 JSON 이 받을 수 있는 값으로 바꾼다."""
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def records(frame):
    return [{key: clean(value) for key, value in row.items()} for row in frame.to_dict("records")]


def arg_int(name, default=None, minimum=None, maximum=None):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError("invalid_parameter", f"{name} 은 정수여야 합니다. 받은 값: {raw}")
    if minimum is not None and value < minimum:
        raise ApiError("invalid_parameter", f"{name} 은 {minimum} 이상이어야 합니다.")
    if maximum is not None and value > maximum:
        raise ApiError("invalid_parameter", f"{name} 은 {maximum} 이하여야 합니다.")
    return value


def arg_float(name, default=None):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ApiError("invalid_parameter", f"{name} 은 숫자여야 합니다. 받은 값: {raw}")
    if not math.isfinite(value):
        raise ApiError("invalid_parameter", f"{name} 은 유한한 숫자여야 합니다.")
    return value


def arg_required(name):
    value = request.args.get(name)
    if not value:
        raise ApiError("missing_parameter", f"{name} 은 필수입니다.")
    return value


def arg_detector():
    detector = request.args.get("detector") or None
    if detector and detector not in DEFAULT_THRESHOLDS:
        raise ApiError(
            "invalid_parameter",
            f"detector 는 {' 또는 '.join(sorted(DEFAULT_THRESHOLDS))} 여야 합니다.",
        )
    return detector


def envelope(store, **payload):
    return jsonify({"data_version": store.data_version, **payload})


# ---------------------------------------------------------------------- 상태
# /api/health 는 index.html 이 url_for("health") 로 참조하므로 web/app.py 에 둔다.

@api_bp.get("/meta")
def meta():
    """지금 서버가 읽고 있는 데이터의 범위와 버전."""
    store = get_store()
    return jsonify(store.meta())


# ---------------------------------------------------------------------- 기관

@api_bp.get("/institutions")
def institutions():
    """기관 검색. role=domestic|foreign, q=이름 일부, type=기관 유형."""
    store = get_store()
    role = request.args.get("role", "domestic")
    if role not in ("domestic", "foreign"):
        raise ApiError("invalid_parameter", "role 은 domestic 또는 foreign 이어야 합니다.")
    limit = arg_int("limit", default=200, minimum=1, maximum=MAX_LIMIT)
    offset = arg_int("offset", default=0, minimum=0)
    frame = store.institutions(
        role=role, query=request.args.get("q"), type_=request.args.get("type"),
        field=request.args.get("field"), domestic_id=request.args.get("domestic_id"),
        foreign_id=request.args.get("foreign_id"),
    )
    total = len(frame)
    items = records(frame.iloc[offset:offset + limit])
    end = offset + len(items)
    return envelope(
        store, role=role, total=total, count=len(items), offset=offset,
        next_offset=end if end < total else None, items=items,
    )


# ------------------------------------------------------------------- 기관 쌍

@api_bp.get("/pairs")
def pairs():
    """국내-해외 기관 쌍 목록. 협력 건수가 많은 순."""
    store = get_store()
    limit = arg_int("limit", default=100, minimum=1, maximum=MAX_LIMIT)
    frame = store.pairs(
        field=request.args.get("field"),
        domestic_id=request.args.get("domestic_id"),
        min_count=arg_int("min_count", minimum=0),
    )
    total = len(frame)
    items = []
    for row in records(frame.head(limit)):
        items.append({
            **row,
            "domestic_name": store.domestic_name(row["domestic_id"]),
            "foreign_name": store.foreign_name(row["foreign_id"]),
            "foreign_country": store.foreign_country(row["foreign_id"]),
        })
    return envelope(store, total=total, count=len(items), items=items)


# ------------------------------------------------------------------ 타임라인

@api_bp.get("/timeline")
def timeline():
    """한 기관 쌍의 연도별 건수·비중과 탐지·주입 시점."""
    store = get_store()
    domestic_id = arg_required("domestic_id")
    foreign_id = arg_required("foreign_id")
    field = arg_required("field")

    frame = store.timeline(domestic_id, foreign_id, field)
    if frame.empty:
        raise ApiError(
            "pair_not_found",
            f"해당 기관 쌍의 자료가 없습니다: {domestic_id} x {foreign_id} ({field})",
            status=404,
        )

    detector = arg_detector()
    threshold = arg_float("threshold")
    pair_filter = {"domestic_id": domestic_id, "foreign_id": foreign_id, "field": field}

    source = _pick_source(store)
    baseline, injected = [], []
    if source == "live":
        k = arg_int("k", default=DEFAULT_K, minimum=2, maximum=10)
        min_count = arg_int("min_count", default=DEFAULT_MIN_COUNT, minimum=0)
        found, _, _ = _live_detections(
            store, detector, k=k, threshold=threshold, min_count=min_count, filters=pair_filter,
        )
        # 기준선 띠는 z-score 결과에서만 나온다. 연도마다 한 행씩.
        zframe = _filter_rows(store.run_detector(
            "zscore", k=k, threshold=threshold if detector == "zscore" else None,
            min_count=min_count,
        ), **pair_filter)
        baseline = records(zframe[[
            "year", "baseline_value", "baseline_std", "baseline_n",
            "current_value", "score", "detected", "skip_reason",
        ]].sort_values("year"))
    else:
        found = _file_detections(store, detector, threshold, pair_filter)
        injected = records(store.injections_for(
            **pair_filter, scenario_id=request.args.get("scenario_id") or None,
        ))

    return envelope(
        store,
        source=source,
        baseline=baseline,
        pair={
            "domestic_id": domestic_id,
            "domestic_name": store.domestic_name(domestic_id),
            "foreign_id": foreign_id,
            "foreign_name": store.foreign_name(foreign_id),
            "foreign_country": store.foreign_country(foreign_id),
            "field": field,
        },
        points=records(frame[[
            "year", "collab_count", "international_total", "share",
        ]]),
        detections=records(found) if len(found) else [],
        injections=injected,
    )


# --------------------------------------------------------------------- 탐지

def _with_names(store, frame, limit):
    items = []
    for row in records(frame.head(limit)):
        items.append({
            **row,
            "domestic_name": store.domestic_name(row.get("domestic_id")),
            "foreign_name": store.foreign_name(row.get("foreign_id")),
            "foreign_country": store.foreign_country(row.get("foreign_id")),
        })
    return items


def _filter_rows(frame, **filters):
    for column, value in filters.items():
        if value is None:
            continue
        if column not in frame.columns:
            return frame.iloc[:0]
        frame = frame[frame[column] == value]
    return frame


def _pick_source(store):
    """자동 모드는 실험 조건을 지정하면 저장된 결과를 선택한다."""
    source = request.args.get("source", "auto")
    if source not in ("auto", "live", "file"):
        raise ApiError("invalid_parameter", "source 는 auto, live, file 중 하나여야 합니다.")
    file_filter = any(request.args.get(name) for name in ("scenario_id", "correction_id"))
    if source == "auto":
        return "live" if store.can_detect and not file_filter else "file"
    if source == "live" and file_filter:
        raise ApiError("invalid_parameter", "시나리오·보정 조건은 source=file에서 조회하세요.")
    if source == "live" and not store.can_detect:
        raise ApiError(
            "detection_unavailable",
            "이 데이터 폴더에는 collab_counts.csv 와 kr_totals.csv 가 없어 탐지를 실행할 수 없습니다.",
            status=409,
        )
    return source


def _file_detections(store, detector, threshold, filters):
    return _filter_rows(
        store.detections, detector=detector, threshold=threshold,
        scenario_id=request.args.get("scenario_id") or None,
        correction_id=request.args.get("correction_id") or None,
        k=arg_int("k"), min_count=arg_int("min_count"), **filters,
    )


def _live_detections(store, detector, k, threshold, min_count, filters):
    """2번 담당자의 탐지 함수를 직접 호출한다. 탐지된 행과 건너뛴 이유를 함께 돌려준다."""
    if threshold is not None and detector is None:
        raise ApiError("invalid_parameter", "실시간 임계값을 지정할 때는 detector도 지정하세요.")
    names = [detector] if detector else sorted(DEFAULT_THRESHOLDS)
    results, skipped, evaluated = [], {}, 0
    used = []
    for name in names:
        value = threshold if threshold is not None else DEFAULT_THRESHOLDS[name]
        frame = _filter_rows(store.run_detector(name, k=k, threshold=value, min_count=min_count), **filters)
        evaluated += len(frame)
        for reason, count in frame["skip_reason"].dropna().value_counts().items():
            skipped[reason] = skipped.get(reason, 0) + int(count)
        results.append(frame[frame["detected"]])
        used.append({"detector": name, "threshold": value, "k": k, "min_count": min_count})
    found = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    return found, {"evaluated_rows": evaluated, "skipped": skipped}, used


@api_bp.get("/detections")
def detections():
    """탐지 목록과 근거. 점수가 높은 순.

    collab_counts.csv 와 kr_totals.csv 가 있으면 2번 담당자의 탐지 함수를 그대로
    호출해 계산한다(source=live). 없으면 저장된 detections.csv 를 읽는다(source=file).
    어느 쪽이든 응답 모양은 같다.
    """
    store = get_store()
    limit = arg_int("limit", default=100, minimum=1, maximum=MAX_LIMIT)
    detector = arg_detector()
    filters = {
        "field": request.args.get("field"),
        "domestic_id": request.args.get("domestic_id"),
        "foreign_id": request.args.get("foreign_id"),
        "year": arg_int("year"),
    }

    if _pick_source(store) == "live":
        found, summary, used = _live_detections(
            store, detector,
            k=arg_int("k", default=DEFAULT_K, minimum=2, maximum=10),
            threshold=arg_float("threshold"),
            min_count=arg_int("min_count", default=DEFAULT_MIN_COUNT, minimum=0),
            filters=filters,
        )
        source, params = "live", used
    else:
        found = _file_detections(store, detector, arg_float("threshold"), filters)
        source, params, summary = "file", [], {"evaluated_rows": len(found), "skipped": {}}

    total = len(found)
    if total and "score" in found.columns:
        found = found.sort_values("score", ascending=False)
    return envelope(store, source=source, params=params, summary=summary,
                    total=total, count=min(total, limit), items=_with_names(store, found, limit))


# -------------------------------------------------------------------- 시나리오

@api_bp.get("/scenarios")
def scenarios():
    """주입 시나리오 목록과 정답 건수."""
    store = get_store()
    if store.injections.empty:
        return envelope(store, total=0, count=0, items=[])
    grouped = store.injections.groupby("scenario_id", as_index=False).agg(
        injected_rows=("year", "count"),
        year_min=("year", "min"),
        year_max=("year", "max"),
    )
    return envelope(store, total=len(grouped), count=len(grouped), items=records(grouped))
