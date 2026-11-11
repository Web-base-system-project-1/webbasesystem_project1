"""증가율 탐지기: 기관 쌍 공동논문 수의 전년 대비 증가율 (최소 건수 조건 포함)."""

import numpy as np
import pandas as pd

from detectors.panel import PAIR_KEYS
from detectors.zscore import OUTPUT_COLUMNS


def detect_growth(panel, params):
    threshold = float(params["threshold"])  # 1.0 = +100%
    min_count = int(params.get("min_count", 0))

    df = panel.sort_values(PAIR_KEYS + ["year"]).reset_index(drop=True)
    prev = df.groupby(PAIR_KEYS, sort=False)["collab_count"].shift(1)
    cur = df["collab_count"]

    reason = pd.Series(pd.NA, index=df.index, dtype="object")
    reason[prev.isna()] = "insufficient_history"
    reason[reason.isna() & (cur < min_count)] = "below_min_count"
    reason[reason.isna() & (prev == 0)] = "prev_zero"

    ok = reason.isna()
    rate = ((cur - prev) / prev).where(ok, np.nan)
    out = pd.DataFrame({
        **{c: df[c] for c in PAIR_KEYS}, "year": df["year"],
        "detector": "growth", "k": np.nan, "threshold": threshold, "min_count": min_count,
        "collab_count": cur, "international_total": df["international_total"],
        "current_value": cur, "baseline_value": prev, "baseline_std": np.nan,
        "baseline_n": np.nan, "change": rate, "score": rate,
        "detected": (rate >= threshold).fillna(False), "skip_reason": reason,
    })
    return out[OUTPUT_COLUMNS]
