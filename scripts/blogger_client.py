"""Google Blogger API v3 클라이언트. token.json(OAuth refresh token)은
generate_oauth_token.py로 로컬에서 1회 발급한다.
클라우드 루틴처럼 token.json 파일이 없는 환경에서는 BLOGGER_TOKEN_JSON
환경변수(같은 내용을 한 줄 JSON으로 담은 값)로 대체할 수 있다."""
import json
import os
import sys

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(ROOT_DIR, "token.json")

BLOGGER_BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "")
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def _load_credentials():
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    else:
        token_json_env = os.getenv("BLOGGER_TOKEN_JSON", "")
        if not token_json_env:
            raise RuntimeError(
                "token.json도 없고 BLOGGER_TOKEN_JSON 환경변수도 없습니다. "
                "로컬이면 python scripts/generate_oauth_token.py 를 먼저 실행하세요."
            )
        creds = Credentials.from_authorized_user_info(json.loads(token_json_env), SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds


def _get_service():
    return build("blogger", "v3", credentials=_load_credentials())


def publish_post(title, html_content, is_draft=False):
    if not BLOGGER_BLOG_ID:
        raise RuntimeError("BLOGGER_BLOG_ID가 설정되어 있지 않습니다 (.env 확인)")
    service = _get_service()
    body = {"title": title, "content": html_content}
    result = (
        service.posts()
        .insert(blogId=BLOGGER_BLOG_ID, body=body, isDraft=is_draft)
        .execute()
    )
    return result


def get_post(post_id):
    service = _get_service()
    return service.posts().get(blogId=BLOGGER_BLOG_ID, postId=post_id).execute()


def update_post(post_id, title=None, html_content=None):
    """발행된 글을 수정한다 (사진 추가, 오타 수정 등).

    Blogger의 posts().update()는 전체 교체(PUT) 방식이라, title을 안 보내면
    제목이 빈 값으로 덮어써진다. 그래서 title/html_content 중 지정 안 한 값은
    반드시 현재 값을 먼저 읽어와 채운 뒤 보낸다 — 절대로 content만 달랑 보내지 말 것."""
    service = _get_service()
    current = service.posts().get(blogId=BLOGGER_BLOG_ID, postId=post_id).execute()
    body = {
        "title": title if title is not None else current.get("title", ""),
        "content": html_content if html_content is not None else current.get("content", ""),
    }
    return service.posts().update(blogId=BLOGGER_BLOG_ID, postId=post_id, body=body).execute()


if __name__ == "__main__":
    # 단독 실행: OAuth 인증과 블로그 접근 권한이 정상인지 확인용 (비공개 초안으로 발행)
    res = publish_post(
        title="KoreaTravelBlog 연결 테스트",
        html_content="<p>이 글은 자동화 파이프라인 연결 테스트용 임시 초안입니다.</p>",
        is_draft=True,
    )
    print("발행 성공 (draft):", res.get("url"))
