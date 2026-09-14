# KoreaTravelBlog

해외 여행자를 위한 한국 여행 가이드를 Google Blogger에 반자동으로 발행하는 파이프라인.

한국관광공사 TourAPI로 실제 관광지 정보를 가져와 초안을 만들고, 텔레그램으로 승인/피드백을 받은 뒤에만 Blogger에 게시합니다. 완전 자동 발행이 아닌 이유는 사람 검수 없는 대량 자동 콘텐츠가 Google의 유용한 콘텐츠 정책에 걸려 검색 노출에 불리해질 수 있기 때문입니다.

## 처음 설정하기

[SETUP.md](SETUP.md)를 따라 Blogger, Google Cloud OAuth, TourAPI 키, 텔레그램 봇을 준비하세요.

```
pip install -r requirements.txt
cp .env.example .env   # 값 채우기
python scripts/generate_oauth_token.py   # 최초 1회, 브라우저 동의
```

## 동작 방식

`scripts/run_cycle.py`는 TourAPI 조회, 텔레그램 송수신, Blogger 발행, `state/` 기록만 담당하는 CLI입니다. **글 자체를 쓰는 것은 이 스크립트가 아니라, 이 파이프라인을 실행하는 Claude(에이전트)입니다.** 별도의 AI API 키 없이, 파이프라인을 굴리는 에이전트가 매 실행마다 아래 순서를 직접 수행합니다.

```
python scripts/run_cycle.py check-replies
```
텔레그램에 새 답장이 있으면 확인합니다.
- "승인"이면 → 이미 자동으로 Blogger에 발행되고 끝.
- 피드백 텍스트면 → 원본 관광지 데이터와 피드백이 JSON으로 출력됨 → 에이전트가 그걸 보고 글을 다시 써서:
  ```
  python scripts/run_cycle.py revise-draft --title "..." --html-file revised.html
  ```
- 대기 중인 초안이 없으면(승인 완료 후):
  ```
  python scripts/run_cycle.py fetch-next
  ```
  아직 다루지 않은 관광지 1곳의 원본 데이터(주소/설명/이용시간/이미지 등)가 JSON으로 출력됩니다. 에이전트가 이 데이터를 바탕으로 외국인 여행자 관점의 글(제목 + HTML 본문: 실용 정보, 주소, 운영시간, 요금, 안전/실전 팁 포함)을 직접 작성한 뒤:
  ```
  python scripts/run_cycle.py save-draft --title "..." --html-file draft.html --content-id <contentId>
  ```
  으로 텔레그램에 전송하고 승인을 기다립니다.

## 로컬 테스트 (엔드투엔드)

1. `python scripts/tourapi_client.py` — TourAPI 키가 유효하고 목록이 오는지 확인
2. `python scripts/telegram_client.py` — 봇 메시지 송수신 확인
3. `python scripts/blogger_client.py` — Blogger에 테스트 비공개 초안이 정상 발행되는지 확인
4. 위 3가지가 모두 통과하면, 실제 사이클을 손으로 한 번 돌려봅니다:
   - `python scripts/run_cycle.py fetch-next` 로 관광지 데이터 확인
   - 직접(또는 Claude Code와 함께) 제목/본문 작성 후 `save-draft`
   - 텔레그램으로 "승인" 답장
   - `python scripts/run_cycle.py check-replies` 실행 → Blogger에 실제로 글이 발행되는지 확인

## 클라우드 자동 실행

로컬 검증이 끝나면 `/schedule` 스킬로 "매일 1회, 위 순서를 수행" 하는 클라우드 루틴을 등록합니다. 비밀값(.env)을 클라우드 루틴 환경에 전달하는 구체적인 방법은 `/schedule` 진행 시 확정합니다.

## 상태 파일 (`state/`)

- `posted.json` — 이미 발행한 TourAPI contentId 목록 (중복 발행 방지)
- `pending_draft.json` — 승인 대기 중인 초안 (없으면 `null`)
- `telegram_offset.json` — 마지막으로 처리한 텔레그램 update_id
- `crawl_cursor.json` — 다음에 조회할 지역/페이지 커서

이 파일들은 클라우드 루틴 실행 사이에 상태를 이어가기 위해 git에 커밋됩니다.
