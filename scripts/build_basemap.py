"""ONE-TIME build helper (not part of the offline demo runtime).

Fetches Bengaluru's road + water geometry for the dataset's bounding box from OpenStreetMap
(via the Overpass API) and bundles it into `web/basemap.js` as `window.PRAVAH_BASEMAP`. The
demo then renders a real street map FULLY OFFLINE — the network is touched only here, at build
time, exactly like the self-hosted fonts. Re-run only if you want to refresh the basemap.

    python scripts/build_basemap.py

Output is simplified (Ramer–Douglas–Peucker) and coordinate-rounded to keep it small.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

# Dataset bounding box (lat_min, lat_max, lon_min, lon_max) — matches the violations extent.
BBOX = (12.803, 13.294, 77.443, 77.772)
EPS = 0.00012            # ~13 m simplification tolerance
OUT = Path("web/basemap.js")
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
RANK = {  # highway tag -> draw rank (1 = arterial, 3 = minor)
    "motorway": 1, "trunk": 1, "primary": 1,
    "secondary": 2, "tertiary": 3,
}


def overpass(query: str) -> dict:
    data = ("data=" + urllib.request.quote(query)).encode()
    last = None
    for url in MIRRORS:
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "pravah-basemap/1.0"})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001 — try the next mirror
            last = e
            print(f"  mirror failed ({url.split('/')[2]}): {e}")
    raise RuntimeError(f"all Overpass mirrors failed: {last}")


def rdp(pts: list[list[float]], eps: float) -> list[list[float]]:
    """Iterative Ramer–Douglas–Peucker — drops points that don't change the shape much."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        dmax, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs((px - ax) * dy - (py - ay) * dx) / norm
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps and idx != -1:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [pts[i] for i in range(len(pts)) if keep[i]]


def way_geom(el: dict) -> list[list[float]]:
    return [[round(p["lon"], 5), round(p["lat"], 5)] for p in el.get("geometry", [])]


def main() -> None:
    s, n, wlon0, elon = BBOX[0], BBOX[1], BBOX[2], BBOX[3]
    bb = f"{s},{wlon0},{n},{elon}"
    print(f"[basemap] querying Overpass for bbox {bb} …")
    q = f"""[out:json][timeout:240];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]({bb});
  way["natural"="water"]({bb});
  way["waterway"="riverbank"]({bb});
);
out geom;"""
    res = overpass(q)
    roads, water = [], []
    for el in res.get("elements", []):
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {})
        pts = way_geom(el)
        if len(pts) < 2:
            continue
        if "highway" in tags:
            rank = RANK.get(tags["highway"], 3)
            roads.append([rank, rdp(pts, EPS)])
        elif tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
            if len(pts) >= 4:
                water.append(rdp(pts, EPS * 1.5))
    out = {"bbox": [BBOX[0], BBOX[1], BBOX[2], BBOX[3]], "roads": roads, "water": water}
    OUT.write_text("window.PRAVAH_BASEMAP=" + json.dumps(out, separators=(",", ":")) + ";")
    pts_total = sum(len(r[1]) for r in roads)
    print(f"[basemap] roads={len(roads)} (pts={pts_total})  water={len(water)}  "
          f"-> {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
