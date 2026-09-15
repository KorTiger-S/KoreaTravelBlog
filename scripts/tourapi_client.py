"""한국관광공사 TourAPI 4.0 클라이언트 (영문 관광정보서비스, EngService2).

기준 문서: data.go.kr "한국관광공사_영문 관광정보서비스_GW"
콘텐츠 분류 코드(contentTypeId)는 국문 서비스(KorService2)와 값 체계가 다르고,
항목마다 제각각이므로 하드코딩하지 않고 목록 조회 결과의 contenttypeid를 그대로 사용한다.
"""
import os
import sys
from datetime import date

import requests
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

TOURAPI_KEY = os.getenv("TOURAPI_KEY", "")
BASE_URL = os.getenv("TOURAPI_BASE_URL", "https://apis.data.go.kr/B551011/EngService2")

# TourAPI 지역코드 (시/도 단위, 세종 포함 17개)
AREA_CODES = [
    "1", "2", "3", "4", "5", "6", "7", "8",
    "31", "32", "33", "34", "35", "36", "37", "38", "39",
]

_COMMON_PARAMS = {
    "MobileOS": "ETC",
    "MobileApp": "KoreaTravelBlog",
    "_type": "json",
}


def _get(endpoint, **params):
    if not TOURAPI_KEY:
        raise RuntimeError("TOURAPI_KEY가 설정되어 있지 않습니다 (.env 확인)")
    url = f"{BASE_URL}/{endpoint}"
    query = dict(_COMMON_PARAMS)
    query.update(params)
    query["serviceKey"] = TOURAPI_KEY
    resp = requests.get(url, params=query, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    if "response" not in body:
        # 이 API는 오류를 {"resultCode": "10", "resultMsg": "..."} 형태(래핑 없이)로 돌려준다
        raise RuntimeError(f"TourAPI 오류: {body}")
    header = body["response"].get("header", {})
    if header.get("resultCode") not in ("0000", "00"):
        raise RuntimeError(f"TourAPI 오류: {header}")
    return body["response"].get("body", {})


def get_area_based_list(area_code, content_type_id=None, page_no=1, num_of_rows=20):
    params = {
        "areaCode": area_code,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "arrange": "A",
    }
    if content_type_id:
        params["contentTypeId"] = content_type_id
    body = _get("areaBasedList2", **params)
    items = body.get("items", {})
    if not items:
        return []
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list


def search_keyword(keyword, page_no=1, num_of_rows=10):
    """사용자가 텔레그램으로 직접 요청한 주제를 찾을 때 쓰는 키워드 검색."""
    body = _get(
        "searchKeyword2",
        keyword=keyword,
        pageNo=page_no,
        numOfRows=num_of_rows,
    )
    items = body.get("items", {})
    if not items:
        return []
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list


def get_detail_common(content_id):
    body = _get("detailCommon2", contentId=content_id)
    items = body.get("items", {})
    if not items:
        return {}
    item = items.get("item", {})
    if isinstance(item, list):
        item = item[0] if item else {}
    return item


def get_detail_intro(content_id, content_type_id):
    body = _get(
        "detailIntro2",
        contentId=content_id,
        contentTypeId=content_type_id,
    )
    items = body.get("items", {})
    if not items:
        return {}
    item = items.get("item", {})
    if isinstance(item, list):
        item = item[0] if item else {}
    return item


def get_detail_images(content_id):
    body = _get(
        "detailImage2",
        contentId=content_id,
        imageYN="Y",
    )
    items = body.get("items", {})
    if not items:
        return []
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return [i.get("originimgurl") for i in item_list if i.get("originimgurl")]


def fetch_attraction_bundle(content_id, content_type_id):
    """블로그 초안 작성에 필요한 정보를 한 번에 모아서 반환."""
    common = get_detail_common(content_id)
    intro = get_detail_intro(content_id, content_type_id)
    images = get_detail_images(content_id)
    if not images and common.get("firstimage"):
        images = [common["firstimage"]]
    return {
        "content_id": content_id,
        "title": common.get("title"),
        "addr": " ".join(filter(None, [common.get("addr1"), common.get("addr2")])),
        "tel": common.get("tel"),
        "homepage": common.get("homepage"),
        "overview": common.get("overview"),
        "mapx": common.get("mapx"),
        "mapy": common.get("mapy"),
        "images": images,
        "intro": intro,
    }


# 여행 가이드 블로그에 어울리는 대분류만 사용 (자연/문화예술역사/레포츠/음식).
# 쇼핑(A04)·교통(B01)·숙박(B02)은 "관광지 소개" 글감으로는 제외.
ALLOWED_CAT1 = {"A01", "A02", "A03", "A05"}
# A0202(Recreational Sites) 안에는 병원/성형외과 등 "의료관광" 항목이 섞여 있어 별도 제외.
EXCLUDED_CAT3 = {"A02020500"}  # Medical Tourism Sites


def _is_relevant_attraction(item):
    return item.get("cat1") in ALLOWED_CAT1 and item.get("cat3") not in EXCLUDED_CAT3


# 외국인 여행자가 대중교통으로 당일/1박 접근하기 쉬운 수도권(서울·인천·경기)만 다룬다.
# EngService2의 areacode/sigungucode는 항상 빈 값이라, lDongRegnCd(행정구역 코드)로 걸러야 한다.
CAPITAL_AREA_REGION_CODES = {"11", "28", "41"}  # 11=서울, 28=인천, 41=경기
SEOUL_REGION_CODE = "11"
# lclsSystm2 == "EV01"은 진짜 축제/전통행사 (search_festivals, 월말 트리거).
# EV02/EV03(전시·공연·행사 등)은 한강·서울숲·광화문 같은 핫플레이스 "행사"로 따로 다룬다
# (search_hotspot_events, 격주 월요일 트리거). 단 "몇 달짜리 상설 프로그램"(APAP 작품투어처럼
# 연중 내내 여는 전시투어)까지 섞이므로, 기간이 이 값(일) 이하인 것만 "행사"로 인정한다.
MAX_EVENT_DURATION_DAYS = 60


def _event_duration_days(item):
    try:
        start = date(*map(int, [item["eventstartdate"][:4], item["eventstartdate"][4:6], item["eventstartdate"][6:8]]))
        end = date(*map(int, [item["eventenddate"][:4], item["eventenddate"][4:6], item["eventenddate"][6:8]]))
        return (end - start).days
    except (KeyError, ValueError, TypeError):
        return None


def _search_festival_api(event_start_date, event_end_date, num_of_rows):
    body = _get(
        "searchFestival2",
        eventStartDate=event_start_date,
        eventEndDate=event_end_date,
        numOfRows=num_of_rows,
        pageNo=1,
        arrange="A",
    )
    items = body.get("items", {})
    item_list = items.get("item", []) if items else []
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list


def _filter_capital_area_seoul_first(item_list, predicate):
    filtered = [it for it in item_list if it.get("lDongRegnCd") in CAPITAL_AREA_REGION_CODES and predicate(it)]
    filtered.sort(
        key=lambda it: (
            it.get("lDongRegnCd") != SEOUL_REGION_CODE,
            it.get("eventstartdate") or "",
        )
    )
    return filtered


def search_festivals(event_start_date, event_end_date, num_of_rows=100):
    """지정 기간(YYYYMMDD)과 겹치는 수도권 "대형 축제" 조회 (월말 다음 달 축제 로스터용).

    lclsSystm2 == "EV01"(진짜 축제/전통행사)만 포함한다. 한강·서울숲·광화문 같은 핫플레이스의
    전시/공연 등 자잘한 "행사"는 search_hotspot_events()가 별도로 담당한다.
    외국인 접근성을 위해 수도권(CAPITAL_AREA_REGION_CODES) 밖은 제외하고,
    서울(SEOUL_REGION_CODE) 항목이 먼저 오도록 정렬해서 반환한다."""
    item_list = _search_festival_api(event_start_date, event_end_date, num_of_rows)
    return _filter_capital_area_seoul_first(item_list, lambda it: it.get("lclsSystm2") == "EV01")


def search_hotspot_events(event_start_date, event_end_date, num_of_rows=100):
    """지정 기간(YYYYMMDD)과 겹치는 수도권 "행사"(격주 월요일 로스터용) 조회.

    lclsSystm2 == "EV02"/"EV03"(전시·공연·팝업 등, 대형 축제로 분류 안 된 것) 중
    기간이 MAX_EVENT_DURATION_DAYS 이하인 것만 포함해 "연중 상설 프로그램" 노이즈를 걸러낸다.
    외국인 접근성을 위해 수도권(CAPITAL_AREA_REGION_CODES) 밖은 제외하고,
    서울(SEOUL_REGION_CODE) 항목이 먼저 오도록 정렬해서 반환한다."""
    item_list = _search_festival_api(event_start_date, event_end_date, num_of_rows)

    def _is_relevant_event(it):
        if it.get("lclsSystm2") not in ("EV02", "EV03"):
            return False
        duration = _event_duration_days(it)
        return duration is not None and duration <= MAX_EVENT_DURATION_DAYS

    return _filter_capital_area_seoul_first(item_list, _is_relevant_event)


def find_next_unposted(posted_ids):
    """area/page 커서를 순회하며 아직 posted_ids에 없는 관광지 1건을 찾는다."""
    from state import load_crawl_cursor, save_crawl_cursor

    cursor = load_crawl_cursor()
    areas_tried = 0
    n_areas = len(AREA_CODES)

    while areas_tried < n_areas:
        area_code = AREA_CODES[cursor["area_index"]]
        items = get_area_based_list(area_code, page_no=cursor["page_no"])

        picked = None
        for item in items:
            cid = item.get("contentid")
            if cid and cid not in posted_ids and _is_relevant_attraction(item):
                picked = item
                break

        cursor["area_index"] = (cursor["area_index"] + 1) % n_areas
        if cursor["area_index"] == 0:
            cursor["page_no"] += 1
        areas_tried += 1

        if picked:
            save_crawl_cursor(cursor)
            return picked

    save_crawl_cursor(cursor)
    return None


if __name__ == "__main__":
    # 단독 실행: TourAPI 키가 유효한지, 목록이 정상적으로 오는지 확인용
    sample = get_area_based_list(area_code="1", page_no=1, num_of_rows=5)
    print(f"서울 관광지 {len(sample)}건 조회됨")
    for it in sample:
        print(f"- [{it.get('contentid')}] {it.get('title')}")
