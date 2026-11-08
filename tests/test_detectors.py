"""Hand-calculated examples (see docs/detector-interface.md section 5)."""

import math

import pandas as pd
import pytest

from detectors import build_panel, detect_growth, detect_zscore


def make_panel(counts, total=100, start=2015, pair=("D1", "F1", "ai")):
    years = list(range(start, start + len(counts)))
    cc = pd.DataFrame([
        dict(domestic_id=pair[0], foreign_id=pair[1], field=pair[2], year=y, collab_count=c)
        for y, c in zip(years, counts) if c > 0
    ])
    totals = pd.DataFrame([
        dict(domestic_id=pair[0], field=pair[2], year=y, international_total=total)
        for y in years
    ])
    return build_panel(cc, totals, years=years)


def row(result, year):
    return result[result["year"] == year].iloc[0]


def test_panel_fills_zero_years_and_missing_denominator():
    cc = pd.DataFrame([dict(domestic_id="D", foreign_id="F", field="ai", year=2016, collab_count=2)])
    tot = pd.DataFrame([dict(domestic_id="D", field="ai", year=2016, international_total=4)])
    panel = build_panel(cc, tot, years=[2015, 2016, 2017])
    assert panel["collab_count"].tolist() == [0, 2, 0]
    assert panel["international_total"].tolist() == [0, 4, 0]
    assert panel["share"].isna().tolist() == [True, False, True]
    assert panel.loc[1, "share"] == 0.5


def test_zscore_hand_example():
    panel = make_panel([10, 11, 9, 30])  # shares .10 .11 .09 .30
    r = row(detect_zscore(panel, dict(k=3, threshold=3.0)), 2018)
    assert r["baseline_value"] == pytest.approx(0.10)
    assert r["baseline_std"] == pytest.approx(0.01)
    assert r["score"] == pytest.approx(20.0)
    assert bool(r["detected"])


def test_zscore_excludes_current_year_from_baseline():
    panel = make_panel([10, 11, 9, 30, 30])
    r = row(detect_zscore(panel, dict(k=3, threshold=3.0)), 2019)
    assert r["baseline_value"] == pytest.approx((0.11 + 0.09 + 0.30) / 3)


def test_zscore_skip_reasons():
    res = detect_zscore(make_panel([10, 11, 9, 30]), dict(k=3, threshold=3.0))
    assert row(res, 2017)["skip_reason"] == "insufficient_history"
    assert not row(res, 2017)["detected"]
    flat = detect_zscore(make_panel([10, 10, 10, 30]), dict(k=3, threshold=3.0))
    assert row(flat, 2018)["skip_reason"] == "zero_std"
    assert math.isnan(row(flat, 2018)["score"])


def test_zscore_missing_share_in_baseline_is_insufficient():
    cc = pd.DataFrame([dict(domestic_id="D", foreign_id="F", field="ai", year=y, collab_count=1) for y in (2015, 2016, 2018)])
    tot = pd.DataFrame([dict(domestic_id="D", field="ai", year=y, international_total=10) for y in (2015, 2016, 2018)])
    panel = build_panel(cc, tot, years=[2015, 2016, 2017, 2018])
    r = row(detect_zscore(panel, dict(k=3, threshold=2.0)), 2018)
    assert r["skip_reason"] == "insufficient_history"


def test_zscore_rejects_small_k():
    with pytest.raises(ValueError):
        detect_zscore(make_panel([1, 2, 3]), dict(k=1, threshold=2.0))


def test_growth_hand_example_threshold_is_inclusive():
    res = detect_growth(make_panel([4, 8]), dict(threshold=1.0, min_count=3))
    r = row(res, 2016)
    assert r["score"] == pytest.approx(1.0)
    assert bool(r["detected"])
    assert row(res, 2015)["skip_reason"] == "insufficient_history"


def test_growth_min_count_and_prev_zero():
    res = detect_growth(make_panel([1, 2]), dict(threshold=0.5, min_count=3))
    assert row(res, 2016)["skip_reason"] == "below_min_count"
    res = detect_growth(make_panel([0, 5]), dict(threshold=0.5, min_count=3))
    assert row(res, 2016)["skip_reason"] == "prev_zero"
    assert not row(res, 2016)["detected"]


def test_same_columns_for_both_detectors_and_pairs_are_independent():
    a, b = make_panel([10, 11, 9, 30]), make_panel([5, 5, 6, 5], pair=("D2", "F2", "bio"))
    panel = pd.concat([a, b], ignore_index=True)
    z = detect_zscore(panel, dict(k=3, threshold=2.0))
    g = detect_growth(panel, dict(threshold=1.0, min_count=1))
    assert list(z.columns) == list(g.columns)
    assert len(z) == len(panel)
    assert row(z[z["domestic_id"] == "D1"], 2018)["detected"]
    assert not z[z["domestic_id"] == "D2"]["detected"].any()
