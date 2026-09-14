"""파이프라인 CLI. 실제 블로그 글 "작성"은 이 스크립트가 아니라
이 스크립트를 실행하는 Claude Code 클라우드 루틴(에이전트)이 담당한다.
이 스크립트는 TourAPI 조회, 텔레그램 송수신, Blogger 발행, state 기록만 담당하는
기계적인 글루(glue) 역할이다.

에이전트가 매 실행마다 따라야 할 순서:
  1) `check-replies` 실행 → 승인/피드백/무응답 결과 확인
     - 승인이면 이미 자동으로 Blogger에 발행되고 pending이 비워짐
     - 피드백이면 원본 데이터와 피드백 텍스트가 출력됨 → 에이전트가 직접 글을 다시 쓴 뒤
       `revise-draft`로 갱신
     - 무응답이면 아무것도 안 해도 됨
  2) pending이 없는 상태라면 `fetch-next` 실행 → 관광지 원본 데이터(JSON) 획득
  3) 에이전트가 그 데이터를 바탕으로 제목(title)과 HTML 본문을 직접 작성
  4) `save-draft`로 초안 저장 + 텔레그램 전송

사용법:
  python run_cycle.py check-replies
  python run_cycle.py fetch-next
  python run_cycle.py save-draft --title "..." --html-file draft.html --content-id 126508
  python run_cycle.py revise-draft --title "..." --html-file draft.html
  python run_cycle.py publish
"""
import argparse
import json
import sys

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
    bundle = tourapi_client.fetch_attraction_bundle(item["contentid"])
    print(json.dumps({"status": "ok", "attraction": bundle}, ensure_ascii=False))


def _read_html(args):
    if args.html_file:
        with open(args.html_file, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def cmd_save_draft(args):
    html = _read_html(args)
    draft = {
        "content_id": args.content_id,
        "title": args.title,
        "html": html,
        "status": "awaiting_approval",
    }
    state.save_pending_draft(draft)
    telegram_client.send_message(
        f"[새 초안]\n제목: {args.title}\n\n{html}\n\n---\n승인하려면 '승인', 수정하려면 원하는 내용을 답장해주세요."
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
    state.save_pending_draft(pending)
    telegram_client.send_message(
        f"[수정된 초안]\n제목: {args.title}\n\n{html}\n\n---\n승인하려면 '승인', 추가로 수정하려면 원하는 내용을 답장해주세요."
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

    p_save = sub.add_parser("save-draft")
    p_save.add_argument("--title", required=True)
    p_save.add_argument("--content-id", required=True)
    p_save.add_argument("--html-file")

    p_revise = sub.add_parser("revise-draft")
    p_revise.add_argument("--title", required=True)
    p_revise.add_argument("--html-file")

    sub.add_parser("publish")

    args = parser.parse_args()
    handlers = {
        "check-replies": cmd_check_replies,
        "fetch-next": cmd_fetch_next,
        "save-draft": cmd_save_draft,
        "revise-draft": cmd_revise_draft,
        "publish": cmd_publish,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
