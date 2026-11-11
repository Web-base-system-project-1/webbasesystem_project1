"""실행기: 모든 시나리오 × 탐지기 × 임계값을 돌려 injections·detections·metrics를 저장한다.

실행 예: python -m experiments.run --synthetic
         python -m experiments.run --counts collab_counts.csv --totals kr_totals.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from detectors import DETECTORS, build_panel
from experiments.evaluate import evaluate
from experiments.inject import build_scenarios, write_injections

THRESHOLDS = {"zscore": (2.0, 2.5, 3.0), "growth": (0.5, 1.0, 2.0)}  # 명세의 필수 임계값
YEARS = list(range(2015, 2025 + 1))


def synthetic_inputs(n_domestic=5, partners=5, seed=0):
    """시연·테스트용 가상 입력 (실제 데이터 아님). collab_counts, kr_totals 형식을 반환한다."""
    rng = np.random.default_rng(seed)
    counts, totals = [], []
    for d in range(n_domestic):
        totals += [dict(domestic_id=f"D{d}", field="ai", year=y, international_total=200) for y in YEARS]
        counts += [dict(domestic_id=f"D{d}", foreign_id=f"F{f}", field="ai", year=y,
                        collab_count=int(rng.integers(3, 7))) for f in range(partners) for y in YEARS]
    return pd.DataFrame(counts), pd.DataFrame(totals)


def run_all(scenarios, k=3, min_count=3, correction_id="none"):
    """detections(탐지된 행만)와 runs(실행 목록)를 돌려준다. 보정 ID는 호출하는 쪽이 정한다."""
    hits, runs = [], []
    for scenario_id, scenario in scenarios.items():
        for name, thresholds in THRESHOLDS.items():
            for threshold in thresholds:
                run_id = f"{name}|th={threshold}|k={k}|min={min_count}|corr={correction_id}"
                result = DETECTORS[name](scenario.panel, dict(k=k, threshold=threshold, min_count=min_count))
                hits.append(result[result["detected"]].assign(
                    scenario_id=scenario_id, run_id=run_id, correction_id=correction_id))
                runs.append(dict(scenario_id=scenario_id, run_id=run_id, detector=name, threshold=threshold,
                                 k=k, min_count=min_count, correction_id=correction_id))
    return pd.concat(hits, ignore_index=True), pd.DataFrame(runs)


def main(argv=None):
    parser = argparse.ArgumentParser(description="주입 → 탐지 → 평가를 한 번에 실행합니다.")
    parser.add_argument("--counts", type=Path, help="collab_counts.csv")
    parser.add_argument("--totals", type=Path, help="kr_totals.csv")
    parser.add_argument("--synthetic", action="store_true", help="가상 데이터로 실행(시연용)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=Path("results/run"))
    args = parser.parse_args(argv)
    if args.synthetic:
        counts, totals = synthetic_inputs()
        print("[주의] 가상 데이터로 실행합니다. 이 결과는 실제 수집 결과가 아닙니다.")
    elif args.counts and args.totals:
        counts, totals = pd.read_csv(args.counts), pd.read_csv(args.totals)
    else:
        parser.error("--synthetic 또는 --counts와 --totals를 지정하세요.")

    scenarios = build_scenarios(build_panel(counts, totals), seed=args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)  # shortcut: 같은 폴더에 다시 실행하면 덮어쓴다, 버전 관리가 필요하면 폴더 이름을 바꿔 실행
    injections = write_injections(scenarios, args.out_dir / "injections.csv")
    detections, runs = run_all(scenarios)
    decoys = pd.concat([s.decoy_targets for s in scenarios.values() if len(s.decoy_targets)], ignore_index=True)
    metrics = evaluate(injections, detections, runs, decoys)
    detections.to_csv(args.out_dir / "detections.csv", index=False, encoding="utf-8")
    metrics.to_csv(args.out_dir / "metrics.csv", index=False, encoding="utf-8")
    print(f"시나리오 {len(scenarios)}개, 실행 {len(runs)}개, 정답 {len(injections)}행, 탐지 {len(detections)}행")
    print(f"저장 폴더: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
