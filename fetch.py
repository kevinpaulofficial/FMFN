import json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

NS = {"media": "http://search.yahoo.com/mrss/"}

KEYWORDS = {
    "suomi": ["hallitus", "eduskunta", "orpo", "stubb", "budjetti", "vero",
              "työttömyys", "työllisyys", "irtisanom", "yt-neuvottelu",
              "inflaatio", "korko", "raja", "rajavartio", "nato", "venäjä",
              "turvallisuus", "pakote", "vaali", "eurovision", "euroviisut",
              "idols", "tangomarkkinat", "emma-gaala"],
    "jalkapallo": ["premier league", "champions league", "uefa", "world cup",
                   "mm-kisat", "mm-", "euro 20", "final", "finaali",
                   "ballon d'or", "derby", "clasico"],
    "teknologia": ["quantum", "kvantti", "tekoäly", "artificial intelligence",
                   "language model", "llm", "openai", "anthropic", "deepmind",
                   "gemini", "chatgpt", "claude", "cybersecurity", "kyber",
                   "hack", "breach", "ransomware", "vulnerability", "tietomurto"],
    "maailma": ["war", "ceasefire", "ukraine", "gaza", "israel", "russia",
                "china", "taiwan", "election", "sanctions", "tariff",
                "inflation", "recession", "interest rate", "central bank",
                "energy", "oil"],
    "musiikki": ["album", "debut", "tour", "festival", "announces", "reunion",
                 "dies", "electronic", "techno", "house", "rave", "suomi",
                 "finnish", "breakthrough", "rising"],
}

STOP = set("the a an of to in on for and with from at by is are was were be as it its this that after over into new says say ja on ei että oli ovat se tai kuin mutta jo vai myös".split())


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
        "hot": False,
    } for it in root.iter("item")]


def score(item, words):
    title = item["title"].lower()
    return sum(1 for w in words if re.search(r"\b" + re.escape(w), title))


def words(title):
    return {w for w in re.findall(r"\w{4,}", title.lower()) if w not in STOP}


def mark_hot(items):
    ws = [words(i["title"]) for i in items]
    for n, a in enumerate(items):
        shared = sum(1 for m, b in enumerate(ws) if m != n and len(ws[n] & b) >= 2)
        a["hot"] = shared >= 2


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
    mark_hot(items)
    items = items[:12]
    best = max(items, key=lambda x: score(x, KEYWORDS.get(cat, [])), default=None)
    if best and score(best, KEYWORDS.get(cat, [])) > 0:
        best["important"] = True
    result[cat] = items

json.dump(result, open("news.json", "w"), ensure_ascii=False, indent=1)
