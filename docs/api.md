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
| 503 | `data_unavailable` | 데이터 폴더·파일이 없거나 열이 모자람 |

검색어 `q`는 정규식이 아닌 일반 문자열로 찾습니다. `threshold`는 유한한 숫자,
`min_count`는 0 이상의 정수만 허용합니다. CSV·메타데이터를 읽을 수 없거나
숫자 열의 형식이 잘못된 경우에도 `503 data_unavailable`을 반환합니다.

## 데이터 출처

서버는 첫 데이터 요청에서 CSV를 한 번 읽고 메모리에서 재사용합니다.
기본값은 [데이터 v1 ZIP](../data/sample/actual/four_fields_2015_2025_v1.zip)입니다.
다른 집계 폴더나 같은 구조의 ZIP을 사용하려면 `.env`의 `DATA_DIR`을 지정합니다.

```dotenv
DATA_DIR=data/processed/four_fields_2015_2025_v1
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
  "data_version": "openalex-four-fields-2015-2025-afe152387c5d",
  "data_scope": "period_pilot",
  "is_real_data": true,
  "data_dir": "four_fields_2015_2025_v1",
  "fields": ["ai", "bio", "quantum", "semiconductor"],
  "years": { "min": 2015, "max": 2025 },
  "detectors": ["growth", "zscore"],
  "counts": {
    "rows": 80564, "domestic_institutions": 78, "foreign_institutions": 2660,
    "pairs": 7324, "detections": 19790, "injections": 420
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

해외 기관은 `type` 이 `null` 입니다.

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

국가·분야·연도별 협력 집계와 탐지 건수. **개요 히트맵 뷰용.**

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `field`, `year`, `country` | — | 분야 코드 · 연도 · 해외 기관의 국가 코드 |
| `limit` | 500 | 최대 1000 |
| `source`, `detector`, `threshold`, `k`, `min_count` | — | 탐지 건수를 셀 조건. `/api/detections` 와 같음 |

```json
{
  "data_version": "openalex-four-fields-2015-2025-afe152387c5d",
  "source": "live",
  "params": [ { "detector": "zscore", "threshold": 2.5, "k": 3, "min_count": 3 } ],
  "summary": { "evaluated_rows": 9010, "skipped": { "below_min_count": 4344 } },
  "fields": ["bio"], "years": [2021],
  "total": 42, "count": 2,
  "items": [
    { "country_code": "US", "field": "bio", "year": 2021,
      "collab_count": 561, "international_total": 166,
      "share": 3.3795, "composition": 0.3435,
      "pairs": 306, "domestic_institutions": 21, "foreign_institutions": 132,
      "detections": 33 }
  ]
}
```

### 두 가지 비중

| 열 | 분모 | 범위 |
|---|---|---|
| `share` | 같은 분야·연도에서 **국내 기관의 국제 공동논문 총수 합** (기관 중복 없음) | **1 을 넘을 수 있음** |
| `composition` | 같은 분야·연도의 **모든 나라 건수 합** | 나라별 합이 정확히 1 |

한 논문에 같은 나라의 기관이 여럿 참여하면 기관 쌍은 여럿 생기지만 국제 공동논문
총수로는 한 편입니다. 그래서 `share` 가 1 을 넘습니다(위 예에서 3.38). 히트맵의
색은 **`composition`** 을 쓰고 `share` 는 숫자로 함께 보여 주는 것을 권합니다.

- `collab_count` 가 0 인 기관 쌍·연도는 빠집니다.
- `country` 로 걸러도 분모는 전체 기준이라, 한 나라만 조회해도 값이 달라지지 않습니다.
- `institutions_foreign.csv` 가 없으면 `country_code` 가 `null` 인 한 칸으로 묶입니다.

## GET `/api/metrics`

주입 실험의 정량 평가표. `experiments.evaluate` 가 만든 `metrics.csv` 를 돌려줍니다.
그 파일이 없는 데이터에서는 **409 `metrics_unavailable`** 입니다.

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `scenario_id` | — | `original`, `step_x2/x3/x5`, `gradual_x3`, `spike_x5`, `decoy_x3` |
| `detector`, `threshold`, `k`, `min_count`, `correction_id` | — | 실험 조건 |
| `sort` | `f1` | 내림차순 정렬에 쓸 열 이름. 없는 열이면 400 |
| `limit` | 100 | 최대 1000 |

```json
{
  "data_version": "openalex-four-fields-2015-2025-afe152387c5d",
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
  "data_version": "openalex-four-fields-2015-2025-afe152387c5d",
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

## 아직 구현하지 않은 API

| 메서드 | 경로 | 목적 | 예정 |
|---|---|---|---|
| POST | `/api/whatif` | 임계값·k·최소 건수 변경 시 재계산과 지표 | 11/19~11/25 |
| GET | `/api/comparison` | 보정 전후 비교 | 11/19~11/25 |

## 현재 한계

- 2025년 샘플의 실시간 탐지는 과거 기준선 부족으로 0건입니다.
  여러 연도의 실시간 탐지는 [데이터 v1](period-v1.md)에서 확인할 수 있습니다.
- 데이터 v1의 저장된 시나리오는 `source=file`과 `scenario_id`로 조회합니다.
- 네 분야 샘플과 기간 집계에는 `institutions_foreign.csv`가 있습니다.
  구형 데이터 폴더에서 이 파일이 없으면 API는 해외 기관 이름에 ID를, 국가에 `null`을 반환합니다.
