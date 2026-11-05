"""Filter a collected sample into auditable international collaboration works."""

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

from pipeline._files import (
    PipelineError, fingerprint, project_path, read_json, source_name,
    utc_now, write_csv, write_json,
)
from pipeline.collect import normalize_topic_id

DOMESTIC_TYPES = frozenset({"education", "facility", "government"})
FIELDS = ("semiconductor", "ai", "bio", "quantum")
WORK_ID = re.compile(r"https://openalex\.org/W[1-9][0-9]*")
INSTITUTION_ID = re.compile(r"https://openalex\.org/I[1-9][0-9]*")
AUDIT_COLUMNS = (
    "source_index", "work_id", "status", "reason", "all_institution_count",
    "domestic_count", "foreign_count", "unknown_country_count",
    "excluded_kr_type_count", "repeated_institution_occurrences",
)


def _institutions(authorships):
    if not isinstance(authorships, list):
        raise PipelineError("invalid_authorships")
    by_id = {}
    repeated = 0
    for authorship in authorships:
        if not isinstance(authorship, dict) or not isinstance(authorship.get("institutions"), list):
            raise PipelineError("invalid_authorships")
        for raw in authorship["institutions"]:
            if not isinstance(raw, dict):
                raise PipelineError("invalid_institution")
            institution_id = raw.get("id")
            if not isinstance(institution_id, str) or not INSTITUTION_ID.fullmatch(institution_id):
                raise PipelineError("invalid_institution_id")
            if any(raw.get(key) is not None and not isinstance(raw[key], str) for key in ("display_name", "type", "ror")):
                raise PipelineError("invalid_institution_metadata")
            country = raw.get("country_code")
            country = country.upper() if isinstance(country, str) else None
            if country is not None and not re.fullmatch(r"[A-Z]{2}", country):
                country = None
            institution = {
                "id": institution_id,
                "display_name": raw.get("display_name") or institution_id,
                "country_code": country,
                "type": raw.get("type"),
                "ror": raw.get("ror"),
            }
            if institution_id in by_id:
                repeated += 1
                previous = by_id[institution_id]
                if previous["display_name"] == institution_id:
                    previous["display_name"] = institution["display_name"]
                for key in ("country_code", "type", "ror"):
                    if previous[key] and institution[key] and previous[key] != institution[key]:
                        raise PipelineError("conflicting_institution_metadata")
                    if not previous[key]:
                        previous[key] = institution[key]
            else:
                by_id[institution_id] = institution
    return [by_id[key] for key in sorted(by_id)], repeated


def preprocess_records(records, *, topic_id, year=2025, field="ai", include_healthcare=False):
    if not isinstance(records, list) or field not in FIELDS:
        raise PipelineError("논문 목록과 분야 코드를 확인하세요.")
    topic_id = normalize_topic_id(topic_id)
    allowed = DOMESTIC_TYPES | ({"healthcare"} if include_healthcare else set())
    retained, audit, seen = [], [], {}

    for index, work in enumerate(records, start=1):
        row = dict.fromkeys(AUDIT_COLUMNS, 0)
        row.update({"source_index": index, "work_id": "", "status": "excluded", "reason": "invalid_work"})
        audit.append(row)
        if not isinstance(work, dict):
            continue
        work_id = work.get("id")
        row["work_id"] = work_id if isinstance(work_id, str) else ""
        if not isinstance(work_id, str) or not WORK_ID.fullmatch(work_id):
            row["reason"] = "invalid_work_id"
            continue
        if work_id in seen:
            if work != seen[work_id]:
                raise PipelineError("같은 논문 ID의 원본 내용이 다릅니다. 중복 원본을 확인하세요.")
            row["reason"] = "duplicate_work_id"
            continue
        seen[work_id] = work
        if work.get("publication_year") != year:
            row["reason"] = "unexpected_year"
            continue
        try:
            actual_topic = normalize_topic_id(work["primary_topic"]["id"])
        except (KeyError, TypeError, AttributeError, ValueError):
            actual_topic = None
        if actual_topic != topic_id:
            row["reason"] = "unexpected_primary_topic"
            continue
        try:
            institutions, repeated = _institutions(work.get("authorships"))
        except PipelineError as error:
            row["reason"] = str(error)
            continue
        domestic = [i for i in institutions if i["country_code"] == "KR" and i["type"] in allowed]
        foreign = [i for i in institutions if i["country_code"] and i["country_code"] != "KR"]
        row.update({
            "all_institution_count": len(institutions),
            "domestic_count": len(domestic),
            "foreign_count": len(foreign),
            "unknown_country_count": sum(i["country_code"] is None for i in institutions),
            "excluded_kr_type_count": sum(i["country_code"] == "KR" and i["type"] not in allowed for i in institutions),
            "repeated_institution_occurrences": repeated,
        })
        # Apply the 50-institution rule BEFORE filtering domestic institution types.
        if len(institutions) > 50:
            row["reason"] = "too_many_institutions"
        elif not domestic:
            row["reason"] = "no_target_domestic_institution"
        elif not foreign:
            row["reason"] = "no_identified_foreign_institution"
        else:
            row.update({"status": "retained", "reason": "included"})
            retained.append({
                "work_id": work_id,
                "title": work.get("title"),
                "field": field,
                "year": year,
                "primary_topic_id": topic_id,
                "all_institution_count": len(institutions),
                "domestic_institutions": domestic,
                "foreign_institutions": foreign,
            })

    summary = {
        "input_records": len(records),
        "retained_works": len(retained),
        "excluded_records": len(records) - len(retained),
        "reasons": dict(sorted(Counter(row["reason"] for row in audit).items())),
        "repeated_institution_occurrences": sum(row["repeated_institution_occurrences"] for row in audit),
        "works_with_unknown_country": sum(row["unknown_country_count"] > 0 for row in audit),
    }
    rules = {
        "domestic_types": sorted(allowed),
        "max_unique_institutions_per_work": 50,
        "foreign": "known_country_other_than_KR_any_institution_type",
        "identity": "exact_openalex_id_no_ror_or_lineage_merging",
        "min_five_papers_period_filter_applied": False,
    }
    return sorted(retained, key=lambda work: work["work_id"]), audit, summary, rules


def preprocess_sample(input_path, output_dir, *, field="ai", include_healthcare=False):
    input_path, output_dir = project_path(input_path), project_path(output_dir)
    sample = read_json(input_path)
    if (
        not isinstance(sample, dict) or not isinstance(sample.get("results"), list)
        or type(sample.get("count")) is not int
        or sample.get("count") != len(sample["results"])
        or not 0 <= sample["count"] <= 100
        or sample.get("year") != 2025 or sample.get("country_code") != "KR"
    ):
        raise PipelineError("collector가 만든 2025년 KR sample.json 형식과 건수를 확인하세요.")
    topic_id = normalize_topic_id(sample.get("topic_id", ""))
    works, audit, summary, rules = preprocess_records(
        sample["results"], topic_id=topic_id, field=field, include_healthcare=include_healthcare
    )
    manifest = {
        "schema_version": 1, "status": "complete", "data_scope": "sample",
        "created_at": utc_now(), "field": field, "year": 2025, "topic_id": topic_id,
        "source": {"path": source_name(input_path), "sha256": fingerprint(input_path)},
        "rules": rules, "summary": summary,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(output_dir / "clean_works.json", {**manifest, "works": works})
    write_csv(output_dir / "preprocess_audit.csv", AUDIT_COLUMNS, audit)
    write_json(output_dir / "preprocess_manifest.json", manifest)
    return output_dir, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="2025년 OpenAlex 샘플을 국제 공동연구 논문으로 정제합니다.")
    parser.add_argument("--input", type=Path, required=True, help="collector의 sample.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="새 출력 폴더")
    parser.add_argument("--field", choices=FIELDS, default="ai")
    parser.add_argument("--include-healthcare", action="store_true", help="국내 healthcare 기관도 대상으로 포함")
    args = parser.parse_args(argv)
    try:
        directory, manifest = preprocess_sample(
            args.input, args.output_dir, field=args.field, include_healthcare=args.include_healthcare
        )
    except FileExistsError:
        print("정제 실패: 출력 폴더가 이미 있습니다. 새 폴더를 지정하세요.", file=sys.stderr)
        return 1
    except (PipelineError, ValueError) as error:
        print(f"정제 실패: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("정제 실패: 입력 파일과 출력 폴더의 위치·권한을 확인하세요.", file=sys.stderr)
        return 1
    summary = manifest["summary"]
    print(f"정제 완료: 입력 {summary['input_records']}건 → 유지 {summary['retained_works']}편, 제외 {summary['excluded_records']}건")
    print(f"출력 폴더: {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
