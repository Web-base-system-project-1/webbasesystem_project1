"""What-if에서 기존 탐지·평가 함수를 재사용하고 실행별 결과를 보관한다."""
from collections import OrderedDict
from threading import Lock

import pandas as pd

from detectors import DETECTORS
from experiments.correct import require_min_international_total, require_share_increase
from experiments.evaluate import evaluate
from web.data_store import experiment_scenarios

CACHE_LIMIT = 12


def calculate(store, scenario_id, detector, k, threshold, min_count, correction_id):
    key = (store.data_version, scenario_id, detector, k, threshold, min_count, correction_id)
    # store는 데이터 버전별로 생성된다. 잠금은 요청 중복 계산을 방지한다.
    if not hasattr(store, '_whatif_cache'):
        with store._scenario_lock:
            if not hasattr(store, '_whatif_cache'):
                store._whatif_lock = Lock()
                store._whatif_cache = OrderedDict()
    scenario = experiment_scenarios(store)[scenario_id]
    with store._whatif_lock:
        if key in store._whatif_cache:
            store._whatif_cache.move_to_end(key)
            return store._whatif_cache[key], True
        params = dict(k=k, threshold=threshold, min_count=min_count)
        result = DETECTORS[detector](scenario.panel, params)
        if correction_id == 'min_international_total_3':
            result = require_min_international_total(result)
        elif correction_id == 'require_share_increase':
            result = require_share_increase(result, scenario.panel)
        run_id = f'{detector}|th={threshold}|k={k}|min={min_count}|corr={correction_id}'
        found = result[result.detected].assign(scenario_id=scenario_id, run_id=run_id, correction_id=correction_id)
        run = dict(scenario_id=scenario_id, run_id=run_id, detector=detector,
                   correction_id=correction_id, **params)
        decoys = scenario.decoy_targets.assign(scenario_id=scenario_id)
        metric = evaluate(scenario.injections, found, pd.DataFrame([run]), decoys).iloc[0]
        output = dict(hits=found, metrics=metric, params=run)
        store._whatif_cache[key] = output
        if len(store._whatif_cache) > CACHE_LIMIT:
            store._whatif_cache.popitem(last=False)
        return output, False
