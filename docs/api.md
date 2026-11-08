# API 명세

로컬 기본 주소: `http://127.0.0.1:5001`

프론트엔드는 상대 경로 `/api/...` 를 사용합니다. Flask 가 화면과 API 를 같은 주소로
제공하므로 별도의 프론트 서버나 CORS 설정은 필요하지 않습니다.

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

## 데이터 출처

서버는 **켜질 때 한 번만** CSV 를 읽어 메모리에 들고 있습니다. 요청마다 파일을 다시
읽지 않습니다. 읽는 폴더는 `.env` 의 `DATA_DIR` 로 바꿉니다.

```dotenv
DATA_DIR=data/processed/ai_2025_sample
```

지정하지 않으면 Git 으로 공유하는 예시 폴더 `data/sample/example` 을 사용합니다.
그 폴더는 `python scripts/make_example_data.py` 로 다시 만들 수 있습니다(시드 고정).
지금 어떤 데이터를 보고 있는지는 `/api/meta` 의 `is_real_data` 로 확인합니다.

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
  "data_version": "example-2026-11-08",
  "data_scope": "example",
  "is_real_data": false,
  "data_dir": "example",
  "fields": ["ai", "bio"],
  "years": { "min": 2015, "max": 2025 },
  "detectors": ["growth", "zscore"],
  "counts": {
    "rows": 198, "domestic_institutions": 3, "foreign_institutions": 3,
    "pairs": 18, "detections": 75, "injections": 5
  }
}
```

화면은 이 응답으로 연도 슬라이더 범위와 분야 필터 항목을 만들 수 있습니다.

## GET `/api/institutions`

기관 검색·필터.

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `role` | `domestic` | `domestic` 또는 `foreign` |
| `q` | — | 이름 또는 ID 의 일부 (대소문자 무시) |
| `type` | — | 기관 유형 (`education`, `facility`, `government`) |
| `limit` | 200 | 최대 1000 |

```
GET /api/institutions?role=domestic&q=기관
```

```json
{
  "data_version": "example-2026-11-08",
  "role": "domestic",
  "total": 3,
  "count": 3,
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
| `threshold` | | 주면 그 임계값만 |

```json
{
  "data_version": "example-2026-11-08",
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
      "year": 2021, "detector": "zscore", "threshold": 2.5, "score": 13.0333,
      "baseline_mean": 0.093305, "baseline_std": 0.017861,
      "current_value": 0.326087, "collab_count": 15,
      "run_id": "example-run", "scenario_id": "example", "correction_id": null
    }
  ],
  "injections": [
    { "scenario_id": "example", "year": 2021 }
  ]
}
```

`baseline_mean` 과 `baseline_std` 로 **직전 k년 기준선 띠**를 그릴 수 있습니다.
`detections` 의 연도와 `injections` 의 연도를 함께 표시하면 탐지 지연이 보입니다.

자료가 없는 기관 쌍은 **404 `pair_not_found`** 입니다.

## GET `/api/detections`

탐지 목록과 근거. 점수가 높은 순. **탐지 결과·근거 뷰용.**

| 쿼리 | 기본값 | 설명 |
|---|---|---|
| `detector` | — | `zscore`, `growth` |
| `threshold` | — | z-score `2.0 / 2.5 / 3.0`, 증가율 `0.5 / 1.0 / 2.0` |
| `field` | — | 분야 코드 |
| `scenario_id` | — | 주입 시나리오 |
| `domestic_id` | — | 국내 기관 |
| `year` | — | 연도 |
| `limit` | 100 | 최대 1000 |

응답 항목 하나는 `/api/timeline` 의 `detections` 와 같은 열에
`domestic_name`, `foreign_name`, `foreign_country` 가 더해진 모양입니다.

| 열 | 의미 |
|---|---|
| `score` | z-score 또는 전년 대비 증가율 |
| `baseline_mean`, `baseline_std` | 직전 k년 기준선 (z-score 전용) |
| `current_value` | 올해 값. z-score 는 비중, 증가율은 건수 |
| `previous_value` | 전년 건수 (증가율 전용) |
| `collab_count` | 올해 공동논문 수 |
| `min_count` | 적용한 최소 건수 (증가율 전용) |
| `correction_id` | 보정 버전. 보정 전은 `null` |

## GET `/api/scenarios`

주입 시나리오 목록과 정답 건수.

```json
{
  "data_version": "example-2026-11-08",
  "total": 1, "count": 1,
  "items": [ { "scenario_id": "example", "injected_rows": 5, "year_min": 2021, "year_max": 2025 } ]
}
```

---

## 아직 구현하지 않은 API

| 메서드 | 경로 | 목적 | 예정 |
|---|---|---|---|
| GET | `/api/overview` | 국가·분야·연도별 히트맵 집계 | 11/12~11/18 |
| POST | `/api/whatif` | 임계값·k·최소 건수 변경 시 재계산과 지표 | 11/19~11/25 |
| GET | `/api/comparison` | 보정 전후 비교 | 11/19~11/25 |
| GET | `/api/metrics` | Precision·Recall·F1·탐지 지연 | 2번 평가 함수 연결 후 |

## 현재 한계

- `/api/detections` 는 **저장된 예시 결과**를 돌려줍니다. 2번 담당자의 탐지 함수를
  호출하지 않습니다. 함수가 완성되면 **응답 형식은 그대로 두고 내부만 교체**하므로
  화면 코드는 바꾸지 않아도 됩니다.
- 기본 데이터가 `data/sample/example` 이라 실제 수집 결과가 아닙니다.
  `/api/meta` 의 `is_real_data` 가 `false` 입니다.
- `institutions_foreign.csv` 는 현재 집계 산출물에 **없습니다.** 히트맵의 국가별 집계와
  협력 관계 뷰에 해외 기관 이름·국가가 필요하므로 형식만 먼저 제안했습니다.
  이 파일이 없으면 해외 기관 이름 자리에 ID 가, 국가 자리에 `null` 이 들어갑니다.
