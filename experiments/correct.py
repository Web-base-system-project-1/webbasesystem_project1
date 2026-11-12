"""기존 탐지 결과에 원인별 보정 규칙을 적용한다."""

from detectors.panel import PAIR_KEYS

SHARE_TOLERANCE = 1e-12


def require_min_international_total(detections, min_total=3):
    """z-score 탐지 중 해당 연도의 국제 공동논문 총수가 기준 이상인 경우만 유지한다."""
    corrected = detections.copy()
    rejected = (
        corrected["detector"].eq("zscore")
        & corrected["detected"]
        & ~corrected["international_total"].ge(min_total).fillna(False)
    )
    corrected.loc[rejected, "detected"] = False
    corrected.loc[rejected, "skip_reason"] = "below_min_international_total"
    return corrected


def require_share_increase(detections, panel):
    """증가율 탐지 중 협력 비중도 전년 대비 증가한 경우만 유지한다."""
    corrected = detections.copy()
    keys = [*PAIR_KEYS, "year"]
    shares = panel.set_index(keys)["share"]
    previous_shares = panel.assign(year=panel["year"] + 1).set_index(keys)["share"]
    share_change = shares - previous_shares.reindex(shares.index)

    result_keys = corrected.set_index(keys).index
    increased = share_change.reindex(result_keys).gt(SHARE_TOLERANCE).fillna(False)
    rejected = (
        corrected["detector"].eq("growth")
        & corrected["detected"]
        & ~increased.to_numpy(dtype=bool)
    )
    corrected.loc[rejected, "detected"] = False
    corrected.loc[rejected, "skip_reason"] = "share_increase_required"
    return corrected
