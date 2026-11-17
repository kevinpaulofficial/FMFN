import json, os, re, html, shutil, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor

PER_SOURCE = 15             # montako uusinta uutista per syöte
MAX_AGE = timedelta(days=7) # tätä vanhempia ei tallenneta
DATA_DIR = "data"
ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]*$")  # ei alaviivaa: se erottaa lähteen ja alalähteen tiedostonimessä

# Tiedostorakenne (sama sääntö on sivulla, index.html: loadCat):
#   data/<lähde>/<lähde>.json               koko lähteen uutiset (kaikki alalähteet yhdessä)
#   data/<lähde>/<lähde>_<alalähde>.json    yhden alalähteen uutiset
# Lähteellä, jolla ei ole alalähteitä, on vain data/<lähde>/<lähde>.json.


def whole_file(sid):
    return os.path.join(DATA_DIR, sid, sid + ".json")


def feed_file(fid):
    return os.path.join(DATA_DIR, fid.split("_")[0], fid + ".json")


def source_list(data):
    """Lähteet ja niiden syötteet lahteet.json:sta.

    Palauttaa listan: {"id": lähde, "feeds": [{"id": syöte, "rss": osoite}, ...]}.
    Lähteen oma rss -> syöte "<lähde>"; alalähde -> syöte "<lähde>_<alalähde>".
    Virheelliset ja päällekkäiset tunnukset ohitetaan ja niistä tulostetaan varoitus.
    """
    out, ids = [], set()
    for src in data["lahteet"]:
        sid = src.get("id", "")
        if not ID_OK.match(sid) or sid in ids:
            print(sid, "OHITETTU: virheellinen tai jo käytössä oleva lähteen id")
            continue
        ids.add(sid)
        feeds = []
        subs = src.get("alalahteet", [])
        if src.get("rss") and subs:
            print(sid, "OHITETTU oma rss: lähteellä on alalähteitä, joten käytetään vain niitä")
        elif src.get("rss"):
            feeds.append({"id": sid, "rss": src["rss"]})
        seen = set()
        for sub in subs:
            aid = sub.get("id", "")
            if not ID_OK.match(aid) or aid in seen:
                print(sid, aid, "OHITETTU: virheellinen tai jo käytössä oleva alalähteen id")
            elif not sub.get("rss"):
                print(sid, aid, "OHITETTU: rss-osoite puuttuu")
            else:
                seen.add(aid)
                feeds.append({"id": sid + "_" + aid, "rss": sub["rss"]})
        if feeds:
            out.append({"id": sid, "feeds": feeds})
        else:
            print(sid, "OHITETTU: ei rss-osoitetta eikä alalähteitä")
    return out


def feed_list(data):
    return [f for s in source_list(data) for f in s["feeds"]]


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


def load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def save(path, name, items):
    """Kirjoittaa tiedoston vain, jos uutiset muuttuivat (muuten jokainen ajo muuttaisi jokaista tiedostoa)."""
    old = load(path)
    if old and old.get("uutiset") == items:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"lahde": name, "haettu": datetime.now(timezone.utc).isoformat(), "uutiset": items},
                  f, ensure_ascii=False, separators=(",", ":"))
    return True


def main():
    sources = source_list(json.load(open("lahteet.json", encoding="utf-8")))
    feeds = [f for s in sources for f in s["feeds"]]
    with ThreadPoolExecutor(10) as ex:
        got = {fid: (items, err) for fid, items, err in ex.map(read, feeds)}

    keep, total = set(), 0
    for src in sources:
        sid, many = src["id"], len(src["feeds"]) > 1 or src["feeds"][0]["id"] != src["id"]
        whole = []
        for feed in src["feeds"]:
            fid = feed["id"]
            path = feed_file(fid)
            keep.add(path)
            items, err = got[fid]
            if err:
                # virheen sattuessa edellinen tiedosto jää voimaan, jotta uutiset eivät katoa sivulta
                print(fid, "VIRHE", err)
                items = (load(path) or {}).get("uutiset", [])
            else:
                print(fid, "OK %d" % len(items) + ("" if save(path, fid, items) else " (ei muutoksia)"))
                total += len(items)
            whole += items
        if many:
            # koko lähteen tiedosto: kaikkien alalähteiden uutiset yhdessä
            path = whole_file(sid)
            keep.add(path)
            whole.sort(key=lambda x: x["p"] or "", reverse=True)
            whole.sort(key=lambda x: x["l"])
            if save(path, sid, whole):
                print(sid, "koko lähde päivitetty (%d)" % len(whole))

    # siivous: poistetaan tiedostot ja kansiot, joiden lähdettä ei ole enää lahteet.json:ssa
    keep = {os.path.normpath(k) for k in keep}
    for root, dirs, files in os.walk(DATA_DIR, topdown=False):
        for name in files:
            path = os.path.normpath(os.path.join(root, name))
            if path not in keep:
                os.remove(path)
                print("Poistettu vanha tiedosto", path)
        if root != DATA_DIR and not os.listdir(root):
            shutil.rmtree(root)

    print("Lähteitä:", len(sources), "· syötteitä:", len(feeds), "· uutisia:", total)


if __name__ == "__main__":
    main()
