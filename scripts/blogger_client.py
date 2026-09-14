"""Google Blogger API v3 클라이언트. token.json(OAuth refresh token)은
generate_oauth_token.py로 로컬에서 1회 발급한다."""
import os

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(ROOT_DIR, "token.json")

BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "")
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def _load_credentials():
    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(
            "token.json이 없습니다. 먼저 python scripts/generate_oauth_token.py 를 로컬에서 실행하세요."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds


def publish_post(title, html_content, is_draft=False):
    if not BLOGGER_BLOG_ID:
        raise RuntimeError("BLOGGER_BLOG_ID가 설정되어 있지 않습니다 (.env 확인)")
    creds = _load_credentials()
    service = build("blogger", "v3", credentials=creds)
    body = {"title": title, "content": html_content}
    result = (
        service.posts()
        .insert(blogId=BLOGGER_BLOG_ID, body=body, isDraft=is_draft)
        .execute()
    )
    return result


if __name__ == "__main__":
    # 단독 실행: OAuth 인증과 블로그 접근 권한이 정상인지 확인용 (비공개 초안으로 발행)
    res = publish_post(
        title="KoreaTravelBlog 연결 테스트",
        html_content="<p>이 글은 자동화 파이프라인 연결 테스트용 임시 초안입니다.</p>",
        is_draft=True,
    )
    print("발행 성공 (draft):", res.get("url"))
