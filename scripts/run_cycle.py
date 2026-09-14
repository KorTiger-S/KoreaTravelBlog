"""파이프라인 CLI. 실제 블로그 글 "작성"은 이 스크립트가 아니라
이 스크립트를 실행하는 Claude Code 클라우드 루틴(에이전트)이 담당한다.
이 스크립트는 TourAPI 조회, 텔레그램 송수신, Blogger 발행, state 기록만 담당하는
기계적인 글루(glue) 역할이다.

에이전트가 매 실행마다 따라야 할 순서:
  1) `check-replies` 실행 → 승인/피드백/무응답 결과 확인
     - 승인이면 이미 자동으로 Blogger에 발행되고 pending이 비워짐
     - 피드백 텍스트가 왔을 때, 에이전트가 그 내용을 읽고 판단:
       a) 지금 초안을 다듬어 달라는 요청 → 원본 데이터 기반으로 글을 고쳐 쓴 뒤
          `revise-draft --title ... --html-file ...` (content_id는 그대로 둠)
       b) "이 주제 말고 OOO 알려줘"처럼 완전히 다른 주제 요청 → `search-topic --keyword OOO`로
          후보를 찾고, 가장 적합한 것을 `fetch-detail --content-id ID --content-type-id TYPE`로
          상세 조회한 뒤 새로 글을 써서 `revise-draft ... --content-id 새ID`로 교체
     - pending이 없는 상태에서 온 메시지(ignored_messages)도 주제 요청일 수 있음 → 위 b)와 동일하게 처리
     - 그 외 무응답이면 아무것도 안 해도 됨
  2) pending도 없고 사용자의 특별한 주제 요청도 없다면 `fetch-next` 실행 → TourAPI 순회로 관광지 자동 선정
  3) 에이전트가 그 데이터를 바탕으로 제목(title)과 HTML 본문을 직접 작성
  4) `save-draft`로 초안 저장 + 텔레그램 전송

사용법:
  python run_cycle.py check-replies
  python run_cycle.py fetch-next
  python run_cycle.py search-topic --keyword "Gyeongbokgung"
  python run_cycle.py fetch-detail --content-id 126508 --content-type-id 76
  python run_cycle.py save-draft --title "..." --html-file draft.html --content-id 126508
  python run_cycle.py revise-draft --title "..." --html-file draft.html [--content-id 새ID]
  python run_cycle.py publish
"""
import argparse
import json
import re
import sys

# Windows 콘솔 기본 인코딩(cp949)에서 관광지 설명에 흔한 유니코드 문자(•, — 등)를
# 출력하면 크래시가 나므로, 표준입출력을 UTF-8로 고정한다.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import blogger_client
import state
import telegram_client
import tourapi_client

APPROVAL_WORDS = {"승인", "발행", "ok", "okay", "yes", "go", "publish"}


def cmd_check_replies(args):
    offset = state.load_telegram_offset()
    messages, next_offset = telegram_client.get_new_messages(offset)
    state.save_telegram_offset(next_offset)

    if not messages:
        print(json.dumps({"status": "no_new_replies"}, ensure_ascii=False))
        return

    pending = state.load_pending_draft()
    last_message = messages[-1].strip()

    if not pending:
        print(json.dumps({"status": "no_pending_draft", "ignored_messages": messages}, ensure_ascii=False))
        return

    if last_message.lower() in APPROVAL_WORDS:
        result = blogger_client.publish_post(pending["title"], pending["html"], is_draft=False)
        state.add_posted_id(pending["content_id"])
        state.clear_pending_draft()
        telegram_client.send_message(f"발행 완료: {result.get('url')}")
        print(json.dumps({"status": "published", "url": result.get("url")}, ensure_ascii=False))
        return

    print(
        json.dumps(
            {
                "status": "feedback_received",
                "feedback": last_message,
                "pending_draft": pending,
            },
            ensure_ascii=False,
        )
    )


def cmd_fetch_next(args):
    posted_ids = state.load_posted_ids()
    item = tourapi_client.find_next_unposted(posted_ids)
    if not item:
        print(json.dumps({"status": "no_more_attractions"}, ensure_ascii=False))
        return
    bundle = tourapi_client.fetch_attraction_bundle(item["contentid"], item["contenttypeid"])
    print(json.dumps({"status": "ok", "attraction": bundle}, ensure_ascii=False))


def cmd_search_topic(args):
    """사용자가 텔레그램으로 직접 요청한 주제를 검색.
    check-replies가 'no_pending_draft'(대기 중인 초안 없음)이면서 ignored_messages에
    주제로 보이는 텍스트가 있거나, feedback_received의 피드백이 사실은 '다른 주제로 바꿔줘'라고
    에이전트가 판단했을 때 사용한다. 결과 중 가장 적합한 항목을 골라 fetch-detail로 상세 정보를 가져온다."""
    results = tourapi_client.search_keyword(args.keyword)
    if not results:
        print(json.dumps({"status": "no_results", "keyword": args.keyword}, ensure_ascii=False))
        return
    trimmed = [
        {
            "content_id": it.get("contentid"),
            "content_type_id": it.get("contenttypeid"),
            "title": it.get("title"),
            "addr": it.get("addr1"),
        }
        for it in results
    ]
    print(json.dumps({"status": "ok", "results": trimmed}, ensure_ascii=False))


def cmd_fetch_detail(args):
    bundle = tourapi_client.fetch_attraction_bundle(args.content_id, args.content_type_id)
    print(json.dumps({"status": "ok", "attraction": bundle}, ensure_ascii=False))


def _read_html(args):
    if args.html_file:
        with open(args.html_file, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def _html_to_preview_text(html):
    """텔레그램 미리보기용: 블로그 HTML을 읽기 쉬운 순수 텍스트로 변환.
    텔레그램 parse_mode=HTML은 <h3>/<ul>/<li>/<img> 같은 태그를 지원하지 않으므로
    아예 태그 없는 텍스트로 보낸다."""
    text = re.sub(r"<li[^>]*>", "\n- ", html, flags=re.I)
    text = re.sub(r"<(h[1-6]|p|br|ul|ol)[^>]*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<img[^>]*>", "\n[image]", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def cmd_save_draft(args):
    html = _read_html(args)
    draft = {
        "content_id": args.content_id,
        "title": args.title,
        "html": html,
        "status": "awaiting_approval",
    }
    state.save_pending_draft(draft)
    preview = _html_to_preview_text(html)
    telegram_client.send_message(
        f"[새 초안]\n제목: {args.title}\n\n{preview}\n\n---\n승인하려면 '승인', 수정하려면 원하는 내용을 답장해주세요."
    )
    print(json.dumps({"status": "sent_for_approval"}, ensure_ascii=False))


def cmd_revise_draft(args):
    pending = state.load_pending_draft()
    if not pending:
        print(json.dumps({"status": "error", "message": "대기 중인 초안이 없습니다"}, ensure_ascii=False))
        return
    html = _read_html(args)
    pending["title"] = args.title
    pending["html"] = html
    if args.content_id:
        # 같은 글을 다듬는 게 아니라 사용자가 완전히 다른 주제로 바꿔달라고 한 경우
        pending["content_id"] = args.content_id
    state.save_pending_draft(pending)
    preview = _html_to_preview_text(html)
    telegram_client.send_message(
        f"[수정된 초안]\n제목: {args.title}\n\n{preview}\n\n---\n승인하려면 '승인', 추가로 수정하려면 원하는 내용을 답장해주세요."
    )
    print(json.dumps({"status": "sent_for_approval"}, ensure_ascii=False))


def cmd_publish(args):
    pending = state.load_pending_draft()
    if not pending:
        print(json.dumps({"status": "error", "message": "대기 중인 초안이 없습니다"}, ensure_ascii=False))
        return
    result = blogger_client.publish_post(pending["title"], pending["html"], is_draft=False)
    state.add_posted_id(pending["content_id"])
    state.clear_pending_draft()
    telegram_client.send_message(f"발행 완료: {result.get('url')}")
    print(json.dumps({"status": "published", "url": result.get("url")}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="KoreaTravelBlog 파이프라인 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-replies")
    sub.add_parser("fetch-next")

    p_search = sub.add_parser("search-topic")
    p_search.add_argument("--keyword", required=True)

    p_detail = sub.add_parser("fetch-detail")
    p_detail.add_argument("--content-id", required=True)
    p_detail.add_argument("--content-type-id", required=True)

    p_save = sub.add_parser("save-draft")
    p_save.add_argument("--title", required=True)
    p_save.add_argument("--content-id", required=True)
    p_save.add_argument("--html-file")

    p_revise = sub.add_parser("revise-draft")
    p_revise.add_argument("--title", required=True)
    p_revise.add_argument("--html-file")
    p_revise.add_argument("--content-id", help="완전히 다른 주제로 바꾸는 경우에만 지정")

    sub.add_parser("publish")

    args = parser.parse_args()
    handlers = {
        "check-replies": cmd_check_replies,
        "fetch-next": cmd_fetch_next,
        "search-topic": cmd_search_topic,
        "fetch-detail": cmd_fetch_detail,
        "save-draft": cmd_save_draft,
        "revise-draft": cmd_revise_draft,
        "publish": cmd_publish,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
