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


def resolve_detections(store, filters):
    """source 에 따라 탐지 결과를 구한다. /detections 와 /overview 가 함께 쓴다."""
    detector = arg_detector()
    if _pick_source(store) == "live":
        found, summary, params = _live_detections(
            store, detector,
            k=arg_int("k", default=DEFAULT_K, minimum=2, maximum=10),
            threshold=arg_float("threshold"),
            min_count=arg_int("min_count", default=DEFAULT_MIN_COUNT, minimum=0),
            filters=filters,
        )
        return found, "live", params, summary
    found = _file_detections(store, detector, arg_float("threshold"), filters)
    return found, "file", [], {"evaluated_rows": len(found), "skipped": {}}


@api_bp.get("/detections")
def detections():
    """탐지 목록과 근거. 점수가 높은 순.

    collab_counts.csv 와 kr_totals.csv 가 있으면 2번 담당자의 탐지 함수를 그대로
    호출해 계산한다(source=live). 없으면 저장된 detections.csv 를 읽는다(source=file).
    어느 쪽이든 응답 모양은 같다.
    """
    store = get_store()
    limit = arg_int("limit", default=100, minimum=1, maximum=MAX_LIMIT)
    filters = {
        "field": request.args.get("field"),
        "domestic_id": request.args.get("domestic_id"),
        "foreign_id": request.args.get("foreign_id"),
        "year": arg_int("year"),
    }
    found, source, params, summary = resolve_detections(store, filters)

    total = len(found)
    if total and "score" in found.columns:
        found = found.sort_values("score", ascending=False)
    return envelope(store, source=source, params=params, summary=summary,
                    total=total, count=min(total, limit), items=_with_names(store, found, limit))


# --------------------------------------------------------------------- 개요

@api_bp.get("/overview")
def overview():
    """국가·분야·연도별 협력 집계와 탐지 건수. 개요 히트맵용."""
    store = get_store()
    field = request.args.get("field")
    year = arg_int("year")
    country = request.args.get("country")
    limit = arg_int("limit", default=500, minimum=1, maximum=MAX_LIMIT)

    frame = store.overview(field=field, year=year, country=country)
    found, source, params, summary = resolve_detections(store, {"field": field, "year": year})

    counts = {}
    if len(found):
        tagged = store.with_country(found)
        if country:
            tagged = tagged[tagged["country_code"] == country]
        grouped = tagged.groupby(["country_code", "field", "year"], dropna=False).size()
        counts = {(None if pd.isna(c) else c, f, int(y)): int(n) for (c, f, y), n in grouped.items()}

    items = [{**row, "detections": counts.get(
        (row["country_code"], row["field"], row["year"]), 0)}
        for row in records(frame.head(limit))]

    return envelope(
        store, source=source, params=params, summary=summary,
        aggregation_basis="unique_country_papers" if not store.country_totals.empty else "institution_pairs",
        fields=sorted(frame["field"].unique().tolist()),
        years=sorted(int(y) for y in frame["year"].unique()),
        total=len(frame), count=len(items), items=items,
    )


# --------------------------------------------------------------------- 평가

@api_bp.get("/metrics")
def metrics():
    """주입 실험의 정량 평가표. experiments.evaluate 가 만든 metrics.csv 를 돌려준다."""
    store = get_store()
    if store.metrics.empty:
        raise ApiError(
            "metrics_unavailable",
            "이 데이터에는 metrics.csv 가 없습니다. python -m experiments.run 으로 만듭니다.",
            status=409,
        )
    frame = _filter_rows(
        store.metrics,
        scenario_id=request.args.get("scenario_id") or None,
        detector=arg_detector(),
        threshold=arg_float("threshold"),
        k=arg_int("k"), min_count=arg_int("min_count"),
        correction_id=request.args.get("correction_id") or None,
    )
    sort_by = request.args.get("sort", "f1")
    if sort_by not in frame.columns:
        raise ApiError("invalid_parameter", f"sort 로 쓸 수 없는 열입니다: {sort_by}")
    frame = frame.sort_values(sort_by, ascending=False, na_position="last")
    limit = arg_int("limit", default=100, minimum=1, maximum=MAX_LIMIT)
    return envelope(
        store, sort=sort_by,
        scenarios=sorted(store.metrics["scenario_id"].dropna().unique().tolist()),
        detectors=sorted(store.metrics["detector"].dropna().unique().tolist()),
        total=len(frame), count=min(len(frame), limit),
        items=records(frame.head(limit)),
    )


# -------------------------------------------------------------------- 시나리오

@api_bp.get("/scenarios")
def scenarios():
    """주입 시나리오 목록. 정답 행 수, 주입 유형과 배수, 실제로 값이 바뀐 행 수."""
    store = get_store()
    frame = store.scenario_summary()
    if frame.empty:
        return envelope(store, total=0, count=0, items=[])
    return envelope(store, total=len(frame), count=len(frame), items=records(frame))

@api_bp.get("/experiments")
def experiment_runs():
    """현재 데이터 버전으로 검증된 저장 실험의 실행 목록."""
    store = get_store()
    if not store.experiment_manifest or store.experiment_manifest.get("data_version") != store.data_version:
        raise ApiError("experiment_unavailable", "현재 데이터의 저장된 실험 결과가 없습니다.", 409)
    return envelope(store, seed=store.experiment_manifest["seed"], items=records(store.metrics))


@api_bp.get("/experiment-timeline")
def experiment_timeline():
    from web.data_store import experiment_scenarios
    store = get_store()
    scenario_id = arg_required("scenario_id")
    detector = arg_detector()
    if detector is None:
        raise ApiError("missing_parameter", "detector가 필요합니다.")
    threshold = arg_float("threshold")
    if threshold is None:
        raise ApiError("missing_parameter", "threshold가 필요합니다.")
    run = _filter_rows(store.metrics, scenario_id=scenario_id, detector=detector,
                       threshold=threshold, correction_id="none")
    if len(run) != 1:
        raise ApiError("experiment_unavailable", "저장된 실험 설정이 없습니다.", 404)
    scenarios = experiment_scenarios(store)
    if scenario_id not in scenarios:
        raise ApiError("invalid_parameter", "지원하지 않는 시나리오입니다.")
    pair = {key: arg_required(key) for key in ("domestic_id", "foreign_id", "field")}
    scenario = scenarios[scenario_id]
    original = _filter_rows(scenarios["original"].panel, **pair).sort_values("year")
    changed = _filter_rows(scenario.panel, **pair).sort_values("year")
    if original.empty:
        raise ApiError("pair_not_found", "해당 기관 쌍의 자료가 없습니다.", 404)
    cols = ["year", "collab_count", "international_total", "share"]
    hits = _filter_rows(store.detections, **pair, scenario_id=scenario_id,
                        detector=detector, threshold=threshold, correction_id="none",
                        run_id=run.iloc[0]["run_id"])
    target = scenario.injections.iloc[0] if len(scenario.injections) else None
    return envelope(store, scenario_id=scenario_id, seed=store.experiment_manifest["seed"],
        original=records(original[cols]), points=records(changed[cols]),
        detections=records(hits), injections=records(_filter_rows(scenario.injections, **pair)),
        metrics=records(run)[0],
        target={key: target[key] for key in pair} if target is not None else None)



# ------------------------------------------------------------------- 보정 비교

NO_CORRECTION = "none"
RUN_KEYS = ("scenario_id", "detector", "threshold", "k", "min_count")
DETECTION_KEYS = ("domestic_id", "foreign_id", "field", "year")
METRIC_COLUMNS = ("tp", "fp", "fn", "precision", "recall", "f1",
                  "recall_effective", "delay_mean", "missed_pairs", "decoy_fp")
CHANGE_LABELS = ("resolved_false_positive", "lost_true_positive",
                 "introduced_false_positive", "introduced_true_positive")


def _count(row, name):
    """결측을 0 으로 본 정수. 합계를 낼 때만 쓴다."""
    value = clean(row.get(name))
    return int(value) if value is not None else 0


def _run_signature(frame):
    """실험 조건을 문자열 하나로 묶는다. k 가 결측인 증가율 실행도 짝지을 수 있다."""
    empty = pd.Series([None] * len(frame), index=frame.index)
    parts = []
    for key in RUN_KEYS:
        column = frame[key] if key in frame.columns else empty
        parts.append(column.astype("object").where(column.notna(), "").astype(str))
    return parts[0].str.cat(parts[1:], sep="|")


def _metric_values(row):
    return {name: clean(row.get(name)) for name in METRIC_COLUMNS if name in row}


def _require_corrections(store):
    """보정 전후를 짝지을 수 있는 상태인지 확인하고 보정 이름 목록을 돌려준다."""
    if store.metrics.empty:
        raise ApiError(
            "metrics_unavailable",
            "이 데이터에는 metrics.csv 가 없습니다. python -m experiments.run 으로 만듭니다.",
            status=409,
        )
    if "correction_id" not in store.metrics.columns:
        raise ApiError(
            "comparison_unavailable",
            "metrics.csv 에 correction_id 열이 없어 보정 전후를 짝지을 수 없습니다.",
            status=409,
        )
    names = sorted(
        name for name in store.metrics["correction_id"].dropna().unique()
        if name != NO_CORRECTION
    )
    if not names:
        raise ApiError(
            "comparison_unavailable",
            "보정을 적용한 실행이 없습니다. correction_id 가 none 인 결과만 있습니다.",
            status=409,
        )
    return names


def _paired_runs(store, correction_id=None):
    """보정 후 실행마다 같은 조건의 보정 전 실행을 찾아 (before, after) 로 묶는다.

    탐지기마다 적용하는 보정이 달라도, 같은 조건이 있는 실행만 짝이 되므로
    z-score 보정과 증가율 보정이 섞이지 않는다.
    """
    frame = store.metrics.assign(signature=_run_signature(store.metrics))
    before = {
        row["signature"]: row
        for row in frame[frame["correction_id"] == NO_CORRECTION].to_dict("records")
    }
    pairs = []
    for after in frame[frame["correction_id"] != NO_CORRECTION].to_dict("records"):
        if correction_id and after["correction_id"] != correction_id:
            continue
        base = before.get(after["signature"])
        if base is not None:
            pairs.append((base, after))
    return pairs


def _correction_summary(pairs):
    """보정별로 오탐이 얼마나 줄고 정탐이 얼마나 사라졌는지 합계."""
    totals = {}
    for base, after in pairs:
        row = totals.setdefault(after["correction_id"], {
            "correction_id": after["correction_id"], "runs": 0,
            "tp_before": 0, "tp_after": 0, "fp_before": 0, "fp_after": 0,
            "decoy_fp_before": 0, "decoy_fp_after": 0,
        })
        row["runs"] += 1
        for name in ("tp", "fp", "decoy_fp"):
            row[f"{name}_before"] += _count(base, name)
            row[f"{name}_after"] += _count(after, name)
    for row in totals.values():
        row["fp_removed"] = row["fp_before"] - row["fp_after"]
        row["tp_lost"] = row["tp_before"] - row["tp_after"]
        row["decoy_fp_removed"] = row["decoy_fp_before"] - row["decoy_fp_after"]
    return [totals[name] for name in sorted(totals)]


def _correction_arg(corrections, required=False):
    value = arg_required("correction_id") if required else (request.args.get("correction_id") or None)
    if value is not None and value not in corrections:
        raise ApiError(
            "invalid_parameter",
            f"correction_id 는 {' 또는 '.join(corrections)} 중 하나여야 합니다. 받은 값: {value}",
        )
    return value


@api_bp.get("/comparison")
def comparison():
    """보정 전후를 같은 실험 조건끼리 짝지어 돌려준다. 보정 비교 뷰용.

    숫자는 2번 담당자의 experiments.evaluate 가 만든 metrics.csv 를 그대로 쓴다.
    여기서 지표를 다시 계산하지 않는다.
    """
    store = get_store()
    corrections = _require_corrections(store)
    correction_id = _correction_arg(corrections)
    scenario_id = request.args.get("scenario_id") or None
    detector = arg_detector()
    threshold = arg_float("threshold")
    limit = arg_int("limit", default=100, minimum=1, maximum=MAX_LIMIT)

    pairs = _paired_runs(store, correction_id)
    items = []
    for base, after in pairs:
        if scenario_id and after["scenario_id"] != scenario_id:
            continue
        if detector and after["detector"] != detector:
            continue
        if threshold is not None and clean(after["threshold"]) != threshold:
            continue
        before_values, after_values = _metric_values(base), _metric_values(after)
        items.append({
            **{key: clean(after.get(key)) for key in RUN_KEYS},
            "correction_id": after["correction_id"],
            "run_id": {"before": base.get("run_id"), "after": after.get("run_id")},
            "before": before_values,
            "after": after_values,
            "delta": {
                name: None if before_values.get(name) is None or value is None
                else round(value - before_values[name], 6)
                for name, value in after_values.items()
            },
        })
    items.sort(key=lambda row: (
        row["correction_id"], row["scenario_id"], row["detector"], row["threshold"]))

    return envelope(
        store, corrections=corrections,
        summary=_correction_summary(pairs),
        total=len(items), count=min(len(items), limit), items=items[:limit],
    )


@api_bp.get("/comparison/changes")
def comparison_changes():
    """보정으로 판정이 바뀐 탐지 행. 바로잡힌 오탐과 사라진 정탐을 구분한다.

    보정 전 실행에만 있는 행은 보정이 지운 것이고, 주입 정답에 있으면
    lost_true_positive(새로 생긴 오류), 없으면 resolved_false_positive(바로잡힌 오류)다.
    """
    store = get_store()
    corrections = _require_corrections(store)
    correction_id = _correction_arg(corrections, required=True)
    scenario_id = arg_required("scenario_id")
    detector = arg_detector()
    if detector is None:
        raise ApiError("missing_parameter", "detector 는 필수입니다.")
    threshold = arg_float("threshold")
    if threshold is None:
        raise ApiError("missing_parameter", "threshold 는 필수입니다.")
    change = request.args.get("change") or None
    if change is not None and change not in CHANGE_LABELS:
        raise ApiError(
            "invalid_parameter",
            f"change 는 {' 또는 '.join(CHANGE_LABELS)} 중 하나여야 합니다. 받은 값: {change}",
        )
    limit = arg_int("limit", default=100, minimum=1, maximum=MAX_LIMIT)

    found = [
        (base, after) for base, after in _paired_runs(store, correction_id)
        if after["scenario_id"] == scenario_id and after["detector"] == detector
        and clean(after["threshold"]) == threshold
    ]
    if not found:
        raise ApiError(
            "comparison_unavailable",
            "그 조건으로 저장된 보정 전후 실행이 없습니다.",
            status=404,
        )
    base, after = found[0]

    def key_of(row):
        return tuple(row.get(name) for name in DETECTION_KEYS)

    before_items = records(_filter_rows(
        store.detections, scenario_id=scenario_id, run_id=base.get("run_id")))
    after_items = records(_filter_rows(
        store.detections, scenario_id=scenario_id, run_id=after.get("run_id")))
    truth = store.injections_for(scenario_id=scenario_id)
    truth_keys = {key_of(row) for row in records(truth)} if len(truth) else set()

    before_keys = {key_of(row) for row in before_items}
    after_keys = {key_of(row) for row in after_items}
    removed, added = before_keys - after_keys, after_keys - before_keys

    items, counts = [], {name: 0 for name in CHANGE_LABELS}
    for source, changed, labels in (
        (before_items, removed, ("lost_true_positive", "resolved_false_positive")),
        (after_items, added, ("introduced_true_positive", "introduced_false_positive")),
    ):
        for row in source:
            key = key_of(row)
            if key not in changed:
                continue
            injected = key in truth_keys
            label = labels[0] if injected else labels[1]
            counts[label] += 1
            items.append({**row, "change": label, "was_injected": injected})

    items.sort(key=lambda row: (row["change"], -(row.get("score") or 0)))
    shown = [row for row in items if change is None or row["change"] == change]

    return envelope(
        store,
        run={**{key: clean(after.get(key)) for key in RUN_KEYS}, "correction_id": correction_id},
        run_id={"before": base.get("run_id"), "after": after.get("run_id")},
        before_detections=len(before_items), after_detections=len(after_items),
        unchanged=len(before_keys & after_keys),
        counts=counts,
        total=len(shown), count=min(len(shown), limit),
        items=[{
            **row,
            "domestic_name": store.domestic_name(row.get("domestic_id")),
            "foreign_name": store.foreign_name(row.get("foreign_id")),
            "foreign_country": store.foreign_country(row.get("foreign_id")),
        } for row in shown[:limit]],
    )
