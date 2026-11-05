"""Synthetic edge cases and offline reconciliation for collaboration counts."""

from copy import deepcopy
import json

import pytest

from pipeline._files import PipelineError, fingerprint, read_csv, read_json, write_csv
from pipeline.aggregate import CSV_COLUMNS, aggregate_file, aggregate_records
from pipeline.preprocess import preprocess_records, preprocess_sample
from scripts.check_aggregation import inspect_aggregation

TOPIC = "T11636"


def institution(number, country="KR", kind="education", ror=None):
    return {
        "id": f"https://openalex.org/I{number}",
        "display_name": f"시험 기관 {number}",
        "country_code": country, "type": kind, "ror": ror,
    }


def work(number, institutions):
    return {
        "id": f"https://openalex.org/W{number}",
        "title": f"합성 시험 논문 {number}",
        "publication_year": 2025,
        "primary_topic": {"id": f"https://openalex.org/{TOPIC}"},
        "authorships": [{"institutions": institutions}],
    }


def clean(records, **kwargs):
    return preprocess_records(records, topic_id=TOPIC, **kwargs)


def run_files(tmp_path, records):
    source = tmp_path / "sample.json"
    source.write_text(json.dumps({
        "topic_id": TOPIC, "year": 2025, "country_code": "KR",
        "count": len(records), "results": records,
    }, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "processed"
    preprocess_sample(source, output)
    aggregate_file(output / "clean_works.json")
    return source, output


def test_two_domestic_three_foreign_with_repeated_author_affiliations():
    original = work(1, [institution(1), institution(2), institution(3, "US"), institution(4, "US"), institution(5, "GB")])
    original["authorships"].append(deepcopy(original["authorships"][0]))
    before = deepcopy(original)
    records, audit, summary, rules = clean([original])
    artifacts, counts, _ = aggregate_records(records)
    assert original == before
    assert audit[0]["all_institution_count"] == 5
    assert summary["repeated_institution_occurrences"] == 5
    assert len(artifacts["collab_counts.csv"]) == 6
    assert [row["international_total"] for row in artifacts["kr_totals.csv"]] == [1, 1]
    assert all(row["share"] == 1 for row in artifacts["collab_shares.csv"])
    assert counts["pair_contributions"] == 6
    assert counts["total_contributions"] == 2
    assert rules["min_five_papers_period_filter_applied"] is False


def test_numerator_and_denominator_across_two_works():
    records, *_ = clean([
        work(1, [institution(1), institution(2, "US"), institution(3, "GB")]),
        work(2, [institution(1), institution(2, "US")]),
    ])
    artifacts, _, _ = aggregate_records(records)
    rows = {row["foreign_id"]: row for row in artifacts["collab_shares.csv"]}
    assert rows["https://openalex.org/I2"]["collab_count"] == 2
    assert rows["https://openalex.org/I2"]["international_total"] == 2
    assert rows["https://openalex.org/I2"]["share"] == 1
    assert rows["https://openalex.org/I3"]["collab_count"] == 1
    assert rows["https://openalex.org/I3"]["share"] == 0.5


def test_duplicate_work_is_not_double_counted():
    source = work(1, [institution(1), institution(2, "US")])
    records, audit, summary, _ = clean([source, deepcopy(source)])
    assert len(records) == 1
    assert audit[1]["reason"] == "duplicate_work_id"
    assert summary["input_records"] == 2
    assert summary["excluded_records"] == 1
    artifacts, _, _ = aggregate_records(records)
    assert artifacts["collab_counts.csv"][0]["collab_count"] == 1
    with pytest.raises(PipelineError, match="중복 논문"):
        aggregate_records(records + deepcopy(records))


def test_healthcare_option_only_changes_domestic_eligibility():
    hospital_work = work(1, [institution(1, kind="healthcare"), institution(2, "US", "healthcare")])
    records, audit, *_ = clean([hospital_work])
    assert records == []
    assert audit[0]["reason"] == "no_target_domestic_institution"
    records, *_ = clean([hospital_work], include_healthcare=True)
    assert len(records) == 1
    university_work = work(2, [institution(3), institution(2, "US", "healthcare")])
    records, *_ = clean([university_work])
    assert len(records) == 1
    assert records[0]["foreign_institutions"][0]["type"] == "healthcare"


@pytest.mark.parametrize("total,retained", [(50, True), (51, False)])
def test_full_institution_limit_precedes_type_filter(total, retained):
    institutions = [institution(1), institution(2, "US")]
    institutions.extend(institution(n, kind="healthcare") for n in range(3, total + 1))
    records, audit, *_ = clean([work(1, institutions)])
    assert bool(records) is retained
    assert audit[0]["all_institution_count"] == total
    assert audit[0]["reason"] == ("included" if retained else "too_many_institutions")


def test_unknown_country_is_not_treated_as_foreign():
    records, audit, *_ = clean([work(1, [institution(1), institution(2, None)])])
    assert records == []
    assert audit[0]["reason"] == "no_identified_foreign_institution"
    assert audit[0]["unknown_country_count"] == 1
    records, audit, *_ = clean([work(2, [institution(1), institution(2, None), institution(3, "US")])])
    assert len(records[0]["foreign_institutions"]) == 1
    assert audit[0]["unknown_country_count"] == 1


def test_same_ror_or_lineage_does_not_automatically_merge_ids():
    first = institution(1, ror="https://ror.org/example")
    second = institution(2, ror="https://ror.org/example")
    second["lineage"] = [first["id"], second["id"]]
    records, *_ = clean([work(1, [first, second, institution(3, "US")])])
    artifacts, _, review = aggregate_records(records)
    assert len(artifacts["institutions_kr.csv"]) == 2
    assert review == [{"ror": "https://ror.org/example", "institution_ids": [first["id"], second["id"]]}]


def test_conflicting_affiliation_metadata_is_audited():
    records, audit, *_ = clean([work(1, [institution(1), institution(1, "US")])])
    assert records == []
    assert audit[0]["reason"] == "conflicting_institution_metadata"


@pytest.mark.parametrize("change,reason", [
    ("year", "unexpected_year"), ("topic", "unexpected_primary_topic"),
    ("work_id", "invalid_work_id"), ("institution_id", "invalid_institution_id"),
    ("institutions", "invalid_authorships"), ("type", "invalid_institution_metadata"),
])
def test_bad_records_have_explicit_exclusion_reasons(change, reason):
    source = work(1, [institution(1), institution(2, "US")])
    if change == "year": source["publication_year"] = 2024
    elif change == "topic": source["primary_topic"] = None
    elif change == "work_id": source["id"] = "unknown"
    elif change == "institution_id": source["authorships"][0]["institutions"][0]["id"] = None
    elif change == "institutions": source["authorships"][0]["institutions"] = None
    else: source["authorships"][0]["institutions"][0]["type"] = ["education"]
    records, audit, summary, _ = clean([source])
    assert records == []
    assert audit[0]["reason"] == reason
    assert summary["reasons"] == {reason: 1}


def test_file_pipeline_reconciles_and_preserves_source(tmp_path):
    records = [
        work(1, [institution(1), institution(2), institution(3, "US")]),
        work(2, [institution(1)]),
    ]
    source, output = run_files(tmp_path, records)
    assert read_json(source)["results"] == records
    manifest = read_json(output / "preprocess_manifest.json")
    assert manifest["source"]["sha256"] == fingerprint(source)
    assert manifest["summary"]["retained_works"] == 1
    assert inspect_aggregation(output) == {"works": 1, "pairs": 2, "domestic_institutions": 2, "manual_cases": 0}


def test_reference_examples_are_checked(tmp_path):
    source, output = run_files(tmp_path, [work(1, [institution(1), institution(2, "US")])])
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({
        "source_sample_sha256": fingerprint(source),
        "domestic_types": ["education", "facility", "government"],
        "cases": [{
            "work_id": "https://openalex.org/W1", "expected_status": "retained",
            "expected_reason": "included", "all_institution_count": 2,
            "domestic_ids": ["https://openalex.org/I1"], "foreign_ids": ["https://openalex.org/I2"],
            "pair_contributions": 1, "total_contributions": 1,
        }],
    }), encoding="utf-8")
    assert inspect_aggregation(output, reference)["manual_cases"] == 1


def test_changed_count_is_detected(tmp_path):
    _, output = run_files(tmp_path, [work(1, [institution(1), institution(2, "US")])])
    rows = read_csv(output / "kr_totals.csv")
    rows[0]["international_total"] = 2
    write_csv(output / "kr_totals.csv", CSV_COLUMNS["kr_totals.csv"], rows)
    with pytest.raises(PipelineError, match="총수"):
        inspect_aggregation(output)


def test_changed_source_is_detected(tmp_path):
    source, output = run_files(tmp_path, [work(1, [institution(1), institution(2, "US")])])
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(PipelineError, match="원본 샘플의 해시"):
        inspect_aggregation(output)


def test_empty_sample_produces_header_only_tables(tmp_path):
    _, output = run_files(tmp_path, [])
    for name in CSV_COLUMNS:
        assert read_csv(output / name) == []
    assert inspect_aggregation(output)["works"] == 0


def test_existing_outputs_are_preserved(tmp_path):
    source, output = run_files(tmp_path, [work(1, [institution(1), institution(2, "US")])])
    before = fingerprint(output / "collab_counts.csv")
    with pytest.raises(FileExistsError):
        preprocess_sample(source, output)
    with pytest.raises(PipelineError, match="이미"):
        aggregate_file(output / "clean_works.json")
    assert fingerprint(output / "collab_counts.csv") == before


def test_conflicting_duplicate_work_requires_review():
    first = work(1, [institution(1), institution(2, "US")])
    changed = deepcopy(first)
    changed["publication_year"] = 2024
    with pytest.raises(PipelineError, match="같은 논문 ID"):
        clean([first, changed])


def test_inconsistent_total_institution_count_is_rejected():
    records, *_ = clean([work(1, [institution(1), institution(2, "US")])])
    records[0]["all_institution_count"] = 1
    with pytest.raises(PipelineError, match="전체 기관 수"):
        aggregate_records(records)
