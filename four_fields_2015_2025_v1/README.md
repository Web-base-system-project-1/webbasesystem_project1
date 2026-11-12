# 2015~2025년 네 분야 데이터 v1

과제 설명서 Project 7의 1~4쪽에 나온 출처, 분야 정의, 수집·집계 규칙과 필수 주입 조건을 적용했습니다. 집계 버전은 `openalex-four-fields-2015-2025-afe152387c5d`입니다.

## 분야 정의

| 분야 코드 | OpenAlex 토픽 | 선정 근거 |
|---|---|---|
| semiconductor | T10099 | 질화갈륨계 반도체 재료와 고전력 트랜지스터 등 소자 연구를 함께 다룹니다. [OpenAlex](https://openalex.org/topics/T10099) |
| ai | T10036 | 영상 인식과 객체 탐지에 쓰이는 심층신경망과 모델 설계를 다룹니다. [OpenAlex](https://openalex.org/topics/T10036) |
| bio | T10158 | 면역항암제의 치료 기전과 치료 반응 바이오마커를 다룹니다. [OpenAlex](https://openalex.org/topics/T10158) |
| quantum | T10020 | 양자 얽힘, 통신, 암호와 양자 정보 처리를 다룹니다. [OpenAlex](https://openalex.org/topics/T10020) |

[분야 정의 CSV](field_definition.csv)에 토픽의 공식 영문 이름과 선정 근거가 있습니다. 각 분야의 분석 범위는 표에 적은 하위 토픽입니다. 논문은 `primary_topic`의 ID가 일치하는 분야 하나에 배정합니다. [OpenAlex 토픽 정의](https://help.openalex.org/data/topics/)

## 수집·집계 결과

| 분야 | 한국 기관 참여 수집 논문 | 정제 후 유지한 국제 공동논문 | 주입 후보 |
|---|---:|---:|---:|
| 반도체 | 1,838 | 533 | 4 |
| AI | 4,620 | 813 | 0 |
| 바이오 | 2,922 | 990 | 22 |
| 양자 | 1,083 | 382 | 0 |
| 합계 | 10,463 | 2,718 | 26 |

- 출판 연도 2015~2025년과 한국 기관 참여 조건으로 44개 토픽·연도 조합을 모두 조회했습니다. OpenAlex 요청 143건이 성공했고, 조회 건수와 원본 고유 논문 수가 모두 일치했습니다. 원본과 조회 로그는 `data/raw/four_fields_2015_2025_v1/`에 있습니다.
- 소속 기관이 50곳을 초과한 논문 10편을 제외했습니다. 교육·연구시설·정부 유형의 국내 기관에 기간 내 국제 공동논문 5편 이상을 적용한 뒤 국내 78곳, 해외 2,660곳을 집계했습니다. 동일 논문 안의 동일 기관 쌍과 국내 기관 총수는 각각 한 번만 셉니다.
- 기관 쌍·분야 조합 7,324개 중 4,484개(61.2%)는 전 기간에 공동논문이 1편입니다. 원본 소속에서 다시 센 기관 쌍 기여 19,274행과 국내 기관 총수 기여 3,812행이 집계 파일과 일치했습니다. 분야·연도별 유지 논문 수는 `data-verification.json`에 기록했습니다.
- 국내 병원을 포함해 같은 원본을 집계하면 국내 기관은 101곳, 유지 논문은 2,965편, 주입 후보는 78쌍입니다. 추가된 논문 247편과 후보 52쌍은 모두 바이오에 속합니다. 필수 실험 기준을 충족하면서 바이오에 더 집중되는 것을 줄이기 위해 기본 집계는 교육·연구시설·정부 기관을 사용합니다.
- 국내 기관 78곳의 ROR 레코드를 직접 조회했습니다. 78곳 모두 활성 상태였고 공식명 또는 별칭과 OpenAlex 표시명이 일치했으며, ROR 국가 정보에도 한국이 있었습니다. 이름을 정규화했을 때 같은 이름의 서로 다른 국내 OpenAlex ID는 0그룹이고, 전체 집계에서 동일한 ROR을 가진 서로 다른 OpenAlex ID도 0그룹이었습니다. 집계 키는 OpenAlex ID입니다. ROR API 원본은 `data/raw/ror_four_fields_2015_2025_v1/`에 보관했습니다. [ROR 기관 조회](https://ror.readme.io/docs/api-single)

## 필수 주입 실험 입력 확인

2015~2020년의 6개 연도에서 합계 18편 이상인 기관 쌍·분야 조합을 `injection_candidates.csv`에 기록했습니다. 26쌍 가운데 22쌍이 바이오라 전체 주입 평가를 분야별 성능으로 해석할 때 후보 분포를 고려해야 합니다.

실제 집계 입력으로 고정 시드 42에서 20쌍을 뽑고 7개 시나리오와 42개 평가 실행을 완료했습니다. 필수 2·3·5배 시나리오는 각각 2021~2025년 100행(20쌍 × 5년)의 정답을 기록합니다. 각 시나리오에서 20행은 해당 연도의 원본이 0편이라 배수를 적용한 뒤에도 0편이며, 평가에서는 `effective=False`로 확인할 수 있습니다.

## 다시 실행하기

가상환경을 켜고 프로젝트 최상위에서 실행합니다. 중단된 수집은 같은 출력 폴더로 재시도하면 완료된 토픽·연도는 재사용합니다. 집계를 다시 생성할 때는 아직 없는 새 출력 경로를 지정하세요.

```bash
python -m pipeline.collect_period --output-dir data/raw/four_fields_2015_2025_v1
python -m pipeline.aggregate_period --input-dir data/raw/four_fields_2015_2025_v1 --output-dir data/processed/four_fields_2015_2025_v1
python -m pipeline.aggregate_period --input-dir data/raw/four_fields_2015_2025_v1 --output-dir data/processed/four_fields_2015_2025_v1_with_healthcare --include-healthcare
python -m experiments.run --counts data/processed/four_fields_2015_2025_v1/collab_counts.csv --totals data/processed/four_fields_2015_2025_v1/kr_totals.csv --seed 42 --out-dir results/four_fields_2015_2025_v1/experiment_check
```

Flask와 `python -m experiments.run`은 저장소의 데이터 v1 ZIP을 바로 읽습니다. ZIP에는 집계 파일, 수집 로그, 검증 기록, 시드 42의 주입·탐지·평가 결과가 있습니다. 실험 결과의 입력 버전과 파일 해시는 `experiment_manifest.json`에서 확인합니다.

다른 집계 폴더나 ZIP을 사용하려면 `DATA_DIR`에 지정하세요. `/api/meta`에서 데이터 버전과 연도 범위를 확인할 수 있습니다. `collection_coverage.csv`에서 조회 완료 상태를, `preprocess_audit.csv`에서 제외 사유를, `pair_contributions.csv`와 `total_contributions.csv`에서 논문별 근거를 확인할 수 있습니다.
