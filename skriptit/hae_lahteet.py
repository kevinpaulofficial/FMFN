import json, re, html, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor

PER_SOURCE = 15             # montako uusinta uutista per lähde
MAX_AGE = timedelta(days=7) # tätä vanhempia ei tallenneta


def local(tag):
    return tag.split("}")[-1]


def clean(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def text(el, *names):
    for n in names:
        for c in el:
            if local(c.tag) == n and (c.text or "").strip():
                return c.text.strip()
    return ""


def link(el):
    for c in el:
        if local(c.tag) == "link":
            if c.get("href") and c.get("rel", "alternate") == "alternate":
                return c.get("href")
            if (c.text or "").strip():
                return c.text.strip()
    return ""


def image(el):
    for c in el.iter():
        n = local(c.tag)
        if n in ("content", "thumbnail") and c.get("url"):
            if c.get("medium") == "image" or (c.get("type") or "image").startswith("image"):
                return c.get("url")
        if n == "enclosure" and (c.get("type") or "").startswith("image"):
            return c.get("url")
    return None


def read(src):
    try:
        req = urllib.request.Request(src["rss"], headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        return src["id"], [], str(e)[:80]
    now = datetime.now(timezone.utc)
    out = []
    for it in root.iter():
        if local(it.tag) not in ("item", "entry"):
            continue
        d = parse_date(text(it, "pubDate", "published", "updated", "date"))
        if d and now - d > MAX_AGE:
            continue
        t = clean(text(it, "title"))
        u = link(it)
        if not t or not u:
            continue
        out.append({
            "l": src["id"],
            "t": t,
            "u": u,
            "p": d.isoformat() if d else None,
            "s": clean(text(it, "description", "summary", "encoded"))[:300],
            "i": image(it),
        })
    out.sort(key=lambda x: x["p"] or "", reverse=True)
    return src["id"], out[:PER_SOURCE], None


def main():
    data = json.load(open("lahteet.json", encoding="utf-8"))
    with ThreadPoolExecutor(10) as ex:
        results = list(ex.map(read, data["lahteet"]))

    items = []
    for sid, got, err in results:
        print(sid, "VIRHE " + err if err else "OK %d" % len(got))
        items += got

    seen, uniq = set(), []
    for x in items:
        if x["u"] not in seen:
            seen.add(x["u"])
            uniq.append(x)
    # vakaa järjestys (lähde, uusin ensin), jotta tiedosto muuttuu ajojen välillä mahdollisimman vähän
    uniq.sort(key=lambda x: x["p"] or "", reverse=True)
    uniq.sort(key=lambda x: x["l"])

    out = {"haettu": datetime.now(timezone.utc).isoformat(), "uutiset": uniq}
    json.dump(out, open("kaikki.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("Uutisia yhteensä:", len(uniq))


if __name__ == "__main__":
    main()
