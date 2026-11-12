"""Regression checks for historical OpenAlex collection."""

import pytest

from pipeline import collect_period
from pipeline._files import read_json
from pipeline.collect import CollectionError


def work_with_affiliations(authorships):
    return {
        "id": "https://openalex.org/W1",
        "publication_year": 2015,
        "primary_topic": {"id": "https://openalex.org/T10472"},
        "authorships": authorships,
    }


def record(*args, **kwargs):
    pass


def test_period_fetches_full_authorships_before_checking_kr(monkeypatch, tmp_path):
    foreign = {"institutions": [{"id": "https://openalex.org/I1", "country_code": "US"}]}
    domestic = {"institutions": [{"id": "https://openalex.org/I2", "country_code": "KR"}]}
    truncated = work_with_affiliations([foreign] * 100)
    full = {**work_with_affiliations([foreign] * 100 + [domestic]), "institutions_distinct_count": 2}

    def fetch(session, key, params, timeout, log, *, work_id=None):
        if work_id is None:
            return {"meta": {"count": 1, "next_cursor": None}, "results": [truncated]}
        assert work_id == "W1"
        return full

    monkeypatch.setattr(collect_period, "_fetch_payload", fetch)
    directory = tmp_path / "2015"
    manifest = collect_period.collect_shard(None, "fake", "T10472", 2015, directory, 1, record)
    assert manifest["singleton_works"] == 1
    assert read_json(directory / "page-0001.json")["results"] == [truncated]
    assert collect_period.read_shard(directory, "T10472", 2015)[1] == [full]


def test_incomplete_cursor_run_does_not_publish_complete_shard(monkeypatch, tmp_path):
    work = work_with_affiliations([
        {"institutions": [{"id": "https://openalex.org/I2", "country_code": "KR"}]},
    ])
    monkeypatch.setattr(
        collect_period, "_fetch_payload",
        lambda *args: {"meta": {"count": 2, "next_cursor": None}, "results": [work]},
    )
    directory = tmp_path / "2015"
    with pytest.raises(CollectionError, match="API 조회 건수"):
        collect_period.collect_shard(None, "fake", "T10472", 2015, directory, 1, record)
    assert not directory.exists()
