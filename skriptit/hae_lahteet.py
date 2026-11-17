import json, os, re, html, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor

PER_SOURCE = 15             # montako uusinta uutista per lähde
MAX_AGE = timedelta(days=7) # tätä vanhempia ei tallenneta
DATA_DIR = "data"           # jokainen syöte omaan tiedostoonsa: data/<syötteen id>.json
ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def feed_file(fid):
    # sama sääntö on sivulla (index.html, feedFile): data/<syötteen id>.json
    return os.path.join(DATA_DIR, fid + ".json")


def feed_list(data):
    """Kaikki haettavat syötteet lahteet.json:sta.

    Lähteen oma rss -> syöte, jonka id on lähteen id (esim. "hs").
    Alalähde -> syöte, jonka id on "<lähteen id>-<alalähteen id>" (esim. "yle-talous").
    """
    feeds, ids = [], set()

    def add(fid, rss):
        if not ID_OK.match(fid):
            print(fid, "OHITETTU: id saa sisältää vain pieniä kirjaimia a-z, numeroita ja viivoja")
        elif fid in ids:
            print(fid, "OHITETTU: sama id on jo käytössä")
        elif not rss:
            print(fid, "OHITETTU: rss-osoite puuttuu")
        else:
            ids.add(fid)
            feeds.append({"id": fid, "rss": rss})

    for src in data["lahteet"]:
        if src.get("rss"):
            add(src["id"], src["rss"])
        for sub in src.get("alalahteet", []):
            add(src["id"] + "-" + sub["id"], sub.get("rss"))
    return feeds


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


def read(feed):
    fid, rss = feed["id"], feed["rss"]
    try:
        req = urllib.request.Request(rss, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        return fid, [], str(e)[:80]
    now = datetime.now(timezone.utc)
    out, seen = [], set()
    for it in root.iter():
        if local(it.tag) not in ("item", "entry"):
            continue
        d = parse_date(text(it, "pubDate", "published", "updated", "date"))
        if d and now - d > MAX_AGE:
            continue
        t = clean(text(it, "title"))
        u = link(it)
        if not t or not u or u in seen:
            continue
        seen.add(u)
        out.append({
            "l": fid,
            "t": t,
            "u": u,
            "p": d.isoformat() if d else None,
            "s": clean(text(it, "description", "summary", "encoded"))[:300],
            "i": image(it),
        })
    out.sort(key=lambda x: x["p"] or "", reverse=True)
    return fid, out[:PER_SOURCE], None


def main():
    data = json.load(open("lahteet.json", encoding="utf-8"))
    feeds = feed_list(data)
    os.makedirs(DATA_DIR, exist_ok=True)
    with ThreadPoolExecutor(10) as ex:
        results = list(ex.map(read, feeds))

    total = 0
    for fid, got, err in results:
        path = feed_file(fid)
        if err:
            # virheen sattuessa edellinen tiedosto jää voimaan, jotta uutiset eivät katoa sivulta
            print(fid, "VIRHE", err)
            continue
        total += len(got)
        old = None
        if os.path.exists(path):
            try:
                old = json.load(open(path, encoding="utf-8"))
            except Exception:
                old = None
        # kirjoitetaan vain, jos uutiset muuttuivat: muuten jokainen ajo muuttaisi jokaista tiedostoa
        if old and old.get("uutiset") == got:
            print(fid, "OK %d (ei muutoksia)" % len(got))
            continue
        out = {"lahde": fid, "haettu": datetime.now(timezone.utc).isoformat(), "uutiset": got}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        print(fid, "OK %d" % len(got))

    # poistetaan tiedostot, joiden syöte ei ole enää lahteet.json:ssa
    keep = {os.path.basename(feed_file(f["id"])) for f in feeds}
    for name in os.listdir(DATA_DIR):
        if name.endswith(".json") and name not in keep:
            os.remove(os.path.join(DATA_DIR, name))
            print("Poistettu vanha tiedosto", name)

    print("Syötteitä:", len(feeds), "· uutisia:", total)


if __name__ == "__main__":
    main()
