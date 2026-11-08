"""API 응답 형식 합의와 화면 개발을 위한 예시 데이터를 만든다.

실제 OpenAlex 수집 결과가 아니다. 기관 ID 는 모두 EXAMPLE_ 로 시작해
실제 ID 와 구분한다. 실제 집계가 준비되면 .env 의 DATA_DIR 로 교체한다.

    python scripts/make_example_data.py
"""

import csv
import json
import random
from pathlib import Path
from statistics import mean, pstdev

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "data" / "sample" / "example"

SEED = 7
YEARS = list(range(2015, 2026))
FIELDS = ["ai", "bio"]
DOMESTIC = [
    ("EXAMPLE_KR_1", "예시 국내기관 1", "education"),
    ("EXAMPLE_KR_2", "예시 국내기관 2", "education"),
    ("EXAMPLE_KR_3", "예시 국내기관 3", "government"),
]
FOREIGN = [
    ("EXAMPLE_FR_1", "예시 해외기관 1", "US"),
    ("EXAMPLE_FR_2", "예시 해외기관 2", "JP"),
    ("EXAMPLE_FR_3", "예시 해외기관 3", "DE"),
]
# 2021년부터 3배로 올린 주입 예시 쌍
INJECTED = ("EXAMPLE_KR_1", "EXAMPLE_FR_1", "ai")
INJECT_FROM = 2021
K = 3
MIN_COUNT = 3


def write_csv(name, columns, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_shares():
    """국내 기관의 분야·연도별 총수를 먼저 정하고, 쌍별 건수를 그 안에서 만든다."""
    totals = {}
    for domestic_id, _, _ in DOMESTIC:
        for field in FIELDS:
            base = random.randint(30, 45)
            for index, year in enumerate(YEARS):
                totals[(domestic_id, field, year)] = base + index * random.randint(1, 3)

    rows = []
    for domestic_id, _, _ in DOMESTIC:
        for foreign_id, _, _ in FOREIGN:
            for field in FIELDS:
                base = random.randint(2, 5)
                for year in YEARS:
                    count = max(1, base + random.randint(-1, 1))
                    if (domestic_id, foreign_id, field) == INJECTED and year >= INJECT_FROM:
                        count *= 3
                    total = totals[(domestic_id, field, year)]
                    count = min(count, total)
                    rows.append({
                        "domestic_id": domestic_id, "foreign_id": foreign_id,
                        "field": field, "year": year,
                        "collab_count": count, "international_total": total,
                        "share": round(count / total, 6),
                    })
    return rows


def build_detections(rows):
    """예시 데이터에 z-score(k=3)와 전년 대비 증가율을 적용한다."""
    series = {}
    for row in rows:
        key = (row["domestic_id"], row["foreign_id"], row["field"])
        series.setdefault(key, {})[row["year"]] = row

    found = []
    for (domestic_id, foreign_id, field), by_year in sorted(series.items()):
        for year in sorted(by_year):
            current = by_year[year]
            past = [by_year[p]["share"] for p in range(year - K, year) if p in by_year]
            if len(past) == K:
                baseline_mean, baseline_std = mean(past), pstdev(past)
                if baseline_std > 0:
                    score = (current["share"] - baseline_mean) / baseline_std
                    for threshold in (2.0, 2.5, 3.0):
                        if score >= threshold:
                            found.append({
                                "run_id": "example-run", "scenario_id": "example",
                                "domestic_id": domestic_id, "foreign_id": foreign_id,
                                "field": field, "year": year,
                                "detector": "zscore", "threshold": threshold,
                                "correction_id": "", "score": round(score, 4),
                                "baseline_mean": round(baseline_mean, 6),
                                "baseline_std": round(baseline_std, 6),
                                "current_value": current["share"], "previous_value": "",
                                "collab_count": current["collab_count"], "min_count": "",
                            })
            previous = by_year.get(year - 1)
            if previous and current["collab_count"] >= MIN_COUNT and previous["collab_count"] > 0:
                growth = (current["collab_count"] - previous["collab_count"]) / previous["collab_count"]
                for threshold in (0.5, 1.0, 2.0):
                    if growth >= threshold:
                        found.append({
                            "run_id": "example-run", "scenario_id": "example",
                            "domestic_id": domestic_id, "foreign_id": foreign_id,
                            "field": field, "year": year,
                            "detector": "growth", "threshold": threshold,
                            "correction_id": "", "score": round(growth, 4),
                            "baseline_mean": "", "baseline_std": "",
                            "current_value": current["collab_count"],
                            "previous_value": previous["collab_count"],
                            "collab_count": current["collab_count"], "min_count": MIN_COUNT,
                        })
    return found


def main():
    random.seed(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    shares = build_shares()
    detections = build_detections(shares)
    injections = [{
        "scenario_id": "example", "domestic_id": INJECTED[0],
        "foreign_id": INJECTED[1], "field": INJECTED[2], "year": year,
    } for year in range(INJECT_FROM, YEARS[-1] + 1)]

    write_csv("collab_shares.csv",
              ["domestic_id", "foreign_id", "field", "year",
               "collab_count", "international_total", "share"], shares)
    write_csv("institutions_kr.csv", ["domestic_id", "name", "type", "ror"],
              [{"domestic_id": i, "name": n, "type": t, "ror": ""} for i, n, t in DOMESTIC])
    write_csv("institutions_foreign.csv", ["foreign_id", "name", "country_code"],
              [{"foreign_id": i, "name": n, "country_code": c} for i, n, c in FOREIGN])
    write_csv("detections.csv",
              ["run_id", "scenario_id", "domestic_id", "foreign_id", "field", "year",
               "detector", "threshold", "correction_id", "score",
               "baseline_mean", "baseline_std", "current_value", "previous_value",
               "collab_count", "min_count"], detections)
    write_csv("injections.csv",
              ["scenario_id", "domestic_id", "foreign_id", "field", "year"], injections)

    manifest = {
        "schema_version": 1,
        "data_scope": "example",
        "is_real_data": False,
        "data_version": "example-2026-11-08",
        "seed": SEED,
        "generated_by": "scripts/make_example_data.py",
        "purpose": "API 응답 형식 합의와 화면 개발용 예시 데이터. 실제 수집 결과가 아님.",
        "fields": FIELDS,
        "years": {"min": YEARS[0], "max": YEARS[-1]},
        "injected_pair": {"domestic_id": INJECTED[0], "foreign_id": INJECTED[1],
                          "field": INJECTED[2], "from_year": INJECT_FROM, "multiplier": 3},
    }
    (OUT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"collab_shares {len(shares)}행, detections {len(detections)}행, injections {len(injections)}행")
    print(f"출력 폴더: {OUT}")


if __name__ == "__main__":
    main()
