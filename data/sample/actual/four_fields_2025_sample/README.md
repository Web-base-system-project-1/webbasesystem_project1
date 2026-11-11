# 2025년 네 분야 실제 집계 샘플

2026년 11월 11일 OpenAlex에서 대표 토픽별로 2025년 한국 기관 참여 논문의 첫 페이지를 수집했습니다. 분야마다 하위 토픽 하나로 수집·정제·API 연결을 점검한 샘플입니다.

| 분야 | 대표 토픽 | 수집 | 유지 | 국내 기관 | 해외 기관 | 기관 쌍 행 |
|---|---|---:|---:|---:|---:|---:|
| 반도체 | T10472 · Semiconductor materials and devices | 100 | 14 | 21 | 22 | 42 |
| AI | T11636 · Artificial Intelligence in Healthcare and Education | 100 | 37 | 31 | 136 | 174 |
| 바이오 | T10878 · CRISPR and Genetic Engineering | 100 | 25 | 26 | 48 | 90 |
| 양자 | T10682 · Quantum Computing Algorithms and Architecture | 100 | 39 | 24 | 71 | 117 |

총 400편에서 115편을 유지했습니다. 네 분야의 고유 국내 기관은 67곳, 해외 기관은 259곳입니다. 같은 기관 쌍이 여러 분야에 등장하면 분야별로 한 행씩 계산해 총 423행입니다.

토픽 선정 근거는 [분야 정의 초안](../../../../config/field_definition.csv)에 있습니다. 한 논문은 OpenAlex 대표 토픽과 일치하는 분야에만 배정합니다. 수집한 400편의 논문 ID는 모두 달랐습니다. [OpenAlex 토픽 문서](https://help.openalex.org/data/topics/)

기존 AI 샘플과 같은 토픽을 11월 11일에 다시 조회해 이번 AI 샘플을 만들었습니다. 기존 AI 샘플의 결과와 이번 결과는 각자의 수집 시각과 해시로 구분합니다.

## 집계 파일

[ZIP](../four_fields_2025_sample.zip)을 풀면 이 폴더와 같은 파일을 사용할 수 있습니다. CSV는 UTF-8이며 첫 줄에 열 이름이 있습니다.

| 파일 | 행 수 | 내용 |
|---|---:|---|
| collab_shares.csv | 423 | 국내·해외 기관 쌍, 분야, 연도별 건수와 국내 총수, 협력 비중 |
| collab_counts.csv | 423 | 기관 쌍·분야·연도별 공동논문 수 |
| kr_totals.csv | 102 | 국내 기관·분야·연도별 국제 공동논문 총수 |
| institutions_kr.csv | 67 | 국내 기관 ID·이름·유형·ROR |
| institutions_foreign.csv | 259 | 해외 기관 ID·이름·국가 코드 |
| pair_contributions.csv | 443 | 기관 쌍 집계에 기여한 논문 ID |
| total_contributions.csv | 196 | 국내 기관 총수에 기여한 논문 ID |

collab_shares.csv에서 share는 collab_count를 international_total로 나눈 값입니다. 한 논문에 여러 해외 기관이 참여해도 국내 기관·분야·연도별 총수에는 한 편으로 셉니다. 기관 표시 이름과 국가는 기관 ID로 기관 목록을 연결해 조회합니다.

MANIFEST.json에 분야별 조회 조건, 수집 시각, 제외 사유별 건수, 입력 해시, CSV·검증 기준 파일의 해시가 있습니다. manual_expected 폴더에는 분야별 원본 5편의 별도 검증 기준이 있습니다.

## API에서 확인

프로젝트의 로컬 .env에 아래 DATA_DIR 값을 지정하고 Flask를 다시 시작합니다. ZIP만 받은 경우 압축을 푼 폴더의 절대 경로를 지정할 수 있습니다.

~~~dotenv
DATA_DIR=data/sample/actual/four_fields_2025_sample
~~~

/api/meta에서 sample 범위, 실제 데이터, 2025년, 네 분야와 기관 쌍 423행을 확인할 수 있습니다. /api/pairs?field=quantum처럼 분야별로 조회할 수 있습니다. 탐지·주입 목록은 비어 있습니다. 과거 연도와 비교하는 탐지 실험에는 여러 연도의 데이터가 필요합니다.

## 수집·정제 확인

기존 수집·정제 기준을 적용했습니다. 국내 기관 유형은 education, facility, government이며, 해외 기관은 국가가 확인된 KR 이외 기관입니다. 고유 기관이 50곳을 넘는 논문은 유형을 거르기 전에 제외합니다. 기관별 국제 공동논문 5편 조건은 전체 기간 집계 단계에서 적용합니다.

가상환경을 활성화한 뒤 프로젝트 최상위에서 실행합니다. 다음 예는 반도체이며, 다른 분야는 위 표의 토픽 ID와 분야 코드를 사용합니다. 다시 수집할 때는 새로운 원본·정제 폴더를 지정합니다.

~~~bash
python -m pipeline.collect --topic-id T10472 --limit 100 --output-dir data/raw/four_fields_2025_rerun/semiconductor
python scripts/check_sample.py data/raw/four_fields_2025_rerun/semiconductor
python -m pipeline.preprocess --input data/raw/four_fields_2025_rerun/semiconductor/sample.json --field semiconductor --output-dir data/processed/four_fields_2025_rerun/semiconductor
python -m pipeline.aggregate --input data/processed/four_fields_2025_rerun/semiconductor/clean_works.json
python scripts/check_aggregation.py data/processed/four_fields_2025_rerun/semiconductor
~~~

이번 원본을 보유한 환경에서는 저장된 검증 기준과도 대조할 수 있습니다. 새로 수집한 결과는 원본 해시가 달라질 수 있으므로 그 수집본의 별도 기준으로 검증합니다.

~~~bash
python scripts/check_aggregation.py data/processed/four_fields_2025_20261111/semiconductor --manual-reference data/sample/actual/four_fields_2025_sample/manual_expected/semiconductor.json
~~~

원본 응답, 정제 JSON, 처리 로그는 각자의 Git 제외 폴더에서 관리합니다. 자세한 규칙과 열 설명은 [정제·집계 안내](../../../../docs/processing.md)와 [데이터 형식](../../../../docs/data-schema.md)에 있습니다.
