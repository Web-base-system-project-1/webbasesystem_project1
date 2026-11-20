"""새 화면용 집계와 재계산 결과를 독립 CSV·저장 실험에 대조한다."""
from pathlib import Path

import pandas as pd
import pytest

from web.app import app
from web import data_store
from web.whatif import CACHE_LIMIT

V2 = Path(__file__).resolve().parents[1] / 'data/sample/actual/four_fields_2015_2025_v2.zip'


@pytest.fixture
def analysis_client(monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(V2))
    monkeypatch.setattr(data_store, '_store', None)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_matrix_filters_and_counts_match_original_rows(analysis_client):
    c = analysis_client
    store = data_store.get_store()
    response = c.get('/api/matrix?field=bio&year=2021&country=US&type=education&limit=10')
    assert response.status_code == 200
    body = response.get_json()
    source = store.shares[(store.shares.field == 'bio') & (store.shares.year == 2021)]
    expected = source.groupby(['domestic_id', 'foreign_id']).collab_count.sum()
    valid_domestic = set(store.domestic.loc[store.domestic.type == 'education', 'domestic_id'])
    assert len(body['domestic']) <= 10 and len(body['foreign']) <= 10
    assert body['count'] > 0
    for row in body['items']:
        assert row['domestic_id'] in valid_domestic
        assert store.foreign_country(row['foreign_id']) == 'US'
        assert row['collab_count'] == expected[(row['domestic_id'], row['foreign_id'])]
        assert row['collab_count'] > 0
    assert c.get('/api/matrix?field=absent').get_json()['items'] == []
    assert c.get('/api/matrix?field=bio&year=abc').status_code == 400
    assert c.get('/api/matrix').status_code == 400


def test_related_foreign_search_respects_year_and_domestic_type(analysis_client):
    c = analysis_client
    store = data_store.get_store()
    body = c.get('/api/institutions?role=foreign&field=bio&year=2021&type=facility&limit=1000').get_json()
    allowed = store.domestic.loc[store.domestic.type == 'facility', 'domestic_id']
    rows = store.shares[(store.shares.field == 'bio') & (store.shares.year == 2021)
                        & store.shares.domestic_id.isin(allowed) & (store.shares.collab_count > 0)]
    assert {row['id'] for row in body['items']} == set(rows.foreign_id)


@pytest.mark.parametrize('detector,correction,threshold', [
    ('growth', 'require_share_increase', 1),
    ('zscore', 'min_international_total_3', 2.5),
])
def test_correction_comparison_matches_saved_metrics(analysis_client, detector, correction, threshold):
    c = analysis_client
    store = data_store.get_store()
    pair = store.injections.iloc[0][['domestic_id', 'foreign_id', 'field']].to_dict()
    query = {**pair, 'scenario_id': 'step_x3', 'detector': detector,
             'threshold': threshold, 'correction_id': correction}
    r = c.get('/api/experiment-timeline', query_string=query)
    assert r.status_code == 200
    body = r.get_json()
    assert body['correction_id'] == correction
    assert body['metrics']['fp'] <= body['before_metrics']['fp']
    if detector == 'growth':
        assert (body['before_metrics']['tp'], body['metrics']['tp']) == (23, 20)
        assert (body['before_metrics']['fp'], body['metrics']['fp']) == (413, 359)
        assert body['metrics']['fn'] > body['before_metrics']['fn']
    before = {d['year'] for d in body['before_detections']}
    assert {d['year'] for d in body['detections']} <= before


def test_whatif_reproduces_saved_run_and_returns_changes(analysis_client):
    c = analysis_client
    params = dict(scenario_id='step_x3', detector='growth', k=3, threshold=1,
                  min_count=3, correction_id='require_share_increase')
    first = c.post('/api/whatif', json=params)
    assert first.status_code == 200
    body = first.get_json()
    assert body['cached'] is False
    assert body['reference_metrics']['tp'] == 23
    assert body['metrics']['tp'] == 20
    assert body['metrics']['fp'] == 359
    assert body['added_total'] == 0 and body['removed_total'] == 57
    assert len(body['removed']) == 57
    again = c.post('/api/whatif', json=params).get_json()
    assert again['cached'] is True
    store = data_store.get_store()
    saved = store.metrics[(store.metrics.scenario_id == 'step_x3') & (store.metrics.detector == 'growth')
                          & (store.metrics.threshold == 1) & (store.metrics.correction_id == params['correction_id'])].iloc[0]
    for column in ['tp', 'fp', 'fn', 'precision', 'recall', 'f1', 'delay_mean', 'decoy_fp']:
        assert body['metrics'][column] == pytest.approx(saved[column])
    changed = c.post('/api/whatif', json={**params, 'threshold': 2}).get_json()
    assert changed['params']['threshold'] == 2
    assert changed['metrics']['tp'] <= body['metrics']['tp']
    assert len(store._whatif_cache) <= CACHE_LIMIT


@pytest.mark.parametrize('params', [None, [], {'k': 1}, {'k': 3.5}, {'k': True}, {'threshold': -1},
                                   {'min_count': -1}, {'threshold': 10 ** 400}, {'detector': 'wrong'}, {'scenario_id': 'nope'},
                                   {'detector': 'growth', 'correction_id': 'min_international_total_3'}])
def test_whatif_rejects_invalid_settings(analysis_client, params):
    assert analysis_client.post('/api/whatif', json=params).status_code == 400
