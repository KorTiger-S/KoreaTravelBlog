"""텔레그램 봇 API 클라이언트 (초안 전송 + 승인/피드백 폴링)."""
import os
import sys
import tempfile

import requests
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

API_BASE = "https://api.telegram.org"


def _require_config():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID가 설정되어 있지 않습니다 (.env 확인)")


TELEGRAM_MAX_LEN = 4096


def send_message(text):
    """일반 텍스트로 전송. 블로그 HTML(<h3>/<ul>/<img> 등)은 텔레그램 HTML 파싱모드가
    지원하지 않는 태그가 많아 parse_mode를 쓰지 않는다 — 미리보기는 항상 순수 텍스트로 변환해서 넘길 것."""
    _require_config()
    if len(text) > TELEGRAM_MAX_LEN:
        text = text[: TELEGRAM_MAX_LEN - 20] + "\n...(내용 일부 생략)"
    url = f"{API_BASE}/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["result"]


def _download_photo(file_id):
    """파일 ID로 사진 원본을 받아 임시 파일로 저장하고 로컬 경로를 반환한다.
    봇 토큰이 들어간 다운로드 URL은 여기서만 쓰고 절대 바깥(블로그 본문 등)에 노출하지 않는다 —
    블로그에 쓸 땐 run_cycle.py가 이 파일을 읽어 base64 data URI로 바꿔 삽입한다."""
    _require_config()
    file_info = requests.get(
        f"{API_BASE}/bot{BOT_TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=15,
    )
    file_info.raise_for_status()
    file_path = file_info.json()["result"]["file_path"]

    content = requests.get(
        f"{API_BASE}/file/bot{BOT_TOKEN}/{file_path}",
        timeout=30,
    )
    content.raise_for_status()

    suffix = os.path.splitext(file_path)[1] or ".jpg"
    fd, local_path = tempfile.mkstemp(prefix="telegram_photo_", suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content.content)
    return local_path


def get_new_messages(offset):
    """offset 이후의 새 메시지(내 chat에서 온 것만)와 다음 offset을 반환.
    각 메시지는 {"text": str, "photo_path": str} 형태의 dict이며, 둘 중 있는 키만 채워진다
    (텍스트만 보낸 메시지는 "text"만, 사진을 올린 메시지는 "photo_path"만 또는 캡션이 있으면 둘 다)."""
    _require_config()
    url = f"{API_BASE}/bot{BOT_TOKEN}/getUpdates"
    resp = requests.get(
        url,
        params={"offset": offset, "timeout": 0, "allowed_updates": '["message"]'},
        timeout=15,
    )
    resp.raise_for_status()
    updates = resp.json()["result"]

    messages = []
    next_offset = offset
    for update in updates:
        next_offset = max(next_offset, update["update_id"] + 1)
        msg = update.get("message")
        if not msg:
            continue
        if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
            continue

        entry = {}
        text = msg.get("text") or msg.get("caption")
        if text:
            entry["text"] = text
        photo_sizes = msg.get("photo")
        if photo_sizes:
            # photo_sizes는 작은 것부터 큰 것 순서로 오므로 마지막(가장 큰 해상도)을 받는다.
            entry["photo_path"] = _download_photo(photo_sizes[-1]["file_id"])
        if entry:
            messages.append(entry)

    return messages, next_offset


if __name__ == "__main__":
    # 단독 실행: 봇 토큰/chat_id가 유효한지, 메시지 송수신이 되는지 확인용
    send_message("KoreaTravelBlog 파이프라인 연결 테스트 메시지입니다.")
    print("메시지 전송 완료. 텔레그램에서 아무 답장이나 보낸 뒤 아래를 확인하세요.")
    msgs, off = get_new_messages(0)
    print(f"현재까지 수신된 메시지 {len(msgs)}건, next_offset={off}")
