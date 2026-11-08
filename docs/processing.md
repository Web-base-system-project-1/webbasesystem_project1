# 샘플 정제·기관 쌍 집계

수집한 논문 샘플을 국제 공동연구 관계로 정제하고, 기관 쌍별 건수와 국내 기관별 논문 총수·협력 비중을 계산합니다. 네트워크 요청이나 API 키를 사용하지 않는 오프라인 단계입니다.

## 1. 실행 명령

프로젝트 최상위에서 가상환경을 활성화합니다. 최초 설정은 [setting.md](../setting.md), 입력 샘플 수집은 [collection.md](collection.md)를 참고하세요.

```bash
python -m pipeline.preprocess --input data/raw/ai_2025_sample/sample.json --output-dir data/processed/ai_2025_sample
python -m pipeline.aggregate --input data/processed/ai_2025_sample/clean_works.json
python scripts/check_aggregation.py data/processed/ai_2025_sample --manual-reference data/sample/manual_expected.json
```

Windows에서 가상환경 활성화를 생략했다면 각 명령의 `python`을 `.\.venv\Scripts\python.exe`로 바꿉니다.

이미 만들어진 출력 폴더나 집계 결과는 덮어쓰지 않습니다. 다시 실행하려면 새 출력 폴더 이름을 사용합니다. 예:

```bash
python -m pipeline.preprocess --input data/raw/ai_2025_sample/sample.json --output-dir data/processed/ai_2025_sample_v2
python -m pipeline.aggregate --input data/processed/ai_2025_sample_v2/clean_works.json
python scripts/check_aggregation.py data/processed/ai_2025_sample_v2 --manual-reference data/sample/manual_expected.json
```

모든 상대 입력·출력 경로는 프로젝트 최상위를 기준으로 합니다.

## 2. 기본 정제 규칙

1. 논문 ID가 올바르고 입력 샘플의 2025년·대표 토픽 조건과 일치하는지 확인합니다.
2. 같은 논문 ID는 한 번만 처리합니다. 동일 ID의 내용이 서로 다르면 실행을 중단해 원본 확인을 요청합니다.
3. 저자별 소속에 반복 등장하는 기관을 **OpenAlex 기관 ID 기준**으로 한 번만 남깁니다.
4. 유형을 거르기 전 논문 전체의 고유 기관 수가 **50곳을 넘으면 제외**합니다.
5. 국내 기관은 `KR`이면서 `education`, `facility`, `government`인 기관을 대상으로 합니다.
6. 해외 기관은 국가가 확인되고 `KR`이 아닌 기관입니다. 해외 기관에는 별도 유형 제한을 두지 않습니다.
7. 대상 국내 기관과 확인된 해외 기관이 각각 하나 이상인 논문을 유지합니다.

국가 정보가 없는 기관은 해외 기관으로 추정하지 않고 별도 건수로 기록합니다. 다른 해외 기관이 확인되면 그 관계만 집계합니다. 기관 ID가 없거나 같은 ID의 국가·유형·ROR 정보가 충돌하는 논문은 감사 파일에 제외 사유를 남깁니다.

이름·ROR·`lineage`가 비슷하다는 이유로 다른 기관 ID를 자동 병합하지 않습니다. 예를 들어 병원을 상위 대학 소속 논문으로 자동 바꾸지 않습니다. 집계에 사용된 서로 다른 ID가 같은 ROR를 공유하면 `institution_review.json`에 확인 후보를 기록합니다.

### 국내 병원 포함 비교

기본 실행은 국내 `healthcare` 기관을 제외합니다. 팀이 병원 포함 실험을 선택하면 별도 출력 폴더에서:

```bash
python -m pipeline.preprocess --input data/raw/ai_2025_sample/sample.json --output-dir data/processed/ai_2025_with_healthcare --include-healthcare
python -m pipeline.aggregate --input data/processed/ai_2025_with_healthcare/clean_works.json
python scripts/check_aggregation.py data/processed/ai_2025_with_healthcare
```

기본 조건의 수작업 기준 파일은 병원 포함 조건과 다르므로 이 비교 실행에는 지정하지 않습니다. 어떤 조건을 선택했는지는 실행 요약에 보존됩니다.

**2015~2025년 국제 공동논문 5편 이상인 기관 조건은 전체 기간 수집 후 적용합니다.** 현재 샘플에서 5편 미만이라는 이유로 기관을 제외하지 않습니다.

## 3. 집계 규칙

예를 들어 국내 대학 A·B와 해외 기관 X·Y가 논문 한 편에 참여하면:

| 대상 | 해당 논문의 기여 |
|---|---:|
| A–X, A–Y, B–X, B–Y | 각각 1건 |
| A의 국제 공동논문 총수 | 1편 |
| B의 국제 공동논문 총수 | 1편 |

- 기관 쌍의 키: `(domestic_id, foreign_id, field, year)`.
- 국내 기관 논문 총수의 키: `(domestic_id, field, year)`.
- 같은 논문이 같은 키에 두 번 기여하지 않습니다.
- `share = collab_count / international_total`.

한 논문에 해외 기관이 여러 곳 참여할 수 있으므로 **국내 기관의 국제 공동논문 총수를 기관 쌍 건수의 합으로 만들지 않습니다.** 같은 국내 기관의 해외 파트너별 비중 합이 1을 넘을 수 있으며, 이를 합계 100%로 다시 정규화하지 않습니다.

현재 입력은 2025년 한 하위 토픽의 첫 100편입니다. 샘플 안에서 계산한 비중이며, 전체 기간·전체 AI 분야의 공식 수치가 아닙니다. 수집하지 않은 연도를 0건으로 만들어 채우지 않습니다.

## 4. 출력 파일

```text
data/processed/ai_2025_sample/
├── clean_works.json              # 유지한 논문과 국내·해외 기관 목록
├── preprocess_audit.csv          # 입력 100건 각각의 유지·제외 이유
├── preprocess_manifest.json      # 원본 해시·규칙·단계별 건수
├── collab_counts.csv             # 기관 쌍별 공동논문 수
├── kr_totals.csv                 # 국내 기관별 국제 공동논문 총수
├── institutions_kr.csv           # 집계 대상 국내 기관 목록
├── collab_shares.csv             # 기관 쌍 건수·국내 기관 총수·협력 비중
├── pair_contributions.csv        # 기관 쌍 건수에 기여한 논문 ID
├── total_contributions.csv       # 국내 기관 총수에 기여한 논문 ID
├── institution_review.json       # 같은 ROR·다른 ID 확인 후보
├── aggregation_manifest.json     # 정제 입력 해시·집계 규칙·결과 요약
└── verification.json             # 이번 샘플의 검증·재실행 대조 기록
```

주요 CSV 형식:

| 파일 | 열 |
|---|---|
| `collab_counts.csv` | domestic_id, foreign_id, field, year, collab_count |
| `kr_totals.csv` | domestic_id, field, year, international_total |
| `institutions_kr.csv` | domestic_id, name, type, ror |
| `collab_shares.csv` | domestic_id, foreign_id, field, year, collab_count, international_total, share |
| `pair_contributions.csv` | work_id, domestic_id, foreign_id, field, year |
| `total_contributions.csv` | work_id, domestic_id, field, year |

CSV·JSON은 UTF-8입니다. 빈 결과도 CSV 헤더와 0건 요약을 남깁니다. 원본 `data/raw/`의 파일은 수정하지 않습니다. `data/processed/` 역시 Git 제외 대상입니다.

## 5. 실제 샘플 실행 결과

2026-11-05 수집한 T11636 샘플 100편에 기본 조건을 적용했습니다.

| 단계·결과 | 건수 |
|---|---:|
| 입력 논문 | 100편 |
| 유지한 국제 공동연구 논문 | **33편** |
| 확인된 해외 기관 없음으로 제외 | 55편 |
| 기본 대상 국내 기관 없음으로 제외 | 11편 |
| 전체 고유 기관 50곳 초과로 제외 | 1편 |
| 집계에 참여한 국내 기관 | **31곳** |
| 집계에 참여한 해외 기관 | 123곳 |
| 서로 다른 국내–해외 기관 쌍 | **158개** |
| 논문별 기관 쌍 기여 합 | 165건 |
| 논문별 국내 기관 총수 기여 합 | 52건 |
| 같은 ROR·다른 ID 확인 후보 | 0개 그룹 |

한 논문이 여러 국내 기관과 여러 해외 기관에 기여하므로 33편·165건·52건은 각각 다른 의미입니다.

제외 이유는 중복 없이 한 가지를 우선 적용합니다. 큰 공동연구 제외 → 대상 국내 기관 확인 → 해외 기관 확인 순서이므로, 정제 전의 단순 해외 기관 유무 통계와 사유별 제외 건수는 다를 수 있습니다. 모든 입력의 판정은 `preprocess_audit.csv`에서 확인할 수 있습니다.

## 6. 원본 5편 대조 기준

`data/sample/manual_expected.json`은 실제 원본의 기관 목록을 대조해 별도로 적은 기준입니다. 집계 함수의 계산값을 정답으로 복사해 만든 파일이 아닙니다. 수집 원본의 SHA-256도 고정해 다른 샘플과 혼용하지 않게 했습니다.

| 논문 ID 끝부분 | 직접 확인한 관계 | 기관 쌍 기여 | 국내 기관 총수 기여 |
|---|---|---:|---:|
| W4411182927 | 영남대 소속만 확인되어 제외 | 0 | 0 |
| W4407584988 | 중앙대 × 미국 기관 3곳 | 3 | 1 |
| W4410028173 | 고려대 × Yale·Imperial. 국내 서울대병원은 기본 대상에서 제외 | 2 | 1 |
| W4408332484 | 순천향대·경희대 × 미국 병원 2곳 | 4 | 2 |
| W4409371320 | 호서대 × 중국 기관 3곳 | 3 | 1 |

검증 명령은 각 논문의 실제 기여 행과 위 기관 ID·쌍·총수·포함 판정을 대조합니다. 다섯 사례 모두 통과했습니다. 병원 포함 여부나 원본 샘플을 바꾸면 그 조건에 맞는 기준을 새로 검토해야 합니다.

## 7. 결과 확인·자동 테스트

```bash
python scripts/check_aggregation.py data/processed/ai_2025_sample --manual-reference data/sample/manual_expected.json
python -m pytest -q
```

검증기는 다음을 확인합니다.

- 원본·정제 입력의 해시와 실행 상태.
- 정제 입력 건수·유지 건수·사유별 감사 행의 일치.
- 논문별 기여의 중복과 정제 논문 누락 여부.
- 기여 근거를 합산한 값과 최종 집계 표의 일치.
- 협력 비중의 분자·분모·계산값.
- 국내 기관 목록과 집계에 참여한 기관의 일치.
- 선택적으로 원본 5편의 별도 기준값과 비교.

자동 테스트에서는 반복 소속·복수 국내 기관·복수 해외 기관, 50/51개 경계, 국내 병원 옵션, 해외 병원 유지, 국가 누락, 중복 논문·메타데이터 충돌, ROR 확인 후보, 빈 결과, 원본 보존, 결과 변조 감지를 검증합니다. 수집기 테스트도 함께 실행하며 실제 API 키나 네트워크를 사용하지 않습니다.

이번 구현에서 자동 테스트 67개가 통과했습니다. 임시 폴더에 실제 원본을 다시 정제·집계해 기존 CSV 전체와 일치하는 것도 확인했으며, 원본 5편 대조 결과와 함께 `verification.json`에 기록했습니다.

## 8. 다음 단계

1. 팀과 4개 분야 토픽·병원 포함 여부·기관 정규화 방침을 확정합니다.
2. 2015~2025년 전체 범위를 수집합니다.
3. 전체 기간의 국제 공동논문 5편 이상 조건을 적용합니다.
4. 해당 버전의 집계·시계열을 2번 탐지 담당자에게 전달합니다.

현재 2025년 샘플은 집계 로직 검증용입니다. 실제 과거 k년 기준선과 탐지 성능 실험에는 전체 기간 데이터가 필요합니다.

## 9. 팀 공유용 실제 집계 받기

검증한 집계 CSV 6개를 [공유용 실제 샘플 폴더](../data/sample/actual/ai_2025_sample/README.md)에 게시했습니다.
원본을 수집하지 않은 팀원도 최신 main에서 받거나 [집계 ZIP](https://raw.githubusercontent.com/Web-base-system-project-1/webbasesystem_project1/main/data/sample/actual/ai_2025_sample.zip)만 내려받을 수 있습니다.
파일별 열·행 수·해시·조회 API 연결 방법은 공유 폴더의 README.md와 MANIFEST.json에 있습니다.

실제 데이터의 범위는 **2025년 AI 하위 토픽 T11636의 첫 100편 중 유지한 33편**입니다.
기존 `data/sample/example`은 화면 개발용 가상 데이터이며, 이번 공유본은 `data/sample/actual/ai_2025_sample`로 구분합니다.
수집 원본과 자동 생성 산출물은 계속 Git에서 제외하고, 공유본은 검증된 시점의 스냅샷으로 관리합니다.
