# API 명세

로컬 기본 주소: `http://127.0.0.1:5001`

React는 상대 경로 `/api/...`를 사용합니다. 개발 중 Vite(5173)의 프록시가 Flask(5001)로 요청을 전달하므로 별도의 CORS 설정은 필요하지 않습니다. 기존 Flask 실행 확인 화면은 유지하며, 최종 배포 연결 방식은 별도 확정합니다.

## 공통 규칙

- 모든 응답은 UTF-8 JSON 이며 한글을 그대로 보냅니다(`ensure_ascii=False`).
- 조회 응답에는 **`data_version`** 이 함께 들어갑니다. 화면이 여러 API 를 조합할 때
  서로 다른 버전의 데이터가 섞였는지 이 값으로 확인합니다.
- 목록 응답은 `total`(조건에 맞는 전체 수)과 `count`(이번 응답에 담긴 수)를 함께 줍니다.
  `limit` 으로 자르며 기본값은 API 마다 다릅니다(최대 1000).
- 결측값은 JSON `null` 입니다. 분모가 0인 협력 비중도 `null` 입니다.
- `share` 는 0~1 비중입니다. 퍼센트 변환은 화면에서 합니다.

### 오류 응답

모든 오류는 같은 모양입니다.

```json
{ "error": { "code": "invalid_parameter", "message": "min_count 은 정수여야 합니다. 받은 값: abc" } }
```

| 상태 | `code` | 언제 |
|---|---|---|
| 400 | `invalid_parameter` | 숫자 자리에 글자, 허용하지 않는 값 |
| 400 | `missing_parameter` | 필수 쿼리 누락 |
| 404 | `pair_not_found` | 요청한 기관 쌍의 자료가 없음 |
| 404 | `comparison_unavailable` | 그 조건의 보정 전후 실행이 저장돼 있지 않음 |
| 409 | `comparison_unavailable` | 데이터에 보정을 적용한 실행이 하나도 없음 |
| 503 | `data_unavailable` | 데이터 폴더·파일이 없거나 열이 모자람 |

검색어 `q`는 정규식이 아닌 일반 문자열로 찾습니다. `threshold`는 유한한 숫자,
`min_count`는 0 이상의 정수만 허용합니다. CSV·메타데이터를 읽을 수 없거나
숫자 열의 형식이 잘못된 경우에도 `503 data_unavailable`을 반환합니다.

## 데이터 출처

서버는 첫 데이터 요청에서 CSV를 한 번 읽고 메모리에서 재사용합니다.
기본값은 [데이터 v2 ZIP](../data/sample/actual/four_fields_2015_2025_v2.zip)입니다.
다른 집계 폴더나 같은 구조의 ZIP을 사용하려면 `.env`의 `DATA_DIR`을 지정합니다.

```dotenv
DATA_DIR=data/processed/four_fields_2015_2025_v2
```

지금 사용하는 데이터는 `/api/meta`의 `data_version`과 `is_real_data`로 확인합니다.
화면 테스트에 쓰는 가상 데이터는 `DATA_DIR=data/sample/example`로 선택할 수 있습니다.

폴더를 바꾸면 **서버를 다시 켜야** 반영됩니다.

---

## GET `/api/health`

서버가 떠 있는지 확인합니다.

```json
{ "status": "ok" }
```

## GET `/api/meta`

지금 읽고 있는 데이터의 범위와 버전.

```json
{
  "data_version": "openalex-four-fields-2015-2025-1c38caf53194",
  "data_scope": "period_pilot",
  "is_real_data": true,
  "data_dir": "four_fields_2015_2025_v2",
  "fields": ["ai", "bio", "quantum", "semiconductor"],
  "years": { "min": 2015, "max": 2025 },
  "detectors": ["growth", "zscore"],
  "counts": {
    "rows": 80564, "domestic_institutions": 78, "foreign_institutions": 2660,
    "pairs": 7324, "detections": 37869, "injections": 420
  }
}
```

화면은 이 응답으로 연도 슬라이더 범위와 분야 필터 항목을 만들 수 있습니다.
집계 결과가 0행이면 `fields`는 빈 목록, `years.min`과 `years.max`는 `null`이며
건수는 0입니다. 정상적인 빈 결과를 서버 오류로 취급하지 않습니다.

## GET `/api/institutions`

기관 검색·필터.

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `role` | `domestic` | `domestic` 또는 `foreign` |
| `q` | — | 이름 또는 ID 의 일부 (대소문자 무시) |
| `type` | — | 기관 유형 (`education`, `facility`, `government`) |
| `limit` | 200 | 최대 1000 |
| `offset` | 0 | 검색 결과에서 건너뛸 행 수 |

`next_offset`을 다음 요청의 `offset`에 사용합니다. 마지막 페이지는 `next_offset: null`입니다.
화면은 페이지마다 `data_version`과 `total`을 확인합니다.

```
GET /api/institutions?role=domestic&q=기관
```

```json
{
  "data_version": "example-2026-11-08",
  "role": "domestic",
  "total": 3,
  "count": 3,
  "offset": 0,
  "next_offset": null,
  "items": [
    { "id": "EXAMPLE_KR_1", "name": "예시 국내기관 1", "type": "education", "ror": null, "country_code": "KR" }
  ]
}
```

해외 기관은 `type`이 `null`입니다. `role=foreign&type=education`처럼 조회하면 해당 유형의 **국내 기관과 협력한** 해외 기관을 반환합니다.

기관 선택 연동용 쿼리: `field`, `domestic_id`, `foreign_id`, `year`를 지원합니다.
예: `/api/institutions?role=foreign&field=ai&domestic_id=...`는 해당 국내 기관과 AI 공동논문이 있는 해외 기관만 반환합니다.
반대로 `role=domestic&field=ai&foreign_id=...`로 국내 협력 기관을 조회합니다.
해당 범위에 공동논문이 1편 이상인 관계만 포함하고 0으로 채운 시계열만 있는 관계는 제외합니다.
검색어·기관 유형 필터와 함께 적용되며, 관련 기관 필터를 적용한 뒤 total과 limit을 계산합니다.


## GET `/api/pairs`

국내–해외 기관 쌍 목록. 협력 건수 합이 많은 순.

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `field` | — | 분야 코드 |
| `domestic_id` | — | 국내 기관 |
| `min_count` | — | 전체 기간 합이 이 값 이상인 쌍만 |
| `limit` | 100 | 최대 1000 |

```json
{
  "data_version": "example-2026-11-08",
  "total": 9, "count": 3,
  "items": [
    {
      "domestic_id": "EXAMPLE_KR_1", "domestic_name": "예시 국내기관 1",
      "foreign_id": "EXAMPLE_FR_1", "foreign_name": "예시 해외기관 1",
      "foreign_country": "US", "field": "ai",
      "total_count": 86, "max_share": 0.326087,
      "year_min": 2015, "year_max": 2025
    }
  ]
}
```

## GET `/api/timeline`

한 기관 쌍의 연도별 건수·비중과 탐지·주입 시점. **기관 타임라인 뷰용.**

| 쿼리 | 필수 | 설명 |
|---|---|---|
| `domestic_id` | ✅ | |
| `foreign_id` | ✅ | |
| `field` | ✅ | |
| `detector` | | `zscore`, `growth`. 주면 그 탐지기만 |
| `threshold` | | 지정한 탐지기의 임계값. live에서 지정할 때 `detector` 필수 |
| `k` | | live 기준선 길이(기본 3, 2~10) 또는 file 실행 설정 필터 |
| `min_count` | | live 증가율의 최소 건수(기본 3) 또는 file 실행 설정 필터 |
| `source` | | `auto`(기본) / `live` / `file`. 아래 설명 참고 |
| `scenario_id` | | 저장된 탐지와 주입 시점에 적용할 시나리오 |
| `correction_id` | | 저장된 탐지에 적용할 보정 버전 |

```json
{
  "data_version": "example-2026-11-08",
  "source": "live",
  "pair": {
    "domestic_id": "EXAMPLE_KR_1", "domestic_name": "예시 국내기관 1",
    "foreign_id": "EXAMPLE_FR_1", "foreign_name": "예시 해외기관 1",
    "foreign_country": "US", "field": "ai"
  },
  "points": [
    { "year": 2015, "collab_count": 4, "international_total": 43, "share": 0.093023 }
  ],
  "detections": [
    {
      "year": 2021, "detector": "zscore", "threshold": 2.5, "score": 10.6435,
      "baseline_value": 0.093305, "baseline_std": 0.021875,
      "current_value": 0.326087, "collab_count": 15
    }
  ],
  "baseline": [
    { "year": 2015, "baseline_value": null, "baseline_std": null, "baseline_n": null,
      "current_value": 0.125, "score": null, "detected": false,
      "skip_reason": "insufficient_history" },
    { "year": 2021, "baseline_value": 0.093305, "baseline_std": 0.021875, "baseline_n": 3,
      "current_value": 0.326087, "score": 10.6435, "detected": true, "skip_reason": null }
  ],
  "injections": []
}
```

`baseline` 은 **수집을 확인한 연도마다 한 행**이며 z-score 탐지기의 출력에서 나옵니다.
`baseline_value` ± `baseline_std` 로 **직전 k년 기준선 띠**를 그리고, 그 위에
`points` 의 실제 값을 얹으면 됩니다. 기준선을 낼 수 없는 연도는 값이 `null` 이고
`skip_reason` 에 이유가 들어갑니다(`insufficient_history`, `zero_std`, `missing_share`).
`source=file`에서는 `baseline: []`이며, 탐지와 주입 시점에 같은 `scenario_id`가 적용됩니다.
`points`는 원본 집계 시계열입니다. 실시간 원본 탐지의 `injections`는 빈 배열입니다.

자료가 없는 기관 쌍은 **404 `pair_not_found`** 입니다.

## GET `/api/detections`

탐지 목록과 근거. 점수가 높은 순. **탐지 결과·근거 뷰용.**

### 어디서 계산하는가

| `source` | 동작 |
|---|---|
| `auto` (기본) | 시나리오·보정을 지정하거나 탐지 입력이 없으면 `file`. 그 외에는 `live` |
| `live` | `detectors.detect_zscore` / `detect_growth` 를 **직접 호출**해 계산 |
| `file` | 데이터 폴더의 `detections.csv` 를 읽음 (실험 실행기가 만든 결과) |

`live` 는 데이터 폴더에 **`collab_counts.csv` 와 `kr_totals.csv`** 가 있어야 합니다.
서버가 `detectors.build_panel` 로 기관 쌍 × 연도 패널을 만든 뒤 탐지 함수에 넘깁니다.
수집 기록이 있으면 분야·연도별 완료 기록을, 기존 폴더에서는 집계표에 있는 분야·연도를 사용합니다.
수집을 확인한 연도에만 0건을 채우며, 수집 공백은 기준선의 연속성을 끊습니다.
**API 는 계산식을 다시 구현하지 않습니다.** 입력이 없는데 `source=live` 를 주면
**409 `detection_unavailable`** 입니다.

같은 `(데이터 버전, 탐지기, k, 임계값, 최소 건수)` 로 다시 물으면 보관한 결과를
돌려줍니다. 최근 설정 네 개의 결과를 보관합니다.

### 쿼리

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `source` | `auto` | 위 표 참고 |
| `detector` | 둘 다 | `zscore`, `growth` |
| `threshold` | 탐지기별 기본값 | z-score `2.5`, 증가율 `1.0`. live에서 지정할 때 `detector` 필수 |
| `k` | live에서 3 | 기준선 길이(2~10) 또는 저장된 실행 설정 필터 |
| `min_count` | live에서 3 | 증가율의 최소 건수 또는 저장된 실행 설정 필터 |
| `field` | — | 분야 코드 |
| `domestic_id`, `foreign_id` | — | 기관 |
| `year` | — | 연도 |
| `scenario_id` | — | 주입 시나리오 (`file` 전용) |
| `correction_id` | — | 보정 버전 (`file` 전용) |
| `limit` | 100 | 최대 1000 |

### 응답

```json
{
  "data_version": "example-2026-11-08",
  "source": "live",
  "params": [ { "detector": "zscore", "threshold": 2.5, "k": 3, "min_count": 3 } ],
  "summary": {
    "evaluated_rows": 198,
    "skipped": { "insufficient_history": 54, "below_min_count": 20 }
  },
  "total": 4, "count": 4,
  "items": [
    {
      "domestic_id": "EXAMPLE_KR_1", "domestic_name": "예시 국내기관 1",
      "foreign_id": "EXAMPLE_FR_1", "foreign_name": "예시 해외기관 1",
      "foreign_country": "US", "field": "ai", "year": 2021,
      "detector": "zscore", "k": 3, "threshold": 2.5, "min_count": 3,
      "collab_count": 15, "international_total": 46,
      "current_value": 0.326087, "baseline_value": 0.093305,
      "baseline_std": 0.021875, "baseline_n": 3, "change": 0.232782,
      "score": 10.6435, "detected": true, "skip_reason": null
    }
  ]
}
```

`summary.skipped` 는 **탐지하지 못한 이유별 행 수**입니다. 결과가 0건일 때
"데이터가 깨끗해서"인지 "조건을 못 채워서"인지 구분할 수 있습니다.

### 항목의 열

`detectors` 의 출력 열을 그대로 쓰고 기관 이름만 더합니다.

| 열 | 의미 |
|---|---|
| `score` | z-score 또는 전년 대비 증가율 |
| `detected` | 임계값을 넘었는지. `items` 는 `true` 인 행만 |
| `baseline_value` | z-score 는 직전 k년 비중 평균, 증가율은 전년 건수 |
| `baseline_std`, `baseline_n` | 직전 k년 표준편차와 사용한 연도 수 (z-score 전용) |
| `current_value` | 올해 값. z-score 는 비중, 증가율은 건수 |
| `change` | 올해 값 − 기준선 (증가율은 증가율 자체) |
| `collab_count`, `international_total` | 올해 공동논문 수와 분모 |
| `k`, `threshold`, `min_count` | 이 결과를 낸 설정 |
| `skip_reason` | 계산을 건너뛴 이유. 탐지된 행은 `null` |
| `scenario_id`, `run_id`, `correction_id` | `file` 모드에만 있음 |

`skip_reason` 값: `insufficient_history`(과거 k년 부족), `zero_std`(기준선 표준편차 0),
`missing_share`(비중 결측), `below_min_count`(최소 건수 미만), `prev_zero`(전년 0건).

## GET `/api/overview`

국가·분야·연도별 협력 집계와 탐지 건수를 반환합니다.

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `field`, `year`, `country` | — | 분야 코드, 연도, 해외 국가 코드 |
| `limit` | 500 | 최대 1000 |
| `source`, `detector`, `threshold`, `k`, `min_count` | — | 탐지 건수를 셀 조건. `/api/detections`와 동일 |

기본 v2의 `country_overview.csv`는 같은 논문·국가와 여러 국내 기관의 중복을 제거합니다. 분모는 같은 분야·연도의 고유 국제 공동논문 총수입니다. 각 국가의 `share`는 0~1이며, 여러 국가가 한 논문에 참여하면 국가별 비중의 합은 1을 넘을 수 있습니다. `composition`은 각 나라 건수를 모든 나라 건수의 합으로 나눠 합계 1로 정규화한 값입니다.

국가 집계 파일이 있는 응답의 `aggregation_basis`는 `unique_country_papers`입니다. 구형 데이터의 기관 쌍 합산 방식은 `institution_pairs`로 표시하며, 이 경우 `share`가 1을 넘을 수 있습니다. 국가 필터는 비중 계산 후 적용하므로 분모가 바뀌지 않습니다.

아래는 `/api/overview?field=bio&year=2021&country=US&detector=zscore&threshold=2.5`의 집계 부분입니다.

```json
{
  "data_version": "openalex-four-fields-2015-2025-1c38caf53194",
  "aggregation_basis": "unique_country_papers",
  "source": "live",
  "total": 1,
  "count": 1,
  "items": [{
    "country_code": "US", "field": "bio", "year": 2021,
    "collab_count": 94, "international_total": 110,
    "share": 0.8545454545454545, "composition": 0.20434782608695654,
    "pairs": 306, "domestic_institutions": 21,
    "foreign_institutions": 132, "detections": 16
  }]
}
```

공동논문 0건인 국가·연도는 목록에서 생략합니다. 탐지 건수는 쿼리 조건에 맞는 기관 쌍의 탐지 행 수이며, 국가 집계는 원본 데이터에 대한 값입니다.

## GET `/api/metrics`

주입 실험의 정량 평가표. `experiments.evaluate` 가 만든 `metrics.csv` 를 돌려줍니다.
그 파일이 없는 데이터에서는 **409 `metrics_unavailable`** 입니다. v2는 보정 전후 84개 실행을 포함하며 `correction_id=none`으로 보정 전 실행을 선택할 수 있습니다.

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `scenario_id` | — | `original`, `step_x2/x3/x5`, `gradual_x3`, `spike_x5`, `decoy_x3` |
| `detector`, `threshold`, `k`, `min_count`, `correction_id` | — | 실험 조건 |
| `sort` | `f1` | 내림차순 정렬에 쓸 열 이름. 없는 열이면 400 |
| `limit` | 100 | 최대 1000 |

```json
{
  "data_version": "openalex-four-fields-2015-2025-1c38caf53194",
  "sort": "f1",
  "scenarios": ["decoy_x3", "gradual_x3", "original", "spike_x5", "step_x2", "step_x3", "step_x5"],
  "detectors": ["growth", "zscore"],
  "total": 7, "count": 7,
  "items": [
    { "scenario_id": "spike_x5", "detector": "zscore", "threshold": 2.5,
      "k": 3, "min_count": 3, "correction_id": "none",
      "tp": 3, "fp": 579, "fn": 17,
      "precision": 0.0052, "recall": 0.15, "f1": 0.0100,
      "recall_effective": 0.1579, "delay_mean": 0.0,
      "missed_pairs": 17, "decoy_fp": 0 }
  ]
}
```

| 열 | 의미 |
|---|---|
| `tp` / `fp` / `fn` | 정탐 · 오탐 · 미탐 행 수 |
| `precision` / `recall` / `f1` | 정답이 없는 `original` 과 `decoy_x3` 에서는 `null` 또는 0 |
| `recall_effective` | 배수를 적용해도 값이 바뀌지 않은 행(`effective=False`)을 뺀 recall |
| `delay_mean` | 주입 시작 연도와 첫 탐지 연도의 차이, 평균 |
| `missed_pairs` | 한 해도 탐지되지 않은 기관 쌍 수 |
| **`decoy_fp`** | **미끼 시나리오의 오탐 수. 목표는 0** |

## GET `/api/scenarios`

주입 시나리오 목록. 정답 행이 없는 `original` 과 `decoy_x3` 도 **빠뜨리지 않습니다** —
미끼는 「탐지되면 안 되는」 실험이라 화면에 반드시 보여야 합니다.

```json
{
  "data_version": "openalex-four-fields-2015-2025-1c38caf53194",
  "total": 7, "count": 7,
  "items": [
    { "scenario_id": "decoy_x3", "injected_rows": 0, "effective_rows": 0, "pairs": 0,
      "injection_type": null, "multiplier": null, "year_min": null, "year_max": null },
    { "scenario_id": "step_x5", "injected_rows": 100, "effective_rows": 80, "pairs": 20,
      "injection_type": "step", "multiplier": 5.0, "year_min": 2021, "year_max": 2025 }
  ]
}
```

`injected_rows` 는 정답 행 수(20 쌍 × 5 년), `effective_rows` 는 그중 **배수를 적용한
뒤 실제로 값이 바뀐** 행 수입니다. 원본이 0 편인 해는 배수를 곱해도 0 편이라
`effective=False` 이고, 그 차이가 `recall` 과 `recall_effective` 의 차이로 이어집니다.

---

## GET `/api/comparison`

보정 전후를 **같은 실험 조건끼리 짝지어** 돌려줍니다. **보정 비교 뷰용.**

숫자는 `experiments.evaluate` 가 만든 `metrics.csv` 를 그대로 씁니다. API 는 지표를
다시 계산하지 않고 `correction_id=none` 행과 보정 행을 맞대기만 합니다. 짝은
시나리오·탐지기·임계값·k·최소 건수가 모두 같을 때만 생기므로, z-score 보정과
증가율 보정이 섞이지 않습니다.

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `correction_id` | — | 보정 버전. 생략하면 전부 |
| `scenario_id` | — | 주입 시나리오 |
| `detector` | — | `zscore`, `growth` |
| `threshold` | — | 임계값 |
| `k` | — | 기준 기간. 정수 2~10 |
| `min_count` | — | 최소 건수. 정수 0 이상 |
| `limit` | 100 | 최대 1000 |

```json
{
  "data_version": "openalex-four-fields-2015-2025-1c38caf53194",
  "corrections": ["min_international_total_3", "require_share_increase"],
  "summary": [
    { "correction_id": "min_international_total_3", "runs": 21,
      "tp_before": 78, "tp_after": 78, "tp_lost": 0,
      "fp_before": 10399, "fp_after": 9595, "fp_removed": 804,
      "decoy_fp_before": 7, "decoy_fp_after": 7, "decoy_fp_removed": 0 }
  ],
  "total": 42, "count": 42,
  "items": [
    {
      "scenario_id": "step_x5", "detector": "zscore", "threshold": 2.5,
      "k": 3, "min_count": 3, "correction_id": "min_international_total_3",
      "run_id": { "before": "zscore|th=2.5|k=3|min=3|corr=none",
                  "after": "zscore|th=2.5|k=3|min=3|corr=min_international_total_3" },
      "before": { "tp": 6, "fp": 462, "precision": 0.0128, "recall": 0.06, "decoy_fp": 0 },
      "after":  { "tp": 6, "fp": 423, "precision": 0.0140, "recall": 0.06, "decoy_fp": 0 },
      "delta":  { "tp": 0, "fp": -39, "precision": 0.0012, "recall": 0.0, "decoy_fp": 0 }
    }
  ]
}
```

위 `before`·`after`·`delta` 는 지면상 열을 줄인 것이고, 실제 응답에는
`metrics.csv` 의 평가 열(`tp`, `fp`, `fn`, `precision`, `recall`, `f1`,
`recall_effective`, `delay_mean`, `missed_pairs`, `decoy_fp`)이 모두 들어갑니다.

`summary` 는 위 필터를 통과한 실행 전체의 보정 효과를 한 줄로 봅니다. `limit`은 상세 목록만 제한합니다. **`fp_removed` 는 지운 오탐,
`tp_lost` 는 같이 지워진 정탐**입니다. 두 숫자를 함께 봐야 보정이 남는 장사인지 알 수 있습니다.

`delta` 는 `after - before` 입니다. 보정은 탐지를 지우기만 하므로 `tp` 와 `fp` 의
`delta` 는 0 이하입니다.

저장된 보정 실행이 하나도 없으면 **409 `comparison_unavailable`**,
`metrics.csv` 자체가 없으면 **409 `metrics_unavailable`** 입니다.

## GET `/api/comparison/changes`

실행 하나에서 **보정으로 판정이 바뀐 탐지 행**을 돌려줍니다. 「바로잡힌 오류와
새로 생긴 오류, 판정 변화의 근거」에 해당합니다.

| 쿼리 | 필수 | 설명 |
|---|---|---|
| `correction_id` | ✅ | 보정 버전 |
| `scenario_id` | ✅ | 주입 시나리오 |
| `detector` | ✅ | `zscore`, `growth` |
| `threshold` | ✅ | 임계값 |
| `k` | | 기준 기간. 정수 2~10 |
| `min_count` | | 최소 건수. 정수 0 이상 |
| `change` | | 아래 네 값 중 하나로 거르기 |
| `limit` | 100 | 최대 1000 |

| `change` | 뜻 |
|---|---|
| `resolved_false_positive` | 보정이 지웠고 주입 정답이 아니었음 — **바로잡힌 오류** |
| `lost_true_positive` | 보정이 지웠는데 주입 정답이었음 — **새로 생긴 오류** |
| `introduced_false_positive` | 보정 뒤 새로 생긴 탐지, 정답 아님 |
| `introduced_true_positive` | 보정 뒤 새로 생긴 탐지, 정답 |

```json
{
  "run": { "scenario_id": "step_x5", "detector": "zscore", "threshold": 2.5,
           "k": 3, "min_count": 3, "correction_id": "min_international_total_3" },
  "before_detections": 468, "after_detections": 429, "unchanged": 429,
  "counts": { "resolved_false_positive": 39, "lost_true_positive": 0,
              "introduced_false_positive": 0, "introduced_true_positive": 0 },
  "total": 39, "count": 39,
  "items": [
    { "domestic_id": "...", "domestic_name": "Jeonbuk National University",
      "foreign_id": "...", "foreign_name": "Pennsylvania State University",
      "foreign_country": "US", "field": "semiconductor", "year": 2019,
      "collab_count": 1, "international_total": 1, "score": 21.94,
      "change": "resolved_false_positive", "was_injected": false }
  ]
}
```

각 행에는 `/api/detections` 와 같은 근거 열(`score`, `baseline_value`,
`international_total` 등)이 그대로 실려 있어, 화면에서 **왜 판정이 바뀌었는지**를
숫자로 보여줄 수 있습니다. 위 예시 행은 국제 공동논문 총수가 1 편인 쌍이라
비중이 0%↔100% 로 튀어 z-score 가 21.94 까지 올라갔던 경우입니다.

여러 실행이 일치하면 k와 min_count로 하나를 지정해야 하며, 그렇지 않으면 **400 `invalid_parameter`** 입니다.

그 조건의 전후 실행이 저장돼 있지 않으면 **404 `comparison_unavailable`** 입니다.
예를 들어 z-score 보정을 증가율 실행에 물어보면 짝이 없으므로 404 입니다.

---
## POST `/api/whatif`

임계값·k·최소 건수를 바꿔 **다시 계산**하고, 기준 설정과 견줍니다. **What-if 뷰용.**

저장된 결과를 읽는 것이 아니라 2번 담당자의 탐지·보정·평가 함수를 그 자리에서
호출합니다. 수식을 API 에서 다시 구현하지 않습니다.

요청 본문은 JSON 객체입니다. 빈 본문은 기본 설정을 사용하며 명시적인 null·배열·잘못된 JSON은 400입니다. 지정하지 않은 값은 명세의 기본값(z-score 2.5,
증가율 1.0, k 3, 최소 건수 3, 보정 없음)을 씁니다.

| 필드 | 기본값 | 설명 |
|---|---|---|
| `detector` | `zscore` | `zscore`, `growth` |
| `threshold` | 탐지기 기본값 | 유한한 숫자 0~1000 |
| `k` | 3 | 정수 2~10. Z-score에 사용 |
| `min_count` | 3 | 정수 0 이상. 증가율에 사용 |
| `scenario_id` | `original` | 주입 시나리오 |
| `correction_id` | `none` | 해당 탐지기의 보정 또는 `none` |
| `baseline` | 기본 설정 | 견줄 설정. `threshold`·`k`·`min_count`·`correction_id` 만 바꿉니다 |
| `limit` | 100 | 최대 1000 |

```json
{ "detector": "zscore", "threshold": 3.0, "scenario_id": "step_x5",
  "baseline": { "threshold": 2.5 } }
```

```json
{
  "data_version": "openalex-four-fields-2015-2025-1c38caf53194",
  "scenario_id": "step_x5",
  "params":   { "detector": "zscore", "threshold": 3.0, "k": 3, "min_count": 3, "correction_id": "none" },
  "baseline": { "detector": "zscore", "threshold": 2.5, "k": 3, "min_count": 3, "correction_id": "none" },
  "unchanged_settings": false,
  "metrics":          { "tp": 4, "fp": 305, "fn": 96, "recall": 0.04, "f1": 0.0196 },
  "baseline_metrics": { "tp": 6, "fp": 462, "fn": 94, "recall": 0.06, "f1": 0.0211 },
  "delta":            { "tp": -2, "fp": -157, "recall": -0.02, "f1": -0.0016 },
  "counts": { "current": 309, "baseline": 468, "added": 0, "removed": 159, "unchanged": 309 },
  "cached": { "current": false, "baseline": false },
  "summary": { "evaluated_rows": 63857, "skipped": { "insufficient_history": 41724, "zero_std": 20789 } },
  "total": 159, "count": 100,
  "items": [
    { "domestic_id": "...", "domestic_name": "...", "field": "bio", "year": 2023,
      "score": 2.97, "change": "removed", "was_injected": false }
  ]
}
```

`items` 의 `change` 는 기준 설정 대비 **`added`(새로 생긴 탐지)** 와
**`removed`(사라진 탐지)** 입니다. `was_injected` 로 그것이 주입 정답이었는지
구분합니다. 화면의 「새로 생긴/사라진 탐지 표시」가 이 목록입니다. 평가 범위는 같은 시나리오 전체이며 화면의 기관·분야·연도 필터와 별도입니다.

분석 화면 호환용 `reference_params`·`reference_metrics`는 `baseline`·`baseline_metrics`의 별칭입니다. `added_total`·`removed_total`은 전체 증감 건수이고 `added`·`removed`는 각각 최대 200행입니다. 상세 목록 `items`는 `limit`을 따릅니다. 정답 없는 original의 Recall은 null이며, 실험의 FP는 실제 이상 여부를 확정하지 않습니다.

**캐시**: 같은 설정으로 다시 물으면 계산하지 않고 보관한 결과를 돌려주고
`cached.current` 또는 `cached.baseline` 이 `true` 가 됩니다. 캐시 키에 **데이터 버전·시나리오·탐지기·임계값·k·
최소 건수·보정 버전**이 모두 들어가므로 오래된 결과가 섞이지 않습니다.
DataStore 인스턴스마다 최근 8벌을 보관하며, 잠금으로 동시 계산을 보호합니다. 데이터 재로드 시 캐시도 새로 만듭니다.

`metrics` 는 주입 정답이 있는 데이터에서만 나옵니다. 실험 기록이 없는 폴더에서는
`metrics` 와 `delta` 가 `null` 이고 탐지 목록과 증감만 제공합니다. 그런 폴더에
주입 시나리오를 요청하면 **409 `whatif_unavailable`**, `collab_counts.csv` 와
`kr_totals.csv` 가 없으면 **409 `detection_unavailable`** 입니다.

v2 데이터에서는 이 재계산 결과가 저장된 `metrics.csv` 의 `tp`·`fp`·`fn`·`decoy_fp`
와 정확히 일치합니다(`tests/test_api.py`에서 7개 시나리오의 보정 전후 84개 실행으로 확인).

## 현재 한계

- 2025년 샘플의 실시간 탐지는 과거 기준선 부족으로 0건입니다.
  여러 연도의 실시간 탐지는 [데이터 v2](data-review-2026-11-19.md)에서 확인할 수 있습니다.
- 데이터 v2의 저장된 시나리오는 `source=file`과 `scenario_id`로 조회합니다.
- 네 분야 샘플과 기간 집계에는 `institutions_foreign.csv`가 있습니다.
  구형 데이터 폴더에서 이 파일이 없으면 API는 해외 기관 이름에 ID를, 국가에 `null`을 반환합니다.

## GET `/api/experiments` (프론트 통합 추가)

현재 데이터 버전과 일치하는 저장 실험의 seed와 metrics.csv 실행 행을 items로 반환합니다.
실험 기록이 없거나 버전이 다르면 409 experiment_unavailable 입니다.
평가 수치는 전체 실행 기준이며 기관 쌍별 수치가 아닙니다.

## GET `/api/experiment-timeline` (프론트 통합 추가)

필수 쿼리: domestic_id, foreign_id, field, scenario_id, detector, threshold.
correction_id는 기본 none이며 require_share_increase(증가율), min_international_total_3(Z-score)를 지원합니다. 저장 실행 하나를 선택합니다. 응답은 data_version, seed, original(원본 시계열),
points(주입 시계열), detections(해당 run_id의 탐지 근거), injections(기관 쌍별 정답),
metrics(전체 실행 지표), target(대표 주입 기관 쌍)입니다.

주입 계산을 API에서 중복 구현하지 않고 experiments.inject.build_scenarios를 재사용합니다.
experiment_manifest의 데이터 버전·시드·주입/탐지/평가 파일 해시를 확인하고, 재구성한 주입 편수를 저장된 정답과 대조합니다.
불일치 시 503 data_unavailable, 존재하지 않는 실행이나 기관 쌍은 404 입니다.
증가율의 k 열은 결측일 수 있으므로 탐지 근거는 metrics의 run_id로 대응합니다.
기존 /api/timeline은 계속 원본 시계열을 반환하며, 주입 비교에는 이 전용 API를 사용해야 합니다.
현재 v2 ZIP의 보정 전후 84회 결과를 제공합니다. `before_metrics`, `before_detections`는 같은 시나리오·탐지기·임계값의 보정 전 실행입니다. `metrics`, `detections`는 요청한 보정 실행이며, 기관 쌍별 시계열과 전체 평가를 구분합니다.

## GET `/api/matrix`

필수 `field`; 선택 `year`, `domestic_id`, `foreign_id`, `type`(국내 기관), `country`(해외 기관), `limit`(기본 15, 최대 30). 탐지는 기존 `source=live|file`, 탐지기·임계값 조회 규칙을 따릅니다. React는 source=live를 사용합니다.

현재 조건에서 양수 공동논문 수를 합산하고 국내·해외 각각 합계 상위 limit곳의 교차 행렬을 반환합니다. `domestic`, `foreign`는 `{id,name}` 축 목록, `items`는 `{domestic_id,foreign_id,collab_count,detections}`입니다. `total_pairs`는 축 제한 전 양수 관계 수이며 `count`는 표시 관계 수입니다. 기관 쌍 건수 합은 고유 논문 수가 아닙니다.
