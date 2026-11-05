"""Count unique work contributions, keeping collaboration numerators separate."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

from pipeline._files import (
    PipelineError, fingerprint, project_path, read_json, source_name,
    utc_now, write_csv, write_json,
)

PAIR_KEYS = ("domestic_id", "foreign_id", "field", "year")
TOTAL_KEYS = ("domestic_id", "field", "year")
CSV_COLUMNS = {
    "collab_counts.csv": (*PAIR_KEYS, "collab_count"),
    "kr_totals.csv": (*TOTAL_KEYS, "international_total"),
    "institutions_kr.csv": ("domestic_id", "name", "type", "ror"),
    "collab_shares.csv": (*PAIR_KEYS, "collab_count", "international_total", "share"),
    "pair_contributions.csv": ("work_id", *PAIR_KEYS),
    "total_contributions.csv": ("work_id", *TOTAL_KEYS),
}


def aggregate_records(works):
    pair_evidence, total_evidence, registry, seen = set(), set(), {}, set()
    for work in works:
        work_id = work["work_id"]
        if work_id in seen:
            raise PipelineError("정제 입력에 중복 논문 ID가 있습니다.")
        seen.add(work_id)
        field, year = work["field"], work["year"]
        domestic = {i["id"]: i for i in work["domestic_institutions"]}
        foreign = {i["id"]: i for i in work["foreign_institutions"]}
        if not domestic or not foreign or not 1 <= work["all_institution_count"] <= 50:
            raise PipelineError("정제 입력에 집계 조건을 만족하지 않는 논문이 있습니다.")
        if set(domestic) & set(foreign) or len(domestic) + len(foreign) > work["all_institution_count"]:
            raise PipelineError("정제 입력의 전체 기관 수와 국내·해외 기관 목록이 다릅니다.")
        if any(i["country_code"] != "KR" for i in domestic.values()):
            raise PipelineError("국내 기관 목록의 국가 코드를 확인하세요.")
        if any(not i["country_code"] or i["country_code"] == "KR" for i in foreign.values()):
            raise PipelineError("해외 기관 목록의 국가 코드를 확인하세요.")

        for institution in (*domestic.values(), *foreign.values()):
            institution_id = institution["id"]
            if institution_id in registry:
                for key in ("country_code", "type", "ror"):
                    previous, current = registry[institution_id].get(key), institution.get(key)
                    if previous and current and previous != current:
                        raise PipelineError("같은 기관 ID의 국가·유형·ROR 정보가 충돌합니다. 원본을 확인하세요.")
                    if not previous:
                        registry[institution_id][key] = current
            else:
                registry[institution_id] = dict(institution)

        for domestic_id in domestic:
            # Exactly one denominator contribution per domestic institution/work.
            total_evidence.add((work_id, domestic_id, field, year))
            for foreign_id in foreign:
                pair_evidence.add((work_id, domestic_id, foreign_id, field, year))

    pairs = Counter(row[1:] for row in pair_evidence)
    totals = Counter(row[1:] for row in total_evidence)
    pair_rows, total_rows, share_rows = [], [], []
    for key, count in sorted(pairs.items()):
        row = dict(zip(PAIR_KEYS, key))
        row["collab_count"] = count
        pair_rows.append(row)
        domestic_id, _, field, year = key
        denominator = totals[(domestic_id, field, year)]
        if not 0 < count <= denominator:
            raise PipelineError("기관 쌍 건수와 국제 공동논문 총수가 일치하지 않습니다.")
        share_rows.append({**row, "international_total": denominator, "share": count / denominator})
    for key, count in sorted(totals.items()):
        total_rows.append({**dict(zip(TOTAL_KEYS, key)), "international_total": count})
    domestic_ids = sorted({key[0] for key in totals})
    institutions = [{
        "domestic_id": institution_id,
        "name": registry[institution_id]["display_name"],
        "type": registry[institution_id]["type"],
        "ror": registry[institution_id].get("ror"),
    } for institution_id in domestic_ids]
    artifacts = {
        "collab_counts.csv": pair_rows,
        "kr_totals.csv": total_rows,
        "institutions_kr.csv": institutions,
        "collab_shares.csv": share_rows,
        "pair_contributions.csv": [dict(zip(("work_id", *PAIR_KEYS), row)) for row in sorted(pair_evidence)],
        "total_contributions.csv": [dict(zip(("work_id", *TOTAL_KEYS), row)) for row in sorted(total_evidence)],
    }
    ror_ids = defaultdict(list)
    for institution_id, institution in registry.items():
        if institution.get("ror"):
            ror_ids[institution["ror"]].append(institution_id)
    review = [{"ror": ror, "institution_ids": sorted(ids)} for ror, ids in sorted(ror_ids.items()) if len(ids) > 1]
    summary = {
        "retained_works": len(works), "domestic_institutions": len(domestic_ids),
        "foreign_institutions": len({key[1] for key in pairs}),
        "institution_pair_rows": len(pairs),
        "pair_contributions": len(pair_evidence), "total_contributions": len(total_evidence),
        "same_ror_review_groups": len(review),
    }
    return artifacts, summary, review


def aggregate_file(input_path, output_dir=None):
    input_path = project_path(input_path)
    output_dir = project_path(output_dir) if output_dir is not None else input_path.parent
    payload = read_json(input_path)
    if (
        not isinstance(payload, dict) or payload.get("status") != "complete"
        or payload.get("data_scope") != "sample" or not isinstance(payload.get("works"), list)
    ):
        raise PipelineError("완료된 sample 범위의 clean_works.json을 지정하세요.")
    artifacts, summary, review = aggregate_records(payload["works"])
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = [*CSV_COLUMNS, "institution_review.json", "aggregation_manifest.json"]
    if any((output_dir / name).exists() for name in targets):
        raise PipelineError("집계 결과 파일이 이미 있습니다. 새 출력 폴더를 지정하세요.")
    manifest = {
        "schema_version": 1, "status": "complete", "data_scope": "sample",
        "created_at": utc_now(),
        "source": {"path": source_name(input_path), "sha256": fingerprint(input_path)},
        "source_sample": payload["source"], "rules": payload["rules"], "summary": summary,
    }
    for name, columns in CSV_COLUMNS.items():
        write_csv(output_dir / name, columns, artifacts[name])
    write_json(output_dir / "institution_review.json", {"same_ror_candidates": review, "automatic_merging": False})
    write_json(output_dir / "aggregation_manifest.json", manifest)
    return output_dir, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="정제 샘플의 기관 쌍·국제 공동논문 총수·비중을 집계합니다.")
    parser.add_argument("--input", type=Path, required=True, help="정제 단계의 clean_works.json")
    parser.add_argument("--output-dir", type=Path, help="기본값은 입력 파일과 같은 폴더")
    args = parser.parse_args(argv)
    try:
        directory, manifest = aggregate_file(args.input, args.output_dir)
    except (PipelineError, ValueError, KeyError, TypeError) as error:
        print(f"집계 실패: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("집계 실패: 입력 파일과 출력 폴더의 위치·권한을 확인하세요.", file=sys.stderr)
        return 1
    summary = manifest["summary"]
    print(f"집계 완료: 논문 {summary['retained_works']}편, 국내 기관 {summary['domestic_institutions']}곳, 기관 쌍 {summary['institution_pair_rows']}개")
    print(f"출력 폴더: {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
