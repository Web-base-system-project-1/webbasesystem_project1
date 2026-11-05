"""Verify saved collector output offline, without reading an API key."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.collect import COUNTRY, YEAR, CollectionError, normalize_topic_id, validate_results


def inspect_sample(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "complete":
        raise CollectionError("완료된 수집이 아닙니다. manifest.json과 수집 로그를 확인하세요.")
    topic_id = normalize_topic_id(manifest["topic_id"])
    limit = manifest["limit"]
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise CollectionError("샘플 상한 정보가 올바르지 않습니다.")
    response = json.loads((directory / "response.json").read_text(encoding="utf-8"))
    sample = json.loads((directory / "sample.json").read_text(encoding="utf-8"))
    results, duplicate_count = validate_results(response, topic_id, limit)
    if (
        sample["results"] != results
        or sample["count"] != len(results)
        or sample["topic_id"] != topic_id
        or sample["year"] != YEAR
        or sample["country_code"] != COUNTRY
        or manifest["year"] != YEAR
        or manifest["country_code"] != COUNTRY
        or manifest["collected_count"] != len(results)
        or manifest["response_count"] != len(response["results"])
        or manifest["duplicate_count"] != duplicate_count
    ):
        raise CollectionError("원본 응답·샘플·실행 요약이 서로 일치하지 않습니다.")
    return {"topic_id": topic_id, "year": YEAR, "count": len(results), "duplicates": duplicate_count}


def main(argv=None):
    parser = argparse.ArgumentParser(description="OpenAlex 샘플 수집 결과를 네트워크 없이 검증합니다.")
    parser.add_argument("directory", type=Path, help="manifest.json 등이 저장된 실행 폴더")
    args = parser.parse_args(argv)
    try:
        result = inspect_sample(args.directory)
    except CollectionError as error:
        print(f"검증 실패: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print("검증 실패: 출력 폴더와 JSON 파일의 형식·필수 항목을 확인하세요.", file=sys.stderr)
        return 1
    print(f"검증 완료: topic={result['topic_id']}, year={result['year']}, count={result['count']}, duplicates={result['duplicates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
