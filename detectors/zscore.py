"""z-score detector: this year's share vs. the mean/std of the previous k years."""

import numpy as np
import pandas as pd

from detectors.panel import PAIR_KEYS

OUTPUT_COLUMNS = [
    *PAIR_KEYS, "year", "detector", "k", "threshold", "min_count",
    "collab_count", "international_total", "current_value", "baseline_value",
    "baseline_std", "baseline_n", "change", "score", "detected", "skip_reason",
]
STD_EPS = 1e-12


def detect_zscore(panel, params):
    k, threshold = int(params["k"]), float(params["threshold"])
    min_count = int(params.get("min_count", 0))
    if k < 2:
        raise ValueError("k must be >= 2 (sample std needs two points)")

    df = panel.sort_values(PAIR_KEYS + ["year"]).reset_index(drop=True)
    # shift(1): the current year is never part of its own baseline.
    prev = df.groupby(PAIR_KEYS, sort=False)["share"].shift(1)
    roll = prev.groupby([df[c] for c in PAIR_KEYS], sort=False).rolling(k, min_periods=1)
    n = roll.count().reset_index(level=list(range(len(PAIR_KEYS))), drop=True).sort_index()
    mean = roll.mean().reset_index(level=list(range(len(PAIR_KEYS))), drop=True).sort_index()
    std = roll.std(ddof=1).reset_index(level=list(range(len(PAIR_KEYS))), drop=True).sort_index()

    enough = n.fillna(0) >= k
    mean, std = mean.where(enough), std.where(enough)

    reason = pd.Series(pd.NA, index=df.index, dtype="object")
    reason[~enough] = "insufficient_history"
    reason[reason.isna() & df["share"].isna()] = "missing_share"
    reason[reason.isna() & (std <= STD_EPS)] = "zero_std"

    ok = reason.isna()
    score = ((df["share"] - mean) / std).where(ok, np.nan)
    out = pd.DataFrame({
        **{c: df[c] for c in PAIR_KEYS}, "year": df["year"],
        "detector": "zscore", "k": k, "threshold": threshold, "min_count": min_count,
        "collab_count": df["collab_count"], "international_total": df["international_total"],
        "current_value": df["share"], "baseline_value": mean, "baseline_std": std,
        "baseline_n": n.where(enough), "change": df["share"] - mean,
        "score": score, "detected": (score >= threshold).fillna(False),
        "skip_reason": reason,
    })
    return out[OUTPUT_COLUMNS]
