# 11/19~11/25 데이터 담당 검증과 데이터 v2

Project 7 설명서 2~4쪽의 집계 기준과 필수 주입 조건에 맞춰 원본, 국가 집계, 대표 오탐·미탐 사례를 대조했습니다. 데이터 버전은 `openalex-four-fields-2015-2025-1c38caf53194`입니다.

## 이번 주 완료한 항목

| 항목 | 검증 결과 |
|---|---|
| 수집·정제 | 저장된 44개 토픽·연도, 원본 10,463편과 최종 유지 2,718편 대조 |
| 기관 쌍·분모 | 원본 소속에서 다시 센 기관 쌍 기여 19,274행과 국내 기관 총수 기여 3,812행 일치 |
| 국가 집계 | 국내 기관별 논문·국가 기여 9,074행, 양수 집계 3,745행, 해외 97개국 |
| 분야·기관 매핑 | 네 분야의 2015·2020·2025년 대표 논문 12편과 기관 ID 점검 |
| ROR 대조 | 국내 78곳과 사례·동명이름 해외 기관을 포함한 88곳의 공식명·별칭·국가 대조 |
| 실험 사례 | 시드 42로 보정 전후 84개 실행, 대표 사례 11건을 원본 논문 ID까지 대조 |

기존 v1의 기관 쌍 집계, 국내 총수, 비중, 기관 목록과 주입 후보 파일은 v2에서도 해시가 같습니다. 국가별 파일을 추가하면서 전체 데이터 버전을 갱신했습니다. 설명서에 따른 주입 후보는 26쌍이며 22쌍이 바이오에 속합니다.

## 국가별 데이터 사용

| 파일 | 한 행의 기준 | 건수·비중 |
|---|---|---|
| country_contributions.csv | 논문 ID·국내 기관·해외 국가·분야·연도 | 중복을 제거한 논문별 집계 근거 |
| country_counts.csv | 국내 기관·국가·분야·연도 | 공동논문이 양수인 행 |
| country_shares.csv | 국내 기관·국가·분야·연도 | 국가 공동논문 수 ÷ 같은 국내 기관·분야·연도의 국제 공동논문 총수 |
| country_overview.csv | 국가·분야·연도 | 국가 공동논문 수 ÷ 같은 분야·연도의 전체 고유 국제 공동논문 수 |

한 논문에 국내 기관 2곳, 미국 기관 2곳, 영국 기관 1곳이 참여하면 국내 기관별 미국·영국에 각각 1편씩 기여합니다. `country_overview.csv`에서는 미국 1편, 영국 1편, 해당 분야 국제 공동논문 총수 1편입니다. 같은 논문의 여러 국내 기관도 개요 집계에서 중복 제거합니다.

각 나라의 비중은 0~1입니다. 여러 나라가 한 논문에 참여할 수 있어 나라별 비중 합은 1을 넘을 수 있습니다. 44개 조회 완료를 확인한 뒤 0건 연도를 채웠고, 해당 분모가 0이면 비중은 빈 값입니다.

3번 담당자는 국가·분야·연도 개요에 `country_overview.csv`를 사용하고, 국내 기관을 선택한 국가별 조회에는 `country_shares.csv`를 사용하면 됩니다. 기관 쌍 수와 논문 수를 화면에서 각각 표시할 수 있습니다. 원본 국가별 집계는 원본 데이터에 대한 수치이며, 주입 시나리오의 국가별 건수는 논문·국가 단위의 별도 주입 규칙을 정해야 합니다.

## 분야·기관 매핑 검토

네 토픽의 대표 논문은 심층신경망·영상 인식, 면역항암제와 바이오마커, GaN 소자, 양자정보·광자 연구에 해당합니다. 토픽 ID와 분야 코드는 v1과 동일합니다. 일부 논문은 학술대회 초록 유형이며 설명서의 현재 집계 규칙에 따라 포함했습니다. 기관 유형, 50곳 초과 제외, 기간 내 국제 공동논문 5편 이상 기준을 적용했습니다.

집계 기관 2,738곳에서 같은 ID의 국가·유형·ROR 충돌과 ROR 누락은 발견되지 않았습니다. 공식 ROR 레코드를 재조회한 88곳은 모두 활성 상태였고 국가와 표시명이 공식명 또는 별칭에 일치했습니다. 이름이 같은 다음 기관들은 ROR의 위치와 관계를 확인해 각각의 OpenAlex ID로 집계합니다.

| 표시 이름 | 확인 결과와 처리 |
|---|---|
| Wuyi University | Jiangmen의 ROR 0488wz367과 Wuyishan의 059djzq42를 각각 유지 |
| Presidency University | Kolkata의 ROR 04xgbph11과 Bengaluru의 03218pf76을 각각 유지 |
| European Molecular Biology Laboratory | Heidelberg의 ROR 03mstc592와 하위 Hamburg 연구소 050589e39를 각각 유지. 상위 기관으로 합산하려면 별도 기관 범위 정의가 필요 |

ROR의 응답과 비교 항목은 ZIP의 `institution-mapping-review.json`에 있습니다. ROR 원본 JSON은 로컬 `data/raw/ror_weekly_20261119/`에 보존했습니다.

## 오탐·미탐 원자료 검토

대표 사례의 기준은 z-score 임계값 2.5·k=3, 증가율 임계값 100%·최소 3편입니다. `detection-data-review.json`에 원본·주입 타임라인, 분자·분모에 기여한 논문 ID, 해당 원본 파일 경로와 보정 후 판정을 기록했습니다.

| 사례 | 원자료 확인과 해석 |
|---|---|
| 2021년 서울대–Merck, 3배 주입의 z-score 미탐 | 원본 분자 15·분모 42. 여러 선정 쌍의 주입이 같은 국내 기관의 분모에도 더해져 주입 후 45/130. z-score 1.681로 임계값 미달 |
| 2022년 서울대–Merck, 3배 주입의 증가율 미탐 | 주입 후 2021년 45편에서 2022년 39편으로 감소. 해당 행은 주입 정답이지만 전년 대비 급증 조건을 충족하지 않음 |
| 2021년 서울대–National Taiwan University Hospital | 주입 후 15편으로 증가율 150%를 충족. 비중은 전년 6/35에서 15/130으로 하락해 비중 증가 보정에서 정탐이 해제됨 |
| 2023년 울산대–NTT의 미끼 오탐 | 원본 2편→4편, 미끼 6편→12편. 비중은 1.0→0.8. 비중 증가 보정이 이 오탐을 해제 |
| 2023년 고려대–Columbia University Irving Medical Center의 미끼 오탐 | 원본 비중 자체가 1/8→2/3으로 증가. 미끼에서 분자·분모를 같은 배수로 늘려도 이 원본 변화가 유지되어 z-score가 탐지 |

서울대–Merck의 2021년 원본에는 면역항암제 pembrolizumab 임상 연구가 포함돼 있습니다. 사례별 논문 ID와 양 기관의 소속은 저장된 응답에서 확인했습니다. [대표 원본 논문](https://openalex.org/W3120745011)

| 시나리오·탐지기 | 보정 | TP | FP | FN | 미끼 대상 내 FP |
|---|---|---:|---:|---:|---:|
| 3배 주입·z-score | 기본 | 5 | 427 | 95 | 0 |
| 3배 주입·z-score | 국내 국제 공동논문 총수 3편 이상 | 5 | 388 | 95 | 0 |
| 3배 주입·증가율 | 기본 | 23 | 413 | 77 | 0 |
| 3배 주입·증가율 | 협력 비중도 증가 | 20 | 359 | 80 | 0 |
| 미끼·z-score | 기본 | 0 | 506 | 0 | 2 |
| 미끼·z-score | 국내 국제 공동논문 총수 3편 이상 | 0 | 467 | 0 | 2 |
| 미끼·증가율 | 기본 | 0 | 423 | 0 | 2 |
| 미끼·증가율 | 협력 비중도 증가 | 0 | 400 | 0 | 1 |

원본 데이터에서 발견된 신호의 이상 여부는 미확인 상태로 기록했습니다. 주입 실험의 FP에는 원본에서도 탐지되던 신호가 포함됩니다. 필수 2·3·5배 시나리오의 각 정답 100행 중 20행은 원본 0편에 배수를 곱해 값이 변하지 않습니다. 전체 정답 기준 Recall과 `recall_effective`를 함께 확인하세요.

## 실행과 전달

기본 앱과 실험은 `data/sample/actual/four_fields_2015_2025_v2.zip`을 읽습니다. 기존 `DATA_DIR`을 지정한 팀원은 값을 비우고 Flask를 재시작하면 이 기본 데이터로 전환됩니다. ZIP을 풀면 국가별 CSV, 원본 대조 기록, 매핑·사례 검토와 보정 전후 84개 실행 결과를 받을 수 있습니다.

```bash
python -m pipeline.aggregate_period --input-dir data/raw/four_fields_2015_2025_v1 --output-dir data/processed/four_fields_2015_2025_v2
python scripts/check_period_data.py --raw-dir data/raw/four_fields_2015_2025_v1 --data-dir data/processed/four_fields_2015_2025_v2 --output results/weekly_20261119/data-verification.json
python -m experiments.run --counts data/processed/four_fields_2015_2025_v2/collab_counts.csv --totals data/processed/four_fields_2015_2025_v2/kr_totals.csv --seed 42 --out-dir results/weekly_20261119/experiments
python scripts/review_detection_data.py --raw-dir data/raw/four_fields_2015_2025_v1 --data-dir data/processed/four_fields_2015_2025_v2 --experiments-dir results/weekly_20261119/experiments --output-dir results/weekly_20261119
python scripts/package_period_data.py --data-dir data/processed/four_fields_2015_2025_v2 --experiments-dir results/weekly_20261119/experiments --review-dir results/weekly_20261119 --output data/sample/actual/four_fields_2015_2025_v2.zip
```

집계 출력에는 아직 없는 폴더를 지정합니다. ROR 검토는 당시 API 응답을 보관한 기록이며 이후 기관 정보를 다시 조회하면 조회 일시와 응답 해시를 새로 남겨야 합니다. 국가별 API·화면 연결은 3·4번 담당자가 이어서 진행합니다. 탐지 보정의 최종 채택과 분야별 성능 해석은 2번 담당자가 위 사례와 지표를 바탕으로 결정합니다.
