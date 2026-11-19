"""Reconcile period aggregates against the saved OpenAlex authorships."""

import argparse
from collections import Counter, defaultdict
import math
from pathlib import Path
import sys
import unicodedata

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline._files import PipelineError, fingerprint, project_path, read_csv, read_json, write_json
from pipeline.collect_period import read_shard

PAIR = ("domestic_id", "foreign_id", "field", "year")
TOTAL = ("domestic_id", "field", "year")
COUNTRY = ("domestic_id", "country_code", "field", "year")


def require(condition, message):
    if not condition:
        raise PipelineError(message)


def key(row, columns):
    return tuple(row[column] for column in columns)


def table(directory, filename, columns):
    rows = read_csv(directory / filename)
    values = {key(row, columns): int(row["collab_count"]) for row in rows}
    require(len(values) == len(rows), f"{filename} 중복 키")
    require(all(value > 0 for value in values.values()), f"{filename} 양수 건수 확인")
    return values


def check_shares(directory, filename, columns, counts, totals, years):
    rows = read_csv(directory / filename)
    expected = {(*group, str(year)) for group in {k[:-1] for k in counts} for year in years}
    actual = {key(row, columns) for row in rows}
    require(actual == expected and len(actual) == len(rows), f"{filename} 연도 패널 불일치")
    for row in rows:
        value = key(row, columns)
        total_key = (value[0], value[-2], value[-1]) if len(columns) == 4 else value[-2:]
        denominator = totals[total_key]
        require(int(row["collab_count"]) == counts[value], f"{filename} 분자 불일치")
        require(int(row["international_total"]) == denominator, f"{filename} 분모 불일치")
        valid_share = (
            math.isclose(float(row["share"]), counts[value] / denominator, abs_tol=1e-12)
            if denominator else row["share"] == ""
        )
        require(valid_share, f"{filename} 비중 불일치")


def verify(raw_dir, data_dir):
    manifest = read_json(data_dir / "MANIFEST.json")
    source = read_json(raw_dir / "manifest.json")
    require(fingerprint(raw_dir / "manifest.json") == manifest["source"]["sha256"], "원본 manifest 해시")
    for filename, info in manifest["files"].items():
        require(fingerprint(data_dir / filename) == info["sha256"], f"{filename} 해시")
    years = range(manifest["years"]["min"], manifest["years"]["max"] + 1)
    definitions = {(row["field"], row["topic_id"]) for row in manifest["definitions"]}
    require(source["years"] == list(years), "원본과 집계의 연도 범위")
    require(source["definitions"] == manifest["definitions"], "원본과 집계의 분야 정의")
    expected_shards = {(field, topic, str(year)) for field, topic in definitions for year in years}
    require(
        {(r["field"], r["topic_id"], str(r["year"])) for r in source["shards"]} == expected_shards
        and len(source["shards"]) == len(expected_shards),
        "원본 조회 기록의 누락·중복",
    )
    coverage = read_csv(data_dir / "collection_coverage.csv")
    require({key(row, ("field", "topic_id", "year")) for row in coverage} == expected_shards, "조회 누락")
    require(len(coverage) == len(expected_shards), "중복 조회 기록")
    require(all(r["status"] == "complete" and r["api_count"] == r["collected_works"] for r in coverage), "미완료 조회")

    raw_ids, records, decisions, institution_counts = set(), [], {}, Counter()
    allowed = set(manifest["rules"]["domestic_types"])
    for shard in source["shards"]:
        folder = raw_dir / shard["topic_id"] / str(shard["year"])
        require(fingerprint(folder / "manifest.json") == shard["manifest_sha256"], "원본 조회 기록 해시")
        _, works = read_shard(folder, shard["topic_id"], shard["year"])
        for work in works:
            work_id = work["id"]
            require(work_id not in raw_ids, "중복 논문")
            raw_ids.add(work_id)
            require(work["publication_year"] == shard["year"], "출판 연도 불일치")
            require(work["primary_topic"]["id"].endswith("/" + shard["topic_id"]), "대표 토픽 불일치")
            institutions = {i["id"]: i for author in work["authorships"] for i in author["institutions"]}
            domestic = {iid: i for iid, i in institutions.items() if i["country_code"] == "KR" and i["type"] in allowed}
            foreign = {iid: i for iid, i in institutions.items() if i["country_code"] and i["country_code"] != "KR"}
            reason = "included"
            if len(institutions) > manifest["rules"]["max_unique_institutions_per_work"]:
                reason = "too_many_institutions"
            elif not domestic:
                reason = "no_target_domestic_institution"
            elif not foreign:
                reason = "no_identified_foreign_institution"
            decisions[work_id] = reason
            if reason == "included":
                institution_counts.update(domestic.keys())
                records.append((work, shard["field"], domestic, foreign))

    pairs, totals, countries, registry, examples = set(), set(), set(), {}, defaultdict(list)
    names, rors = defaultdict(set), defaultdict(set)
    for work, field, domestic, foreign in records:
        work_id, year = work["id"], str(work["publication_year"])
        domestic = {iid: i for iid, i in domestic.items() if institution_counts[iid] >= manifest["rules"]["min_domestic_period_works"]}
        if not domestic:
            decisions[work_id] = "below_domestic_period_minimum"
            continue
        examples[field].append({
            "work_id": work_id, "title": work["title"], "year": int(year),
            "primary_topic_id": work["primary_topic"]["id"],
        })
        for iid, institution in {**domestic, **foreign}.items():
            record = (institution["country_code"], institution["type"], institution.get("ror"))
            require(iid not in registry or registry[iid] == record, "기관 ID의 국가·유형·ROR 충돌")
            registry[iid] = record
            folded = "".join(c for c in unicodedata.normalize("NFKC", institution["display_name"]).casefold() if c.isalnum())
            names[(institution["country_code"], folded)].add(iid)
            rors[institution.get("ror")].add(iid)
        for domestic_id in domestic:
            totals.add((work_id, domestic_id, field, year))
            pairs.update((work_id, domestic_id, foreign_id, field, year) for foreign_id in foreign)
            countries.update((work_id, domestic_id, country, field, year) for country in {i["country_code"] for i in foreign.values()})

    for filename, columns, expected in (
        ("pair_contributions.csv", PAIR, pairs),
        ("total_contributions.csv", TOTAL, totals),
        ("country_contributions.csv", COUNTRY, countries),
    ):
        rows = read_csv(data_dir / filename)
        require(len(rows) == len(expected) and {key(row, ("work_id", *columns)) for row in rows} == expected, f"{filename} 원본 근거 불일치")
    audit = read_csv(data_dir / "preprocess_audit.csv")
    require(len(audit) == len(raw_ids) and {row["work_id"] for row in audit} == raw_ids, "감사 행 누락")
    require(all(decisions[row["work_id"]] == row["period_reason"] for row in audit), "최종 제외 판정 불일치")
    pair_counts = Counter(row[1:] for row in pairs)
    country_counts = Counter(row[1:] for row in countries)
    total_counts = Counter(row[1:] for row in totals)
    require(table(data_dir, "collab_counts.csv", PAIR) == pair_counts, "기관 쌍 건수 불일치")
    require(table(data_dir, "country_counts.csv", COUNTRY) == country_counts, "국가 건수 불일치")
    total_rows = read_csv(data_dir / "kr_totals.csv")
    require(len(total_rows) == len(total_counts) and {key(row, TOTAL): int(row["international_total"]) for row in total_rows} == total_counts, "국내 총수 불일치")
    check_shares(data_dir, "collab_shares.csv", PAIR, pair_counts, total_counts, years)
    check_shares(data_dir, "country_shares.csv", COUNTRY, country_counts, total_counts, years)
    national_counts = Counter(row[1:] for row in {(wid, country, field, year) for wid, _, country, field, year in countries})
    national_totals = Counter(row[1:] for row in {(wid, field, year) for wid, _, field, year in totals})
    check_shares(data_dir, "country_overview.csv", ("country_code", "field", "year"), national_counts, national_totals, years)

    baseline = Counter()
    for (domestic, foreign, field, year), count in pair_counts.items():
        if int(year) in manifest["injection_eligibility"]["baseline_years"]:
            baseline[(domestic, foreign, field)] += count
    required = len(manifest["injection_eligibility"]["baseline_years"]) * manifest["injection_eligibility"]["minimum_mean"]
    candidates = read_csv(data_dir / "injection_candidates.csv")
    expected = {pair: count for pair, count in baseline.items() if count >= required}
    require(len(candidates) == len(expected) and {key(row, PAIR[:-1]): int(row["baseline_total"]) for row in candidates} == expected, "주입 후보 불일치")
    duplicates = [
        {"country_code": country, "normalized_name": name, "openalex_ids": sorted(ids)}
        for (country, name), ids in sorted(names.items()) if len(ids) > 1
    ]
    return {
        "data_version": manifest["data_version"], "raw_manifest_sha256": manifest["source"]["sha256"],
        "topic_years": len(coverage), "raw_works": len(raw_ids),
        "retained_works": len({row[0] for row in totals}), "pair_contributions": len(pairs),
        "country_contributions": len(countries), "eligible_pairs": len(candidates),
        "excluded": dict(Counter(reason for reason in decisions.values() if reason != "included")),
        "mapping": {
            "institutions": len(registry), "missing_ror": sum(not row[2] for row in registry.values()),
            "same_ror_multiple_ids": [
                {"ror": ror, "openalex_ids": sorted(ids)}
                for ror, ids in sorted(rors.items(), key=lambda row: row[0] or "") if ror and len(ids) > 1
            ],
            "same_name_groups": duplicates,
        },
        "field_examples": {
            field: [next((row for row in rows if row["year"] == year), None) for year in (2015, 2020, 2025)]
            for field, rows in sorted(examples.items())
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(project_path(args.raw_dir), project_path(args.data_dir))
        output = project_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, result)
    except (OSError, KeyError, ValueError, TypeError, PipelineError) as error:
        print(f"기간 검증 실패: {error}", file=sys.stderr)
        return 1
    print(f"원본 대조 완료: {result['raw_works']}편 → {result['retained_works']}편, 후보 {result['eligible_pairs']}쌍")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
