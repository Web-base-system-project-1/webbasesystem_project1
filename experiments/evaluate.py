"""정답(injections)과 탐지(detections)를 맞대어 정탐·오탐·미탐과 지표를 계산한다."""

import numpy as np
import pandas as pd

KEY = ["scenario_id", "domestic_id", "foreign_id", "field", "year"]
PAIR = ["scenario_id", "domestic_id", "foreign_id", "field"]
RUN_COLUMNS = ["scenario_id", "run_id", "detector", "threshold", "k", "min_count", "correction_id"]


def _ratio(a, b):
    return a / b if b else np.nan


def evaluate(injections, detections, runs, decoy_targets=None, decoy_start=2021):
    """runs의 실행(시나리오 × 탐지기 × 파라미터)마다 한 행씩 지표를 돌려준다.

    runs를 따로 받는 이유: 탐지가 0건인 실행도 미탐으로 세어야 하기 때문이다.
    decoy_fp: 미끼 그룹(국내 기관, 분야)에서 decoy_start년 이후에 나온 탐지 수.
    """
    rows = []
    for run in runs.itertuples(index=False):
        truth = injections[injections["scenario_id"] == run.scenario_id]
        det = detections[(detections["scenario_id"] == run.scenario_id)
                         & (detections["run_id"] == run.run_id)][KEY].drop_duplicates()
        m = truth.merge(det, on=KEY, how="outer", indicator=True)
        hit = m["_merge"] == "both"
        tp, fp, fn = int(hit.sum()), int((m["_merge"] == "right_only").sum()), int((m["_merge"] == "left_only").sum())

        # 탐지 지연: 주입 시작 연도 대비 처음 정탐한 연도. 끝까지 못 잡은 쌍은 지연에서 빼고 따로 센다.
        first_hit = m[hit].groupby(PAIR)["year"].min()
        start = truth.groupby(PAIR)["year"].min()
        delay = first_hit - start.reindex(first_hit.index)

        decoy_fp = 0
        if decoy_targets is not None:
            groups = decoy_targets[decoy_targets["scenario_id"] == run.scenario_id]
            in_decoy = det.merge(groups[["domestic_id", "field"]], on=["domestic_id", "field"])
            decoy_fp = int((in_decoy["year"] >= decoy_start).sum())

        effective = int(truth["effective"].sum()) if len(truth) else 0
        precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
        rows.append({
            **run._asdict(), "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall,
            "f1": _ratio(2 * precision * recall, precision + recall) if tp else (np.nan if np.isnan(precision) and np.isnan(recall) else 0.0),
            "recall_effective": _ratio(int((hit & m["effective"].eq(True)).sum()), effective),
            "delay_mean": delay.mean() if len(delay) else np.nan,
            "missed_pairs": len(start) - len(first_hit), "decoy_fp": decoy_fp,
        })
    return pd.DataFrame(rows)
