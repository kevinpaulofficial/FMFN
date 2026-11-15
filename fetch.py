import json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

NS = {"media": "http://search.yahoo.com/mrss/"}

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
    } for it in root.iter("item")]

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
    result[cat] = items[:8]

json.dump(result, open("news.json", "w"), ensure_ascii=False, indent=1)
