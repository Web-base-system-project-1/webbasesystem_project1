"""주입된 패널과 저장된 정답·평가의 일치 여부를 검증한다."""
from pathlib import Path

import pytest

from web.app import app
from web import data_store

V1 = Path(__file__).resolve().parents[1] / 'data/sample/actual/four_fields_2015_2025_v1.zip'


@pytest.fixture
def experiment_client(monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(V1))
    monkeypatch.setattr(data_store, '_store', None)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_saved_metrics_and_rebuilt_injections_match(experiment_client):
    client = experiment_client
    runs = client.get('/api/experiments').get_json()['items']
    assert len(runs) == 42
    store = data_store.get_store()
    pair = store.injections.iloc[0][['domestic_id', 'foreign_id', 'field']].to_dict()
    for scenario in ['step_x2', 'step_x3', 'step_x5', 'gradual_x3', 'spike_x5', 'decoy_x3', 'original']:
        query = {**pair, 'scenario_id': scenario, 'detector': 'zscore', 'threshold': 2.5}
        response = client.get('/api/experiment-timeline', query_string=query)
        assert response.status_code == 200
        body = response.get_json()
        assert body['seed'] == 42
        assert len(body['points']) == len(body['original']) == 11
        metric = next(row for row in runs if row['scenario_id'] == scenario and row['detector'] == 'zscore' and row['threshold'] == 2.5)
        assert body['metrics'] == metric
        expected = store.detections
        for column, value in {**pair, 'run_id': metric['run_id'], 'scenario_id': scenario}.items():
            expected = expected[expected[column] == value]
        assert len(body['detections']) == len(expected)
        for truth in body['injections']:
            point = next(row for row in body['points'] if row['year'] == truth['year'])
            original = next(row for row in body['original'] if row['year'] == truth['year'])
            assert point['collab_count'] == truth['injected_count']
            assert original['collab_count'] == truth['original_count']
        if scenario in ('decoy_x3', 'original'):
            for original, point in zip(body['original'], body['points']):
                assert point['share'] == pytest.approx(original['share']) if original['share'] is not None else point['share'] is None
        assert all(row['scenario_id'] == scenario and row['threshold'] == 2.5 for row in body['detections'])


def test_experiment_errors_and_version_guard(experiment_client, monkeypatch):
    client = experiment_client
    query = dict(domestic_id='absent', foreign_id='absent', field='ai', scenario_id='step_x2', detector='growth', threshold=1)
    assert client.get('/api/experiment-timeline', query_string=query).status_code == 404
    assert client.get('/api/experiment-timeline').status_code == 400
    store = data_store.get_store()
    monkeypatch.setattr(store, 'experiment_manifest', {'data_version': 'wrong', 'seed': 42})
    assert client.get('/api/experiments').status_code == 409
    assert client.get('/api/experiment-timeline', query_string=query).status_code == 503


def test_growth_evidence_uses_run_id_not_nullable_k(experiment_client):
    store = data_store.get_store()
    truth = store.injections.iloc[0]
    query = {key: truth[key] for key in ['domestic_id', 'foreign_id', 'field']}
    response = experiment_client.get('/api/experiment-timeline', query_string={
        **query, 'scenario_id': 'step_x5', 'detector': 'growth', 'threshold': 1,
    })
    body = response.get_json()
    hit = next(row for row in body['detections'] if row['year'] == 2021)
    assert hit['collab_count'] == 75
    assert hit['baseline_value'] == 11
    assert hit['score'] == pytest.approx((75 - 11) / 11)
