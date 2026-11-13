# 국제 공동연구 변화 분석 · Project 7

OpenAlex의 국내–해외 기관 공동연구 데이터를 수집하고, 협력 비중의 변화를 탐지·분석하는 웹기반시스템 팀 프로젝트입니다.

저장 폴더 이름은 `webbasesystem_project1`이며, 과제 주제는 Project 7입니다.

## 설치 및 실행

처음 실행하는 팀원은 [Mac·Windows 실행 안내](docs/running.md)를 따라 하세요.
Python 3.12와 Node.js·npm이 필요하며, Flask와 React를 **터미널 두 개**에서 실행합니다.

설치가 끝난 Mac 기준, 두 터미널 모두 프로젝트 최상위 폴더에서 시작합니다.

터미널 1 — Flask:

```bash
source .venv/bin/activate
python -m flask --app web.app run --debug --port 5001
```

터미널 2 — React:

```bash
cd frontend
npm run dev
```

화면: <http://127.0.0.1:5173/> · API 상태: <http://127.0.0.1:5001/api/health>
두 터미널을 켜두고 사용하며, 종료는 각 터미널에서 `Ctrl+C`입니다.
React 최초 패키지 설치는 `frontend/`에서 `npm ci`로 진행합니다.
화면과 `python -m experiments.run`은 같은 2015~2025년 데이터 v1 ZIP을 기본으로 사용합니다.

## 화면과 API 구조

- `frontend/`: React 화면, 선택 메뉴, 차트와 화면 상태 관리.
- `web/`: Flask 서버와 `/api/...` 데이터 응답.
- React는 `/api/...` 상대 경로로 요청하고, Vite 개발 서버(5173)가 Flask(5001)로 전달합니다.
- `web/templates/`, `web/static/`은 기존 Flask 실행 확인 화면입니다. 환경 검사에서도 사용하므로 유지하고, 새 분석 화면은 `frontend/`에서 개발합니다.

개발 중에는 두 서버를 함께 실행합니다. Vite 프록시는 개발용이며,
최종 제출·배포 시 React 빌드 파일 제공 방식과 실행 절차는 3·4번 담당자가 함께 정합니다.

## 역할과 위치

| 담당 | 위치 | 작업 |
|---|---|---|
| 1번 | `pipeline/`, `config/`, `data/sample/` | 분야 정의·수집·정제·집계 |
| 2번 | `detectors/`, `experiments/` | 탐지·주입·평가·보정 |
| 3번 | `web/`, `.vscode/`, `scripts/` | Flask API·통합·실행 환경 |
| 4번 | `frontend/` | React 화면·시각화·API 연동 |
| 공동 | `tests/`, `docs/` | 계산 검증·문서·인터페이스 합의 |

## 현재 구현 범위

- 기존 Flask 실행 확인 화면, API 연결 상태 표시, `/api/health`.
- React 기관·분야 선택, 공동논문 타임라인·연도별 수치 표·탐지 목록(방법 필터·정렬).
- z-score·전년 대비 증가율 탐지기, 주입 시나리오 생성과 실험 평가 실행기.
- 실시간 탐지·기준선 API, 저장된 시나리오 조회, 해외 기관 목록의 페이지 조회.
- Mac·Windows용 VS Code 설정과 개발 환경 확인 스크립트.
- 수집·탐지·실험용 패키지와 폴더 구조.
- OpenAlex 2025년 한국 기관 참여 논문 샘플 수집기, 오프라인 결과 검증과 자동 테스트.
- 샘플 정제·기관 쌍 집계·협력 비중·논문별 근거와 원본 5편 대조 검증.

데이터 v1은 네 분야별 토픽 하나씩을 사용한 2015~2025년 집계입니다.
필수 주입 실험의 기준에 맞는 기관 쌍 26개를 확보했습니다.
국가 집계와 분석 화면의 기준선·시나리오 연결은 이후 작업입니다.

## 문서

- [11/13 프론트 통합·실험 비교 진행](docs/frontend-progress-2026-11-13.md)

- [2015~2025년 데이터 v1 · 분야 정의·수집·검증](docs/period-v1.md) · [집계·시나리오 ZIP](data/sample/actual/four_fields_2015_2025_v1.zip)
- [11월 11일 기간 파일럿 검증](docs/period-pilot.md) · [파일럿 집계 ZIP](data/sample/actual/four_fields_2015_2025_pilot.zip)
- [반도체·AI·바이오·양자 실제 집계 샘플](data/sample/actual/four_fields_2025_sample/README.md) · [집계 ZIP](data/sample/actual/four_fields_2025_sample.zip)
- [공유용 실제 집계 샘플: AI·2025년](data/sample/actual/ai_2025_sample/README.md) · [집계만 ZIP 다운로드](https://raw.githubusercontent.com/Web-base-system-project-1/webbasesystem_project1/main/data/sample/actual/ai_2025_sample.zip)

- [11/8 프론트 진행 기록](docs/frontend-progress-2026-11-08.md)

- [기간별 역할 일정과 AI 작업 방식](schedule.md)
- [OpenAlex 샘플 수집·결과 확인](docs/collection.md)
- [샘플 정제·기관 쌍 집계·검증 결과](docs/processing.md)
- [전체 환경 설정](setting.md)
- [API 명세](docs/api.md)
- [데이터 형식 초안](docs/data-schema.md)

Git에는 기본 데이터 v1 ZIP, 예시 데이터, 재생성 코드를 공유합니다. `.venv/`, `.env`, 원본, 로컬 실험 출력은 Git에서 제외합니다.
