"""
Gather Sentinel‑2, SRTM DEM, and Planet NICFI tiles for Chapada Diamantina
===========================================================================
A single‑file helper that
* **downloads** raw analysis‑ready data (Sentinel‑2 SR bands, SRTM DEM, NICFI mosaics),
* builds an 8‑bit **RGB quick‑look** for every Sentinel‑2 scene, **and**
* writes a lightweight **≤ 1000 × 1000 px JPEG copy** of every preview/NICFI image in a parallel folder so you can browse everything quickly.

Dependencies
------------
```
pip install pystac-client planetary-computer shapely rasterio requests boto3 python-dotenv numpy pillow
```

Environment variables
---------------------
* ``AWS_NO_SIGN_REQUEST=YES`` – anonymous reads from the public SRTM bucket.
* ``PL_API_KEY`` – Planet NICFI key (skip NICFI if unset).

Bounding box (WGS‑84)
---------------------
West  –41.65   South –12.80   East –40.95   North –12.10

Tweak the constants at the top for a different AOI, cloud threshold, NICFI month, or resize limit.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Sequence

import boto3
import numpy as np
import planetary_computer
import rasterio
import requests
from dotenv import load_dotenv
from PIL import Image
from pystac_client import Client

# ────────────────────────────────
# User‑tweakable parameters
# ────────────────────────────────
BBOX: Sequence[float] = [-41.65, -12.80, -40.95, -12.10]  # [minx, miny, maxx, maxy]
S2_MAX_CLOUD = 20                           # percent
S2_DATE_RANGE = ("2024-01-01", datetime.utcnow().strftime("%Y-%m-%d"))
NICFI_MONTH = (2024, 3)                     # (year, month)
OUTPUT_DIR = Path("data_tiles")             # raw + preview storage
PREVIEW_DIR = Path("previews_1k")           # resized JPEGs (mirrors structure)
PREVIEW_MAX = 1000                          # max width OR height in px

for p in (OUTPUT_DIR, PREVIEW_DIR):
    p.mkdir(exist_ok=True)

# ────────────────────────────────
# Helper utilities
# ────────────────────────────────

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

# ────────────────────────────────
# SRTM DEM (1‑arc‑second) via AWS
# ────────────────────────────────

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

# ────────────────────────────────
# Sentinel‑2 search & download
# ────────────────────────────────

def make_rgb_preview(scene_dir: Path, out_name: str = "preview.jpg", scale: float = 0.0001, gamma: float = 0.9) -> Path | None:
    print(f"Making preview for {scene_dir.name}")
    """Create an 8‑bit RGB JPEG from B04,B03,B02. Return the path or None."""
    paths = [scene_dir / f"{b}.tif" for b in ("B04", "B03", "B02")]
    if not all(p.exists() for p in paths):
        print(f"⚠️  Bands missing in {scene_dir.name}, skipping preview")
        return None

    rgb = []
    for p in paths:
        with rasterio.open(p) as src:
            rgb.append(src.read(1).astype("float32") * scale)

    def stretch(ch):
        lo, hi = np.percentile(ch, (2, 98))
        return np.clip((ch - lo) / (hi - lo + 1e-6), 0, 1) ** gamma

    rgb = [stretch(c) for c in rgb]
    rgb8 = (np.stack(rgb, axis=2) * 255).astype("uint8")  # H,W,C
    img = Image.fromarray(rgb8, mode="RGB")

    out_path = scene_dir / out_name
    img.save(out_path, "JPEG", quality=85, optimize=True)
    print(f"✓ preview → {out_path.relative_to(Path.cwd())}")
    return out_path


def fetch_sentinel2(bbox, date_range, max_cloud, limit=20):
    client = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{date_range[0]}/{date_range[1]}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        limit=limit,
    )
    items = list(search.items())
    print(f"Found {len(items)} Sentinel‑2 scenes meeting criteria")

    for item in items:
        try:
            print(f"Processing {item.id}")
            # Create a directory for this scene
            scene_dir = OUTPUT_DIR / item.id
            scene_dir.mkdir(exist_ok=True)

            # Download each band
            for band in ("B04", "B03", "B02"):
                asset = item.assets[band]
                # Get the signed URL using planetary_computer
                signed_href = planetary_computer.sign(asset.href)
                dest = scene_dir / f"{band}.tif"
                try:
                    print(f"Downloading {band} band...")
                    _download(signed_href, dest)
                    make_rgb_preview(scene_dir)
                except requests.exceptions.HTTPError as e:
                    print(f"⚠️  Failed to download {band} band for {item.id}: {e}")
                    continue
                except Exception as e:
                    print(f"⚠️  Unexpected error downloading {band} band: {e}")
                    continue

            # Save the STAC metadata
            (scene_dir / "metadata.json").write_text(item.to_json())
            print(f"✓ Completed processing {item.id}")


        except Exception as e:
            print(f"⚠️  Error processing {item.id}: {e}")
            continue

# ────────────────────────────────
# Planet NICFI monthly mosaics
# ────────────────────────────────

def fetch_nicfi(bbox, year, month):
    api_key = os.getenv("PL_API_KEY")
    if not api_key:
        print("NICFI: PL_API_KEY not set – skipping download")
        return

    mosaic_id = f"nicfi_monthly_{year}_{month:02d}_mosaic"
    mosaic_url = f"https://api.planet.com/basemaps/v1/mosaics/{mosaic_id}?api_key={api_key}"

    try:
        response = requests.get(mosaic_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        mosaic = response.json()

        # Debug the response
        print(f"NICFI API Response: {mosaic}")

        if "_links" not in mosaic:
            print(f"Error: Unexpected API response format. Missing '_links' key. Full response: {mosaic}")
            return

        quad_url = mosaic["_links"]["quads"]
        bbox_str = ",".join(map(str, bbox))
        page = requests.get(quad_url, params={"bbox": bbox_str, "api_key": api_key}).json()

        for quad in page["items"]:
            quad_id = quad["id"]
            dest = OUTPUT_DIR / f"{quad_id}.tif"
            tile_url = quad["_links"]["download"] + f"?api_key={api_key}"
            _download(tile_url, dest)

    except requests.exceptions.RequestException as e:
        print(f"Error accessing Planet NICFI API: {e}")
    except KeyError as e:
        print(f"Error parsing API response: {e}")
        print(f"Full response: {mosaic}")
    except Exception as e:
        print(f"Unexpected error: {e}")

# ────────────────────────────────
# Resize helper
# ────────────────────────────────

def _resize_and_write(src_path: Path, rel: Path) -> None:
    dst_path = PREVIEW_DIR / rel.with_suffix(".jpg")  # force JPEG
    if dst_path.exists():
        return
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if src_path.suffix.lower() in {".jpg", ".jpeg"}:
            img = Image.open(src_path)
        else:  # assume 3‑band GeoTIFF uint8
            with rasterio.open(src_path) as src:
                if src.count < 3 or src.dtypes[0] != "uint8":
                    return  # skip non‑RGB rasters
                arr = np.dstack([src.read(i + 1) for i in range(3)])
                img = Image.fromarray(arr, "RGB")

        img.thumbnail((PREVIEW_MAX, PREVIEW_MAX), Image.LANCZOS)
        img.save(dst_path, "JPEG", quality=80, optimize=True)
        print(f"◎ resized → {dst_path.relative_to(Path.cwd())}")
    except Exception as exc:
        print(f"⚠️  Resize failed for {src_path.name}: {exc}")


def build_resized_gallery() -> None:
    for path in OUTPUT_DIR.rglob("*"):
        if path.is_dir():
            continue
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            # Get the parent folder name and file name
            folder_name = path.parent.name
            file_name = path.stem
            # Create new relative path with folder-file naming
            new_name = f"{folder_name}-{file_name}.jpg"
            rel = Path("preview") / new_name
            _resize_and_write(path, rel)

# ────────────────────────────────
# Main entry
# ────────────────────────────────

def main() -> None:
    load_dotenv()
    # fetch_srtm(BBOX)
    fetch_sentinel2(BBOX, S2_DATE_RANGE, S2_MAX_CLOUD)
    fetch_nicfi(BBOX, *NICFI_MONTH)
    build_resized_gallery()
    print("✔ All tiles + 1 kpx previews saved to", OUTPUT_DIR, "and", PREVIEW_DIR)


if __name__ == "__main__":
    main()
