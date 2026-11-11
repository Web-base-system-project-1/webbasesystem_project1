"""패널에 가상의 이상 사례를 주입한다 (docs/detector-interface.md 참고).

규칙
- 주입한 논문은 해당 기관 쌍만의 추가 논문으로 본다. 따라서 국내 기관의 분모
  (international_total)도 늘어난 건수만큼 함께 늘어난다.
  이렇게 하면 share가 1을 넘지 않고, 같은 기관의 다른 파트너 비중은 조금 내려간다.
- 미끼 시나리오: 한 (국내 기관, 분야)의 모든 쌍에 같은 정수 배수를 분자와 분모에
  모두 곱한다. 그래서 모든 share가 그대로다.
- 건수는 반올림(0.5는 올림)한다. 명세에 따라 주입한 쌍의 예정된 모든 연도
  (예: 2021~2025)를 injections.csv에 기록한다. 건수가 실제로 늘지 않은 행
  (0편 × n = 0)은 effective=False로 표시해, 평가할 때 포함/제외 Recall을 모두 낼 수 있다.
- 입력은 수정하지 않는다. 모든 함수는 새 패널을 반환한다.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from detectors.panel import LAST_YEAR, PAIR_KEYS

GROUP_KEYS = ["domestic_id", "field"]
INJECTION_COLUMNS = [
    "scenario_id", "domestic_id", "foreign_id", "field", "year",
    "injection_type", "multiplier", "original_count", "injected_count", "effective",
]
# (시나리오 ID, 주입 유형, 배수). gradual은 RAMP_YEARS년에 걸쳐 서서히 늘린다.
DEFAULT_SPECS = [
    ("step_x2", "step", 2), ("step_x3", "step", 3), ("step_x5", "step", 5),
    ("gradual_x3", "gradual", 3), ("spike_x5", "spike", 5),
]
RAMP_YEARS = 3
DECOY_FACTOR = 3


@dataclass
class Scenario:
    scenario_id: str
    kind: str                      # original | step | gradual | spike | decoy
    panel: pd.DataFrame
    injections: pd.DataFrame       # 정답 행 (original, decoy는 비어 있음)
    decoy_targets: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=GROUP_KEYS))


def _round_half_up(values):
    return np.floor(np.asarray(values, dtype=float) + 0.5).astype(int)


def _with_share(panel):
    out = panel.copy()
    out["share"] = out["collab_count"] / out["international_total"].replace(0, np.nan)
    return out


def select_pairs(panel, n_pairs=20, seed=42, base_years=(2015, 2020), min_avg=3.0):
    """base_years 동안 연평균 공동논문 수가 min_avg 이상인 쌍 중 무작위로 고른다 (시드 고정)."""
    base = panel[panel["year"].between(*base_years)]
    mean = base.groupby(PAIR_KEYS)["collab_count"].mean()
    eligible = mean[mean >= min_avg].index.to_frame(index=False)
    eligible = eligible.sort_values(PAIR_KEYS).reset_index(drop=True)
    if len(eligible) < n_pairs:
        raise ValueError(f"eligible pairs {len(eligible)} < requested {n_pairs}")
    picked = np.random.default_rng(seed).choice(len(eligible), size=n_pairs, replace=False)
    return eligible.iloc[sorted(picked)].reset_index(drop=True)


def multiplier_schedule(kind, factor, start_year, end_year, ramp_years=RAMP_YEARS):
    """주입할 연도별 배수 {연도: 배수}를 반환한다."""
    if kind == "step":
        return {y: float(factor) for y in range(start_year, end_year + 1)}
    if kind == "spike":
        return {start_year: float(factor)}
    if kind == "gradual":
        return {
            y: 1 + (factor - 1) * min(i + 1, ramp_years) / ramp_years
            for i, y in enumerate(range(start_year, end_year + 1))
        }
    raise ValueError(f"unknown injection kind: {kind}")


def inject_pairs(panel, pairs, schedule, scenario_id, kind):
    """쌍 건수에 schedule[연도]를 곱하고, 늘어난 건수만큼 분모에도 더한다."""
    target = panel.set_index(PAIR_KEYS).index.isin(pairs.set_index(PAIR_KEYS).index)
    mult = panel["year"].map(schedule).fillna(1.0).where(target, 1.0)
    new_count = _round_half_up(panel["collab_count"] * mult)
    delta = pd.Series(new_count - panel["collab_count"].to_numpy(), index=panel.index)
    group_delta = delta.groupby([panel["domestic_id"], panel["field"], panel["year"]]).transform("sum")

    out = panel.copy()
    out["collab_count"] = new_count
    out["international_total"] = panel["international_total"] + group_delta
    out = _with_share(out)

    hit = target & panel["year"].isin(list(schedule)).to_numpy()
    truth = pd.DataFrame({
        "scenario_id": scenario_id,
        **{c: panel.loc[hit, c] for c in PAIR_KEYS}, "year": panel.loc[hit, "year"],
        "injection_type": kind, "multiplier": mult[hit],
        "original_count": panel.loc[hit, "collab_count"], "injected_count": new_count[hit],
        "effective": (delta[hit] > 0).to_numpy(),
    })[INJECTION_COLUMNS].reset_index(drop=True)
    return out, truth


def select_decoy_groups(panel, n_groups=5, seed=42, min_pairs=3):
    """해외 파트너가 min_pairs곳 이상인 (국내 기관, 분야) 그룹을 무작위로 고른다."""
    pairs_per_group = panel.drop_duplicates(PAIR_KEYS).groupby(GROUP_KEYS).size()
    eligible = pairs_per_group[pairs_per_group >= min_pairs].index.to_frame(index=False)
    eligible = eligible.sort_values(GROUP_KEYS).reset_index(drop=True)
    if len(eligible) < n_groups:
        raise ValueError(f"eligible decoy groups {len(eligible)} < requested {n_groups}")
    picked = np.random.default_rng(seed).choice(len(eligible), size=n_groups, replace=False)
    return eligible.iloc[sorted(picked)].reset_index(drop=True)


def inject_decoy(panel, groups, factor=DECOY_FACTOR, start_year=2021):
    """그룹 내 모든 쌍의 분자와 분모에 같은 배수를 곱한다. share는 변하지 않는다."""
    if int(factor) != factor or factor < 2:
        raise ValueError("decoy factor must be an integer >= 2 (keeps share exact)")
    in_group = panel.set_index(GROUP_KEYS).index.isin(groups.set_index(GROUP_KEYS).index)
    rows = in_group & (panel["year"] >= start_year).to_numpy()
    out = panel.copy()
    out.loc[rows, "collab_count"] = panel.loc[rows, "collab_count"] * int(factor)
    out.loc[rows, "international_total"] = panel.loc[rows, "international_total"] * int(factor)
    return _with_share(out)


def build_scenarios(panel, seed=42, n_pairs=20, start_year=2021, specs=DEFAULT_SPECS):
    """원본과 주입 시나리오를 만든다. 모든 시나리오가 같은 선정 쌍과 시드를 쓴다."""
    end_year = min(int(panel["year"].max()), LAST_YEAR)
    pairs = select_pairs(panel, n_pairs=n_pairs, seed=seed)
    scenarios = {"original": Scenario("original", "original", panel.copy(),
                                      pd.DataFrame(columns=INJECTION_COLUMNS))}
    for scenario_id, kind, factor in specs:
        schedule = multiplier_schedule(kind, factor, start_year, end_year)
        new_panel, truth = inject_pairs(panel, pairs, schedule, scenario_id, kind)
        scenarios[scenario_id] = Scenario(scenario_id, kind, new_panel, truth)
    groups = select_decoy_groups(panel, seed=seed)
    decoy_id = f"decoy_x{DECOY_FACTOR}"
    scenarios[decoy_id] = Scenario(
        decoy_id, "decoy", inject_decoy(panel, groups, DECOY_FACTOR, start_year),
        pd.DataFrame(columns=INJECTION_COLUMNS), groups.assign(scenario_id=decoy_id),
    )
    return scenarios


def write_injections(scenarios, path):
    """모든 시나리오의 정답을 injections.csv(UTF-8)로 저장한다."""
    frames = [s.injections for s in scenarios.values() if len(s.injections)]
    table = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=INJECTION_COLUMNS)
    table.to_csv(path, index=False, encoding="utf-8")
    return table
