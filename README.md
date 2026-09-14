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
- 피드백 텍스트면 → 원본 관광지 데이터와 피드백이 JSON으로 출력됨 → 에이전트가 그 내용을 읽고 판단합니다.
  - 지금 초안을 다듬어 달라는 요청이면, 원본 데이터를 기반으로 글을 고쳐 쓴 뒤:
    ```
    python scripts/run_cycle.py revise-draft --title "..." --html-file revised.html
    ```
  - "이 주제 말고 OOO 알려줘"처럼 **완전히 다른 주제를 요청**한 경우(대기 중인 초안이 있을 때든 없을 때든):
    ```
    python scripts/run_cycle.py search-topic --keyword "OOO"
    python scripts/run_cycle.py fetch-detail --content-id <ID> --content-type-id <TYPE>
    ```
    로 사용자가 원하는 곳의 실제 데이터를 가져온 뒤, 그 데이터로 글을 써서 `revise-draft ... --content-id <새ID>`로 대기 중인 초안을 교체합니다(대기 중인 초안이 없었다면 `save-draft`로 새로 만듭니다).
- 대기 중인 초안이 없고 사용자의 주제 요청도 없으면(승인 완료 후), **여행 팁 콘텐츠를 먼저 소진**합니다:
  ```
  python scripts/run_cycle.py next-tip
  ```
  `state/tips_backlog.json`에서 아직 안 쓴 팁 주제(`{id, topic}`)가 나옵니다. TourAPI 장소 데이터가 아니라 일반 지식(및 필요하면 `WelcomeToKorea/` 같은 기존 검증 자료)을 바탕으로 에이전트가 직접 글을 씁니다.
  - `"no_tips_left"`이면 팁 주제가 소진된 것이므로 TourAPI 관광지 로테이션으로 넘어갑니다:
    ```
    python scripts/run_cycle.py fetch-next
    ```
    아직 다루지 않은 관광지 1곳의 원본 데이터(주소/설명/이용시간/이미지 등)가 JSON으로 출력됩니다.

  어느 쪽이든, 에이전트가 그 데이터를 바탕으로 외국인 여행자 관점의 글(제목 + HTML 본문: 실용 정보, 안전/실전 팁 포함)을 직접 작성한 뒤, **한글로 소주제(각 섹션이 뭘 다루는지) 요약을 한두 문단 따로 작성**해서(블로그 본문에는 넣지 않음, 텔레그램 확인용):
  ```
  python scripts/run_cycle.py save-draft --title "..." --html-file draft.html --content-id <tip id 또는 contentId> --summary-ko-file summary_ko.txt
  ```
  으로 텔레그램에 전송하고 승인을 기다립니다. (`revise-draft`도 동일하게 `--summary-ko-file` 지원)

## 콘텐츠 작성 원칙 (모든 글에 적용)

- **사진을 반드시 넣는다.** 글만 있는 포스팅은 만들지 않는다.
  - TourAPI 데이터 기반 글(`fetch-next`/`search-topic`)이면 `fetch_attraction_bundle`이 주는 `images` 필드를 그대로 `<img>`로 삽입한다.
  - 팁 콘텐츠(`next-tip`)처럼 TourAPI 이미지가 없는 주제는 Wikimedia Commons에서 라이선스가 명확한(CC BY-SA, Public Domain 등) 사진을 찾아 쓴다. `https://commons.wikimedia.org/wiki/Special:FilePath/<파일명>?width=900` 형태 URL을 쓰면 리사이즈된 이미지를 바로 임베드할 수 있다. 사진마다 촬영자/라이선스명/링크를 캡션(`<small>`)으로 반드시 표기한다 — 예시는 이미 발행된 "Incheon Airport to Seoul" 글의 AREX·택시 사진 참고.
  - 본문 흐름과 관련 없는 아무 사진이나 넣지 말고, 각 섹션 내용과 실제로 맞는 사진을 그 섹션 바로 뒤에 넣는다.
  - **소주제(각 `<h3>` 섹션)마다 최소 1장씩** 사진을 넣는다. 포스팅 전체에 사진 1~2장만 있는 건 부족하다 — 섹션이 4개면 사진도 최소 4장.
- **글 난이도는 "한국에 처음 오는 사람" 기준으로 쉽게 쓴다.**
  - 짧은 문장, 쉬운 단어 위주. 전문용어·업계 용어는 피하고, 꼭 써야 하면 바로 옆에서 풀어서 설명한다.
  - 한국어 고유명사(지하철역명, 음식명 등)는 처음 나올 때 무엇인지 간단히 설명하고 쓴다.
  - 독자가 이미 한국을 잘 안다고 가정하지 않는다 — "당연히 알겠지" 하고 생략하는 정보가 없는지 스스로 점검한다.
- **정보와 사진은 최근 3년 이내 것을 우선한다.**
  - TourAPI 데이터는 `modifiedtime`/`createdtime` 필드로 시점을 확인한다. 3년보다 오래됐으면, 그대로 쓰지 말고 Google 검색(WebSearch)으로 최근 1년 이내 정보를 찾아 가격·운영시간·폐업 여부 등이 바뀌지 않았는지 확인한 뒤, 바뀐 부분은 검색으로 확인한 최신 정보로 고쳐서 쓴다.
  - 사진도 마찬가지: 가능하면 3년 이내에 찍히거나 업로드된 사진을 쓴다. 그보다 오래된 사진밖에 없다면, 검색으로 최근 1년 내 자료를 찾아 그 장소/사물의 현재 모습이 크게 달라지지 않았는지 확인한 뒤 사용한다 (예: 리모델링, 폐업, 노선 변경 등으로 사진이 더 이상 실제와 다르면 그 사진은 쓰지 않는다).
- **글 마지막엔 항상 댓글 유도 문구를 이모지와 함께 넣는다.** 예: `<p>💬 Got a question about this? Drop it in the comments below — happy to help!</p>`. 매번 문구를 그대로 복붙하지 말고 그 글 주제에 맞게 살짝 바꿔서 쓴다 (톤/이모지는 유지).
- **주제에 자연스럽게 맞으면, "실제 한국인들은 어떻게 하는지" 팁을 넣는다.** 이동수단/결제/음식/에티켓처럼 현지인의 실제 선택이 있는 주제면, 관광객용 정보만 나열하지 말고 "현지인들도 보통 이렇게 한다/이걸 선호한다" 같은 인사이트를 한 문장이라도 곁들인다. K-ETA나 비자 요건처럼 "현지인의 선택"이 애초에 성립하지 않는 주제엔 억지로 넣지 않는다.

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

- `posted.json` — 이미 발행한 콘텐츠 id 목록 (TourAPI contentId 또는 팁 id, 중복 발행 방지)
- `pending_draft.json` — 승인 대기 중인 초안 (없으면 `null`)
- `telegram_offset.json` — 마지막으로 처리한 텔레그램 update_id
- `crawl_cursor.json` — 다음에 조회할 지역/페이지 커서 (TourAPI 로테이션용)
- `tips_backlog.json` — 우선 발행할 여행 팁 주제 목록 (직접 편집해서 추가/삭제 가능)

이 파일들은 클라우드 루틴 실행 사이에 상태를 이어가기 위해 git에 커밋됩니다.
