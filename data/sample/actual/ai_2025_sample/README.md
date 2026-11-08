# 실제 집계 샘플 · AI / 2025 / T11636

OpenAlex에서 실제 수집한 논문으로 만든 **연결·집계 검증용 샘플**입니다.
가상 예시 데이터와 구분하기 위해 별도 폴더에 보관합니다.

- 입력: 2025년 한국 기관 참여, 대표 토픽 T11636인 논문의 첫 페이지 최대 100편.
- 유지한 국제 공동연구 논문: 33편.
- 국내 기관 31곳, 해외 기관 123곳, 국내–해외 기관 쌍 158개.
- 범위: AI 하위 토픽 하나의 2025년 샘플. 전체 AI·전체 기간의 통계가 아니며 무작위 표본도 아닙니다.
- 데이터 버전·출처 해시·규칙·파일별 해시: MANIFEST.json.

## 받는 방법

프로젝트의 main 브랜치에서 git pull --ff-only를 실행하면 이 폴더도 내려받습니다.
이 집계만 따로 받으려면 [ZIP 다운로드](https://raw.githubusercontent.com/Web-base-system-project-1/webbasesystem_project1/main/data/sample/actual/ai_2025_sample.zip)를 사용하세요.
압축을 풀면 ai_2025_sample/ 폴더에 CSV 6개, 이 설명서, MANIFEST.json이 있습니다.

수집 API 키나 원본 JSON 없이 CSV를 읽을 수 있습니다.

## 파일과 행의 의미

| 파일 | 행 수 | 한 행의 의미 |
|---|---:|---|
| collab_shares.csv | 158 | 국내 기관 × 해외 기관 × 분야 × 연도별 건수·분모·비중 |
| collab_counts.csv | 158 | 같은 기관 쌍·분야·연도의 공동논문 수 |
| kr_totals.csv | 31 | 국내 기관 × 분야 × 연도별 국제 공동논문 총수 |
| institutions_kr.csv | 31 | 국내 기관 ID·이름·유형·ROR |
| pair_contributions.csv | 165 | 해당 기관 쌍의 건수에 기여한 논문 ID |
| total_contributions.csv | 52 | 해당 국내 기관 총수에 기여한 논문 ID |

모든 CSV는 UTF-8이며 첫 줄이 열 이름입니다. 기관·논문 ID는 OpenAlex 전체 URL입니다.

### 분석에 사용할 기본 파일

collab_shares.csv의 열:

| 열 | 의미 |
|---|---|
| domestic_id | 국내 기관 ID |
| foreign_id | 해외 기관 ID |
| field | 분야 코드, 현재 ai |
| year | 연도, 현재 2025 |
| collab_count | 해당 기관 쌍의 공동논문 수 |
| international_total | 해당 국내 기관·분야·연도의 국제 공동논문 총수 |
| share | collab_count / international_total, 0~1 |

한 논문에 해외 기관 여러 곳이 참여해도 국내 기관 총수에는 한 번만 기여합니다.
international_total을 해외 기관별 collab_count의 합으로 계산하지 않습니다.
같은 국내 기관의 파트너별 share 합은 1을 넘을 수 있습니다.
33편·기관 쌍 기여 165건·국내 기관 총수 기여 52건은 서로 다른 수치입니다.

프로젝트 최상위에서 Python으로 읽는 예:

~~~python
import pandas as pd

df = pd.read_csv(
    "data/sample/actual/ai_2025_sample/collab_shares.csv",
    encoding="utf-8",
)
print(df.head())
~~~

## 담당자별 사용

- 2번: CSV 열·기관 ID와 함수 입출력 연결을 확인합니다. 과거 k년 기준선·전년 대비 탐지·주입 성능 평가는 여러 연도의 데이터가 추가된 뒤 진행합니다.
- 3번: 로컬 .env에 아래 DATA_DIR을 설정하고 Flask를 다시 시작하면 실제 샘플 조회 API를 사용할 수 있습니다.
- 4번: 3번이 해당 데이터 폴더를 선택한 뒤 기존 API로 타임라인·기관 목록을 확인합니다.

~~~dotenv
DATA_DIR=data/sample/actual/ai_2025_sample
~~~

ZIP만 받은 경우에는 압축을 푼 ai_2025_sample 폴더의 절대 경로를 DATA_DIR로 지정해도 됩니다.
OPENALEX_API_KEY는 조회에 사용하지 않습니다.

이 폴더에는 해외 기관 이름·국가 파일, 탐지·주입 결과가 없습니다.
API의 해외 기관 이름은 ID로 표시되고 국가는 null, 탐지·주입 목록은 빈 목록입니다.
해외 기관 정보를 위한 institutions_foreign.csv는 다음 데이터 작업에서 추가합니다.

## 출처·규칙·검증

- 국내 기관 유형: education, facility, government. 국내 healthcare는 제외.
- 해외 기관: 국가가 확인된 KR 이외 기관. 해외 기관 유형은 제한하지 않음.
- 논문별 기관 ID 중복 제거, 전체 고유 기관 수가 50곳 초과인 논문 제외.
- 서로 다른 OpenAlex ID를 이름·ROR·상위 기관 정보만으로 자동 병합하지 않음.
- 전체 기간 국제 공동논문 5편 이상 조건은 아직 적용하지 않음.
- 공개 전 원본·정제 입력 해시, 논문별 기여, 분자·분모, 원본 5편의 별도 기준값 대조를 통과했습니다.
- 원본 응답·정제 JSON·개인 설정·실험 결과는 이 공유본에 포함하지 않습니다.

공유본의 파일 해시를 확인하려면 이 폴더에서 다음 명령을 실행합니다(Mac·Windows 공통, Python 사용).

~~~bash
python -c "import hashlib,json; from pathlib import Path; p=Path('.'); m=json.loads((p/'MANIFEST.json').read_text(encoding='utf-8')); assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==v['sha256'] for n,v in m['files'].items()), 'checksum mismatch'; print('CSV checksum verification passed')"
~~~

검증한 원래 집계 CSV를 UTF-8/LF로 공유하며, MANIFEST.json에 원래 파일 해시와 공유 파일 해시를 각각 기록합니다.
전체 원본이 필요한 검증 명령은 원본을 보유한 컴퓨터에서 실행합니다.

자세한 문서:
[수집](https://github.com/Web-base-system-project-1/webbasesystem_project1/blob/main/docs/collection.md),
[데이터 형식](https://github.com/Web-base-system-project-1/webbasesystem_project1/blob/main/docs/data-schema.md),
[정제·집계](https://github.com/Web-base-system-project-1/webbasesystem_project1/blob/main/docs/processing.md).
