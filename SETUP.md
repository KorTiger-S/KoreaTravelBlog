# 사전 설정 가이드

이 파이프라인을 쓰려면 아래 4가지를 먼저 준비해야 합니다. 모두 계정 소유자 본인만 할 수 있는 작업이라 Claude가 대신 할 수 없습니다.

## 1. Blogger 블로그 생성

1. https://www.blogger.com 접속 → Google 계정으로 로그인
2. "새 블로그 만들기" → 제목, 주소(URL), 테마 선택 후 생성
3. 생성된 블로그의 **블로그 ID**를 확인해야 함 (2번 단계 OAuth 인증 후 아래 명령으로 조회 가능):
   ```
   # token.json 발급(2단계) 후 아무 파이썬 콘솔에서
   from googleapiclient.discovery import build
   from google.oauth2.credentials import Credentials
   creds = Credentials.from_authorized_user_file("token.json")
   service = build("blogger", "v3", credentials=creds)
   print(service.blogs().listByUser(userId="self").execute())
   ```
   결과의 `items[].id` 값이 블로그 ID입니다. 이 값을 `.env`의 `BLOGGER_BLOG_ID`에 넣습니다.

## 2. Google Cloud OAuth 설정

1. https://console.cloud.google.com 접속 → 새 프로젝트 생성 (예: `korea-travel-blog`)
2. 좌측 메뉴 "API 및 서비스" → "라이브러리" → "Blogger API v3" 검색 → 사용 설정
3. "API 및 서비스" → "OAuth 동의 화면" → User type: **외부(External)** 선택 → 앱 이름/이메일 등 최소 정보 입력 → 저장
   - 테스트 사용자로 본인 Google 계정 이메일(예: `your-email@gmail.com`)을 추가해둘 것 (앱이 "게시" 상태가 아니어도 테스트 사용자는 계속 사용 가능)
4. "API 및 서비스" → "사용자 인증 정보" → "사용자 인증 정보 만들기" → "OAuth 클라이언트 ID"
   - 애플리케이션 유형: **데스크톱 앱**
   - 생성 후 JSON 다운로드 → 파일명을 `credentials.json`으로 바꿔 프로젝트 루트(`KoreaTravelBlog/`)에 저장
5. 로컬에서 아래 실행 (최초 1회, 브라우저가 열리고 Google 로그인 동의 화면이 뜸):
   ```
   pip install -r requirements.txt
   python scripts/generate_oauth_token.py
   ```
   완료되면 `token.json`이 생성됩니다. 이 파일이 있으면 이후 재인증 없이 계속 Blogger에 글을 올릴 수 있습니다.

## 3. TourAPI 키 발급

1. https://www.data.go.kr 회원가입/로그인
2. "한국관광공사_국문 관광정보 서비스" 검색 → 활용신청 (일반 오픈API, 승인은 보통 즉시~수 시간 내)
3. 마이페이지 → 개발계정 → 인증키 확인
   - **"일반 인증키(Decoding)"** 값을 복사할 것 (Encoding 키를 쓰면 URL 이중 인코딩으로 요청이 실패함)
4. `.env`의 `TOURAPI_KEY`에 붙여넣기

## 4. 텔레그램 봇 생성

1. 텔레그램 앱에서 `@BotFather` 검색 → 대화 시작
2. `/newbot` 입력 → 봇 이름/username 설정 → 봇 토큰(`123456:ABC-...` 형태) 발급받음 → `.env`의 `TELEGRAM_BOT_TOKEN`에 저장
3. 방금 만든 봇을 텔레그램에서 검색해서 아무 메시지나 하나 보냄 (예: "hi")
4. 브라우저에서 아래 URL 접속 (BOT_TOKEN을 실제 값으로 교체):
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
5. 응답 JSON에서 `result[0].message.chat.id` 값을 확인 → `.env`의 `TELEGRAM_CHAT_ID`에 저장

## 완료 후 확인

`.env` 파일에 4가지 값(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TOURAPI_KEY, BLOGGER_BLOG_ID)과 프로젝트 루트의 `token.json`이 모두 준비되면, README.md의 "로컬 테스트" 순서대로 파이프라인을 검증합니다.
