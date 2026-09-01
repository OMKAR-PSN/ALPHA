import argparse
import requests
import json
import os
import sys
from pathlib import Path
from PIL import Image
import io

def download_pc_preview(item_id: str, collection: str = "sentinel-2-l2a") -> Image.Image:
    """Download a preview PNG from Planetary Computer."""
    url = (
        f"https://planetarycomputer.microsoft.com/api/data/v1/item/preview.png?"
        f"collection={collection}&item={item_id}&assets=visual&asset_bidx=visual%7C1%2C2%2C3&nodata=0&format=png"
    )
    print(f"Fetching preview for {item_id}...")
    r = requests.get(url)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content))

def process_cloud_scene(data_dir: Path):
    """Scene A: Real Cloud Scene"""
    print("\n--- Processing Scene A: Cloud ---")
    scene_dir = data_dir / "real" / "cloud" / "real_cloud_001"
    scene_dir.mkdir(parents=True, exist_ok=True)

    # 2022-07-15 T46RCQ (35% cloud)
    item_id = "S2A_MSIL2A_20220715T042721_R133_T46RCQ_20220715T175944"
    img = download_pc_preview(item_id)
    
    # The preview is usually ~1024x1024 or similar, we crop a nice 512x512 window
    w, h = img.size
    cx, cy = int(w * 0.4), int(h * 0.4)
    crop = img.crop((cx, cy, cx + 512, cy + 512))
    
    out_path = scene_dir / "input.png"
    crop.save(out_path)
    print(f"Saved {out_path} (size: {os.path.getsize(out_path)/1024:.1f} KB)")

    meta = {
        "scene_id": "real_cloud_001",
        "scenario_type": "cloud_analysis",
        "sensor": "Sentinel-2",
        "platform": "Sentinel-2A",
        "product_type": "optical",
        "source": "Copernicus Data Space via Planetary Computer",
        "source_item_id": item_id,
        "acquisition_date": "2022-07-15",
        "aoi_name": "Assam, India",
        "bands_used": ["R", "G", "B"],
        "input_provenance": "REAL_SATELLITE_DATA",
        "image_path": str(out_path.as_posix()),
        "notes": "Real cropped optical scene used for cloud demo."
    }
    with open(scene_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

def process_change_scene(data_dir: Path):
    """Scene B: Real Change Scene"""
    print("\n--- Processing Scene B: Change ---")
    scene_dir = data_dir / "real" / "change" / "real_change_001"
    scene_dir.mkdir(parents=True, exist_ok=True)

    # Pre-flood: 2022-04-21 T46RCP
    item_t1 = "S2B_MSIL2A_20220421T042659_R133_T46RCP_20220421T192301"
    # Post-flood: 2022-07-15 T46RCP
    item_t2 = "S2A_MSIL2A_20220715T042721_R133_T46RCP_20220715T163457"

    img_t1 = download_pc_preview(item_t1)
    img_t2 = download_pc_preview(item_t2)

    # Crop the exact same bounding box from the thumbnails (since they are same tile, pixel sizes match)
    w, h = img_t1.size
    cx, cy = int(w * 0.5), int(h * 0.3)
    crop_t1 = img_t1.crop((cx, cy, cx + 512, cy + 512))
    crop_t2 = img_t2.crop((cx, cy, cx + 512, cy + 512))

    out_t1 = scene_dir / "t1.png"
    out_t2 = scene_dir / "t2.png"
    crop_t1.save(out_t1)
    crop_t2.save(out_t2)
    print(f"Saved {out_t1} and {out_t2}")

    meta = {
        "scene_id": "real_change_001",
        "scenario_type": "bi_temporal_change",
        "sensor_t1": "Sentinel-2",
        "sensor_t2": "Sentinel-2",
        "source": "Planetary Computer",
        "acquisition_date_t1": "2022-04-21",
        "acquisition_date_t2": "2022-07-15",
        "aoi_name": "Assam, India (Flood)",
        "image_t1": str(out_t1.as_posix()),
        "image_t2": str(out_t2.as_posix()),
        "input_provenance": "REAL_SATELLITE_DATA"
    }
    with open(scene_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

def process_sar_optical_scene(data_dir: Path):
    """Scene C: SAR + Optical (Experimental/Unavailable)"""
    print("\n--- Processing Scene C: SAR + Optical ---")
    scene_dir = data_dir / "real" / "sar_optical" / "real_crossmodal_001"
    scene_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "scene_id": "real_crossmodal_001",
        "scenario_type": "sar_optical",
        "sensor_optical": "Sentinel-2",
        "sensor_sar": "Sentinel-1",
        "status": "CROSS_MODAL_ANALYSIS_UNAVAILABLE",
        "notes": "Proper aligned SAR+Optical pair requires Rasterio/GDAL for reprojection. Left blank to demonstrate honest capability reporting."
    }
    with open(scene_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Marked Scene C as UNAVAILABLE.")

def main():
    parser = argparse.ArgumentParser(description="Download small real remote-sensing scenes for SatQuery AI demos.")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print("SatQuery AI - Real Demo Scene Preparation")
    print("This script will download ~5-10 MB of PNG thumbnails from Planetary Computer API.")
    print("These will replace the synthetic procedural demo images.\n")

    if not args.confirm:
        ans = input("Proceed with download? [y/N]: ")
        if ans.lower() not in ('y', 'yes'):
            print("Aborted.")
            sys.exit(0)

    data_dir = Path("data")
    
    process_cloud_scene(data_dir)
    process_change_scene(data_dir)
    process_sar_optical_scene(data_dir)

    print("\nDone! To use these scenes, update data/metadata/scenes.json.")

if __name__ == "__main__":
    main()
