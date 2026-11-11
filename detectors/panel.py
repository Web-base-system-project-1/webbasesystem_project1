"""기관 쌍 × 연도 전체 패널을 만든다. 건수가 0인 연도도 행으로 남긴다."""

import numpy as np
import pandas as pd

PAIR_KEYS = ["domestic_id", "foreign_id", "field"]
FIRST_YEAR, LAST_YEAR = 2015, 2025  # 명세: 출판 연도 2015~2025 (양 끝 포함)
YEARS = tuple(range(FIRST_YEAR, LAST_YEAR + 1))


def build_panel(collab_counts, kr_totals, years=YEARS):
    """collab_counts, kr_totals: collab_counts.csv, kr_totals.csv와 같은 열을 가진 DataFrame.

    한 번이라도 등장한 기관 쌍마다 연도별로 한 행씩 만든다.
    쌍 행이 없는 연도의 건수는 0, 분모가 없으면 분모는 0이고 share는 결측(NaN)이다.
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
