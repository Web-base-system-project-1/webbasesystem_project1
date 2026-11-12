"""Collect the 2015–2025 OpenAlex coverage for the configured primary topics."""

import argparse
import csv
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

import requests

from pipeline._files import PipelineError, fingerprint, project_path, read_csv, read_json, utc_now, write_csv, write_json
from pipeline.collect import (
    API_URL, COUNTRY, MAX_WORKS, SELECT_FIELDS, YEAR, CollectionError,
    _fetch_payload, load_api_key, normalize_topic_id, validate_results,
)
from pipeline.preprocess import FIELDS, WORK_ID

YEARS = tuple(range(2015, YEAR + 1))
LIST_AUTHOR_LIMIT = 100
LOG_COLUMNS = (
    "time", "field", "topic_id", "year", "page", "work_id", "status",
    "attempt", "http_status", "response_count",
)


def load_definitions(path):
    return validate_definitions(read_csv(project_path(path)))


def validate_definitions(rows):
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise PipelineError("분야 정의 행의 형식을 확인하세요.")
    definitions = [dict(row) for row in rows]
    topic_ids = set()
    for row in definitions:
        field = row.get("field")
        if not isinstance(row.get("topic_id"), str):
            raise PipelineError("대표 토픽 ID를 확인하세요.")
        topic_id = normalize_topic_id(row["topic_id"])
        if field not in FIELDS or topic_id in topic_ids:
            raise PipelineError("분야 코드를 확인하고 한 대표 토픽을 한 분야에만 배정하세요.")
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in ("topic_name", "rationale")):
            raise PipelineError("토픽 이름과 선정 근거가 필요합니다.")
        row["topic_id"] = topic_id
        topic_ids.add(topic_id)
    if {row["field"] for row in definitions} != set(FIELDS):
        raise PipelineError("네 분야에 각각 하나 이상의 대표 토픽이 필요합니다.")
    return definitions


def work_query(topic_id, year):
    return {
        "filter": f"publication_year:{year},authorships.institutions.country_code:{COUNTRY},primary_topic.id:{topic_id}",
        "select": SELECT_FIELDS,
        "per_page": MAX_WORKS,
    }


def may_have_truncated_authorships(work):
    authorships = work.get("authorships") if isinstance(work, dict) else None
    return isinstance(authorships, list) and len(authorships) >= LIST_AUTHOR_LIMIT


def read_shard(directory, topic_id, year):
    manifest = read_json(directory / "manifest.json")
    if manifest["status"] != "complete" or manifest["query"] != work_query(topic_id, year):
        raise PipelineError(f"{topic_id}/{year} 수집 기록의 완료 상태와 조회 조건을 확인하세요.")
    if "works.json" not in manifest["files"]:
        raise PipelineError(f"{topic_id}/{year}의 논문 파일 해시가 없습니다.")
    for name, sha256 in manifest["files"].items():
        if fingerprint(directory / name) != sha256:
            raise PipelineError(f"{topic_id}/{year} 수집 파일의 해시가 달라졌습니다: {name}")
    records = read_json(directory / "works.json")
    if not isinstance(records, list) or len(records) != manifest["api_count"]:
        raise PipelineError(f"{topic_id}/{year} 수집 건수가 조회 건수와 다릅니다.")
    for work in records:
        if may_have_truncated_authorships(work):
            name = "singleton-" + work["id"].rsplit("/", 1)[-1] + ".json"
            if name not in manifest["files"]:
                raise PipelineError(f"{topic_id}/{year}의 저자 100명 이상 논문에 단건 원본이 필요합니다.")
    return manifest, records


def complete_authorships(work, session, key, staging, files, timeout, record):
    if not may_have_truncated_authorships(work):
        return work
    work_id = work.get("id")
    if not isinstance(work_id, str) or not WORK_ID.fullmatch(work_id):
        raise CollectionError("단건 소속을 조회할 논문 ID가 올바르지 않습니다.")
    short_id = work_id.rsplit("/", 1)[-1]
    name = f"singleton-{short_id}.json"
    if name in files:
        return read_json(staging / name)
    full = _fetch_payload(
        session, key, {"select": SELECT_FIELDS + ",institutions_distinct_count"},
        timeout, record, work_id=short_id,
    )
    if full.get("id") != work_id:
        raise CollectionError("단건 조회의 논문 ID가 목록의 논문 ID와 다릅니다.")
    if type(full.get("institutions_distinct_count")) is not int:
        raise CollectionError("단건 응답에 전체 소속 기관 수가 없습니다.")
    write_json(staging / name, full)
    files[name] = fingerprint(staging / name)
    return full


def collect_shard(session, key, topic_id, year, directory, timeout, record):
    if directory.exists():
        manifest, _ = read_shard(directory, topic_id, year)
        record(0, "reused_complete_shard", response_count=manifest["api_count"])
        return manifest

    directory.parent.mkdir(parents=True, exist_ok=True)
    query = work_query(topic_id, year)
    works = {}
    cursors = set()
    cursor = "*"
    api_count = None
    received = 0
    started_at = utc_now()
    with TemporaryDirectory(prefix=f".{year}-", dir=directory.parent) as temporary:
        staging = Path(temporary) / "shard"
        staging.mkdir()
        files = {}
        while cursor is not None:
            if cursor in cursors:
                raise CollectionError("커서가 반복되어 연도별 수집을 완료하지 못했습니다.")
            cursors.add(cursor)
            page = len(cursors)
            payload = _fetch_payload(
                session, key, {**query, "cursor": cursor}, timeout,
                lambda status, **values: record(page, status, **values),
            )
            meta = payload.get("meta")
            if not isinstance(meta, dict):
                raise CollectionError("OpenAlex 응답에 메타데이터가 없습니다.")
            count = meta.get("count")
            if type(count) is not int or count < 0 or "next_cursor" not in meta:
                raise CollectionError("OpenAlex 응답에 조회 건수나 다음 커서가 없습니다.")
            if api_count is not None and count != api_count:
                raise CollectionError("페이지 사이에 조회 건수가 바뀌었습니다. 이 연도를 다시 수집하세요.")
            api_count = count
            results = payload["results"]
            next_cursor = meta["next_cursor"]
            if next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor or not results):
                raise CollectionError("OpenAlex 응답의 다음 커서가 올바르지 않습니다.")
            received += len(results)
            hydrated = [
                complete_authorships(
                    work, session, key, staging, files, timeout,
                    lambda status, **values: record(
                        page, status, work_id=work.get("id", ""), **values,
                    ),
                )
                for work in results
            ]
            validate_results({"results": hydrated}, topic_id, MAX_WORKS, year=year)
            for work in hydrated:
                if "institutions_distinct_count" in work:
                    count = len({i["id"] for a in work["authorships"] for i in a["institutions"]})
                    if count != work["institutions_distinct_count"] and count <= 50:
                        raise CollectionError("단건 응답의 소속 기관 수가 OpenAlex의 전체 기관 수와 다릅니다.")
                work_id = work["id"]
                previous = works.setdefault(work_id, work)
                if previous != work:
                    raise CollectionError("같은 논문 ID의 페이지별 내용이 다릅니다.")
            name = f"page-{page:04d}.json"
            write_json(staging / name, payload)
            files[name] = fingerprint(staging / name)
            cursor = next_cursor

        if len(works) != api_count:
            raise CollectionError(f"고유 논문 {len(works)}편과 API 조회 건수 {api_count}편이 다릅니다.")
        write_json(staging / "works.json", [works[work_id] for work_id in sorted(works)])
        files["works.json"] = fingerprint(staging / "works.json")
        manifest = {
            "status": "complete", "topic_id": topic_id, "year": year, "query": query,
            "started_at": started_at, "completed_at": utc_now(), "api_count": api_count,
            "response_rows": received, "duplicates": received - len(works),
            "pages": len(cursors), "singleton_works": sum(name.startswith("singleton-") for name in files),
            "files": files,
        }
        write_json(staging / "manifest.json", manifest)
        staging.rename(directory)
    record(len(cursors), "shard_complete", response_count=api_count)
    return manifest


def collect_period(definitions, output_dir, timeout):
    key = load_api_key()
    output_dir.mkdir(parents=True, exist_ok=True)
    logs = output_dir / "logs"
    logs.mkdir(exist_ok=True)
    shards = []
    with (logs / f"{uuid4().hex}.csv").open("w", encoding="utf-8", newline="") as handle, requests.Session() as session:
        writer = csv.DictWriter(handle, fieldnames=LOG_COLUMNS)
        writer.writeheader()
        for definition in definitions:
            field, topic_id = definition["field"], definition["topic_id"]
            for year in YEARS:
                def record(page, status, **values):
                    writer.writerow({
                        "time": utc_now(), "field": field, "topic_id": topic_id,
                        "year": year, "page": page, "status": status, **values,
                    })
                    handle.flush()

                directory = output_dir / topic_id / str(year)
                try:
                    manifest = collect_shard(session, key, topic_id, year, directory, timeout, record)
                except (CollectionError, PipelineError):
                    record(0, "shard_failed")
                    raise
                shards.append({
                    "field": field, "topic_id": topic_id, "year": year,
                    "manifest_sha256": fingerprint(directory / "manifest.json"),
                    "api_count": manifest["api_count"], "duplicates": manifest["duplicates"],
                })
                print(f"{field} {year}: {manifest['api_count']}편 확인", flush=True)
    manifest = {
        "schema_version": 1, "status": "complete", "endpoint": API_URL,
        "years": list(YEARS), "definitions": definitions, "shards": shards,
    }
    target = output_dir / "manifest.json"
    previous = read_json(target) if target.exists() else {}
    log_rows = [row for path in logs.glob("*.csv") for row in read_csv(path)]
    with TemporaryDirectory(prefix=".collection-", dir=output_dir) as temporary:
        staging = Path(temporary)
        write_csv(staging / "collection_log.csv", LOG_COLUMNS, sorted(log_rows, key=lambda row: row["time"]))
        (staging / "collection_log.csv").replace(output_dir / "collection_log.csv")
        if any(previous.get(key) != value for key, value in manifest.items()):
            write_json(staging / "manifest.json", {**manifest, "created_at": utc_now()})
            (staging / "manifest.json").replace(target)
    return shards


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definitions", default="config/field_definition.csv")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 60:
        parser.error("timeout은 0 초과 60 이하의 초 단위 값이어야 합니다.")
    try:
        definitions = load_definitions(args.definitions)
        shards = collect_period(definitions, project_path(args.output_dir), args.timeout)
    except (CollectionError, PipelineError, ValueError) as error:
        print(f"기간 수집 실패: {error}", file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError):
        print("기간 수집 실패: 설정 또는 저장된 수집 파일을 확인하세요.", file=sys.stderr)
        return 1
    print(f"수집 완료: {len(shards)}개 토픽·연도, {sum(row['api_count'] for row in shards)}편")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
