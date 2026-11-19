"""Trace representative experiment errors back to collected paper IDs."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from detectors import DETECTORS, build_panel
from detectors.panel import PAIR_KEYS
from experiments.correct import require_min_international_total, require_share_increase
from experiments.inject import build_scenarios
from pipeline._files import fingerprint, project_path, read_json, source_name, write_json

KEYS = [*PAIR_KEYS, "year"]


def records(frame):
    return json.loads(frame.to_json(orient="records"))


def review(data_dir, raw_dir, experiment_dir, output, seed):
    manifest = read_json(data_dir / "MANIFEST.json")
    if fingerprint(raw_dir / "manifest.json") != manifest["source"]["sha256"]:
        raise ValueError("집계 버전과 원본 폴더가 다릅니다.")
    counts = pd.read_csv(data_dir / "collab_counts.csv")
    totals = pd.read_csv(data_dir / "kr_totals.csv")
    panel = build_panel(counts, totals)
    scenarios = build_scenarios(panel, seed=seed)
    evidence = pd.read_csv(data_dir / "pair_contributions.csv")
    total_evidence = pd.read_csv(data_dir / "total_contributions.csv")
    domestic = pd.read_csv(data_dir / "institutions_kr.csv").set_index("domestic_id")["name"]
    foreign = pd.read_csv(data_dir / "institutions_foreign.csv").set_index("foreign_id")["name"]

    raw_index = {}
    source = read_json(raw_dir / "manifest.json")
    for shard in source["shards"]:
        path = raw_dir / shard["topic_id"] / str(shard["year"]) / "works.json"
        for work in read_json(path):
            raw_index[work["id"]] = (work, path)

    cases, metrics = [], pd.read_csv(experiment_dir / "metrics.csv")
    saved_truth = pd.read_csv(experiment_dir / "injections.csv")
    expected_truth = pd.concat(
        [s.injections for s in scenarios.values() if not s.injections.empty], ignore_index=True,
    )
    pd.testing.assert_frame_equal(
        saved_truth.sort_values(["scenario_id", *KEYS]).reset_index(drop=True),
        expected_truth.sort_values(["scenario_id", *KEYS]).reset_index(drop=True),
        check_dtype=False,
    )
    saved_detections = pd.read_csv(experiment_dir / "detections.csv")
    for scenario_id in ("original", "step_x3", "decoy_x3"):
        scenario = scenarios[scenario_id]
        truth = pd.MultiIndex.from_frame(scenario.injections[KEYS])
        for detector, threshold in (("zscore", 2.5), ("growth", 1.0)):
            result = DETECTORS[detector](scenario.panel, {"k": 3, "threshold": threshold, "min_count": 3})
            run_id = f"{detector}|th={threshold}|k=3|min=3|corr=none"
            saved = saved_detections[
                saved_detections["scenario_id"].eq(scenario_id) & saved_detections["run_id"].eq(run_id)
            ]
            if set(saved[KEYS].itertuples(index=False, name=None)) != set(
                result.loc[result["detected"], KEYS].itertuples(index=False, name=None)
            ):
                raise ValueError("저장된 탐지 결과와 현재 입력·탐지기가 다릅니다.")
            corrected = (
                require_min_international_total(result)
                if detector == "zscore" else require_share_increase(result, scenario.panel)
            )
            result["corrected_detected"] = corrected["detected"]
            result["corrected_skip_reason"] = corrected["skip_reason"]
            index = pd.MultiIndex.from_frame(result[KEYS])
            injected = index.isin(truth)
            injected_effective = pd.MultiIndex.from_frame(
                scenario.injections.loc[scenario.injections["effective"].eq(True), KEYS]
            )
            effective = index.isin(injected_effective)
            result["effective"] = effective
            selections = {}
            if scenario_id == "original":
                selections["original_signal"] = result[result["detected"]]
            elif scenario_id == "step_x3":
                selections["effective_false_negative"] = result[injected & effective & ~result["detected"]]
                selections["zero_count_false_negative"] = result[injected & ~effective & ~result["detected"]]
                selections["true_positive"] = result[injected & result["detected"]]
                selections["correction_removed_true_positive"] = result[injected & result["detected"] & ~result["corrected_detected"]]
            else:
                groups = pd.MultiIndex.from_frame(scenario.decoy_targets[["domestic_id", "field"]])
                targeted = pd.MultiIndex.from_frame(result[["domestic_id", "field"]]).isin(groups)
                decoy_hits = result[targeted & result["year"].ge(2021) & result["detected"]]
                selections["decoy_false_positive"] = decoy_hits
                selections["correction_removed_decoy_false_positive"] = decoy_hits[~decoy_hits["corrected_detected"]]

            for label, selection in selections.items():
                if selection.empty:
                    continue
                selection = selection.sort_values(
                    ["collab_count", "score", *KEYS], ascending=[False, False, *([True] * len(KEYS))],
                )
                # Keep a distinct pair/year when two categories overlap.
                used = {
                    tuple(item[name] for name in KEYS)
                    for item in cases if item["scenario_id"] == scenario_id and item["detector"] == detector
                }
                available = selection[
                    ~pd.MultiIndex.from_frame(selection[KEYS]).isin(list(used))
                ] if used else selection
                if available.empty:
                    continue
                row = available.iloc[[0]]
                item = records(row)[0]
                domestic_id, foreign_id, field, year = (item[name] for name in KEYS)
                same_pair = (
                    panel["domestic_id"].eq(domestic_id) & panel["foreign_id"].eq(foreign_id)
                    & panel["field"].eq(field)
                )
                same_scenario_pair = (
                    scenario.panel["domestic_id"].eq(domestic_id)
                    & scenario.panel["foreign_id"].eq(foreign_id)
                    & scenario.panel["field"].eq(field)
                )
                contributions = evidence[
                    evidence["domestic_id"].eq(domestic_id)
                    & evidence["foreign_id"].eq(foreign_id) & evidence["field"].eq(field)
                ]
                numerator = contributions[contributions["year"].eq(year)]
                denominator = total_evidence[
                    total_evidence["domestic_id"].eq(domestic_id)
                    & total_evidence["field"].eq(field) & total_evidence["year"].eq(year)
                ]
                original = panel[same_pair & panel["year"].eq(year)].iloc[0]
                if len(numerator) != original["collab_count"] or len(denominator) != original["international_total"]:
                    raise ValueError("사례의 원본 분자·분모가 논문 근거와 다릅니다.")

                paper_rows = []
                for paper_id in sorted(contributions["work_id"].unique()):
                    paper, path = raw_index[paper_id]
                    institutions = {
                        i["id"] for author in paper["authorships"] for i in author["institutions"]
                    }
                    if domestic_id not in institutions or foreign_id not in institutions:
                        raise ValueError("원본에 사례의 기관 쌍이 없습니다.")
                    paper_rows.append({
                        "work_id": paper_id, "title": paper["title"],
                        "year": paper["publication_year"], "primary_topic_id": paper["primary_topic"]["id"],
                        "raw_file": source_name(path),
                    })
                item.update({
                    "classification": label, "scenario_id": scenario_id,
                    "domestic_name": domestic[domestic_id], "foreign_name": foreign[foreign_id],
                    "original_timeline": records(panel[same_pair]),
                    "scenario_timeline": records(scenario.panel[same_scenario_pair]),
                    "original_current_paper_ids": sorted(numerator["work_id"].tolist()),
                    "original_current_total_ids": sorted(denominator["work_id"].tolist()),
                    "pair_papers": paper_rows,
                })
                cases.append(item)

    result = {
        "data_version": manifest["data_version"], "seed": seed,
        "experiment_files": {
            name: fingerprint(experiment_dir / name) for name in ("injections.csv", "detections.csv", "metrics.csv")
        },
        "cases": cases,
        "case_counts": dict(Counter(item["classification"] for item in cases)),
        "metrics": records(metrics),
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "detection-data-review.json", result)
    print(f"원본 기관 쌍 대조 사례 {len(cases)}건, 평가 {len(metrics)}건")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--experiments-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    review(
        project_path(args.data_dir), project_path(args.raw_dir), project_path(args.experiments_dir),
        project_path(args.output_dir), args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
