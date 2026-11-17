import json, sys, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "skriptit")
from hae_lahteet import feed_list  # noqa: E402  (sama syötelista kuin haussa)


def check(feed):
    try:
        req = urllib.request.Request(feed["rss"], headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
        n = sum(1 for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry"))
        return feed["id"], n, None
    except Exception as e:
        return feed["id"], 0, str(e)[:80]


data = json.load(open("lahteet.json", encoding="utf-8"))
feeds = feed_list(data)
with ThreadPoolExecutor(10) as ex:
    by = {r[0]: r for r in ex.map(check, feeds)}

ok = 0
for fid, n, err in by.values():
    ok += n > 0
    print(fid, "OK" if n > 0 else "VIRHE", n if n > 0 else err)

# merkitään testattu jokaiselle lähteelle ja alalähteelle (lähde on kunnossa, kun kaikki sen syötteet toimivat)
for src in data["lahteet"]:
    own = []
    if src.get("rss"):
        own.append(by.get(src["id"], (0, 0))[1] > 0)
    for sub in src.get("alalahteet", []):
        sub["testattu"] = by.get(src["id"] + "_" + sub["id"], (0, 0))[1] > 0
        own.append(sub["testattu"])
    src["testattu"] = bool(own) and all(own)

print("Toimivia syötteitä:", ok, "/", len(feeds))
json.dump(data, open("lahteet.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
