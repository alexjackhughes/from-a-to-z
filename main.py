"""
Gather Sentinel‑2, SRTM DEM, and Planet NICFI mosaic tiles for the Chapada Diamantina search box
===================================================================

Dependencies
------------
    pip install pystac-client planetary-computer shapely rasterio requests boto3

Environment variables
---------------------
* ``AWS_NO_SIGN_REQUEST=YES`` – allows anonymous reads from the public S3 SRTM bucket.
* ``PL_API_KEY`` – your **Planet NICFI** API key (skip NICFI download if not set).

Bounding box (WGS‑84)
---------------------
West  –41.65
South –12.80
East  –40.95
North –12.10

The script grabs:
* **Sentinel‑2 L2A** scenes with <20 % cloud cover since 2024‑01‑01 (true‑colour bands B04‑03‑02).
* All **SRTM‑1 arc‑second** tiles overlapping the box.
* The **NICFI March 2024 mosaic** quads that intersect the box.

Edit the parameters at the top if you want a different time span, cloud threshold, or NICFI month.
"""

import os
from datetime import datetime
from pathlib import Path
from shapely.geometry import box, mapping
import requests
import boto3
from pystac_client import Client

# ──────────────────────────────────────────────────────────────────────
# User‑tweakable parameters
# ──────────────────────────────────────────────────────────────────────
BBOX = [-41.65, -12.80, -40.95, -12.10]  # [minx, miny, maxx, maxy]
S2_MAX_CLOUD = 20                        # percent
S2_DATE_RANGE = ("2024-01-01", datetime.utcnow().strftime("%Y-%m-%d"))
NICFI_MONTH = (2024, 3)                  # (year, month)
OUTPUT_DIR = Path("data_tiles")
OUTPUT_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────────────────────────────

def _download(url: str, dest: Path, chunk: int = 8192):
    """Stream a URL to *dest* if the file is not already present."""
    if dest.exists():
        return
    print(f"↓ {dest}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk):
                f.write(chunk)

# ──────────────────────────────────────────────────────────────────────
# SRTM DEM (1‑arc‑second) via the public AWS bucket
# ──────────────────────────────────────────────────────────────────────

def fetch_srtm(bbox):
    s3 = boto3.client("s3", region_name="us-west-2")
    minx, miny, maxx, maxy = bbox
    lats = range(int(miny), int(maxy) + 1)
    lons = range(int(minx), int(maxx) + 1)
    for lat in lats:
        for lon in lons:
            hemi_ns = "N" if lat >= 0 else "S"
            hemi_ew = "E" if lon >= 0 else "W"
            tile = f"{abs(lat):02d}{hemi_ns}{abs(lon):03d}{hemi_ew}.hgt.zip"
            key = f"SRTM1/{tile}"
            dest = OUTPUT_DIR / tile
            try:
                _download(f"https://srtm-pds.s3.amazonaws.com/{key}", dest)
            except Exception as exc:
                print(f"⚠️  Skipped {tile}: {exc}")

# ──────────────────────────────────────────────────────────────────────
# Sentinel‑2 L2A true‑colour bands via Microsoft Planetary Computer
# ──────────────────────────────────────────────────────────────────────

def fetch_sentinel2(bbox, date_range, max_cloud, limit=20):
    client = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{date_range[0]}/{date_range[1]}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        limit=limit,
    )
    items = list(search.get_items())
    print(f"Found {len(items)} Sentinel‑2 scenes meeting criteria")

    for item in items:
        signed_item = Client.open(item.href).get_item(item.id).signed_links()
        for band in ("B04", "B03", "B02"):
            asset = signed_item.assets[band]
            dest = OUTPUT_DIR / f"{item.id}_{band}.tif"
            _download(asset.href, dest)
        (OUTPUT_DIR / f"{item.id}.json").write_text(item.to_json())

# ──────────────────────────────────────────────────────────────────────
# Planet NICFI monthly mosaics (requires PL_API_KEY)
# ──────────────────────────────────────────────────────────────────────

def fetch_nicfi(bbox, year, month):
    api_key = os.getenv("PL_API_KEY")
    if not api_key:
        print("NICFI: PL_API_KEY not set – skipping download")
        return

    mosaic_id = f"nicfi_monthly_{year}_{month:02d}_mosaic"
    mosaic_url = f"https://api.planet.com/basemaps/v1/mosaics/{mosaic_id}?api_key={api_key}"
    mosaic = requests.get(mosaic_url).json()
    quad_url = mosaic["_links"]["quads"]
    bbox_str = ",".join(map(str, bbox))
    page = requests.get(quad_url, params={"bbox": bbox_str, "api_key": api_key}).json()

    for quad in page["items"]:
        quad_id = quad["id"]
        dest = OUTPUT_DIR / f"{quad_id}.tif"
        tile_url = quad["_links"]["download"] + f"?api_key={api_key}"
        _download(tile_url, dest)

# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fetch_srtm(BBOX)
    fetch_sentinel2(BBOX, S2_DATE_RANGE, S2_MAX_CLOUD)
    fetch_nicfi(BBOX, *NICFI_MONTH)
    print("✔ Done – all requested tiles saved to", OUTPUT_DIR)
