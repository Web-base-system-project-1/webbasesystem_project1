# OpenAlex 샘플 수집

1번 데이터 담당자의 첫 단계입니다. 2025년 한국 기관 참여 논문 중, 실행 시 지정한 대표 토픽의 논문을 **최대 100편** 받아 저장합니다. 초기 수집·집계 코드 검증용 샘플이며, 전체 공동논문 수의 추정값으로 사용하지 않습니다.

## 1. 준비

프로젝트 최상위에서 실행합니다. 가상환경 준비는 [setting.md](../setting.md)를 참고하세요.

Mac:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShell 활성화가 차단되면 아래 명령의 `python`을 `.\.venv\Scripts\python.exe`로 바꿔 실행합니다.

프로젝트 `.env`에 자신의 키를 입력합니다.

```dotenv
OPENALEX_API_KEY=자신의_실제_API_키
```

수집기는 이 프로젝트 `.env`의 값을 읽습니다. 키를 실행 인자로 받지 않고, 요청의 `Authorization: Bearer ...` 헤더로만 보냅니다. 요청 URL·조회 조건·콘솔·CSV 로그에 키를 넣지 않습니다. 키가 비어 있으면 네트워크 요청 전에 종료합니다.

키 발급·이메일 인증은 [OpenAlex 공식 인증 안내](https://help.openalex.org/api/authentication/)를 참고하세요.

## 2. 토픽 ID 선택

인자는 `T11636` 또는 `https://openalex.org/T11636` 형식을 받습니다. 토픽 이름을 그대로 인자로 넣지 않습니다.

**실행 예시 토픽:** [T11636 — Artificial Intelligence in Healthcare and Education](https://api.openalex.org/topics/T11636). 2026-11-05 공개 API에서 ID·이름과 해당 조건의 논문 응답을 확인했습니다.

이것은 AI의 한 하위 토픽에 대한 실행 예시입니다. 네 분야의 샘플 토픽과 선정 근거는 [파일럿 분야 정의](../config/field_definition_pilot.csv)에 있습니다. 2025년 샘플의 조회 조건과 집계 사용법은 [네 분야 집계 안내](../data/sample/actual/four_fields_2025_sample/README.md)에 기록했습니다.

## 3. 실행

### 권장: 실행마다 새 폴더 자동 생성

```bash
python -m pipeline.collect --topic-id T11636 --limit 100
```

기본값은 `--limit 100`, `--timeout 30`입니다. 조회 연도 2025와 국가 KR은 현재 샘플 수집기의 고정 조건입니다.

명령이 성공하면 수집한 고유 논문 수·중복 수와 저장 폴더를 출력합니다. 예를 들어:

```text
수집 완료: N편 (중복 M건)
저장 폴더: .../data/raw/ai_2025_T11636_실행UTC시각/
```

`N`과 `M`은 실제 응답에 따라 달라집니다. 최대 100편이므로 조회 대상이 적으면 더 적게 저장합니다. 응답이 0편이면 `count: 0`인 정상 결과로 남깁니다.

### 설명서대로 고정 폴더에 한 번 실행

```bash
python -m pipeline.collect --topic-id T11636 --limit 100 --timeout 30 --output-dir data/raw/ai_2025_sample
```

이 폴더가 이미 있으면 덮어쓰지 않고 종료합니다. 반복 수집은 `--output-dir`을 생략하거나 새 이름을 지정합니다. 상대 출력 경로는 프로젝트 최상위를 기준으로 합니다.

처음 연결 확인은 1편으로 해도 됩니다.

```bash
python -m pipeline.collect --topic-id T11636 --limit 1
```

`--limit`은 1~100, 읽기 `--timeout`은 0 초과~60초를 허용합니다. 연결 timeout은 5초입니다. 한 번의 수집은 목록 첫 페이지 한 장만 요청하며, 일시 오류에 대한 재시도 외에 추가 페이지는 요청하지 않습니다. 무작위 표본이 아니므로 대표성 분석에 사용하지 않습니다.

## 4. 조회·검증 조건

요청 필터:

```text
publication_year:2025,
authorships.institutions.country_code:KR,
primary_topic.id:실행_인자
```

API에서 `select=id,doi,title,publication_year,primary_topic,authorships`를 요청합니다. 저자별 소속 정보는 `authorships` 전체를 보존합니다.

저장 전에 각 논문에서 다음을 다시 검증합니다.

1. 올바른 OpenAlex 논문 ID가 있음.
2. `publication_year`가 2025임.
3. `primary_topic.id`가 지정한 토픽과 일치함.
4. `authorships[].institutions[]`에 `country_code: KR`인 기관이 있음.
5. 응답 건수가 요청 상한 이하임.

조건을 어긴 논문이 하나라도 있으면 성공 샘플을 만들지 않고 실패로 기록합니다. 중복된 논문 ID는 `sample.json`에서 한 번만 남기고 중복 수를 기록합니다. 응답 원본은 중복까지 보존합니다.

정제 단계에서는 국제 공동연구 여부, 대상 기관 유형, 기간 내 공동논문 수, 대형 공동연구 제외 조건과 ROR 정리를 추가합니다. 이번 구현 범위는 샘플 수집·입력 조건 검증까지입니다.

## 5. 저장 파일

```text
data/raw/실행별_폴더/
├── response.json        # API가 반환한 JSON 값 전체(select 기준)
├── sample.json          # 조건 검증을 통과한 고유 논문 목록
├── manifest.json        # 실행 조건·시간·상태·건수
└── collection_log.csv   # 요청·재시도·완료·실패 기록
```

- `response.json`: `meta`, `results` 등 API 응답 내용을 JSON으로 재저장합니다. 정렬·중복 제거·필드 재작성은 하지 않습니다.
- `sample.json`: `topic_id`, `year`, `country_code`, `count`, `results`. 논문의 ID·연도·대표 토픽·저자와 소속 기관 객체가 보존됩니다.
- `manifest.json`: 인증 정보가 없는 조회 조건, 시작·종료 UTC 시각, 상태, 응답 건수, 고유 논문 수, 중복 수, timeout과 샘플 목적.
- `collection_log.csv`: `request_id`, `collected_at`, `query`, `response_count`, `status`, `attempt`, `http_status`.

`meta.count`는 API의 전체 조회 대상 건수이고, `sample.json`의 `count`는 이번에 저장한 고유 논문 수입니다. 두 값의 의미를 구분합니다.

파일은 UTF-8로 저장합니다. `data/raw/`는 Git에서 제외됩니다. 팀에 공유할 작은 예시 데이터는 출처·샘플임을 표시하고 별도로 `data/sample/`에 정리합니다.

## 6. 저장 결과 확인

고정 폴더 실행 예시를 사용했다면:

```bash
python scripts/check_sample.py data/raw/ai_2025_sample
```

자동 생성 폴더를 사용했다면 인자만 실제 출력된 폴더 경로로 바꿉니다. 경로에 공백이 있으면 큰따옴표로 감쌉니다.

이 명령은 네트워크나 API 키를 사용하지 않고 다음을 확인합니다.

- 실행 상태가 `complete`인지.
- 원본 응답의 모든 논문이 연도·대표 토픽·한국 소속 조건을 만족하는지.
- 원본에서 중복을 제거한 결과와 `sample.json`이 같은지.
- 실행 요약·샘플의 토픽·연도·국가·건수·중복 수가 일치하는지.

정상 출력 형식:

```text
검증 완료: topic=T11636, year=2025, count=N, duplicates=M
```

VS Code에서 `sample.json`을 열어 `results`의 논문 한 편을 펼쳐 보면 보존된 저자·소속 기관도 직접 확인할 수 있습니다.

## 7. 오류·재시도 동작

| 상황 | 동작 |
|---|---|
| `.env` 키 없음·잘못된 키 형식 | 요청 전에 종료. 출력 폴더도 만들지 않음 |
| 잘못된 토픽 형식·건수·timeout | 요청 전에 종료 |
| HTTP 401·403 | 재시도 없이 종료. 키와 이메일 인증·권한 확인 안내 |
| HTTP 429·500·502·503·504 | 최초 요청 포함 최대 3회, 지수 대기 후 재시도 |
| timeout·연결 오류 | 최초 요청 포함 최대 3회 재시도 |
| `Retry-After` 30초 초과 | 기다리는 척 조기 재시도하지 않고 종료. 나중에 재실행 |
| 그 외 HTTP 오류·리다이렉트 | 재시도 없이 종료. 리다이렉트를 따라 키를 보내지 않음 |
| JSON 형식 오류·조건 불일치 | 실패 기록. 성공 샘플 생성 중단 |
| 기존 출력 폴더 | 덮어쓰지 않고 종료 |

API 오류 응답 본문, 요청 헤더, 네트워크 예외의 원문 문자열은 출력하거나 로그에 기록하지 않습니다. 성공한 API JSON만 `response.json`에 저장합니다.

API·검증 실패 시 `manifest.json`의 `status`는 `failed`입니다. 중단·파일 저장 문제 등으로 `started` 상태가 남은 실행도 완료된 데이터로 사용하지 않습니다. 종료 코드 0은 성공, 1은 수집 또는 확인 실패입니다.

## 8. 자동 테스트

```bash
python -m pytest tests/test_collect.py -q
```

시험용 응답으로 필터 조건 검증, 저자·기관 정보 보존, 중복 처리, 100편 상한, 빈 결과, HTTP·timeout 재시도, 오류 메시지의 키 비노출, 기존 파일 보호, 저장 결과 변조 감지를 확인합니다. 테스트는 실제 네트워크 요청을 차단하고, 실제 키나 API 사용량을 소비하지 않습니다.

## 공식 참고

- 인증 헤더: <https://help.openalex.org/api/authentication/>
- 필터: <https://help.openalex.org/api/filtering/>
- 페이지 크기와 페이지네이션: <https://help.openalex.org/api/paging/>
- 필드 선택: <https://help.openalex.org/api/selecting-fields/>
