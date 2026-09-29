"""Windows 작업 스케줄러 전용. 6일마다 10:30 KST에 실행되어,
1시간 뒤(11:30) Blogger OAuth 토큰 자동 재발급이 있으니
PC를 켜두고 전원에 연결해달라고 텔레그램으로 미리 알린다.
(11:00에는 기존 scheduled_token_alert.py가 30분 전 알림을 한 번 더 보낸다.)
"""
import telegram_client

telegram_client.send_message(
    "\U0001F5A5️ [KoreaTravelBlog] 1시간 뒤(11:30)에 Blogger OAuth 토큰 자동 재발급이 예정되어 있습니다.\n"
    "PC를 켜두고 전원 어댑터를 연결해주세요 (배터리 모드면 자동 재발급이 거부될 수 있어요).\n"
    "11:00에 한 번 더 알림이 갑니다."
)
