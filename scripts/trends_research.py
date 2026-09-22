"""Google Trends(pytrends, 비공식)로 외국인 한국 여행 준비 검색어를 조사해 팁 백로그 후보를 찾는다.
백로그(state/tips_backlog.json)를 자동 수정하지 않고 결과만 출력한다 — 후보 채택은 사람이 판단.

사용법:
  python scripts/trends_research.py                    # 기본 시드, 상위 검색어 표 출력
  python scripts/trends_research.py --seeds "korea budget,korea hotel" --save trends.json
  python scripts/trends_research.py --timeframe "today 3-m" --geo US

주의: 비공식 API라 요청이 잦으면 429로 차단될 수 있다(시드 사이 --sleep 간격 유지).
"""
import argparse
import json
import sys
import time

from pytrends.request import TrendReq

DEFAULT_SEEDS = [
    "korea travel tips",
    "korea trip cost",
    "korea itinerary",
    "korea hotel",
    "korea transportation",
    "korea visa",
    "korea sim card",
    "korea travel pass",
    "best time to visit korea",
    "seoul things to do",
    "busan travel",
    "jeju travel",
]
TRAVEL_CATEGORY = 67
NOISE = ("news", "north korea", "ai ", "anthropic", "nvidia", "openai", "lidl", "python", "meaning")


def is_noise(query):
    q = query.lower()
    return any(n in q for n in NOISE)


def fetch(pt, seed, timeframe, geo, cat):
    pt.build_payload([seed], cat=cat, timeframe=timeframe, geo=geo)
    rq = pt.related_queries().get(seed, {})
    result = {}
    for kind in ("top", "rising"):
        df = rq.get(kind)
        rows = df.to_dict("records") if df is not None else []
        result[kind] = [r for r in rows if not is_noise(r["query"])]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", help="콤마 구분 시드. 생략하면 기본 시드")
    ap.add_argument("--timeframe", default="today 12-m")
    ap.add_argument("--geo", default="", help="국가 코드(예: US). 생략하면 전 세계")
    ap.add_argument("--cat", type=int, default=TRAVEL_CATEGORY, help="Trends 카테고리(67=여행, 0=전체). 저검색량 시드가 비면 0으로")
    ap.add_argument("--sleep", type=float, default=6.0)
    ap.add_argument("--save", help="결과 JSON 저장 경로")
    args = ap.parse_args()

    seeds = [s.strip() for s in args.seeds.split(",")] if args.seeds else DEFAULT_SEEDS
    pt = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
    out = {}
    for seed in seeds:
        try:
            out[seed] = fetch(pt, seed, args.timeframe, args.geo, args.cat)
        except Exception as e:
            out[seed] = {"error": repr(e)}
            print(f"fail {seed}: {e!r}"[:200], file=sys.stderr)
        time.sleep(args.sleep)

    for seed, v in out.items():
        print(f"== {seed}")
        if "error" in v:
            print("  error:", v["error"])
            continue
        print("  TOP   :", "; ".join(f"{r['query']}({r['value']})" for r in v["top"][:12]))
        print("  RISING:", "; ".join(f"{r['query']}({r['value']})" for r in v["rising"][:8]))

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
