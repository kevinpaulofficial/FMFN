import json, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor


def check(src):
    try:
        req = urllib.request.Request(src["rss"], headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=20).read()
        root = ET.fromstring(data)
        n = sum(1 for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry"))
        return src["id"], n, None
    except Exception as e:
        return src["id"], 0, str(e)[:80]


data = json.load(open("lahteet.json", encoding="utf-8"))
with ThreadPoolExecutor(10) as ex:
    results = list(ex.map(check, data["lahteet"]))

by = {r[0]: r for r in results}
ok = 0
for s in data["lahteet"]:
    _, n, err = by[s["id"]]
    s["testattu"] = n > 0
    ok += n > 0
    print(s["id"], "OK" if n > 0 else "VIRHE", n if n > 0 else err)

print("Toimivia:", ok, "/", len(data["lahteet"]))
json.dump(data, open("lahteet.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
