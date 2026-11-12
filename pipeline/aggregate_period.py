"""Aggregate the verified 2015–2025 collection and check injection eligibility."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from pipeline._files import PipelineError, fingerprint, project_path, read_json, source_name, utc_now, write_csv, write_json
from pipeline.aggregate import CSV_COLUMNS, PAIR_KEYS, TOTAL_KEYS, aggregate_records
from pipeline.collect_period import YEARS, read_shard, validate_definitions
from pipeline.preprocess import AUDIT_COLUMNS, DOMESTIC_TYPES, preprocess_records

BASELINE_YEARS = tuple(range(2015, 2021))
MIN_DOMESTIC_WORKS = 5
MIN_BASELINE_MEAN = 3
REQUIRED_PAIRS = 20
BASELINE_COLUMNS = (
    *PAIR_KEYS[:-1], *(f"count_{year}" for year in BASELINE_YEARS), "baseline_total", "baseline_mean",
)
COVERAGE_COLUMNS = ("field", "topic_id", "year", "status", "api_count", "collected_works", "duplicates")
FOREIGN_COLUMNS = ("foreign_id", "name", "country_code")
AUDIT_PERIOD_COLUMNS = ("field", "topic_id", "year", *AUDIT_COLUMNS, "period_status", "period_reason")


def load_coverage(directory):
    source = read_json(directory / "manifest.json")
    if source["status"] != "complete" or source["years"] != list(YEARS):
        raise PipelineError("2015~2025년 수집을 모두 완료한 원본 폴더가 필요합니다.")
    definitions = validate_definitions(source["definitions"])
    expected = {
        (row["field"], row["topic_id"], year)
        for row in definitions for year in YEARS
    }
    actual = {(row["field"], row["topic_id"], row["year"]) for row in source["shards"]}
    if expected != actual or len(source["shards"]) != len(expected):
        raise PipelineError("토픽·연도별 수집 기록에 누락 또는 중복이 있습니다.")
    return source


def preprocess_period(directory, source, *, include_healthcare=False):
    all_works, audit, coverage, seen = [], [], [], set()
    for shard in source["shards"]:
        field, topic_id, year = (shard[key] for key in ("field", "topic_id", "year"))
        path = directory / topic_id / str(year)
        if fingerprint(path / "manifest.json") != shard["manifest_sha256"]:
            raise PipelineError(f"{topic_id}/{year} 수집 기록의 해시가 달라졌습니다.")
        manifest, records = read_shard(path, topic_id, year)
        if shard["api_count"] != manifest["api_count"] or shard["duplicates"] != manifest["duplicates"]:
            raise PipelineError(f"{topic_id}/{year} 수집 기록의 건수가 다릅니다.")
        ids = {work["id"] for work in records}
        if len(ids) != len(records) or ids & seen:
            raise PipelineError("토픽·연도별 원본에 같은 논문 ID가 있습니다. 수집 시점을 확인하세요.")
        seen.update(ids)
        works, rows, _, _ = preprocess_records(
            records, topic_id=topic_id, year=year, field=field,
            include_healthcare=include_healthcare,
        )
        all_works.extend(works)
        audit.extend({"field": field, "topic_id": topic_id, "year": year, **row} for row in rows)
        coverage.append({
            "field": field, "topic_id": topic_id, "year": year, "status": "complete",
            "api_count": manifest["api_count"], "collected_works": len(records), "duplicates": manifest["duplicates"],
        })
    return all_works, audit, coverage


def filter_domestic_institutions(works, audit):
    works_by_institution = Counter(
        institution["id"] for work in works for institution in work["domestic_institutions"]
    )
    eligible = {key for key, count in works_by_institution.items() if count >= MIN_DOMESTIC_WORKS}
    retained = []
    for work in works:
        domestic = [institution for institution in work["domestic_institutions"] if institution["id"] in eligible]
        if domestic:
            retained.append({**work, "domestic_institutions": domestic})
    retained_ids = {work["work_id"] for work in retained}
    for row in audit:
        if row["work_id"] in retained_ids:
            row["period_status"], row["period_reason"] = "retained", "included"
        elif row["status"] == "retained":
            row["period_status"], row["period_reason"] = "excluded", "below_domestic_period_minimum"
        else:
            row["period_status"], row["period_reason"] = "excluded", row["reason"]
    return retained


def build_series(artifacts):
    counts = {
        tuple(row[key] for key in PAIR_KEYS): row["collab_count"]
        for row in artifacts["collab_counts.csv"]
    }
    totals = {
        tuple(row[key] for key in TOTAL_KEYS): row["international_total"]
        for row in artifacts["kr_totals.csv"]
    }
    series, baselines = [], []
    for domestic_id, foreign_id, field in sorted({key[:-1] for key in counts}):
        pair = (domestic_id, foreign_id, field)
        annual = {year: counts.get((*pair, year), 0) for year in YEARS}
        for year, count in annual.items():
            total = totals.get((domestic_id, field, year), 0)
            series.append({
                **dict(zip(PAIR_KEYS, (*pair, year))), "collab_count": count,
                "international_total": total, "share": count / total if total else None,
            })
        baseline_total = sum(annual[year] for year in BASELINE_YEARS)
        baselines.append({
            **dict(zip(PAIR_KEYS[:-1], pair)),
            **{f"count_{year}": annual[year] for year in BASELINE_YEARS},
            "baseline_total": baseline_total, "baseline_mean": baseline_total / len(BASELINE_YEARS),
        })
    baselines.sort(key=lambda row: (-row["baseline_total"], *(row[key] for key in PAIR_KEYS[:-1])))
    candidates = [row for row in baselines if row["baseline_total"] >= MIN_BASELINE_MEAN * len(BASELINE_YEARS)]
    return series, baselines, candidates


def foreign_institutions(works):
    registry = {}
    for work in works:
        for institution in work["foreign_institutions"]:
            registry.setdefault(institution["id"], {
                "foreign_id": institution["id"], "name": institution["display_name"],
                "country_code": institution["country_code"],
            })
    return [registry[key] for key in sorted(registry)]


def aggregate_period(input_dir, output_dir, *, include_healthcare=False):
    source = load_coverage(input_dir)
    preliminary, audit, coverage = preprocess_period(
        input_dir, source, include_healthcare=include_healthcare,
    )
    works = filter_domestic_institutions(preliminary, audit)
    artifacts, summary, review = aggregate_records(works)
    series, baselines, candidates = build_series(artifacts)
    artifacts.update({
        "collab_shares.csv": series,
        "institutions_foreign.csv": foreign_institutions(works),
        "collection_coverage.csv": coverage,
        "injection_candidates.csv": candidates,
        "preprocess_audit.csv": audit,
    })
    columns = {
        **CSV_COLUMNS, "institutions_foreign.csv": FOREIGN_COLUMNS,
        "collection_coverage.csv": COVERAGE_COLUMNS, "injection_candidates.csv": BASELINE_COLUMNS,
        "preprocess_audit.csv": AUDIT_PERIOD_COLUMNS,
    }

    source_sha256 = fingerprint(input_dir / "manifest.json")
    domestic_types = DOMESTIC_TYPES | ({"healthcare"} if include_healthcare else set())
    manifest = {
        "schema_version": 1, "status": "complete", "data_scope": "period_pilot", "is_real_data": True,
        "created_at": utc_now(), "years": {"min": YEARS[0], "max": YEARS[-1]},
        "definitions": source["definitions"], "source": {
            "path": source_name(input_dir / "manifest.json"), "sha256": source_sha256,
        },
        "summary": {
            **summary, "input_works": len(audit), "prethreshold_works": len(preliminary),
            "shards": len(coverage), "duplicate_api_rows": sum(row["duplicates"] for row in coverage),
            "repeated_institution_occurrences": sum(row["repeated_institution_occurrences"] for row in audit),
            "exclusion_counts": dict(sorted(Counter(
                row["period_reason"] for row in audit if row["period_status"] == "excluded"
            ).items())),
            "distinct_pair_fields": len(baselines), "timeline_rows": len(series),
        },
        "rules": {
            "domestic_types": sorted(domestic_types),
            "min_domestic_period_works": MIN_DOMESTIC_WORKS, "max_unique_institutions_per_work": 50,
            "identity": "exact_openalex_id_no_ror_or_lineage_merging",
            "zero_years": "filled only after all configured topic and year queries are complete",
        },
        "injection_eligibility": {
            "baseline_years": list(BASELINE_YEARS), "minimum_mean": MIN_BASELINE_MEAN,
            "required_pairs": REQUIRED_PAIRS, "eligible_pairs": len(candidates),
            "shortfall": max(0, REQUIRED_PAIRS - len(candidates)),
            "top_baselines": baselines[:10],
        },
    }
    if output_dir.exists():
        raise PipelineError("집계 출력 폴더가 이미 있습니다. 새 폴더를 지정하세요.")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".period-", dir=output_dir.parent) as temporary:
        staging = Path(temporary) / "output"
        staging.mkdir()
        for name, rows in artifacts.items():
            write_csv(staging / name, columns[name], rows)
        write_json(staging / "institution_review.json", {
            "same_ror_candidates": review, "automatic_merging": False,
        })
        manifest["files"] = {
            path.name: {"sha256": fingerprint(path)} for path in sorted(staging.iterdir())
        }
        version_input = {"source_sha256": source_sha256, "files": manifest["files"]}
        digest = hashlib.sha256(json.dumps(version_input, sort_keys=True).encode("utf-8")).hexdigest()
        manifest["data_version"] = f"openalex-four-fields-2015-2025-{digest[:12]}"
        write_json(staging / "MANIFEST.json", manifest)
        staging.rename(output_dir)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--include-healthcare", action="store_true", help="국내 병원도 포함해 비교 집계")
    args = parser.parse_args(argv)
    try:
        result = aggregate_period(
            project_path(args.input_dir), project_path(args.output_dir),
            include_healthcare=args.include_healthcare,
        )
    except (PipelineError, ValueError) as error:
        print(f"기간 집계 실패: {error}", file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError):
        print("기간 집계 실패: 수집 기록과 파일 위치·형식을 확인하세요.", file=sys.stderr)
        return 1
    summary, eligibility = result["summary"], result["injection_eligibility"]
    print(f"집계 완료: {summary['input_works']}편 중 {summary['retained_works']}편, 타임라인 {summary['timeline_rows']}행")
    print(f"주입 후보: {eligibility['eligible_pairs']}쌍, 목표 {eligibility['required_pairs']}쌍, 부족 {eligibility['shortfall']}쌍")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
