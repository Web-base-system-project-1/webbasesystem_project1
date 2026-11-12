# 데이터 형식 초안

샘플과 기간 집계는 아래의 핵심 데이터 형식을 공통으로 사용합니다. 2015~2025년 결과, 토픽과 집계 규칙, 재실행 방법은 [데이터 v1 안내](period-v1.md)에 정리했습니다.

샘플의 원본 응답·검증 결과·실행 기록 형식과 실행 명령은 [샘플 수집 안내](collection.md)를 참고하세요.

정제 규칙·집계 표·논문별 근거·실제 샘플 결과·검증 방법은 [샘플 정제·집계 안내](processing.md)에 정리했습니다. 샘플 결과는 `data_scope: sample`로 구분합니다.

## 공통 규칙

- 인코딩: UTF-8. 파일 읽기·쓰기에 인코딩을 명시합니다.
- `domestic_id`, `foreign_id`: 기관 식별자. 표시 이름과 구분합니다.
- `field`: `semiconductor`, `ai`, `bio`, `quantum`을 초기 분야 코드로 제안합니다.
- `year`: 논문 출판 연도를 나타내는 정수.
- `share`: 0~1 비중. 퍼센트 변환은 화면 표시 단계에서 합니다.
- 수집 완료 후 건수가 없는 연도는 0, 수집 누락은 결측으로 구분합니다.
- 분모가 0인 협력 비중은 결측으로 저장합니다. JSON에서는 `null`을 사용합니다.

## 핵심 파일

| 파일 | 주요 열 |
|---|---|
| `field_definition.csv` | field, topic_id, topic_name, rationale |
| `institutions_kr.csv` | domestic_id, name, type, ror |
| `institutions_foreign.csv` | foreign_id, name, country_code |
| `collab_counts.csv` | domestic_id, foreign_id, field, year, collab_count |
| `kr_totals.csv` | domestic_id, field, year, international_total |
| `collab_shares.csv` | domestic_id, foreign_id, field, year, collab_count, international_total, share |
| `pair_contributions.csv` | work_id, domestic_id, foreign_id, field, year |
| `total_contributions.csv` | work_id, domestic_id, field, year |
| `collection_log.csv` | request_id, collected_at, query, response_count, status |
| `injections.csv` | scenario_id, domestic_id, foreign_id, field, year |
| `detections.csv` | run_id, scenario_id, domestic_id, foreign_id, field, year, detector, threshold, correction_id, score |

수집 로그에 API 키를 포함한 전체 요청 URL을 그대로 저장하지 않습니다. 키를 제외한 조회 조건만 기록합니다.

[네 분야 공유 샘플](../data/sample/actual/four_fields_2025_sample/README.md)의 해외 기관 목록은 정제 논문의 기관 ID·이름·국가에서 추출합니다. `foreign_id`로 협력 표와 연결할 수 있습니다.

한 논문이 KAIST·MIT·Stanford의 공동연구라면 KAIST–MIT와 KAIST–Stanford는 각각 1건이지만, KAIST 국제 공동논문 총수는 1편입니다. 국제 공동논문 총수를 기관 쌍의 건수 합으로 계산하지 않습니다.

탐지 결과에는 기준 평균·표준편차, 현재 값, 최소 건수, 처리 사유 등 근거 열을 추가합니다. 실험별 파라미터와 시드는 별도 설정에 보존하고, 탐지기·임계값·보정 버전을 구분해서 평가합니다.
