import numpy as np
import pandas as pd
import pytest

from detectors import build_panel
from experiments.evaluate import evaluate
from experiments.inject import build_scenarios
from experiments.run import run_all, synthetic_inputs

RUN = dict(scenario_id="s", run_id="r", detector="zscore", threshold=2.0, k=3, min_count=3, correction_id="none")


def truth(rows):
    return pd.DataFrame([dict(scenario_id="s", domestic_id=d, foreign_id="F", field="ai", year=y, effective=e)
                         for d, y, e in rows])


def det(rows):
    cols = ["scenario_id", "run_id", "domestic_id", "foreign_id", "field", "year"]
    return pd.DataFrame([dict(scenario_id="s", run_id="r", domestic_id=d, foreign_id="F", field="ai", year=y) for d, y in rows], columns=cols)


def one(inj, dets, **kw):
    return evaluate(inj, dets, pd.DataFrame([RUN]), **kw).iloc[0]


def test_counts_metrics_and_delay_by_hand():
    r = one(truth([("A", 2021, True), ("A", 2022, True)]), det([("A", 2021), ("B", 2021)]))
    assert (r.tp, r.fp, r.fn) == (1, 1, 1)
    assert r.precision == r.recall == r.f1 == 0.5
    assert r.delay_mean == 0 and r.missed_pairs == 0


def test_late_detection_has_delay_and_undetected_pair_is_counted_separately():
    r = one(truth([("A", 2021, True), ("A", 2022, True), ("C", 2021, True)]), det([("A", 2022)]))
    assert r.delay_mean == 1          # C는 지연 계산에서 제외
    assert r.missed_pairs == 1


def test_run_without_any_detection_is_all_misses():
    r = one(truth([("A", 2021, True), ("A", 2022, True)]), det([]))
    assert (r.tp, r.fp, r.fn, r.recall) == (0, 0, 2, 0)
    assert np.isnan(r.precision) and np.isnan(r.delay_mean)


def test_recall_effective_ignores_rows_that_did_not_really_change():
    r = one(truth([("A", 2021, True), ("A", 2022, False)]), det([("A", 2021)]))
    assert r.recall == 0.5 and r.recall_effective == 1.0


def test_decoy_fp_counts_only_decoy_groups_from_start_year():
    targets = pd.DataFrame([dict(scenario_id="s", domestic_id="A", field="ai")])
    r = one(truth([]).reindex(columns=["scenario_id", "domestic_id", "foreign_id", "field", "year", "effective"]),
            det([("A", 2020), ("A", 2021), ("A", 2023), ("B", 2023)]), decoy_targets=targets)
    assert r.decoy_fp == 2 and r.fp == 4


def test_full_flow_on_synthetic_data():
    scenarios = build_scenarios(build_panel(*synthetic_inputs(), years=list(range(2015, 2026))), seed=1)
    detections, runs = run_all(scenarios)
    assert len(runs) == 7 * 6 and {"run_id", "correction_id", "scenario_id"} <= set(detections.columns)
    injections = pd.concat([s.injections for s in scenarios.values() if len(s.injections)], ignore_index=True)
    decoys = pd.concat([s.decoy_targets for s in scenarios.values() if len(s.decoy_targets)], ignore_index=True)
    m = evaluate(injections, detections, runs, decoys).set_index(["scenario_id", "run_id"])
    assert len(m) == 42
    # 미끼: share가 같으므로 z-score의 미끼 오탐은 원본의 같은 그룹 탐지와 같고, 증가율 탐지기는 더 많이 오탐한다
    z, g = "zscore|th=2.0|k=3|min=3|corr=none", "growth|th=1.0|k=3|min=3|corr=none"
    original = detections[(detections.scenario_id == "original") & (detections.run_id == z) & (detections.year >= 2021)]
    in_decoy = original.merge(decoys[["domestic_id", "field"]], on=["domestic_id", "field"])
    assert m.loc[("decoy_x3", z), "decoy_fp"] == len(in_decoy)
    assert m.loc[("decoy_x3", g), "decoy_fp"] > m.loc[("original", g), "decoy_fp"] == 0
    assert m.loc[("step_x5", z), "recall"] > 0
