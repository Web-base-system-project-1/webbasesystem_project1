"""조회 API. 모든 응답은 data_version 을 함께 돌려준다.

프론트엔드는 상대 주소 /api/... 로 부른다. 숫자가 아닌 입력, 없는 기관 쌍,
빈 결과는 모두 같은 모양의 오류 또는 빈 목록으로 응답한다.
"""

import math

from flask import Blueprint, jsonify, request

from web.data_store import DataError, get_store

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
    frame = store.institutions(role=role, query=request.args.get("q"), type_=request.args.get("type"))
    total = len(frame)
    return envelope(store, role=role, total=total, count=min(total, limit), items=records(frame.head(limit)))


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

    detector = request.args.get("detector")
    threshold = arg_float("threshold")
    found = store.detections_for(
        domestic_id=domestic_id, foreign_id=foreign_id, field=field,
        detector=detector, threshold=threshold,
    )
    injected = store.injections_for(domestic_id=domestic_id, foreign_id=foreign_id, field=field)

    return envelope(
        store,
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
        injections=records(injected) if len(injected) else [],
    )


# --------------------------------------------------------------------- 탐지

@api_bp.get("/detections")
def detections():
    """탐지 목록과 근거. 점수가 높은 순.

    2번 담당자의 탐지 함수가 완성되기 전까지는 저장된 예시 결과를 그대로 돌려준다.
    응답 형식은 바뀌지 않으므로 화면 쪽 코드는 그대로 쓸 수 있다.
    """
    store = get_store()
    limit = arg_int("limit", default=100, minimum=1, maximum=MAX_LIMIT)
    frame = store.detections_for(
        detector=request.args.get("detector"),
        field=request.args.get("field"),
        scenario_id=request.args.get("scenario_id"),
        domestic_id=request.args.get("domestic_id"),
        threshold=arg_float("threshold"),
        year=arg_int("year"),
    )
    total = len(frame)
    if total and "score" in frame.columns:
        frame = frame.sort_values("score", ascending=False)
    items = []
    for row in records(frame.head(limit)):
        items.append({
            **row,
            "domestic_name": store.domestic_name(row.get("domestic_id")),
            "foreign_name": store.foreign_name(row.get("foreign_id")),
            "foreign_country": store.foreign_country(row.get("foreign_id")),
        })
    return envelope(store, total=total, count=len(items), items=items)


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
