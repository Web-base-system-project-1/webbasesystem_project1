"""Collect one bounded page of 2025 OpenAlex works with Korean affiliations.

Run from the project root with ``python -m pipeline.collect --topic-id T11636``.
Credentials are loaded from the project .env and sent only in an HTTPS header.
"""

import argparse
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import math
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from dotenv import dotenv_values
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
API_URL = "https://api.openalex.org/works"
YEAR = 2025
COUNTRY = "KR"
MAX_WORKS = 100
MAX_ATTEMPTS = 3
MAX_RETRY_WAIT = 30
SELECT_FIELDS = "id,doi,title,publication_year,primary_topic,authorships"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
LOGGER = logging.getLogger(__name__)


class CollectionError(Exception):
    """An error safe to display without exposing credentials or HTTP bodies."""


def normalize_topic_id(value):
    """Accept T12345 or its canonical OpenAlex URL, rejecting filter syntax."""
    match = re.fullmatch(
        r"(?:https://openalex\.org/)?(T[1-9][0-9]*)/?", value.strip(), re.IGNORECASE
    )
    if match is None:
        raise ValueError("토픽 ID는 T숫자 또는 https://openalex.org/T숫자 형식이어야 합니다.")
    return match.group(1).upper()


def load_api_key():
    try:
        key = dotenv_values(ENV_FILE, encoding="utf-8").get("OPENALEX_API_KEY")
    except (OSError, UnicodeError):
        raise CollectionError("프로젝트 .env 파일을 읽지 못했습니다.") from None
    if not key or not key.strip():
        raise CollectionError("프로젝트 .env에 OPENALEX_API_KEY를 입력한 뒤 다시 실행하세요.")
    key = key.strip()
    if not key.isascii() or any(not 33 <= ord(character) <= 126 for character in key):
        raise CollectionError("OPENALEX_API_KEY는 공백·줄바꿈 없는 ASCII 키 값이어야 합니다.")
    return key


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _save_json(path, data):
    """Replace a completed JSON file atomically, preserving Unicode."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _retry_wait(response, attempt):
    delay = float(2 ** (attempt - 1))
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            requested = float(retry_after)
        except ValueError:
            try:
                requested = parsedate_to_datetime(retry_after).timestamp() - time.time()
            except (ValueError, TypeError, OverflowError):
                requested = delay
        if not math.isfinite(requested) or requested > MAX_RETRY_WAIT:
            raise CollectionError("서버가 긴 재시도 대기를 요청했습니다. 사용 한도를 확인하고 나중에 실행하세요.")
        delay = max(delay, requested)
    return delay


def _fetch_payload(session, key, params, timeout, record, *, work_id=None):
    endpoint = API_URL if work_id is None else f"{API_URL}/{work_id}"
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "Project7-OpenAlex-Sample/1.0",
    }
    for attempt in range(1, MAX_ATTEMPTS + 1):
        record("request_started", attempt=attempt)
        try:
            response = session.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=(5.0, timeout),
                allow_redirects=False,
            )
        except requests.RequestException as error:
            # Never stringify a RequestException: it can contain a URL or key.
            category = "timeout" if isinstance(error, requests.Timeout) else "network"
            record(f"{category}_error", attempt=attempt)
            if attempt == MAX_ATTEMPTS:
                raise CollectionError(f"{category} 오류로 요청에 실패했습니다. 네트워크와 timeout을 확인하세요.") from None
            time.sleep(_retry_wait(None, attempt))
            continue

        status = response.status_code
        record("http_response", attempt=attempt, http_status=status)
        if status == 200:
            try:
                payload = response.json()
            except ValueError:
                raise CollectionError("OpenAlex 응답을 JSON으로 읽지 못했습니다.") from None
            if work_id is None and (not isinstance(payload, dict) or not isinstance(payload.get("results"), list)):
                raise CollectionError("OpenAlex 응답에 results 배열이 없습니다.")
            if work_id is not None and not isinstance(payload, dict):
                raise CollectionError("OpenAlex 단건 응답이 논문 객체가 아닙니다.")
            count = len(payload["results"]) if work_id is None else 1
            record("request_succeeded", attempt=attempt, http_status=200, response_count=count)
            return payload

        if status in (401, 403):
            raise CollectionError(f"HTTP {status}: .env의 API 키와 이메일 인증·접근 권한을 확인하세요.")
        if status not in RETRYABLE_STATUSES or attempt == MAX_ATTEMPTS:
            raise CollectionError(f"HTTP {status}: 수집에 실패했습니다. 토픽 ID·조회 조건·API 사용 한도를 확인하세요.")
        delay = _retry_wait(response, attempt)
        record("retry_scheduled", attempt=attempt, http_status=status)
        time.sleep(delay)

    raise CollectionError("요청을 완료하지 못했습니다.")


def validate_results(payload, topic_id, limit=MAX_WORKS, *, year=YEAR):
    """Validate every result; deduplicate work IDs without altering the raw data."""
    topic_id = normalize_topic_id(topic_id)
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise CollectionError("검증할 results 배열이 없습니다.")
    if len(results) > limit:
        raise CollectionError("응답 건수가 요청한 샘플 상한을 초과했습니다.")

    seen = set()
    unique = []
    for index, work in enumerate(results, start=1):
        if not isinstance(work, dict):
            raise CollectionError(f"응답 {index}번의 논문 형식이 올바르지 않습니다.")
        work_id = work.get("id")
        if not isinstance(work_id, str) or not re.fullmatch(r"https://openalex\.org/W[1-9][0-9]*", work_id):
            raise CollectionError(f"응답 {index}번의 논문 ID가 올바르지 않습니다.")
        if work.get("publication_year") != year:
            raise CollectionError(f"응답 {index}번의 출판 연도가 {year}년이 아닙니다.")

        primary = work.get("primary_topic")
        try:
            actual_topic = normalize_topic_id(primary["id"])
        except (KeyError, TypeError, AttributeError, ValueError):
            raise CollectionError(f"응답 {index}번의 대표 토픽이 없거나 올바르지 않습니다.") from None
        if actual_topic != topic_id:
            raise CollectionError(f"응답 {index}번의 대표 토픽이 요청한 토픽과 다릅니다.")

        authorships = work.get("authorships")
        if not isinstance(authorships, list):
            raise CollectionError(f"응답 {index}번에 저자 소속 정보가 없습니다.")
        has_korean_institution = False
        for authorship in authorships:
            if not isinstance(authorship, dict) or not isinstance(authorship.get("institutions"), list):
                raise CollectionError(f"응답 {index}번의 저자 소속 형식이 올바르지 않습니다.")
            for institution in authorship["institutions"]:
                if not isinstance(institution, dict):
                    raise CollectionError(f"응답 {index}번의 기관 형식이 올바르지 않습니다.")
                if institution.get("country_code") == COUNTRY:
                    has_korean_institution = True
        if not has_korean_institution:
            raise CollectionError(f"응답 {index}번에 한국 소속 기관이 없습니다.")

        if work_id not in seen:
            seen.add(work_id)
            unique.append(work)
    return unique, len(results) - len(unique)


def collect_sample(topic_id, *, limit=MAX_WORKS, timeout=30.0, output_dir=None):
    topic_id = normalize_topic_id(topic_id)
    if not isinstance(limit, int) or not 1 <= limit <= MAX_WORKS:
        raise ValueError("limit은 1~100의 정수여야 합니다.")
    if not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("timeout은 0보다 크고 60 이하인 초 단위 값이어야 합니다.")

    key = load_api_key()
    params = {
        "filter": f"publication_year:{YEAR},authorships.institutions.country_code:{COUNTRY},primary_topic.id:{topic_id}",
        "select": SELECT_FIELDS,
        "per_page": limit,
        "page": 1,
    }
    if output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = RAW_DIR / f"ai_{YEAR}_{topic_id}_{stamp}"
    else:
        output_dir = Path(output_dir).expanduser()
        if not output_dir.is_absolute():
            output_dir = PROJECT_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=False)

    request_id = uuid4().hex
    manifest = {
        "request_id": request_id,
        "status": "started",
        "started_at": _utc_now(),
        "endpoint": API_URL,
        "query": params,
        "topic_id": topic_id,
        "year": YEAR,
        "country_code": COUNTRY,
        "limit": limit,
        "timeout_seconds": {"connect": 5.0, "read": timeout},
        "sampling": "first_page_not_random",
        "purpose": "pipeline_validation_sample_not_population_counts",
    }
    _save_json(output_dir / "manifest.json", manifest)

    with (output_dir / "collection_log.csv").open("w", encoding="utf-8", newline="") as log_file:
        fields = ("request_id", "collected_at", "query", "response_count", "status", "attempt", "http_status")
        writer = csv.DictWriter(log_file, fieldnames=fields)
        writer.writeheader()

        def record(status, *, attempt=None, http_status=None, response_count=None):
            writer.writerow({
                "request_id": request_id,
                "collected_at": _utc_now(),
                "query": json.dumps(params, ensure_ascii=False),
                "response_count": response_count,
                "status": status,
                "attempt": attempt,
                "http_status": http_status,
            })
            log_file.flush()
            LOGGER.info("status=%s attempt=%s http=%s count=%s", status, attempt, http_status, response_count)

        try:
            with requests.Session() as session:
                payload = _fetch_payload(session, key, params, timeout, record)
            _save_json(output_dir / "response.json", payload)
            results, duplicate_count = validate_results(payload, topic_id, limit)
            sample = {
                "topic_id": topic_id,
                "year": YEAR,
                "country_code": COUNTRY,
                "count": len(results),
                "results": results,
            }
            _save_json(output_dir / "sample.json", sample)
            manifest.update({
                "status": "complete",
                "finished_at": _utc_now(),
                "response_count": len(payload["results"]),
                "collected_count": len(results),
                "duplicate_count": duplicate_count,
            })
            _save_json(output_dir / "manifest.json", manifest)
            record("collection_complete", response_count=len(results))
        except CollectionError as error:
            manifest.update({"status": "failed", "finished_at": _utc_now(), "error": str(error)})
            _save_json(output_dir / "manifest.json", manifest)
            record("collection_failed")
            raise
    return output_dir, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="2025년 한국 기관 참여 논문의 OpenAlex 샘플을 최대 100편 수집합니다.")
    parser.add_argument("--topic-id", required=True, help="예: T11636 또는 https://openalex.org/T11636")
    parser.add_argument("--limit", type=int, default=100, help="요청할 최대 건수: 1~100, 기본 100")
    parser.add_argument("--timeout", type=float, default=30.0, help="읽기 timeout(초): 0 초과~60, 기본 30")
    parser.add_argument("--output-dir", type=Path, help="새 출력 폴더. 생략하면 data/raw 아래에 실행별 자동 생성")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        directory, manifest = collect_sample(args.topic_id, limit=args.limit, timeout=args.timeout, output_dir=args.output_dir)
    except (CollectionError, ValueError) as error:
        print(f"수집 실패: {error}", file=sys.stderr)
        return 1
    except FileExistsError:
        print("수집 실패: 출력 폴더가 이미 있습니다. 다른 --output-dir를 지정하거나 옵션을 생략하세요.", file=sys.stderr)
        return 1
    except OSError:
        print("수집 실패: 파일 읽기·쓰기에 실패했습니다. 출력 위치와 권한을 확인하세요.", file=sys.stderr)
        return 1
    print(f"수집 완료: {manifest['collected_count']}편 (중복 {manifest['duplicate_count']}건)")
    print(f"저장 폴더: {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
