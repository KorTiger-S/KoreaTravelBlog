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
  2) pending도 없고 사용자의 특별한 주제 요청도 없다면, 먼저 이번 달 마지막 3일인지 확인한다:
     `fetch-monthly-festivals` 실행
     - "not_due"면 아직 트리거 시점이 아니므로 3)으로 넘어간다 (평소엔 항상 이 상태)
     - "no_new_festivals"면 다음 달 축제 로스터를 이미 다 다뤘으므로 3)으로 넘어간다
     - "ok"면 다음 달에 열리는 "대형 축제"(EV01) 목록(제목/날짜/주소)이 나온다. 외국인 여행자가
       대중교통으로 접근하기 쉬운 수도권(서울·인천·경기)만, 서울이 먼저 오도록 정렬되어 나온다
       (`tourapi_client.CAPITAL_AREA_REGION_CODES` + `SEOUL_REGION_CODE` 우선 정렬). 에이전트가 이 목록을 보고:
       a) 겹치는 테마(단풍축제, 빛축제 등)가 있으면 그 테마만 묶어 1개 글로 작성
       b) 테마가 뚜렷하지 않거나 테마 글을 이미 썼다면, 남은 것 중 추천순으로 최대 10개를 골라
          "이번 달 볼만한 축제 Top N" 로스터 글로 작성 (목록이 이미 서울 우선 정렬이므로 그 순서를 따르면 됨)
       - 고른 각 축제는 `fetch-detail --content-id ID --content-type-id 85`로 상세/이미지 조회
       - 테마로 묶은 로스터 글은 지도에 위치를 표시한 이미지가 있으면 좋으므로, `save-draft`/`revise-draft`에
         `--reviewer-note "이 글에 넣을 축제 위치 지도 이미지를 AI로 생성해서 추가해주시면 반영해서 다시 보내드릴게요."`
         같은 안내를 덧붙여 텔레그램으로 요청한다 (이 안내는 블로그 본문이 아니라 텔레그램 메시지에만 붙음).
         사용자가 이미지 URL을 답장하면 다음 check-replies의 피드백으로 들어오므로, 그 URL을 본문에
         `<img>`로 넣어 `revise-draft`로 반영한다.
       - `save-draft --content-id "id1,id2,..." ...`처럼 콤마로 여러 축제 id를 한 번에 넘기면,
         승인 후 그 축제들 전부가 posted_ids에 기록되어 다음 달 말 트리거 때 중복 없이 다뤄진다.
  3) 월말 축제 로스터가 해당 없으면(not_due/no_new_festivals), 격주 월요일인지 확인한다:
     `fetch-biweekly-events` 실행
     - "not_due"면 격주 월요일이 아니므로 4)로 넘어간다
     - "no_new_events"면 이번 주기에 다룰 새 행사가 없으므로 4)로 넘어간다
     - "ok"면 앞으로 3주 안에 열리는 수도권 "행사"(EV02/EV03 — 대형 축제로 분류 안 된 전시/공연/팝업 등)
       목록이 서울 우선으로 정렬되어 나온다. 한강·서울숲·광화문처럼 핫플레이스에서 열리거나, K-pop
       관련처럼 외국인 관광객이 특히 좋아할 만한 소재를 우선적으로 고려해 최대 5~6개를 골라
       "지금 서울에서 놓치기 아까운 행사" 같은 로스터 글로 작성한다. 나머지 작성 방식(사진, 콤마로
       여러 id 지정, 다음 달 축제 로스터와 posted_ids 공유 등)은 2)의 축제 로스터와 동일하다.
  4) 여전히 아무 주제도 없다면, 초반에는 여행 팁 콘텐츠를 우선한다:
     a) `next-tip` 실행 → 아직 안 쓴 팁 주제가 있으면 {id, topic}이 나옴. 에이전트가 일반 지식(및
        필요시 WelcomeToKorea/ 같은 기존 검증 자료)을 바탕으로 글을 쓴 뒤
        `save-draft --content-id <tip id> ...`
     b) 팁 주제가 소진됐으면("no_tips_left") `fetch-next` 실행 → TourAPI 순회로 관광지 자동 선정
  5) 에이전트가 그 데이터를 바탕으로 제목(title)과 HTML 본문을 직접 작성 (README의 콘텐츠 작성 원칙 준수:
     소주제마다 사진 1장 이상, 한국 초행자 기준 쉬운 문장, 3년 이상 지난 정보/사진은 재검증)
  6) 블로그 본문과는 별개로, 각 소주제가 뭘 다루는지 한글로 짧게 요약한 텍스트를 하나 더 작성
  7) 검색결과에 뜨는 요약(meta description)도 영문 150~160자 내외로 하나 작성 (SEO용, 본문에는 안 들어감)
  8) `save-draft --content-id ... --html-file ... --summary-ko-file ... --meta-description "..."`로 초안 저장 + 텔레그램 전송
     (한글 요약과 meta description 모두 블로그 본문에는 안 들어감 — 한글 요약은 텔레그램 미리보기용.
     meta description은 Blogger API의 searchDescription 저장 버그 때문에 자동 반영이 안 되므로,
     발행 완료 시 텔레그램 메시지에 URL과 함께 다시 안내되고 사용자가 Blogger 편집 화면에서 직접 입력함)

사용법:
  python run_cycle.py check-replies
  python run_cycle.py fetch-monthly-festivals
  python run_cycle.py fetch-biweekly-events
  python run_cycle.py next-tip
  python run_cycle.py fetch-next
  python run_cycle.py search-topic --keyword "Gyeongbokgung"
  python run_cycle.py fetch-detail --content-id 126508 --content-type-id 76
  python run_cycle.py save-draft --title "..." --html-file draft.html --content-id 126508 --summary-ko-file summary_ko.txt --meta-description "..." [--reviewer-note "..."]
  python run_cycle.py revise-draft --title "..." --html-file draft.html [--content-id 새ID] --summary-ko-file summary_ko.txt --meta-description "..." [--reviewer-note "..."]
  python run_cycle.py publish
"""
import argparse
import calendar
import json
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Windows 콘솔 기본 인코딩(cp949)에서 관광지 설명에 흔한 유니코드 문자(•, — 등)를
# 출력하면 크래시가 나므로, 표준입출력을 UTF-8로 고정한다.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import blogger_client
import state
import telegram_client
import tourapi_client

APPROVAL_WORDS = {"승인", "발행", "ok", "okay", "yes", "go", "publish"}
KST = ZoneInfo("Asia/Seoul")
FESTIVAL_TRIGGER_DAYS_BEFORE_MONTH_END = 3  # 이번 달 마지막 이 날짜(포함)부터 다음 달 축제 로스터 시도
EVENTS_LOOKAHEAD_DAYS = 21  # 격주 월요일 행사 로스터가 내다보는 기간 (2주 주기 + 여유)


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
        result = blogger_client.publish_post(
            pending["title"],
            pending["html"],
            is_draft=False,
            search_description=pending.get("meta_description"),
        )
        state.add_posted_id(pending["content_id"])
        state.clear_pending_draft()
        telegram_client.send_message(_published_message(result, pending.get("meta_description")))
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


def cmd_next_tip(args):
    posted_ids = state.load_posted_ids()
    for tip in state.load_tips_backlog():
        if tip["id"] not in posted_ids:
            print(json.dumps({"status": "ok", "tip": tip}, ensure_ascii=False))
            return
    print(json.dumps({"status": "no_tips_left"}, ensure_ascii=False))


def cmd_fetch_next(args):
    posted_ids = state.load_posted_ids()
    item = tourapi_client.find_next_unposted(posted_ids)
    if not item:
        print(json.dumps({"status": "no_more_attractions"}, ensure_ascii=False))
        return
    bundle = tourapi_client.fetch_attraction_bundle(item["contentid"], item["contenttypeid"])
    print(json.dumps({"status": "ok", "attraction": bundle}, ensure_ascii=False))


def cmd_fetch_monthly_festivals(args):
    """이번 달 마지막 3일 동안만 동작. 다음 달에 열리는 수도권 "대형 축제"(EV01) 중
    아직 어떤 글에도 안 쓰인(posted_ids에 없는) 것만 추려서 가벼운 목록으로 반환한다
    (필터링·서울 우선 정렬은 tourapi_client.search_festivals가 담당). 한강·서울숲·광화문
    같은 핫플레이스의 자잘한 행사는 cmd_fetch_biweekly_events가 별도로 담당한다.
    테마 묶음(예: 단풍축제) vs Top 10 로스터 선정, 이미지 상세 조회(fetch-detail)는
    에이전트가 이 목록을 보고 직접 판단한다."""
    today = datetime.now(KST).date()
    last_day_of_month = calendar.monthrange(today.year, today.month)[1]
    if last_day_of_month - today.day >= FESTIVAL_TRIGGER_DAYS_BEFORE_MONTH_END:
        print(json.dumps({"status": "not_due"}, ensure_ascii=False))
        return

    if today.month == 12:
        target_year, target_month = today.year + 1, 1
    else:
        target_year, target_month = today.year, today.month + 1
    target_last_day = calendar.monthrange(target_year, target_month)[1]
    month_label = f"{target_year}-{target_month:02d}"

    posted_ids = state.load_posted_ids()
    festivals = tourapi_client.search_festivals(
        f"{target_year}{target_month:02d}01",
        f"{target_year}{target_month:02d}{target_last_day:02d}",
    )
    new_festivals = [f for f in festivals if f.get("contentid") not in posted_ids]

    if not new_festivals:
        print(json.dumps({"status": "no_new_festivals", "month": month_label}, ensure_ascii=False))
        return

    trimmed = [
        {
            "content_id": f.get("contentid"),
            "content_type_id": f.get("contenttypeid"),
            "title": f.get("title"),
            "addr": f.get("addr1"),
            "event_start_date": f.get("eventstartdate"),
            "event_end_date": f.get("eventenddate"),
        }
        for f in new_festivals
    ]
    print(json.dumps({"status": "ok", "month": month_label, "festivals": trimmed}, ensure_ascii=False))


def cmd_fetch_biweekly_events(args):
    """격주 월요일에만 동작 (ISO 주차가 짝수인 월요일). 앞으로 EVENTS_LOOKAHEAD_DAYS일 안에 열리는
    수도권 "행사"(EV02/EV03 — 대형 축제로 분류 안 된 전시/공연/팝업 등, K-pop 관련처럼 외국인에게
    매력적인 소재면 특히 좋음) 중 아직 어떤 글에도 안 쓰인 것만 추려서 가벼운 목록으로 반환한다
    (필터링·서울 우선 정렬은 tourapi_client.search_hotspot_events가 담당)."""
    today = datetime.now(KST).date()
    iso_year, iso_week, iso_weekday = today.isocalendar()
    if iso_weekday != 1 or iso_week % 2 != 0:
        print(json.dumps({"status": "not_due"}, ensure_ascii=False))
        return

    end_date = today + timedelta(days=EVENTS_LOOKAHEAD_DAYS)

    posted_ids = state.load_posted_ids()
    events = tourapi_client.search_hotspot_events(
        today.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
    )
    new_events = [e for e in events if e.get("contentid") not in posted_ids]

    if not new_events:
        print(json.dumps({"status": "no_new_events"}, ensure_ascii=False))
        return

    trimmed = [
        {
            "content_id": e.get("contentid"),
            "content_type_id": e.get("contenttypeid"),
            "title": e.get("title"),
            "addr": e.get("addr1"),
            "event_start_date": e.get("eventstartdate"),
            "event_end_date": e.get("eventenddate"),
        }
        for e in new_events
    ]
    print(json.dumps({"status": "ok", "events": trimmed}, ensure_ascii=False))


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


def _read_summary_ko(args):
    if not args.summary_ko_file:
        return ""
    with open(args.summary_ko_file, "r", encoding="utf-8") as f:
        return f.read().strip()


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


def _reviewer_note_block(args):
    note = getattr(args, "reviewer_note", None)
    return f"\n\n💡 참고: {note}" if note else ""


def _published_message(result, meta_description):
    """Blogger의 searchDescription 필드가 API로는 저장이 안 되는 문제(확인됨, 2026-09-15)가 있어,
    검색 설명은 자동 반영을 시도하되 사용자가 Blogger 글 편집 화면에서 직접 입력하도록 텔레그램에 안내한다."""
    message = f"발행 완료: {result.get('url')}"
    if meta_description:
        message += f"\n\n📋 검색 설명(Search Description)을 Blogger 글 편집 화면에서 직접 입력해주세요:\n{meta_description}"
    return message


def cmd_save_draft(args):
    html = _read_html(args)
    summary_ko = _read_summary_ko(args)
    draft = {
        "content_id": args.content_id,
        "title": args.title,
        "html": html,
        "meta_description": args.meta_description,
        "status": "awaiting_approval",
    }
    state.save_pending_draft(draft)
    preview = _html_to_preview_text(html)
    summary_block = f"📝 한글 요약:\n{summary_ko}\n\n---\n\n" if summary_ko else ""
    telegram_client.send_message(
        f"[새 초안]\n{summary_block}제목: {args.title}\n\n{preview}"
        f"{_reviewer_note_block(args)}\n\n---\n승인하려면 '승인', 수정하려면 원하는 내용을 답장해주세요."
    )
    print(json.dumps({"status": "sent_for_approval"}, ensure_ascii=False))


def cmd_revise_draft(args):
    pending = state.load_pending_draft()
    if not pending:
        print(json.dumps({"status": "error", "message": "대기 중인 초안이 없습니다"}, ensure_ascii=False))
        return
    html = _read_html(args)
    summary_ko = _read_summary_ko(args)
    pending["title"] = args.title
    pending["html"] = html
    if args.meta_description:
        pending["meta_description"] = args.meta_description
    if args.content_id:
        # 같은 글을 다듬는 게 아니라 사용자가 완전히 다른 주제로 바꿔달라고 한 경우
        pending["content_id"] = args.content_id
    state.save_pending_draft(pending)
    preview = _html_to_preview_text(html)
    summary_block = f"📝 한글 요약:\n{summary_ko}\n\n---\n\n" if summary_ko else ""
    telegram_client.send_message(
        f"[수정된 초안]\n{summary_block}제목: {args.title}\n\n{preview}"
        f"{_reviewer_note_block(args)}\n\n---\n승인하려면 '승인', 추가로 수정하려면 원하는 내용을 답장해주세요."
    )
    print(json.dumps({"status": "sent_for_approval"}, ensure_ascii=False))


def cmd_publish(args):
    pending = state.load_pending_draft()
    if not pending:
        print(json.dumps({"status": "error", "message": "대기 중인 초안이 없습니다"}, ensure_ascii=False))
        return
    result = blogger_client.publish_post(
        pending["title"],
        pending["html"],
        is_draft=False,
        search_description=pending.get("meta_description"),
    )
    state.add_posted_id(pending["content_id"])
    state.clear_pending_draft()
    telegram_client.send_message(_published_message(result, pending.get("meta_description")))
    print(json.dumps({"status": "published", "url": result.get("url")}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="KoreaTravelBlog 파이프라인 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-replies")
    sub.add_parser("fetch-monthly-festivals")
    sub.add_parser("fetch-biweekly-events")
    sub.add_parser("next-tip")
    sub.add_parser("fetch-next")

    p_search = sub.add_parser("search-topic")
    p_search.add_argument("--keyword", required=True)

    p_detail = sub.add_parser("fetch-detail")
    p_detail.add_argument("--content-id", required=True)
    p_detail.add_argument("--content-type-id", required=True)

    p_save = sub.add_parser("save-draft")
    p_save.add_argument("--title", required=True)
    p_save.add_argument("--content-id", required=True, help="TourAPI contentId 또는 팁 id. 콤마로 여러 id 지정 가능 (여러 축제를 한 로스터 글로 묶을 때 등)")
    p_save.add_argument("--html-file")
    p_save.add_argument("--summary-ko-file", help="텔레그램에 같이 보낼 한글 소주제 요약 (블로그 본문에는 안 들어감)")
    p_save.add_argument("--meta-description", help="검색결과 요약(searchDescription)용 영문 150~160자 내외 문구")
    p_save.add_argument("--reviewer-note", help="텔레그램 메시지에만 덧붙이는 안내 문구 (예: 지도 이미지 추가 요청). 블로그 본문에는 안 들어감")

    p_revise = sub.add_parser("revise-draft")
    p_revise.add_argument("--title", required=True)
    p_revise.add_argument("--html-file")
    p_revise.add_argument("--content-id", help="완전히 다른 주제로 바꾸는 경우에만 지정 (콤마로 여러 id 지정 가능 — 여러 글감을 한 포스팅으로 묶을 때)")
    p_revise.add_argument("--summary-ko-file", help="텔레그램에 같이 보낼 한글 소주제 요약 (블로그 본문에는 안 들어감)")
    p_revise.add_argument("--meta-description", help="검색결과 요약(searchDescription)용 영문 150~160자 내외 문구")
    p_revise.add_argument("--reviewer-note", help="텔레그램 메시지에만 덧붙이는 안내 문구 (예: 지도 이미지 추가 요청). 블로그 본문에는 안 들어감")

    sub.add_parser("publish")

    args = parser.parse_args()
    handlers = {
        "check-replies": cmd_check_replies,
        "fetch-monthly-festivals": cmd_fetch_monthly_festivals,
        "fetch-biweekly-events": cmd_fetch_biweekly_events,
        "next-tip": cmd_next_tip,
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
