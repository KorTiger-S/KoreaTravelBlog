"""Windows 작업 스케줄러 전용. 6일마다 11:30 KST에 실행되어,
generate_oauth_token.py로 새 Blogger OAuth token.json을 발급받고,
내용을 클립보드에 복사한 뒤 다음 수동 작업(claude.ai Environment의
BLOGGER_TOKEN_JSON 갱신)을 텔레그램으로 안내한다.
"""
import os
import subprocess
import sys

import telegram_client

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
TOKEN_PATH = os.path.join(ROOT_DIR, "token.json")


def main():
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "generate_oauth_token.py")],
        cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        telegram_client.send_message(
            "⚠️ [KoreaTravelBlog] 토큰 자동 재발급 실패 — generate_oauth_token.py가 "
            "오류로 종료되었습니다. 로컬에서 수동으로 다시 실행해주세요."
        )
        return

    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        token_content = f.read().strip()

    try:
        subprocess.run("clip", input=token_content.encode("utf-8"), shell=True, check=True)
        clipboard_note = "새 token.json 내용이 클립보드에 복사되었습니다."
    except Exception:
        clipboard_note = f"클립보드 복사에 실패했습니다 — {TOKEN_PATH} 파일에서 직접 복사하세요."

    telegram_client.send_message(
        "✅ [KoreaTravelBlog] Blogger OAuth 토큰 재발급 완료.\n"
        f"{clipboard_note}\n"
        "claude.ai → Claude Code → 루틴 → KoreaTravelBlog Daily Cycle → "
        "상단 'Default · KoreaTravelBlog' 클릭 → 환경 변수 BLOGGER_TOKEN_JSON에 "
        "붙여넣고 저장해주세요."
    )


if __name__ == "__main__":
    main()
