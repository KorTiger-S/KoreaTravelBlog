"""Windows 작업 스케줄러 전용. 6일마다 11:00 KST에 실행되어,
30분 뒤 Blogger OAuth 토큰 자동 재발급이 시작됨을 텔레그램으로 미리 알린다.
(Google Cloud OAuth 앱이 'Testing' 상태라 refresh token이 7일마다 만료되는 것에 대한 대응.)
"""
import telegram_client

telegram_client.send_message(
    "\U0001F514 [KoreaTravelBlog] Blogger OAuth 토큰 자동 재발급이 30분 뒤(11:30)에 시작됩니다.\n"
    "이 PC 앞에 계셔야 합니다 — 브라우저가 열리면 구글 로그인/동의를 완료해주세요.\n"
    "완료되면 새 token.json 내용이 클립보드에 자동 복사되고, 안내 메시지가 다시 옵니다."
)
