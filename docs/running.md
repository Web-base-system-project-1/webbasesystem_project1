# 팀원용 설치·실행 안내

## 1. 준비

- Python 3.12 설치 확인: Mac은 `python3.12 --version`, Windows는 `py -3.12 --version`.
- Node.js·npm 설치 확인: `node -v`, `npm -v`. 이 프로젝트는 Node 22.21.1과 npm 10.9.4에서 확인했습니다.
- VS Code에서 `webbasesystem_project1` 자체를 폴더로 엽니다.
- PR 검토 시 `feat/react-frontend` 브랜치를 사용하고, 병합 후에는 통합된 main을 사용합니다.
- 아래 터미널은 모두 프로젝트 최상위 폴더에서 시작합니다.

Python 설치·VS Code 설정 상세는 [setting.md](../setting.md)를 참고하세요.
React는 별도로 전역 설치하지 않습니다. `npm ci`가 프로젝트에 필요한 React 패키지까지 설치합니다.

## 2. 최초 설치

이미 이 프로젝트의 `.venv`가 있으면 생성 명령을 생략합니다.

### Mac

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade "pip==25.3"
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python scripts/check_setup.py
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade "pip==25.3"
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts/check_setup.py
```

### React 패키지 설치 — Mac·Windows 공통

```bash
cd frontend
npm ci
cd ..
```

`node_modules`와 `.venv`는 각자 생성하며 Git에 올리지 않습니다.
`package-lock.json`이 바뀌면 `frontend/`에서 `npm ci`를 다시 실행합니다.
저장소의 데이터 v1 ZIP으로 화면을 실행할 때는 OpenAlex API 키가 필요 없습니다.
기존 `.env`의 `DATA_DIR`에 다른 데이터 경로가 있으면 그 경로가 우선합니다. 기본 데이터 v1을 사용하려면 해당 값을 비우고 Flask를 다시 시작하세요.

## 3. 매번 실행 — 터미널 두 개

### 터미널 1: Flask 백엔드

Mac:

```bash
.venv/bin/python -m flask --app web.app run --debug --port 5001
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m flask --app web.app run --debug --port 5001
```

`http://127.0.0.1:5001/api/health`에서 `{"status":"ok"}`를 확인합니다.
`http://127.0.0.1:5001/api/meta`에서 데이터 버전과 2015~2025년 범위를 확인할 수 있습니다.

### 터미널 2: React 프론트엔드

프로젝트 최상위에서 새 터미널을 열고 실행합니다.

```bash
cd frontend
npm run dev
```

브라우저에서 **http://127.0.0.1:5173/** 을 엽니다.
5001은 Flask 주소, 5173은 React 화면 주소입니다.
두 터미널은 켜둡니다. 종료하려면 각각 `Ctrl+C`를 누릅니다.
`index.html`을 더블클릭하거나 Live Server로 열지 않습니다.

## 4. 자주 생기는 문제

| 증상 | 확인할 것 |
| --- | --- |
| npm 명령을 찾을 수 없음 | Node.js·npm 설치 후 새 터미널 열기 |
| package.json을 찾지 못함 | React 명령은 frontend/에서 실행 |
| flask 모듈이 없음 | 프로젝트 .venv의 Python으로 패키지 설치·실행 |
| 화면은 열리지만 데이터 조회 실패 | Flask 실행 여부와 /api/health 확인 |
| 5001 또는 5173 포트가 사용 중 | 이미 실행한 서버 확인. 같은 서버를 중복 실행하지 않기 |
| API 요청이 연결되지 않음 | Flask는 5001에서 실행. 포트 변경 시 frontend/vite.config.js의 프록시 대상도 함께 수정 |

`npm run build`는 배포용 파일을 만드는 명령입니다. 평소 개발·시연에는 `npm run dev`를 사용합니다.
현재 Vite 프록시는 개발용이며 최종 배포 방식은 별도 확정합니다.
