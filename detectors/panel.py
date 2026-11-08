"""Build a full (pair x year) panel so zero-count years are explicit."""

import numpy as np
import pandas as pd

PAIR_KEYS = ["domestic_id", "foreign_id", "field"]
YEARS = tuple(range(2015, 2026))


def build_panel(collab_counts, kr_totals, years=YEARS):
    """collab_counts / kr_totals are DataFrames shaped like collab_counts.csv / kr_totals.csv.

    Every pair that appears at least once gets one row per year.
    Missing pair rows become 0; a missing denominator becomes 0 and share is NaN.
    """
    pairs = collab_counts[PAIR_KEYS].drop_duplicates()
    grid = pairs.merge(pd.DataFrame({"year": list(years)}), how="cross")
    panel = grid.merge(collab_counts, on=PAIR_KEYS + ["year"], how="left")
    panel = panel.merge(kr_totals, on=["domestic_id", "field", "year"], how="left")
    panel["collab_count"] = panel["collab_count"].fillna(0).astype(int)
    panel["international_total"] = panel["international_total"].fillna(0).astype(int)
    denominator = panel["international_total"].replace(0, np.nan)
    panel["share"] = panel["collab_count"] / denominator
    return panel.sort_values(PAIR_KEYS + ["year"]).reset_index(drop=True)
