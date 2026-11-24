"""Regressions for the comparison and unified What-if interfaces."""

from pathlib import Path

import pandas as pd
import pytest

from web.app import app
from web import data_store


@pytest.fixture(autouse=True)
def real_integration_data(monkeypatch):
    # Team members may have a different DATA_DIR in their local environment.
    monkeypatch.setenv("DATA_DIR", str(
        Path(__file__).resolve().parents[1] / "data/sample/actual/four_fields_2015_2025_v2.zip"
    ))
    monkeypatch.setattr(data_store, "_store", None)


@pytest.mark.parametrize("payload", [
    {"detector": []}, {"scenario_id": {}}, {"baseline": []},
    {"k": 3.5}, {"min_count": 1.5}, {"threshold": -1},
    {"threshold": 10 ** 400},
])
def test_unified_whatif_rejects_invalid_input(monkeypatch, payload):
    monkeypatch.setattr(data_store, "_store", None)
    with app.test_client() as client:
        response = client.post("/api/whatif", json=payload)
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "invalid_parameter"


def test_single_whatif_route_preserves_both_response_formats(monkeypatch):
    monkeypatch.setattr(data_store, "_store", None)
    rules = [r for r in app.url_map.iter_rules() if r.rule == "/api/whatif" and "POST" in r.methods]
    assert len(rules) == 1
    with app.test_client() as client:
        response = client.post("/api/whatif", json={
            "scenario_id": "step_x3", "detector": "growth", "threshold": 1,
            "correction_id": "require_share_increase",
        })
        assert response.status_code == 200
        body = response.get_json()
        assert body["baseline_metrics"] == body["reference_metrics"]
        assert body["counts"]["removed"] == body["removed_total"] == 57
        assert body["counts"]["added"] == body["added_total"] == 0
        assert body["metrics"]["tp"] == 20 and body["metrics"]["fp"] == 359
        assert {row["change"] for row in body["items"]} == {"removed"}
        assert client.post("/api/whatif", data="null", content_type="application/json").status_code == 400
        assert client.post("/api/whatif").status_code == 200


def test_comparison_summary_obeys_the_same_filters(monkeypatch):
    monkeypatch.setattr(data_store, "_store", None)
    with app.test_client() as client:
        body = client.get(
            "/api/comparison?scenario_id=step_x3&detector=growth&threshold=1&k=3&min_count=3"
        ).get_json()
        assert body["total"] == 1
        assert len(body["summary"]) == 1 and body["summary"][0]["runs"] == 1
        assert body["summary"][0]["fp_removed"] == 54
        assert body["summary"][0]["tp_lost"] == 3


def test_whatif_cache_isolated_when_data_store_is_reloaded(tmp_path, monkeypatch):
    import shutil
    folder = tmp_path / "example"
    shutil.copytree(Path(__file__).resolve().parents[1] / "data/sample/example", folder)
    monkeypatch.setenv("DATA_DIR", str(folder))
    monkeypatch.setattr(data_store, "_store", None)
    params = {"detector": "growth", "scenario_id": "original", "threshold": 0}
    with app.test_client() as client:
        before = client.post("/api/whatif", json=params).get_json()
        assert before["counts"]["current"] > 0
        for filename in ("collab_counts.csv", "collab_shares.csv"):
            frame = pd.read_csv(folder / filename)
            frame["collab_count"] = 0
            if "share" in frame:
                frame["share"] = 0
            frame.to_csv(folder / filename, index=False)
        monkeypatch.setattr(data_store, "_store", None)
        after = client.post("/api/whatif", json=params).get_json()
        assert after["data_version"] == before["data_version"]
        assert after["cached"]["current"] is False
        assert after["counts"]["current"] == 0
