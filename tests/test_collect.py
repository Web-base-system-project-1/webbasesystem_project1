"""Synthetic responses only; no network or real API key is used in these tests."""

from copy import deepcopy
import csv
import json

import pytest
import requests

from pipeline import collect

TEST_KEY = "test-only-key-never-a-real-credential"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    @property
    def text(self):
        raise AssertionError("Error response bodies must not be read or logged.")


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Tests must not make real HTTP requests.")
    monkeypatch.setattr(requests.Session, "request", fail)


@pytest.fixture
def work():
    return {
        "id": "https://openalex.org/W123",
        "doi": None,
        "title": "합성 시험 논문",
        "publication_year": 2025,
        "primary_topic": {"id": "https://openalex.org/T11636", "display_name": "Synthetic topic"},
        "authorships": [{
            "author": {"id": "https://openalex.org/A123", "display_name": "Synthetic author"},
            "institutions": [
                {"id": "https://openalex.org/I123", "country_code": "KR", "display_name": "시험 기관"},
                {"id": "https://openalex.org/I456", "country_code": "US"},
            ],
            "raw_affiliation_strings": ["시험 소속 원문"],
        }],
    }


@pytest.fixture
def environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(f"OPENALEX_API_KEY={TEST_KEY}\n", encoding="utf-8")
    monkeypatch.setattr(collect, "ENV_FILE", env)
    monkeypatch.setattr(collect.time, "sleep", lambda seconds: None)
    return tmp_path / "run"


def fake_http(monkeypatch, events):
    calls = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            event = events[len(calls) - 1]
            if isinstance(event, Exception):
                raise event
            return event

    monkeypatch.setattr(collect.requests, "Session", FakeSession)
    return calls


@pytest.mark.parametrize("value", ["T11636", "t11636", "https://openalex.org/T11636"])
def test_normalize_topic_id(value):
    assert collect.normalize_topic_id(value) == "T11636"


@pytest.mark.parametrize("value", ["AI", "W123", "T0", "T123,publication_year:2024", "https://evil.example/T11636"])
def test_reject_invalid_topic(value):
    with pytest.raises(ValueError):
        collect.normalize_topic_id(value)


def test_success_preserves_raw_and_affiliations_and_hides_key(environment, work, monkeypatch, caplog):
    payload = {"meta": {"count": 390}, "results": [work]}
    original = deepcopy(payload)
    calls = fake_http(monkeypatch, [FakeResponse(payload=payload)])
    caplog.set_level("INFO")

    directory, manifest = collect.collect_sample("T11636", limit=10, timeout=12, output_dir=environment)

    assert json.loads((directory / "response.json").read_text(encoding="utf-8")) == original
    sample = json.loads((directory / "sample.json").read_text(encoding="utf-8"))
    assert sample["results"] == [work]
    assert sample["count"] == manifest["collected_count"] == 1
    assert manifest["status"] == "complete"
    url, request = calls[0]
    assert url == collect.API_URL
    assert request["headers"]["Authorization"] == f"Bearer {TEST_KEY}"
    assert "api_key" not in request["params"]
    assert "primary_topic.id:T11636" in request["params"]["filter"]
    assert "authorships.institutions.country_code:KR" in request["params"]["filter"]
    assert "publication_year:2025" in request["params"]["filter"]
    assert request["params"]["per_page"] == 10
    assert request["timeout"] == (5.0, 12)
    assert request["allow_redirects"] is False
    for path in directory.iterdir():
        assert TEST_KEY not in path.read_text(encoding="utf-8")
    assert TEST_KEY not in caplog.text


def test_raw_duplicates_preserved_but_sample_is_unique(environment, work, monkeypatch):
    fake_http(monkeypatch, [FakeResponse(payload={"results": [work, deepcopy(work)]})])
    directory, manifest = collect.collect_sample("T11636", output_dir=environment)
    assert len(json.loads((directory / "response.json").read_text(encoding="utf-8"))["results"]) == 2
    assert len(json.loads((directory / "sample.json").read_text(encoding="utf-8"))["results"]) == 1
    assert manifest["duplicate_count"] == 1


@pytest.mark.parametrize("mutation", ["wrong_year", "wrong_topic", "no_topic", "no_kr", "invalid_id", "missing_authorships"])
def test_incorrect_records_fail_without_success_sample(environment, work, monkeypatch, mutation):
    if mutation == "wrong_year":
        work["publication_year"] = 2024
    elif mutation == "wrong_topic":
        work["primary_topic"]["id"] = "https://openalex.org/T99999"
    elif mutation == "no_topic":
        work["primary_topic"] = None
    elif mutation == "no_kr":
        work["authorships"][0]["institutions"][0]["country_code"] = "JP"
    elif mutation == "invalid_id":
        work["id"] = None
    else:
        work.pop("authorships")
    fake_http(monkeypatch, [FakeResponse(payload={"results": [work]})])
    with pytest.raises(collect.CollectionError):
        collect.collect_sample("T11636", output_dir=environment)
    assert (environment / "response.json").exists()
    assert not (environment / "sample.json").exists()
    assert json.loads((environment / "manifest.json").read_text(encoding="utf-8"))["status"] == "failed"


def test_response_cannot_exceed_requested_limit(environment, work, monkeypatch):
    second = deepcopy(work)
    second["id"] = "https://openalex.org/W456"
    fake_http(monkeypatch, [FakeResponse(payload={"results": [work, second]})])
    with pytest.raises(collect.CollectionError, match="상한"):
        collect.collect_sample("T11636", limit=1, output_dir=environment)


def test_empty_result_is_successful_zero_sample(environment, monkeypatch):
    fake_http(monkeypatch, [FakeResponse(payload={"meta": {"count": 0}, "results": []})])
    directory, manifest = collect.collect_sample("T11636", output_dir=environment)
    assert manifest["status"] == "complete"
    assert manifest["collected_count"] == 0
    assert json.loads((directory / "sample.json").read_text(encoding="utf-8"))["results"] == []


@pytest.mark.parametrize("limit", [0, 101])
def test_limit_is_bounded_before_request(environment, limit):
    with pytest.raises(ValueError):
        collect.collect_sample("T11636", limit=limit, output_dir=environment)
    assert not environment.exists()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 61])
def test_timeout_is_bounded_before_request(environment, timeout):
    with pytest.raises(ValueError):
        collect.collect_sample("T11636", timeout=timeout, output_dir=environment)
    assert not environment.exists()


def test_missing_key_fails_before_any_output(environment, monkeypatch):
    collect.ENV_FILE.write_text("OPENALEX_API_KEY=\n", encoding="utf-8")
    with pytest.raises(collect.CollectionError, match="OPENALEX_API_KEY"):
        collect.collect_sample("T11636", output_dir=environment)
    assert not environment.exists()


def test_http_retry_then_success(environment, work, monkeypatch):
    waits = []
    monkeypatch.setattr(collect.time, "sleep", waits.append)
    calls = fake_http(monkeypatch, [FakeResponse(429, headers={"Retry-After": "3"}), FakeResponse(payload={"results": [work]})])
    _, manifest = collect.collect_sample("T11636", output_dir=environment)
    assert len(calls) == 2
    assert waits == [3.0]
    assert manifest["status"] == "complete"


def test_long_retry_after_does_not_retry_early(environment, monkeypatch):
    waits = []
    monkeypatch.setattr(collect.time, "sleep", waits.append)
    calls = fake_http(monkeypatch, [FakeResponse(429, headers={"Retry-After": "3600"})])
    with pytest.raises(collect.CollectionError, match="긴 재시도"):
        collect.collect_sample("T11636", output_dir=environment)
    assert len(calls) == 1
    assert waits == []


def test_network_failure_is_bounded_and_does_not_log_key(environment, monkeypatch, caplog):
    failure = requests.Timeout(f"request included api_key={TEST_KEY}")
    calls = fake_http(monkeypatch, [failure, failure, failure])
    caplog.set_level("INFO")
    with pytest.raises(collect.CollectionError) as caught:
        collect.collect_sample("T11636", output_dir=environment)
    assert len(calls) == 3
    assert TEST_KEY not in str(caught.value)
    assert TEST_KEY not in caplog.text
    for path in environment.iterdir():
        assert TEST_KEY not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("status", [400, 401, 403, 302])
def test_nonretryable_http_error_is_not_retried(environment, monkeypatch, status):
    calls = fake_http(monkeypatch, [FakeResponse(status)])
    with pytest.raises(collect.CollectionError, match=f"HTTP {status}"):
        collect.collect_sample("T11636", output_dir=environment)
    assert len(calls) == 1
    with (environment / "collection_log.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[-1]["status"] == "collection_failed"


@pytest.mark.parametrize("payload", [ValueError(TEST_KEY), {"error": TEST_KEY}, []])
def test_malformed_json_is_safe(environment, monkeypatch, payload, caplog):
    fake_http(monkeypatch, [FakeResponse(payload=payload)])
    with pytest.raises(collect.CollectionError) as caught:
        collect.collect_sample("T11636", output_dir=environment)
    assert TEST_KEY not in str(caught.value)
    assert TEST_KEY not in caplog.text
    assert not (environment / "sample.json").exists()


def test_existing_output_is_not_overwritten(environment, monkeypatch):
    environment.mkdir()
    previous = environment / "sample.json"
    previous.write_text('{"previous": true}', encoding="utf-8")
    with pytest.raises(FileExistsError):
        collect.collect_sample("T11636", output_dir=environment)
    assert previous.read_text(encoding="utf-8") == '{"previous": true}'


def test_cli_reports_missing_key_without_traceback(environment, capsys):
    collect.ENV_FILE.write_text("OPENALEX_API_KEY=\n", encoding="utf-8")
    assert collect.main(["--topic-id", "T11636", "--output-dir", str(environment)]) == 1
    output = capsys.readouterr()
    assert "OPENALEX_API_KEY" in output.err
    assert "Traceback" not in output.err


@pytest.mark.parametrize("bad_key", ["자신의_API_키", "key with spaces", "key\x00value"])
def test_invalid_header_key_is_rejected_without_exposure(environment, bad_key):
    collect.ENV_FILE.write_text(f"OPENALEX_API_KEY={bad_key}\n", encoding="utf-8")
    with pytest.raises(collect.CollectionError) as caught:
        collect.collect_sample("T11636", output_dir=environment)
    assert bad_key not in str(caught.value)
    assert not environment.exists()


def test_one_hundred_valid_works_are_allowed(environment, work, monkeypatch):
    works = [dict(deepcopy(work), id=f"https://openalex.org/W{number}") for number in range(1, 101)]
    fake_http(monkeypatch, [FakeResponse(payload={"results": works})])
    _, manifest = collect.collect_sample("T11636", output_dir=environment)
    assert manifest["collected_count"] == 100


def test_saved_sample_can_be_checked_offline(environment, work, monkeypatch):
    from scripts.check_sample import inspect_sample

    fake_http(monkeypatch, [FakeResponse(payload={"results": [work]})])
    directory, _ = collect.collect_sample("T11636", output_dir=environment)
    assert inspect_sample(directory) == {"topic_id": "T11636", "year": 2025, "count": 1, "duplicates": 0}


def test_saved_sample_tampering_is_detected(environment, work, monkeypatch):
    from scripts.check_sample import inspect_sample

    fake_http(monkeypatch, [FakeResponse(payload={"results": [work]})])
    directory, _ = collect.collect_sample("T11636", output_dir=environment)
    sample_file = directory / "sample.json"
    sample = json.loads(sample_file.read_text(encoding="utf-8"))
    sample["count"] = 100
    sample_file.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(collect.CollectionError, match="일치"):
        inspect_sample(directory)
