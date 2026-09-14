"""로컬에서 1회만 실행하는 스크립트.

Google Cloud Console에서 받은 credentials.json(OAuth 클라이언트, 데스크톱 앱)을
프로젝트 루트에 두고 이 스크립트를 실행하면 브라우저 동의 화면이 뜨고,
동의 후 token.json(refresh token 포함)이 생성된다.
이후 blogger_client.py는 token.json만으로 동작하므로,
클라우드 루틴에서는 이 스크립트를 다시 실행할 필요가 없다.
"""
import os

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(ROOT_DIR, "credentials.json")
TOKEN_PATH = os.path.join(ROOT_DIR, "token.json")
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def main():
    if not os.path.exists(CREDENTIALS_PATH):
        raise SystemExit(
            f"credentials.json을 찾을 수 없습니다: {CREDENTIALS_PATH}\n"
            "SETUP.md 2단계를 따라 Google Cloud Console에서 발급받아 프로젝트 루트에 두세요."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"token.json 생성 완료: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
