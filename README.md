# 국제 공동연구 변화 분석 · Project 7

OpenAlex의 국내–해외 기관 공동연구 데이터를 수집하고, 협력 비중의 변화를 탐지·분석하는 웹기반시스템 팀 프로젝트입니다.

저장 폴더 이름은 `webbasesystem_project1`이며, 과제 주제는 Project 7입니다.

## 처음 시작하기

**Mac·Windows 설치, 가상환경 생성, VS Code 설정, 실행·확인은 [setting.md](setting.md)를 순서대로 따라 하세요.**

Python 3.12를 사용합니다. 가상환경을 만든 다음:

```bash
python -m pip install -r requirements-lock.txt
python scripts/check_setup.py
python -m flask --app web.app run --debug --port 5001
```

브라우저: <http://127.0.0.1:5001/>

## 역할과 위치

| 담당 | 위치 | 작업 |
|---|---|---|
| 1번 | `pipeline/`, `config/`, `data/sample/` | 분야 정의·수집·정제·집계 |
| 2번 | `detectors/`, `experiments/` | 탐지·주입·평가·보정 |
| 3번 | `web/app.py`, `.vscode/`, `scripts/` | Flask API·통합·실행 환경 |
| 4번 | `web/templates/`, `web/static/` | HTML·CSS·JS·시각화·화면 연동 |
| 공동 | `tests/`, `docs/` | 계산 검증·문서·인터페이스 합의 |

## 현재 구현 범위

- 메인 페이지, API 연결 상태 표시, `/api/health`.
- Mac·Windows용 VS Code 설정과 개발 환경 확인 스크립트.
- 수집·탐지·실험용 패키지와 폴더 구조.

데이터 수집, 탐지 알고리즘, 실제 분석 화면은 이후 각 담당자가 구현합니다.

## 문서

- [전체 환경 설정](setting.md)
- [API 명세](docs/api.md)
- [데이터 형식 초안](docs/data-schema.md)

`.venv/`, `.env`, 대용량 데이터, 실험 결과는 Git에서 제외합니다. 작은 예시 데이터와 재생성 코드는 공유합니다.
