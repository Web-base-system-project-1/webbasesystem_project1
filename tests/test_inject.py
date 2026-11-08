import numpy as np
import pandas as pd
import pytest

from detectors import build_panel, detect_growth, detect_zscore
from experiments.inject import (
    build_scenarios, inject_decoy, inject_pairs, multiplier_schedule,
    select_decoy_groups, select_pairs,
)

YEARS = list(range(2015, 2025 + 1))  # 2015~2025


def synthetic_panel(n_domestic=5, partners=5, seed=0):
    rng = np.random.default_rng(seed)
    cc, tot = [], []
    for d in range(n_domestic):
        for y in YEARS:
            tot.append(dict(domestic_id=f"D{d}", field="ai", year=y, international_total=200))
        for f in range(partners):
            for y in YEARS:
                cc.append(dict(domestic_id=f"D{d}", foreign_id=f"F{f}", field="ai", year=y,
                               collab_count=int(rng.integers(3, 7))))
    return build_panel(pd.DataFrame(cc), pd.DataFrame(tot), years=YEARS)


@pytest.fixture
def panel():
    return synthetic_panel()


def test_select_pairs_is_deterministic_and_respects_threshold(panel):
    a, b = select_pairs(panel, 20, seed=1), select_pairs(panel, 20, seed=1)
    assert a.equals(b) and len(a) == 20
    assert not a.equals(select_pairs(panel, 20, seed=2))
    low = panel.copy()
    low.loc[low["foreign_id"] == "F0", "collab_count"] = 0
    assert not (select_pairs(low, 20, seed=1)["foreign_id"] == "F0").any()
    with pytest.raises(ValueError):
        select_pairs(panel, 26, seed=1)  # 조건을 만족하는 쌍은 25개뿐


def test_step_x3_counts_denominator_and_truth(panel):
    before = panel.copy()
    pairs = select_pairs(panel, 3, seed=0)
    sched = multiplier_schedule("step", 3, 2021, 2025)
    out, truth = inject_pairs(panel, pairs, sched, "step_x3", "step")
    assert panel.equals(before)  # 입력은 수정되지 않음
    p = pairs.iloc[0]
    sel = lambda df, y: df[(df.domestic_id == p.domestic_id) & (df.foreign_id == p.foreign_id) & (df.year == y)].iloc[0]
    assert sel(out, 2020).collab_count == sel(panel, 2020).collab_count
    assert sel(out, 2021).collab_count == 3 * sel(panel, 2021).collab_count
    # 분모는 늘어난 논문 수만큼만 증가
    added = (out.collab_count - panel.collab_count).groupby([out.domestic_id, out.field, out.year]).sum()
    grown = (out.international_total - panel.international_total).groupby([out.domestic_id, out.field, out.year]).first()
    assert (added == grown).all()
    assert (out["share"] <= 1).all()
    assert set(truth.year) == {2021, 2022, 2023, 2024, 2025} and len(truth) == 3 * 5
    assert (truth.effective == (truth.injected_count > truth.original_count)).all()
    assert truth.effective.all()  # 이 가상 데이터의 건수는 모두 3 이상


def test_gradual_and_spike_schedules():
    assert multiplier_schedule("gradual", 4, 2021, 2025) == {
        2021: 2.0, 2022: 3.0, 2023: 4.0, 2024: 4.0, 2025: 4.0}
    assert multiplier_schedule("spike", 5, 2021, 2025) == {2021: 5.0}


def test_spike_only_marks_one_year(panel):
    pairs = select_pairs(panel, 4, seed=0)
    out, truth = inject_pairs(panel, pairs, multiplier_schedule("spike", 5, 2021, 2025), "s", "spike")
    assert set(truth.year) == {2021}
    assert (out[out.year == 2022].collab_count == panel[panel.year == 2022].collab_count).all()


def test_zero_count_rows_stay_in_truth_but_are_flagged_not_effective(panel):
    pairs = select_pairs(panel, 2, seed=0)
    zeroed = panel.copy()
    mask = (zeroed.foreign_id == pairs.iloc[0].foreign_id) & (zeroed.domestic_id == pairs.iloc[0].domestic_id) & (zeroed.year == 2023)
    zeroed.loc[mask, "collab_count"] = 0
    _, truth = inject_pairs(zeroed, pairs, multiplier_schedule("step", 2, 2021, 2025), "s", "step")
    row = truth[(truth.domestic_id == pairs.iloc[0].domestic_id) & (truth.foreign_id == pairs.iloc[0].foreign_id) & (truth.year == 2023)]
    assert len(row) == 1 and not row.iloc[0].effective
    assert len(truth) == 2 * 5 and truth.year.min() == 2021 and truth.year.max() == 2025


def test_decoy_keeps_share_exactly_but_growth_detector_fires(panel):
    groups = select_decoy_groups(panel, 2, seed=0)
    out = inject_decoy(panel, groups, 3, 2021)
    assert np.allclose(out["share"], panel["share"], equal_nan=True)
    in_group = out.set_index(["domestic_id", "field"]).index.isin(groups.set_index(["domestic_id", "field"]).index)
    assert (out[in_group & (out.year >= 2021)].collab_count == 3 * panel[in_group & (panel.year >= 2021)].collab_count).all()
    z0 = detect_zscore(panel, dict(k=3, threshold=2.0))["score"]
    z1 = detect_zscore(out, dict(k=3, threshold=2.0))["score"]
    assert np.allclose(z0, z1, equal_nan=True)  # z-score는 미끼를 볼 수 없음
    g = detect_growth(out, dict(threshold=1.0, min_count=3))
    assert g[in_group & (g.year == 2021)]["detected"].any()  # 증가율 탐지기는 오탐을 냄
    with pytest.raises(ValueError):
        inject_decoy(panel, groups, 2.5, 2021)


def test_build_scenarios_shares_pairs_and_original_is_unchanged(panel):
    sc = build_scenarios(panel, seed=7, n_pairs=20)
    assert set(sc) == {"original", "step_x2", "step_x3", "step_x5", "gradual_x3", "spike_x5", "decoy_x3"}
    assert sc["original"].panel.equals(panel)
    keys = lambda s: set(map(tuple, sc[s].injections[["domestic_id", "foreign_id", "field"]].drop_duplicates().values))
    assert keys("step_x2") == keys("step_x3") == keys("step_x5")
    assert len(keys("step_x2")) == 20
    assert sc["decoy_x3"].injections.empty and len(sc["decoy_x3"].decoy_targets) == 5
    again = build_scenarios(panel, seed=7, n_pairs=20)
    assert again["step_x5"].injections.equals(sc["step_x5"].injections)
