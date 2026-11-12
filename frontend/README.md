# React 프론트엔드 개발 환경

React + JavaScript + Vite로 구성했습니다. 기관·분야 선택 시 실제 Flask API에서 타임라인을 조회합니다.
공동논문 수 차트와 접을 수 있는 연도별 표를 제공합니다. 로딩·오류·빈 결과를 구분하고,
빠른 선택 변경 시 이전 요청을 취소합니다.

## 실행

처음 설치하는 팀원과 Windows 사용자는 [팀원용 설치·실행 안내](../docs/running.md)를 참고하세요.

프로젝트 루트의 첫 번째 터미널에서 Flask 실행:

```bash
source .venv/bin/activate
python -m flask --app web.app run --debug --port 5001
```

Flask가 이미 실행 중이면 다시 실행하지 않습니다.
두 번째 터미널에서 React 실행:

```bash
cd frontend
npm ci
npm run dev
```

각 팀원은 최초 실행 전에 npm ci를 실행합니다. 이후 package-lock.json의
의존성이 변경됐을 때도 npm ci로 다시 설치합니다.

React 화면: http://127.0.0.1:5173/
기존 Flask 화면: http://127.0.0.1:5001/
각 서버는 해당 터미널에서 Ctrl+C로 종료합니다.

## API 연결 방식

화면에서는 fetch('/api/meta')처럼 상대 경로를 사용합니다.
Vite의 개발 프록시가 /api 요청을 http://127.0.0.1:5001로 전달합니다.
이 설정은 개발 서버용이며, 배포 시 정적 파일 제공 및 API 연결 방식은
별도로 정해야 합니다. npm run preview에는 이 개발 프록시가 적용되지 않습니다.

API 원본 명세: ../docs/api.md

| API | 다음 화면에서 사용할 용도 |
| --- | --- |
| /api/health | 서버 상태 확인 |
| /api/meta | 분야, 연도 범위, 예시 데이터 여부 |
| /api/institutions?role=domestic | 국내 기관 목록 |
| /api/institutions?role=foreign | 해외 기관 목록 |
| /api/pairs | 데이터가 있는 기관 쌍 조회 |
| /api/timeline?domestic_id=...&foreign_id=...&field=... | 연도별 공동논문 수와 비중 |

주의 사항:
- 현재 기본 데이터는 실제 논문이 아닌 예시 데이터입니다.
- 분야 선택지는 /api/meta의 fields를 사용합니다. 현재 예시는 ai, bio입니다.
- share는 0~1이며, null은 0과 다르게 처리합니다.
- 여러 응답의 data_version을 확인해 같은 데이터인지 판단합니다.
- /api/whatif는 아직 구현되지 않았습니다.

## 파일 역할

- src/main.jsx: React 실행 시작점
- src/App.jsx: 조회 상태·선택 상태 관리와 전체 화면 구성
- src/api/client.js: 공통 JSON 요청과 HTTP 오류 처리
- src/components/InstitutionFilters.jsx: 기관·분야 선택 메뉴
- src/components/TimelineChart.jsx: 연도별 공동논문 수 차트
- src/components/TimelineSummary.jsx: 기간 합계·연간 최다 수치
- src/components/YearlyTable.jsx: 접이식 연도별 수치 표
- src/App.css, src/index.css: 화면 스타일
- vite.config.js: 개발 서버와 API 프록시 설정
- package.json: 의존성과 실행 명령
- package-lock.json: 설치 버전 고정; Git에 함께 커밋
- .gitignore: node_modules와 dist 등 생성 파일 제외

## 확인 명령

```bash
npm test
npm run lint
npm run build
```

API 요청·오류·취소 처리 회귀 테스트 8개를 실행합니다. build 결과는 dist/에 생성됩니다.

## 탐지 목록 및 클릭 연동

/api/detections?limit=1000에서 전체 탐지 목록을 조회합니다. 총 건수보다 잘린 경우 안내합니다.
기관 쌍 버튼을 누르면 국내·해외 기관과 분야 선택이 바뀌고 타임라인에서 탐지 연도를 강조합니다.
수동으로 조건을 변경하면 연도 강조가 해제됩니다. 탐지 방법 필터와 방법별 점수 정렬을 제공합니다.

## 실제 데이터 연결 확인

프로젝트 루트에서 기존 Flask를 종료한 뒤 Mac에서는 다음처럼 실행할 수 있습니다.

```bash
DATA_DIR=data/sample/actual/ai_2025_sample .venv/bin/python -m flask --app web.app run --port 5001
```

Windows는 기존 .env의 DATA_DIR만 해당 경로로 설정하고 Flask를 재시작합니다.
다른 환경 변수나 키를 덮어쓰지 않습니다.
현재 실제 샘플은 AI·2025년 한 해, 기관 쌍 158개입니다. 해외 기관은 이름 대신 ID가 표시될 수 있습니다.
탐지·주입 파일이 없어 목록은 비어 있으며, 이를 정상/이상 판정으로 해석하면 안 됩니다.
여러 해 실제 탐지 결과와 실시간 탐지 API 통합은 후속 작업입니다.
