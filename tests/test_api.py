"""Offline API contract checks against the committed example and invalid inputs."""

import csv
import json
from pathlib import Path
import shutil

import pytest

from web import data_store
from web.app import app

EXAMPLE = Path(__file__).resolve().parents[1] / "data/sample/example"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(EXAMPLE))
    monkeypatch.setattr(data_store, "_store", None)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    folder = tmp_path / "dataset"
    shutil.copytree(EXAMPLE, folder)
    monkeypatch.setenv("DATA_DIR", str(folder))
    return folder


def strict_json(response):
    def reject(value):
        raise AssertionError(f"Non-standard JSON value: {value}")
    return json.loads(response.get_data(as_text=True), parse_constant=reject)


def test_example_meta_and_all_timelines_match_csv(client):
    meta = client.get("/api/meta").get_json()
    assert meta["is_real_data"] is False
    assert meta["counts"] == {
        "rows": 198, "domestic_institutions": 3, "foreign_institutions": 3,
        "pairs": 18, "detections": 75, "injections": 5,
    }
    with (EXAMPLE / "collab_shares.csv").open(encoding="utf-8") as handle:
        shares = list(csv.DictReader(handle))
    with (EXAMPLE / "detections.csv").open(encoding="utf-8") as handle:
        detections = list(csv.DictReader(handle))
    pairs = client.get("/api/pairs").get_json()
    assert pairs["total"] == 18
    observed = 0
    for pair in pairs["items"]:
        keys = {key: pair[key] for key in ("domestic_id", "foreign_id", "field")}
        response = client.get("/api/timeline", query_string={**keys, "source": "file"})
        assert response.status_code == 200
        result = strict_json(response)
        assert result["data_version"] == meta["data_version"]
        expected = [row for row in shares if all(row[k] == v for k, v in keys.items())]
        assert result["points"] == [{
            "year": int(row["year"]), "collab_count": int(row["collab_count"]),
            "international_total": int(row["international_total"]), "share": float(row["share"]),
        } for row in expected]
        expected_detections = [row for row in detections if all(row[k] == v for k, v in keys.items())]
        assert len(result["detections"]) == len(expected_detections)
        for actual, expected in zip(result["detections"], expected_detections):
            for key in ("detector", "run_id", "scenario_id"):
                assert actual[key] == expected[key]
            for key in ("year", "threshold", "score", "collab_count"):
                assert actual[key] == float(expected[key])
        observed += len(result["detections"])
    assert observed == 75


@pytest.mark.parametrize("query", ["[", "(", ".", ".*"])
def test_search_is_literal(client, query):
    response = client.get("/api/institutions", query_string={"q": query})
    assert response.status_code == 200
    assert response.get_json()["total"] == 0
    assert client.get("/api/institutions?q=example_kr").get_json()["total"] == 3


@pytest.mark.parametrize("path", [
    "/api/pairs?min_count=abc", "/api/pairs?min_count=-1",
    "/api/pairs?limit=0", "/api/pairs?limit=1001",
    "/api/institutions?role=other", "/api/detections?year=abc",
    "/api/detections?threshold=nan", "/api/detections?threshold=inf",
    "/api/detections?threshold=-inf",
    "/api/timeline?domestic_id=EXAMPLE_KR_1&foreign_id=EXAMPLE_FR_1&field=ai&threshold=nan",
])
def test_invalid_parameters_return_json_400(client, path):
    response = client.get(path)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_parameter"


def test_missing_and_unknown_pairs(client):
    assert client.get("/api/timeline").get_json()["error"]["code"] == "missing_parameter"
    response = client.get("/api/timeline?domestic_id=NOPE&foreign_id=NOPE&field=ai")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "pair_not_found"


@pytest.mark.parametrize(("filename", "contents"), [
    ("institutions_kr.csv", "domestic_id\nEXAMPLE_KR_1\n"),
    ("institutions_foreign.csv", "foreign_id,name\nEXAMPLE_FR_1,test\n"),
    ("detections.csv", "detector,score\nzscore,3\n"),
    ("injections.csv", "scenario_id\nexample\n"),
    ("collab_shares.csv", ""),
    ("MANIFEST.json", "{invalid"),
    ("MANIFEST.json", "[]"),
])
def test_bad_files_return_data_unavailable(client, dataset, filename, contents):
    (dataset / filename).write_text(contents, encoding="utf-8")
    response = client.get("/api/meta")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "data_unavailable"


@pytest.mark.parametrize(("filename", "column", "value"), [
    ("collab_shares.csv", "year", "2025.5"),
    ("collab_shares.csv", "year", ""),
    ("collab_shares.csv", "share", "inf"),
    ("collab_shares.csv", "collab_count", "invalid"),
    ("detections.csv", "score", "invalid"),
    ("injections.csv", "year", "invalid"),
])
def test_invalid_numeric_data_returns_503(client, dataset, filename, column, value):
    path = dataset / filename
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns, rows = reader.fieldnames, list(reader)
    rows[0][column] = value
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    response = client.get("/api/meta")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "data_unavailable"


def test_empty_aggregate_and_optional_files(client, dataset):
    for path in dataset.glob("*.csv"):
        path.write_text(path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.get_json()["years"] == {"min": None, "max": None}
    assert meta.get_json()["fields"] == []
    assert all(value == 0 for value in meta.get_json()["counts"].values())
    for endpoint in ("institutions", "pairs", "detections", "scenarios"):
        response = client.get(f"/api/{endpoint}")
        assert response.status_code == 200
        assert response.get_json()["items"] == []


def test_missing_optional_files_and_null_metadata_are_json_safe(client, dataset):
    (dataset / "detections.csv").unlink()
    (dataset / "injections.csv").unlink()
    (dataset / "institutions_foreign.csv").write_text(
        "foreign_id,name,country_code\nEXAMPLE_FR_1,,\n", encoding="utf-8",
    )
    pairs = strict_json(client.get("/api/pairs"))
    pair = next(row for row in pairs["items"] if row["foreign_id"] == "EXAMPLE_FR_1")
    assert pair["foreign_name"] == "EXAMPLE_FR_1"
    assert pair["foreign_country"] is None
    assert client.get("/api/detections?source=file").get_json()["items"] == []
    (dataset / "institutions_foreign.csv").unlink()
    data_store._store = None
    assert client.get("/api/institutions?role=foreign").get_json()["total"] == 3


def test_missing_required_file_returns_503(client, dataset):
    (dataset / "collab_shares.csv").unlink()
    assert client.get("/api/meta").status_code == 503


def test_live_detections_call_detector_functions(client):
    """source=live 는 2번 담당자의 탐지 함수를 호출해 계산한다."""
    body = strict_json(client.get("/api/detections?source=live&detector=zscore&threshold=2.5"))
    assert body["source"] == "live"
    assert body["params"] == [{"detector": "zscore", "threshold": 2.5, "k": 3, "min_count": 3}]
    assert body["summary"]["evaluated_rows"] == 198
    assert body["total"] >= 1
    for row in body["items"]:
        assert row["detector"] == "zscore"
        assert row["detected"] is True
        assert row["score"] >= 2.5
        assert row["skip_reason"] is None


def test_live_detection_finds_the_injected_pair(client):
    """예시 데이터는 EXAMPLE_KR_1 x EXAMPLE_FR_1 (ai) 를 2021년부터 3배로 올려 두었다."""
    body = strict_json(client.get(
        "/api/detections?source=live&detector=growth&threshold=1.0&domestic_id=EXAMPLE_KR_1"))
    hit = [row for row in body["items"]
           if row["foreign_id"] == "EXAMPLE_FR_1" and row["field"] == "ai"]
    assert [row["year"] for row in hit] == [2021]


def test_timeline_baseline_comes_from_zscore(client):
    body = strict_json(client.get(
        "/api/timeline?source=live&domestic_id=EXAMPLE_KR_1&foreign_id=EXAMPLE_FR_1&field=ai"))
    years = [row["year"] for row in body["baseline"]]
    assert years == sorted(years) and len(years) == len(body["points"])
    early = body["baseline"][0]
    assert early["skip_reason"] == "insufficient_history" and early["baseline_value"] is None
    detected = [row for row in body["baseline"] if row["detected"]]
    assert detected and detected[0]["year"] == 2021


def test_live_source_is_rejected_without_detection_inputs(client, dataset):
    (dataset / "collab_counts.csv").unlink()
    response = client.get("/api/detections?source=live")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "detection_unavailable"


def test_unknown_source_and_detector_return_400(client):
    assert client.get("/api/detections?source=nope").status_code == 400
    assert client.get("/api/detections?detector=nope").status_code == 400


def test_institution_search_restricts_partners_before_limit(client, dataset):
    import pandas as pd
    shares = pd.read_csv(dataset / 'collab_shares.csv')
    # AI: KR1-FR1만 양수, KR2-FR2는 0으로 채운 시계열만 존재.
    shares.loc[shares.field == 'ai', 'collab_count'] = 0
    shares.loc[(shares.field == 'ai') & (shares.domestic_id == 'EXAMPLE_KR_1') & (shares.foreign_id == 'EXAMPLE_FR_1'), 'collab_count'] = 2
    shares.to_csv(dataset / 'collab_shares.csv', index=False)
    foreign = client.get('/api/institutions', query_string={
        'role': 'foreign', 'field': 'ai', 'domestic_id': 'EXAMPLE_KR_1', 'limit': 1,
    }).get_json()
    assert foreign['total'] == 1
    assert [r['id'] for r in foreign['items']] == ['EXAMPLE_FR_1']
    domestic = client.get('/api/institutions', query_string={
        'role': 'domestic', 'field': 'ai', 'foreign_id': 'EXAMPLE_FR_1',
    }).get_json()
    assert [r['id'] for r in domestic['items']] == ['EXAMPLE_KR_1']
    empty = client.get('/api/institutions', query_string={
        'role': 'foreign', 'field': 'ai', 'domestic_id': 'EXAMPLE_KR_2',
    }).get_json()
    assert empty['total'] == 0 and empty['items'] == []
    assert client.get('/api/institutions', query_string={
        'role': 'foreign', 'field': 'ai', 'domestic_id': 'EXAMPLE_KR_1', 'q': 'no-match',
    }).get_json()['total'] == 0
    assert client.get('/api/institutions?role=foreign').get_json()['total'] == 3
