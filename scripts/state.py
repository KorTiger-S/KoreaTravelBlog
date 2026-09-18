"""state/ 디렉터리의 JSON 파일을 읽고 쓰는 헬퍼."""
import json
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT_DIR, "state")

POSTED_PATH = os.path.join(STATE_DIR, "posted.json")
PENDING_DRAFT_PATH = os.path.join(STATE_DIR, "pending_draft.json")
TELEGRAM_OFFSET_PATH = os.path.join(STATE_DIR, "telegram_offset.json")
CRAWL_CURSOR_PATH = os.path.join(STATE_DIR, "crawl_cursor.json")
TIPS_BACKLOG_PATH = os.path.join(STATE_DIR, "tips_backlog.json")
DESTINATION_THEME_BACKLOG_PATH = os.path.join(STATE_DIR, "destination_theme_backlog.json")
FOOD_TOPIC_BACKLOG_PATH = os.path.join(STATE_DIR, "food_topic_backlog.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return default
        return json.loads(content)


def save_json(path, data):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_posted_ids():
    data = load_json(POSTED_PATH, {"content_ids": []})
    return set(data.get("content_ids", []))


def add_posted_id(content_id):
    """content_id에 콤마(,)가 있으면 여러 개를 한 번에 기록한다.
    (예: 여러 축제를 한 글로 묶은 로스터 포스팅 발행 시 각 축제 id를 모두 기록)"""
    data = load_json(POSTED_PATH, {"content_ids": []})
    ids = data.get("content_ids", [])
    if isinstance(content_id, str) and "," in content_id:
        new_ids = [c.strip() for c in content_id.split(",") if c.strip()]
    else:
        new_ids = [content_id]
    for nid in new_ids:
        if nid not in ids:
            ids.append(nid)
    save_json(POSTED_PATH, {"content_ids": ids})


def load_pending_draft():
    return load_json(PENDING_DRAFT_PATH, None)


def save_pending_draft(draft):
    save_json(PENDING_DRAFT_PATH, draft)


def clear_pending_draft():
    save_json(PENDING_DRAFT_PATH, None)


def load_telegram_offset():
    data = load_json(TELEGRAM_OFFSET_PATH, {"offset": 0})
    return data.get("offset", 0)


def save_telegram_offset(offset):
    save_json(TELEGRAM_OFFSET_PATH, {"offset": offset})


def load_crawl_cursor():
    return load_json(CRAWL_CURSOR_PATH, {"area_index": 0, "page_no": 1})


def save_crawl_cursor(cursor):
    save_json(CRAWL_CURSOR_PATH, cursor)


def load_tips_backlog():
    data = load_json(TIPS_BACKLOG_PATH, {"tips": []})
    return data.get("tips", [])


def load_destination_theme_backlog():
    data = load_json(DESTINATION_THEME_BACKLOG_PATH, {"themes": []})
    return data.get("themes", [])


def add_destination_theme(theme_id, topic):
    """목록이 소진됐을 때 에이전트가 같은 결의 새 테마를 직접 추가할 때 쓴다."""
    data = load_json(DESTINATION_THEME_BACKLOG_PATH, {"themes": []})
    themes = data.get("themes", [])
    if not any(t["id"] == theme_id for t in themes):
        themes.append({"id": theme_id, "topic": topic})
    save_json(DESTINATION_THEME_BACKLOG_PATH, {"themes": themes})


def load_food_topic_backlog():
    data = load_json(FOOD_TOPIC_BACKLOG_PATH, {"topics": []})
    return data.get("topics", [])


def add_food_topic(topic_id, topic):
    """목록이 소진됐을 때 에이전트가 같은 결의 새 주제를 직접 추가할 때 쓴다."""
    data = load_json(FOOD_TOPIC_BACKLOG_PATH, {"topics": []})
    topics = data.get("topics", [])
    if not any(t["id"] == topic_id for t in topics):
        topics.append({"id": topic_id, "topic": topic})
    save_json(FOOD_TOPIC_BACKLOG_PATH, {"topics": topics})
