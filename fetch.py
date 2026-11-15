import json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

NS = {"media": "http://search.yahoo.com/mrss/"}

KEYWORDS = {
    "suomi": ["hallitus", "eduskunta", "presidentti", "stubb", "orpo", "vaali",
              "onnettomuus", "poliisi", "pakote", "raja", "budjetti", "inflaatio"],
    "jalkapallo": ["premier league", "champions league", "world cup", "mm-",
                   "final", "finaali", "transfer", "sacked", "title"],
    "teknologia": ["quantum", "kvantti", "tekoäly", "artificial intelligence",
                   "openai", "anthropic", "nvidia", "breakthrough", "chip", "launch"],
    "maailma": ["war", "ceasefire", "election", "earthquake", "summit",
                "attack", "president", "sanctions", "crisis"],
    "musiikki": ["album", "tour", "festival", "grammy", "announces", "dies", "reunion"],
}

def clean(t):
    return re.sub(r"<[^>]+>", "", t or "").strip()

def parse_date(s):
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def image(item):
    for tag in ("media:content", "media:thumbnail"):
        e = item.find(tag, NS)
        if e is not None and e.get("url"):
            return e.get("url")
    e = item.find("enclosure")
    if e is not None and (e.get("type") or "").startswith("image"):
        return e.get("url")
    return None

def read_feed(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    return [{
        "title": clean(it.findtext("title")),
        "link": (it.findtext("link") or "").strip(),
        "published": parse_date(it.findtext("pubDate") or ""),
        "description": clean(it.findtext("description"))[:400],
        "image": image(it),
        "important": False,
    } for it in root.iter("item")]

def score(item, words):
    title = item["title"].lower()
    return sum(1 for w in words if re.search(r"\b" + re.escape(w), title))

sources = json.load(open("sources.json"))
result = {}
for cat, urls in sources.items():
    items = []
    for url in urls:
        try:
            got = read_feed(url)
            print(cat, url, "OK", len(got))
            items += got
        except Exception as e:
            print(cat, url, "VIRHE", e)
    items.sort(key=lambda x: x["published"] or "", reverse=True)
    items = items[:8]
    best = max(items, key=lambda x: score(x, KEYWORDS.get(cat, [])), default=None)
    if best and score(best, KEYWORDS.get(cat, [])) > 0:
        best["important"] = True
    result[cat] = items

json.dump(result, open("news.json", "w"), ensure_ascii=False, indent=1)
