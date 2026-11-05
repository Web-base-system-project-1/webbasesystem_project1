# Project 7 개발 환경 설정 가이드

이 문서는 `webbasesystem_project1` 공용 레포를 Mac·Windows 팀원이 같은 방식으로 준비하고 실행하기 위한 안내입니다. 폴더 이름은 `webbasesystem_project1`이고, 과제 주제는 **Project 7: 국제 공동연구 변화 분석**입니다.

**각자 자신의 운영체제 절차만 따라 하세요.** 모든 터미널 명령은 별도 설명이 없으면 `requirements.txt`와 이 파일이 있는 프로젝트 최상위 폴더에서 실행합니다.

## 1. 준비물과 설치 범위

| 항목 | 팀 기준 | 확인 방법 |
|---|---|---|
| Python | 3.12.x | Mac `python3.12 --version`, Windows `py -3.12 --version` |
| VS Code | 설치된 버전 사용 | Python 관련 확장 설치 |
| Git | GitHub 공동 작업에 사용 | `git --version` |
| 가상환경 | 프로젝트 안의 `.venv` | 팀원 각자 생성 |
| OpenAlex API 키 | 논문 수집을 시작할 때 필요 | 각자 `.env`에 입력 |

- Python: <https://www.python.org/downloads/>
- VS Code: <https://code.visualstudio.com/>
- Git: <https://git-scm.com/downloads>

Python 3.12가 없으면 먼저 설치합니다. Windows에서는 설치 시 Python Launcher도 설치하고, 터미널에서 Python을 사용할 수 있도록 설치 옵션을 확인합니다. 설치 후 VS Code 터미널을 새로 엽니다.

홈페이지·API 상태 확인에는 OpenAlex 키가 필요 없습니다. 샘플 논문 수집은 15번과 [샘플 수집 안내](docs/collection.md), 정제·집계는 16번과 [정제·집계 안내](docs/processing.md)를 참고하세요. 전체 범위 수집과 탐지는 다음 개발 단계입니다.

## 2. 공용 레포 열기

### 이미 이 폴더가 있는 팀장

VS Code에서 **파일 → 폴더 열기 → `webbasesystem_project1` 선택**을 합니다. 상위의 웹기반시스템 폴더 전체가 아니라 이 프로젝트 폴더를 열어야 `.vscode` 설정이 바로 적용됩니다.

현재 Mac의 폴더 위치:

```text
/Users/minjoonk/Documents/2026 2학기/웹기반시스템/webbasesystem_project1
```

### GitHub에서 내려받는 팀원

팀장이 GitHub에 업로드하고 팀원을 초대한 뒤 진행합니다. 아래 URL 자리를 실제 공용 레포 주소로 바꿉니다. 이미 clone한 폴더에서 다시 clone하지 않습니다.

```bash
git clone "여기에-실제-GitHub-레포-URL" webbasesystem_project1
cd webbasesystem_project1
```

VS Code에서 방금 만든 폴더를 엽니다. `code` 명령이 설정돼 있으면 `code .`를 사용할 수 있고, 명령이 없으면 파일 메뉴에서 열면 됩니다.

터미널 위치 확인:

```bash
pwd
```

Windows PowerShell에서는 `Get-Location`으로도 확인할 수 있습니다. 경로의 마지막이 `webbasesystem_project1`이어야 합니다.

## 3. Mac 최초 설정

VS Code의 zsh 또는 bash 터미널에서 순서대로 실행합니다. 이 절차는 최초 한 번입니다.

### 3-1. Python 버전 확인

```bash
python3.12 --version
```

예상 결과: `Python 3.12.x`.

`python3`가 다른 버전을 가리킬 수 있으므로 **가상환경을 만들 때는 `python3.12`를 명시**합니다.

### 3-2. 가상환경 생성·활성화

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

이미 이 프로젝트의 `.venv`가 만들어져 있다면 생성 명령은 생략하고 활성화부터 진행합니다. 가상환경 안에는 소스 코드를 넣지 않습니다.

### 3-3. 공통 패키지 설치

```bash
python -m pip install --upgrade "pip==25.3"
python -m pip install -r requirements-lock.txt
```

본 프로젝트에서 확인한 pip 25.3을 사용합니다. `requirements.txt`는 사용할 패키지의 범위, `requirements-lock.txt`는 함께 검증한 구체적인 버전 목록입니다. 팀원 최초 설치에는 lock 파일을 사용합니다.

### 3-4. 개인 환경 변수 파일 생성

아래 명령은 `.env`가 없을 때만 예시를 복사하므로 기존 키를 덮어쓰지 않습니다.

```bash
python -c "from pathlib import Path; p=Path('.env'); p.exists() or p.write_bytes(Path('.env.example').read_bytes())"
```

수집을 시작할 때 VS Code에서 `.env`를 열어 자신의 키를 입력합니다.

```dotenv
OPENALEX_API_KEY=자신의_API_키
```

`.env`와 API 키는 GitHub에 업로드하지 않습니다. `.env.example`에는 변수 이름과 설명만 둡니다.

## 4. Windows 최초 설정

VS Code 터미널 종류를 **PowerShell**로 선택하고 순서대로 실행합니다.

### 4-1. Python 버전 확인

```powershell
py -3.12 --version
```

예상 결과: `Python 3.12.x`.

`py` 명령이 없지만 `python --version`이 정확히 3.12.x라면 다음 절차의 `py -3.12 -m venv .venv` 대신 `python -m venv .venv`를 사용해도 됩니다. 둘 다 안 되면 Python 3.12 설치부터 확인합니다.

### 4-2. 가상환경 생성·활성화

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

이미 이 프로젝트의 `.venv`가 있다면 생성 명령은 생략합니다.

### 4-3. 패키지 설치·환경 변수 파일 생성

활성화에 성공했다면:

```powershell
python -m pip install --upgrade "pip==25.3"
python -m pip install -r requirements-lock.txt
python -c "from pathlib import Path; p=Path('.env'); p.exists() or p.write_bytes(Path('.env.example').read_bytes())"
```

### PowerShell 실행 정책 때문에 활성화가 차단되는 경우

활성화는 편의를 위한 기능입니다. 정책을 변경하지 않고 가상환경 Python을 직접 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade "pip==25.3"
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -c "from pathlib import Path; p=Path('.env'); p.exists() or p.write_bytes(Path('.env.example').read_bytes())"
.\.venv\Scripts\python.exe scripts/check_setup.py
.\.venv\Scripts\python.exe -m flask --app web.app run --debug --port 5001
```

이 방식을 선택했다면 이후 명령의 맨 앞 `python`도 `.\.venv\Scripts\python.exe`로 바꿉니다. VS Code의 이 프로젝트 전용 작업(Task) 역시 가상환경 Python을 직접 사용합니다.

명령 프롬프트(cmd.exe)를 사용하는 팀원은 활성화 명령만 다음으로 바꿉니다.

```bat
.venv\Scripts\activate.bat
```

## 5. 환경 확인: Mac·Windows 공통

다음 명령은 프로젝트 가상환경이 활성화된 터미널에서 실행합니다. Windows에서 활성화를 생략했다면 위에서 안내한 Python 실행 경로를 사용합니다.

### 5-1. 실행 중인 Python 확인

```bash
python -c "import sys; print('Python:', sys.version); print('Interpreter:', sys.executable); print('venv:', sys.prefix != sys.base_prefix); assert sys.prefix != sys.base_prefix"
```

정상 기준:

- Python 3.12.x
- 실행 경로에 이 프로젝트의 `.venv` 포함
- `venv: True`

### 5-2. 패키지 확인

```bash
python -m pip check
python -c "import flask, requests, pandas, numpy, yaml, dotenv, pytest; print('Package imports OK')"
```

정상 결과:

```text
No broken requirements found.
Package imports OK
```

### 5-3. 통합 환경 확인 스크립트

```bash
python scripts/check_setup.py
```

확인하는 내용:

1. Python 버전과 이 프로젝트의 가상환경 사용 여부
2. 필수 파일·폴더 존재 여부
3. VS Code 설정 JSON 형식
4. 필요한 패키지 import와 `pip check`
5. Flask 메인 HTML·JavaScript·CSS 응답
6. `/api/health`의 `200`과 `{"status": "ok"}` 응답

마지막에 다음이 나오면 자동 확인을 통과한 것입니다.

```text
Setup check PASSED. Start Flask and check the browser next.
```

`[FAIL]`이 있으면 해당 항목을 해결한 뒤 다시 실행합니다. 이 스크립트는 OpenAlex에 요청하지 않고, 브라우저의 JavaScript 실행까지 확인하지는 않습니다. 다음 단계에서 실제 브라우저도 확인합니다.

## 6. Flask 실행·브라우저 확인

```bash
python -m flask --app web.app run --debug --port 5001
```

터미널에 `Running on http://127.0.0.1:5001`이 나오면 서버가 실행 중입니다. 이 터미널을 켜둔 채 브라우저를 엽니다.

| 주소 | 정상 결과 |
|---|---|
| <http://127.0.0.1:5001/> | 국제 공동연구 변화 분석 제목과 `API 연결: ok` |
| <http://127.0.0.1:5001/api/health> | `{"status":"ok"}` |

HTML 파일을 더블클릭하거나 Live Server로 여는 대신 **위 Flask 주소를 사용**합니다. `index.html`은 Flask 템플릿이고, JavaScript의 상대 경로 `/api/health`도 Flask 서버를 기준으로 동작합니다.

터미널에서도 실제 HTTP 요청을 확인하려면 새 터미널을 열고:

Mac:

```bash
curl -f http://127.0.0.1:5001/api/health
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5001/api/health
```

서버 종료는 실행 중인 터미널에서 `Ctrl+C`입니다. 디버그 서버는 로컬 개발용으로 사용합니다.

## 7. VS Code 설정

`.vscode/`의 설정은 이 프로젝트 폴더를 열었을 때 적용됩니다. 다른 프로젝트나 VS Code 전역 설정은 변경하지 않습니다.

### 7-1. 추천 확장 설치

확장 탭에서 아래 확장을 설치합니다. 이미 설치돼 있으면 생략합니다.

- Python — Microsoft (`ms-python.python`)
- Python Debugger — Microsoft (`ms-python.debugpy`)
- Pylance — Microsoft (`ms-python.vscode-pylance`)

### 7-2. 인터프리터 선택

1. Mac `Cmd+Shift+P`, Windows `Ctrl+Shift+P`.
2. `Python: Select Interpreter` 실행.
3. 이 프로젝트의 `.venv` 선택.
4. 목록에 없으면 `Enter interpreter path`에서 다음 파일 지정.

| OS | 선택할 Python |
|---|---|
| Mac | `.venv/bin/python` |
| Windows | `.venv\Scripts\python.exe` |

`.vscode/settings.json`은 기본 인터프리터 위치를 `.venv`로 지정합니다. 예전에 다른 인터프리터를 선택한 이력이 있으면 위 절차로 다시 선택합니다. 인터프리터 선택 후 터미널을 새로 열고 확인합니다.

### 7-3. 실행·디버깅

- 일반 실행: 터미널에서 6번 명령 사용.
- VS Code 실행: 명령 팔레트 → `Tasks: Run Task` → **Project 7: Flask 서버 실행**.
- 디버깅: 실행 및 디버그 탭 → **Project 7: Flask 디버깅** → `F5`.
- 환경 확인: `Tasks: Run Task` → **Project 7: 환경 확인**.
- 패키지 동기화: `Tasks: Run Task` → **Project 7: 패키지 설치**.

F5와 일반 서버 실행을 동시에 켜면 같은 포트를 사용하므로 하나를 먼저 종료합니다. F5 디버깅 설정은 자동 재시작을 끄고 VS Code 디버거를 사용합니다. 일반 터미널 실행은 코드 변경 시 자동 재시작합니다.

## 8. 다음 날 개발을 다시 시작할 때

### Mac

```bash
source .venv/bin/activate
python -m flask --app web.app run --debug --port 5001
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
python -m flask --app web.app run --debug --port 5001
```

가상환경 종료:

```bash
deactivate
```

가상환경 생성·전체 설치를 매일 반복할 필요는 없습니다. 패키지 목록이 변경됐을 때만 다음을 다시 실행합니다.

```bash
python -m pip install -r requirements-lock.txt
python scripts/check_setup.py
```

## 9. 폴더 구조와 역할

```text
webbasesystem_project1/
├── .vscode/                  # 인터프리터·실행·디버깅 설정
├── pipeline/                 # 1번: collect / preprocess / aggregate
├── detectors/                # 2번: zscore / growth
├── experiments/              # 2번: inject / evaluate / correct
├── web/
│   ├── app.py                # 3번: Flask 서버·API
│   ├── templates/index.html  # 4번: HTML
│   └── static/
│       ├── css/style.css     # 4번: CSS
│       └── js/
│           ├── main.js       # 4번: 화면 초기화
│           ├── api/client.js # 서버 요청
│           ├── charts/       # 차트
│           └── components/   # 필터·목록·설정 패널
├── scripts/check_setup.py    # 공통 환경 확인
├── config/                  # 분야 정의·실험 설정
├── data/
│   ├── raw/                 # Git 제외, 수집 시 생성
│   ├── processed/           # Git 제외, 가공 시 생성
│   └── sample/              # Git 공유용 작은 예시 데이터
├── results/                 # Git 제외, 실험 시 생성
├── tests/                   # 집계·탐지·평가 계산 검증
├── docs/
│   ├── api.md
│   └── data-schema.md
├── requirements.txt         # 패키지 허용 범위
├── requirements-lock.txt    # 함께 검증한 설치 버전
├── .env.example             # 공유용 환경 변수 양식
├── .env                     # 각자 생성, Git 제외
├── .venv/                   # 각자 생성, Git 제외
├── .gitignore
├── README.md
└── setting.md
```

Git은 빈 폴더를 저장하지 않습니다. `.gitkeep`이 있는 폴더는 공유되고, `data/raw`, `data/processed`, `results`는 clone 직후 없어도 정상입니다. 필요하면 두 OS 모두 다음으로 생성할 수 있습니다.

```bash
python -c "from pathlib import Path; [Path(p).mkdir(parents=True, exist_ok=True) for p in ('data/raw', 'data/processed', 'results')]"
```

역할 간 경계:

- 1번은 집계·협력 비중 데이터까지 제공합니다.
- 2번은 웹과 독립적으로 호출할 수 있는 분석 함수를 만듭니다.
- 3번은 해당 함수를 Flask API에 연결합니다.
- 4번은 상대 주소 `/api/...`로 결과를 받아 표시합니다.
- 3번이 탐지 결과 표·What-if 패널 구현을 지원하고 4번이 전체 화면을 통합합니다.
- 데이터 형식과 API 변경은 관련 담당자에게 알리고 `docs/`도 함께 수정합니다.

현재 `pipeline/collect.py`의 샘플 수집과 `pipeline/preprocess.py`·`pipeline/aggregate.py`의 샘플 정제·집계가 구현되어 있습니다. 전체 범위 수집·정제·집계와 탐지·실험은 다음 단계입니다. 환경 확인은 `python scripts/check_setup.py`, 전체 자동 테스트는 `python -m pytest -q`로 실행합니다.

## 10. 패키지를 추가하거나 버전을 바꿀 때

담당자 한 명이 프로젝트 가상환경에서 진행하고, 팀원은 변경된 lock 파일로 설치합니다.

1. 필요한 직접 의존성을 `requirements.txt`에 추가·수정합니다.
2. 아래 명령으로 설치하고 환경·계산 검증을 수행합니다.

```bash
python -m pip install -r requirements.txt
python -m pip check
```

3. Mac·Windows 공통 명령으로 구체적인 버전 목록을 갱신합니다. PowerShell 리다이렉션의 인코딩 차이를 피하기 위해 Python으로 기록합니다.

```bash
python -c "import subprocess, sys; from pathlib import Path; Path('requirements-lock.txt').write_bytes(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze']))"
python scripts/check_setup.py
```

4. `requirements.txt`와 `requirements-lock.txt` 변경을 같은 PR에 넣습니다.

이 lock 파일은 pip freeze로 만든 버전 목록입니다. 운영체제별 패키지·설치 가능 여부는 각 OS에서 확인해야 하며, Mac의 실행 결과만으로 Windows 실행을 완료했다고 간주하지 않습니다.

## 11. GitHub에 올리기와 팀 작업

이 폴더에 로컬 Git 저장소가 준비돼 있다면 `git init`은 반복할 필요가 없습니다. 새 폴더에서 시작하는 경우에만:

```bash
git init -b main
```

업로드 전에 제외 규칙 확인:

```bash
git status --short --ignored
git check-ignore .venv/ .env data/raw/ data/processed/ results/
```

`.venv`, `.env`, 대용량 데이터와 결과가 제외돼야 합니다. 소스·설정·문서·작은 예시 데이터·lock 파일은 공유합니다.

팀장이 GitHub에서 README 등 초기 파일을 추가하지 않은 빈 레포를 만들고, 실제 URL로 아래 명령을 실행합니다. 이미 원격 레포가 연결돼 있으면 `git remote -v`로 확인하고 `remote add`는 생략합니다.

```bash
git add .
git status --short
git commit -m "chore: set up Project 7 development environment"
git remote add origin "여기에-실제-GitHub-레포-URL"
git push -u origin main
```

공유 전 `git status`에서 `.env`나 `.venv`가 스테이징되지 않았는지 확인합니다. Git 사용자 이름·이메일 설정 오류가 발생하면 본인의 정보를 로컬 레포에 설정한 후 다시 커밋합니다.

기능 개발 예시:

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/zscore-detector
```

작업 파일을 커밋·푸시하고 GitHub에서 `main` 대상 PR을 만듭니다. 최소 한 명이 확인한 뒤 병합합니다. 커밋하지 않은 변경이 있으면 먼저 자신의 작업을 정리하고 브랜치를 전환합니다. 기능별 브랜치를 사용하고, 며칠씩 통합을 미루지 않습니다.

## 12. 문제 해결

| 증상 | 확인·해결 |
|---|---|
| `python3.12` 또는 `py -3.12` 없음 | Python 3.12 설치 후 새 터미널 열기 |
| `venv: False` | 활성화하거나 `.venv`의 Python 경로로 직접 실행 |
| 가상환경인데 확인 스크립트가 실패 | 다른 프로젝트 가상환경인지 실행 경로 확인 |
| `No module named flask` 등 | 올바른 가상환경에서 `python -m pip install -r requirements-lock.txt` |
| PowerShell 스크립트 실행 차단 | 4번의 `python.exe` 직접 실행 방식 사용 |
| VS Code에서 import 밑줄 | `Python: Select Interpreter`에서 이 프로젝트 `.venv` 선택 |
| `No module named web` | 프로젝트 최상위에서 실행하는지 확인 |
| `TemplateNotFound` | `web/templates/index.html` 위치 확인 |
| API는 정상이지만 화면은 실패 | Flask 주소로 접속했는지 확인하고 개발자 도구의 Console·Network 확인 |
| `5001` 포트가 이미 사용 중 | 기존 서버를 `Ctrl+C`로 종료하거나 아래처럼 다른 포트 사용 |
| 키가 없어서 수집 불가 | `.env`에 자신의 키 입력. 홈페이지 확인에는 키 불필요 |
| `pytest`에서 테스트 없음 | 아직 계산 테스트를 작성하지 않은 상태. 환경 확인은 `scripts/check_setup.py` 사용 |

`No module named pip.__main__`가 나오면 가상환경의 pip 설치를 복구합니다. 아래 명령은 시스템 pip를 통해 **이 프로젝트 가상환경의 pip만** 재설치합니다.

Mac:

```bash
python3.12 -m pip --python .venv/bin/python install --force-reinstall "pip==25.3"
```

Windows:

```powershell
py -3.12 -m pip --python .venv/Scripts/python.exe install --force-reinstall "pip==25.3"
```

그다음 패키지 설치와 환경 확인을 다시 진행합니다.

다른 포트 사용 예시:

```bash
python -m flask --app web.app run --debug --port 5002
```

이 경우 브라우저도 <http://127.0.0.1:5002/>로 접속합니다. 프론트는 상대 주소를 사용하므로 코드에서 포트를 바꿀 필요는 없습니다.

## 13. 팀원별 최종 체크리스트

- [ ] `webbasesystem_project1`을 VS Code의 루트 폴더로 열었다.
- [ ] Python 3.12.x를 사용한다.
- [ ] 각자 `.venv`를 만들었다.
- [ ] `requirements-lock.txt`로 패키지를 설치했다.
- [ ] VS Code에서 이 프로젝트의 Python을 선택했다.
- [ ] `.env.example`을 `.env`로 복사했다.
- [ ] `python scripts/check_setup.py`가 PASSED다.
- [ ] 실제 서버를 켜고 화면에 `API 연결: ok`가 보인다.
- [ ] `.env`와 `.venv`가 Git에서 제외된다.
- [ ] 역할별 폴더와 데이터·API 합의 문서를 확인했다.

## 14. 공식 참고 문서

- Python 가상환경·OS별 활성화: <https://docs.python.org/3/library/venv.html>
- Flask 실행·템플릿·정적 파일: <https://flask.palletsprojects.com/en/stable/quickstart/>
- VS Code Python 환경: <https://code.visualstudio.com/docs/python/environments>
- VS Code Python 설정: <https://code.visualstudio.com/docs/python/settings-reference>
- VS Code Python 디버깅: <https://code.visualstudio.com/docs/python/debugging>
- GitHub 협업 흐름: <https://docs.github.com/en/get-started/using-github/github-flow>

## 15. 1번 담당자: OpenAlex 샘플 수집

1. 가상환경을 활성화합니다.
2. 프로젝트 `.env`에 본인의 실제 `OPENALEX_API_KEY`를 입력합니다.
3. 실제 토픽 ID를 확인하고 수집합니다. 아래 `T11636`은 실행 확인용 AI 하위 토픽 예시입니다.

```bash
python -m pipeline.collect --topic-id T11636 --limit 100 --output-dir data/raw/ai_2025_sample
python scripts/check_sample.py data/raw/ai_2025_sample
```

같은 출력 폴더가 이미 있으면 덮어쓰지 않습니다. 다시 수집하려면 `--output-dir`을 생략해 실행별 폴더를 자동 생성하거나 새 폴더 이름을 지정합니다.

Windows에서 가상환경을 활성화하지 않았다면:

```powershell
.\.venv\Scripts\python.exe -m pipeline.collect --topic-id T11636 --limit 100 --output-dir data/raw/ai_2025_sample
.\.venv\Scripts\python.exe scripts/check_sample.py data/raw/ai_2025_sample
```

실행 옵션·저장 파일·오류 처리와 실제 결과 확인 방법은 [docs/collection.md](docs/collection.md)에 설명했습니다. 100편 샘플은 파이프라인 검증용이며, 전체 수집과 집계는 다음 단계에서 진행합니다.

## 16. 1번 담당자: 샘플 정제·집계

수집한 100편으로 기본 국내 기관 유형을 적용한 국제 공동연구 샘플을 만들고 집계합니다. 오프라인 처리이므로 이 단계에서는 API 키를 사용하지 않습니다.

```bash
python -m pipeline.preprocess --input data/raw/ai_2025_sample/sample.json --output-dir data/processed/ai_2025_sample
python -m pipeline.aggregate --input data/processed/ai_2025_sample/clean_works.json
python scripts/check_aggregation.py data/processed/ai_2025_sample --manual-reference data/sample/manual_expected.json
python -m pytest -q
```

위 기본 경로는 이미 실행해 결과가 만들어진 상태입니다. 재실행할 때는 정제 출력 폴더 이름을 새로 지정하고, 이후 집계·검증 경로도 같은 폴더로 바꿉니다. Windows에서 가상환경을 활성화하지 않았다면 `python`을 `.\.venv\Scripts\python.exe`로 바꿉니다.

실제 샘플은 100편에서 33편을 유지했고, 국내 기관 31곳·기관 쌍 158개로 집계됐습니다. 제외 사유, 국내 병원 포함 옵션, 집계 근거, CSV 형식과 원본 5편 대조 결과는 [docs/processing.md](docs/processing.md)를 참고하세요. 전체 기간 5편 이상 조건은 최종 기간 수집 후 적용합니다.
