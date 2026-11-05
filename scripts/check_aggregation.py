"""Reconcile saved tables and optional independently prepared manual examples."""

import argparse
from collections import Counter
import math
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline._files import PipelineError, fingerprint, project_path, read_csv, read_json
from pipeline.aggregate import PAIR_KEYS, TOTAL_KEYS


def _require(condition, message):
    if not condition:
        raise PipelineError(message)


def _table_counts(rows, keys, column):
    result = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        _require(key not in result, "집계 표에 중복 키가 있습니다.")
        count = int(row[column])
        _require(count > 0, "집계 건수는 양의 정수여야 합니다.")
        result[key] = count
    return result


def inspect_aggregation(directory, manual_reference=None):
    directory = project_path(directory)
    manifest = read_json(directory / "aggregation_manifest.json")
    _require(manifest["status"] == "complete" and manifest["data_scope"] == "sample", "완료된 샘플 집계가 아닙니다.")
    clean_path = project_path(manifest["source"]["path"])
    _require(fingerprint(clean_path) == manifest["source"]["sha256"], "정제 입력 파일의 해시가 달라졌습니다.")
    clean = read_json(clean_path)
    raw_path = project_path(clean["source"]["path"])
    _require(fingerprint(raw_path) == clean["source"]["sha256"], "원본 샘플의 해시가 달라졌습니다.")
    audit = read_csv(clean_path.parent / "preprocess_audit.csv")
    summary = clean["summary"]
    _require(len(audit) == summary["input_records"], "정제 감사 행 수와 입력 건수가 다릅니다.")
    _require(sum(row["status"] == "retained" for row in audit) == len(clean["works"]) == summary["retained_works"], "정제 유지 건수가 일치하지 않습니다.")
    _require(dict(Counter(row["reason"] for row in audit)) == summary["reasons"], "정제 사유별 건수가 다릅니다.")

    pair_trace = read_csv(directory / "pair_contributions.csv")
    total_trace = read_csv(directory / "total_contributions.csv")
    pair_tuples = [tuple(row[k] for k in ("work_id", *PAIR_KEYS)) for row in pair_trace]
    total_tuples = [tuple(row[k] for k in ("work_id", *TOTAL_KEYS)) for row in total_trace]
    _require(len(set(pair_tuples)) == len(pair_tuples), "동일 논문의 기관 쌍 기여가 중복됐습니다.")
    _require(len(set(total_tuples)) == len(total_tuples), "동일 논문의 국내 기관 총수 기여가 중복됐습니다.")
    work_ids = {work["work_id"] for work in clean["works"]}
    _require({row[0] for row in pair_tuples} == {row[0] for row in total_tuples} == work_ids, "논문별 기여 근거가 정제 논문 목록과 다릅니다.")

    pairs = _table_counts(read_csv(directory / "collab_counts.csv"), PAIR_KEYS, "collab_count")
    totals = _table_counts(read_csv(directory / "kr_totals.csv"), TOTAL_KEYS, "international_total")
    _require(pairs == Counter(row[1:] for row in pair_tuples), "기관 쌍 건수가 논문별 근거와 다릅니다.")
    _require(totals == Counter(row[1:] for row in total_tuples), "국제 공동논문 총수가 논문별 근거와 다릅니다.")

    shares = read_csv(directory / "collab_shares.csv")
    _require(len(shares) == len(pairs), "협력 비중 표의 행 수가 다릅니다.")
    _require({tuple(row[k] for k in PAIR_KEYS) for row in shares} == set(pairs), "협력 비중 표의 기관 쌍이 다릅니다.")
    for row in shares:
        key = tuple(row[k] for k in PAIR_KEYS)
        denominator = totals[(key[0], key[2], key[3])]
        _require(int(row["collab_count"]) == pairs[key] and int(row["international_total"]) == denominator, "협력 비중의 분자·분모가 다릅니다.")
        share = float(row["share"])
        _require(0 < share <= 1 and math.isclose(share, pairs[key] / denominator, abs_tol=1e-12), "협력 비중 계산이 올바르지 않습니다.")
    institutions = read_csv(directory / "institutions_kr.csv")
    ids = [row["domestic_id"] for row in institutions]
    _require(len(ids) == len(set(ids)) and set(ids) == {key[0] for key in totals}, "기관 목록과 집계의 국내 기관이 다릅니다.")
    counts = manifest["summary"]
    _require(counts["retained_works"] == len(work_ids) and counts["institution_pair_rows"] == len(pairs), "실행 요약의 논문·기관 쌍 수가 다릅니다.")
    _require(counts["pair_contributions"] == len(pair_trace) and counts["total_contributions"] == len(total_trace), "실행 요약의 기여 건수가 다릅니다.")

    checked = 0
    if manual_reference is not None:
        reference = read_json(project_path(manual_reference))
        _require(reference["source_sample_sha256"] == clean["source"]["sha256"], "수작업 기준이 다른 원본 샘플을 대상으로 합니다.")
        _require(reference["domestic_types"] == clean["rules"]["domestic_types"], "수작업 기준과 국내 기관 유형 조건이 다릅니다.")
        for case in reference["cases"]:
            rows = [row for row in audit if row["work_id"] == case["work_id"]]
            _require(len(rows) == 1, "수작업 기준 논문의 감사 행이 없거나 중복됐습니다.")
            row = rows[0]
            _require(row["status"] == case["expected_status"] and row["reason"] == case["expected_reason"], "수작업 기준과 포함·제외 판정이 다릅니다.")
            _require(int(row["all_institution_count"]) == case["all_institution_count"], "수작업 기준의 전체 기관 수가 다릅니다.")
            actual_pairs = {(r["domestic_id"], r["foreign_id"]) for r in pair_trace if r["work_id"] == case["work_id"]}
            expected_pairs = {(d, f) for d in case["domestic_ids"] for f in case["foreign_ids"]}
            actual_totals = {r["domestic_id"] for r in total_trace if r["work_id"] == case["work_id"]}
            _require(actual_pairs == expected_pairs and len(actual_pairs) == case["pair_contributions"], "수작업 기준의 기관 쌍 기여와 다릅니다.")
            _require(actual_totals == set(case["domestic_ids"]) and len(actual_totals) == case["total_contributions"], "수작업 기준의 국내 기관 총수 기여와 다릅니다.")
            checked += 1
    return {"works": len(work_ids), "pairs": len(pairs), "domestic_institutions": len(ids), "manual_cases": checked}


def main(argv=None):
    parser = argparse.ArgumentParser(description="집계 CSV·논문별 근거·비중·선택적 수작업 기준을 검증합니다.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manual-reference", type=Path)
    args = parser.parse_args(argv)
    try:
        result = inspect_aggregation(args.directory, args.manual_reference)
    except PipelineError as error:
        print(f"집계 검증 실패: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print("집계 검증 실패: 파일 위치·형식·필수 열을 확인하세요.", file=sys.stderr)
        return 1
    print(f"집계 검증 완료: 논문 {result['works']}편, 국내 기관 {result['domestic_institutions']}곳, 기관 쌍 {result['pairs']}개, 수작업 기준 {result['manual_cases']}편 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
