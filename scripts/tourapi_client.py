"""한국관광공사 TourAPI 4.0 클라이언트.

기준 문서: data.go.kr "한국관광공사_국문 관광정보 서비스"
API 버전(KorService1/2 등)은 공공데이터포털에서 종종 개편되므로,
호출이 404/오류로 실패하면 TOURAPI_BASE_URL 환경변수로 최신 base URL을 덮어써서 쓴다.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOURAPI_KEY = os.getenv("TOURAPI_KEY", "")
BASE_URL = os.getenv("TOURAPI_BASE_URL", "https://apis.data.go.kr/B551011/KorService2")

# TourAPI 지역코드 (시/도 단위, 세종 포함 17개)
AREA_CODES = [
    "1", "2", "3", "4", "5", "6", "7", "8",
    "31", "32", "33", "34", "35", "36", "37", "38", "39",
]

CONTENT_TYPE_ID_TOURIST_SPOT = "12"

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
    header = body.get("response", {}).get("header", {})
    if header.get("resultCode") not in (None, "0000", "00"):
        raise RuntimeError(f"TourAPI 오류: {header}")
    return body.get("response", {}).get("body", {})


def get_area_based_list(area_code, content_type_id=CONTENT_TYPE_ID_TOURIST_SPOT, page_no=1, num_of_rows=20):
    body = _get(
        "areaBasedList2",
        areaCode=area_code,
        contentTypeId=content_type_id,
        pageNo=page_no,
        numOfRows=num_of_rows,
        arrange="A",
    )
    items = body.get("items", {})
    if not items:
        return []
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list


def get_detail_common(content_id):
    body = _get(
        "detailCommon2",
        contentId=content_id,
        defaultYN="Y",
        overviewYN="Y",
        addrinfoYN="Y",
        firstImageYN="Y",
    )
    items = body.get("items", {})
    if not items:
        return {}
    item = items.get("item", {})
    if isinstance(item, list):
        item = item[0] if item else {}
    return item


def get_detail_intro(content_id, content_type_id=CONTENT_TYPE_ID_TOURIST_SPOT):
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


def fetch_attraction_bundle(content_id, content_type_id=CONTENT_TYPE_ID_TOURIST_SPOT):
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
            if cid and cid not in posted_ids:
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
