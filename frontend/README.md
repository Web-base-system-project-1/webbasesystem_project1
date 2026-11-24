# React 프론트엔드

## 실행

팀원 최초 설치와 Windows 실행은 [팀원용 안내](../docs/running.md)를 참고합니다.
Python 3.12, Node.js·npm이 필요합니다. 최초 `frontend/`에서 `npm ci`를 실행합니다.

프로젝트 최상위의 터미널 1:

```bash
.venv/bin/python -m flask --app web.app run --debug --port 5001
```

터미널 2:

```bash
cd frontend
npm run dev
```

화면은 http://127.0.0.1:5173/ 입니다. 각 서버는 Ctrl+C로 종료합니다.
API_TARGET 환경 변수로 Vite 프록시의 목적지를 바꿀 수 있으며 기본값은 http://127.0.0.1:5001 입니다.
이미 같은 포트의 서버가 실행 중이면 중복 실행하지 않습니다.

## 데이터

DATA_DIR을 비우면 저장소의 `data/sample/actual/four_fields_2015_2025_v2.zip`을 바로 읽습니다.
이전에 .env에 `frontend_period_pilot` 같은 경로를 지정했다면 비우고 Flask를 재시작해야 합니다.
API 키·수동 압축 해제 없이 실행할 수 있습니다.
현재 v2는 국내 78곳·해외 2,660곳, 2015~2025년 4개 분야의 지정 하위 토픽 범위입니다.
전체 분야를 대표하는 통계로 해석하지 않습니다.

## 화면

- 국내·해외 기관 검색: 현재 분야·연도·국내 기관 유형과 상대 기관에 공동논문 실적이 있는 기관만 조회합니다. 검색 결과는 최대 100곳이며 검색어로 좁힙니다.
- 어느 쪽 기관부터 선택해도 됩니다. `전체 · 선택 해제`로 다른 조합을 찾고, 분야 변경 시 두 기관 선택을 초기화합니다.
- 국가 개요: 고유 논문·국가로 중복 제거한 협력 비중 및 탐지 건수 히트맵. 분야·연도 조건을 적용하며 기관·유형과 별도인 전국 집계입니다.
- 협력 관계: 현재 조건의 국내·해외 각각 상위 15곳 행렬. 숫자는 기관 쌍 공동논문 수이고 ●는 기본 탐지 여부입니다. 국가 셀 → 해당 국가 행렬 → 기관 타임라인으로 이동합니다.
- 타임라인: 원본 공동논문 수, 합계·최다, 협력 비중·직전 3년 기준선·표준편차·탐지 표시와 근거 표. 과거 기준 확인을 위해 전체 기간을 유지하고 선택 연도를 강조합니다.
- 원본 탐지 목록: source=live의 기본 설정(z-score 2.5/k=3, 증가율 100%/최소 3편). 목록 클릭 시 기관·분야 및 강조 연도가 변경됩니다. 목록은 페이지당 20건 표시합니다.
- 주입 실험: 원본·2/3/5배 지속 증가·점진·급증·미끼를 선택하고, 탐지 방법과 저장된 필수 임계값을 비교합니다.
- 비교 차트: 원본 회색 점선, 시나리오 초록 실선. 주입 대상 보기 버튼으로 대표 사례를 선택합니다.
- 근거 표: 원본/시나리오 건수·비중, 유효한 주입 여부, 탐지 점수와 기준값. Z-score 기준값은 과거 협력 비중 평균, 증가율 기준값은 전년 건수입니다.
- 평가: 전체 실험의 TP/FP/FN·Precision·Recall·F1·유효 주입 행 Recall·평균 지연. 기관별 수치가 아닙니다.

- 보정 비교: 증가율의 비중 동반 증가 보정과 Z-score의 국내 총수 최소 3편 보정을 각각 선택합니다. 동일 시나리오·임계값의 전체 평가와 선택 쌍의 판정 변화·주입 정답 기준 오류 유형을 표시합니다.
- What-if: 시나리오·탐지기·임계값·k·최소 건수·보정을 정하고 `다시 계산`을 누릅니다. 같은 시나리오의 기본 설정 대비 전체 지표와 추가/해제 탐지를 비교합니다. 위 기관·연도 필터와 별도이며, 기관 링크는 원본 타임라인으로 이동합니다.

기본 데이터 v2의 보정 전후 84회 저장 결과를 사용합니다. What-if는 기존 탐지·평가 함수를 재실행합니다.
실험 평가와 대표 사례는 [데이터 v2 검증](../docs/data-review-2026-11-19.md)을 참고하세요.
저장 실험 기록이 없는 데이터는 실험 불가 안내를 표시합니다.

## 파일 역할

- src/App.jsx: 조회·선택 상태와 화면 구성
- src/api/client.js: JSON 요청·오류 처리, 기관 목록 페이지 로딩
- src/components/InstitutionFilters.jsx, InstitutionSearch.jsx: 연관 기관 검색·분야 선택
- src/components/TimelineChart.jsx, TimelineSummary.jsx, YearlyTable.jsx: 차트·요약·표
- src/components/DetectionList.jsx: 탐지 목록·필터·정렬·페이지 이동
- src/components/ExperimentView.jsx: 시나리오 비교·탐지 근거·전체 평가
- src/components/OverviewHeatmap.jsx, CooperationMatrix.jsx: 국가 개요·기관 관계
- src/components/ShareTimeline.jsx: 비중·과거 기준선·탐지 근거
- src/components/CorrectionView.jsx, WhatIfPanel.jsx: 보정 전후·설정 재계산
- src/hooks/useApi.js: 취소·재조회·데이터 버전 확인

## 검증

```bash
npm test
npm run lint
npm run build
```

빌드 결과는 dist/에 생성합니다. npm run preview에는 개발 API 프록시를 제공하지 않으므로 통합 확인은 npm run dev를 사용합니다.
