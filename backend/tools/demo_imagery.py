"""
SatQuery AI — Demo Image Generator
Generates procedural satellite-like imagery for demo scenarios.
All images are clearly labelled as DEMO data.
"""

import numpy as np
import base64
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Optional, Tuple
import random


def _to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _add_demo_watermark(img: Image.Image, text: str = "DEMO DATA") -> Image.Image:
    """Add a subtle watermark to make demo status clear."""
    draw = ImageDraw.Draw(img.copy())
    overlay = img.copy()
    draw2 = ImageDraw.Draw(overlay)
    # Small corner label
    draw2.rectangle([0, 0, 100, 18], fill=(255, 80, 0))
    try:
        draw2.text((4, 2), "DEMO", fill=(255, 255, 255))
    except Exception:
        pass
    return Image.blend(img, overlay, 0.85)


def generate_urban_scene(
    year: str = "2024",
    expansion_factor: float = 0.0,
    width: int = 512,
    height: int = 512,
    seed: int = 42,
) -> str:
    """Generate a pseudo-satellite false-color urban scene."""
    rng = np.random.default_rng(seed)
    img = np.zeros((height, width, 3), dtype=np.uint8)

    # Sky-blue background (water/vegetation base)
    img[:, :] = [34, 85, 60]  # deep vegetation green

    # River — vertical blue band
    river_x = int(width * 0.35)
    river_w = int(width * 0.06)
    img[:, river_x:river_x + river_w] = [28, 80, 160]

    # Agricultural patches
    for _ in range(12):
        x = rng.integers(0, width - 60)
        y = rng.integers(0, height - 60)
        w = rng.integers(30, 80)
        h = rng.integers(30, 80)
        color = [
            int(40 + rng.integers(0, 30)),
            int(100 + rng.integers(0, 60)),
            int(20 + rng.integers(0, 20)),
        ]
        img[y:y+h, x:x+w] = color

    # Urban blocks — right side of river
    urban_x_start = river_x + river_w + int(width * 0.05)
    urban_blocks = int(8 + expansion_factor * 14)
    for i in range(urban_blocks):
        x = rng.integers(urban_x_start, min(urban_x_start + int(width * 0.5), width - 30))
        y = rng.integers(int(height * 0.1), int(height * 0.9))
        w = rng.integers(15, 45)
        h = rng.integers(15, 45)
        shade = int(160 + rng.integers(0, 50))
        img[y:y+h, x:x+w] = [shade, shade - 10, shade - 20]

    # Road network
    for _ in range(4):
        x1 = rng.integers(urban_x_start, width)
        img[x1:x1+3, :] = [180, 170, 165]
    for _ in range(4):
        y1 = rng.integers(50, height - 50)
        img[:, y1:y1+3] = [180, 170, 165]

    # Water body — bottom left
    img[int(height * 0.75):, :int(width * 0.3)] = [28, 95, 175]

    # Add some texture/noise
    noise = rng.integers(-12, 12, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    pil = Image.fromarray(img)
    pil = pil.filter(ImageFilter.SMOOTH)

    # Year label
    draw = ImageDraw.Draw(pil)
    draw.rectangle([width - 85, height - 22, width, height], fill=(10, 30, 60, 200))
    draw.text((width - 80, height - 18), year, fill=(255, 255, 255))
    draw.rectangle([0, 0, 80, 16], fill=(220, 60, 0))
    draw.text((3, 1), "DEMO DATA", fill=(255, 255, 255))

    return _to_base64(pil)


def generate_change_map(width: int = 512, height: int = 512, seed: int = 42) -> str:
    """Generate a change detection map (red=change, grey=no change)."""
    rng = np.random.default_rng(seed)
    img = np.ones((height, width, 3), dtype=np.uint8) * 40  # dark background

    # Change areas (right of river, urban expansion zones)
    river_x = int(width * 0.35)
    river_w = int(width * 0.06)
    urban_x_start = river_x + river_w + int(width * 0.05)

    for _ in range(18):
        x = rng.integers(urban_x_start, min(urban_x_start + int(width * 0.5), width - 30))
        y = rng.integers(int(height * 0.1), int(height * 0.9))
        w = rng.integers(15, 50)
        h = rng.integers(15, 50)
        intensity = rng.integers(180, 255)
        img[y:y+h, x:x+w] = [intensity, int(intensity * 0.15), int(intensity * 0.1)]

    # Minor change areas (false positives, lighter)
    for _ in range(8):
        x = rng.integers(0, width - 20)
        y = rng.integers(0, height - 20)
        w = rng.integers(5, 20)
        h = rng.integers(5, 20)
        img[y:y+h, x:x+w] = [100, 60, 30]

    # River
    img[:, river_x:river_x + river_w] = [20, 60, 140]

    pil = Image.fromarray(img)
    pil = pil.filter(ImageFilter.SMOOTH_MORE)
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 80, 16], fill=(220, 60, 0))
    draw.text((3, 1), "DEMO DATA", fill=(255, 255, 255))
    draw.rectangle([0, height - 18, 130, height], fill=(10, 10, 10))
    draw.text((3, height - 16), "■ Change  ■ No Change", fill=(200, 200, 200))
    return _to_base64(pil)


def generate_cloud_image(width: int = 512, height: int = 512, seed: int = 77) -> str:
    """Generate a cloud-contaminated optical image."""
    rng = np.random.default_rng(seed)
    # Base scene
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = [34, 85, 60]

    # Some urban areas
    for _ in range(6):
        x = rng.integers(50, width - 60)
        y = rng.integers(50, height - 60)
        shade = int(155 + rng.integers(0, 40))
        img[y:y+40, x:x+40] = [shade, shade - 10, shade - 20]

    # Heavy cloud patches
    cloud_patches = [
        (100, 80, 200, 150),
        (280, 60, 420, 220),
        (150, 280, 360, 380),
    ]
    for cx, cy, cw, ch in cloud_patches:
        patch = rng.integers(210, 245, (ch - cy, cw - cx, 3), dtype=np.uint8)
        img[cy:ch, cx:cw] = patch

    # Add cloud blur
    noise = rng.integers(-8, 8, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    pil = Image.fromarray(img)
    pil = pil.filter(ImageFilter.GaussianBlur(radius=1))
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 80, 16], fill=(220, 60, 0))
    draw.text((3, 1), "DEMO DATA", fill=(255, 255, 255))
    draw.rectangle([width - 160, height - 22, width, height], fill=(200, 80, 0, 180))
    draw.text((width - 155, height - 18), "☁ CLOUD DETECTED", fill=(255, 255, 255))
    return _to_base64(pil)


def generate_cloud_mask(width: int = 512, height: int = 512) -> str:
    """Generate a cloud mask (white=cloud, black=clear)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cloud_patches = [
        (100, 80, 200, 150),
        (280, 60, 420, 220),
        (150, 280, 360, 380),
    ]
    for cx, cy, cw, ch in cloud_patches:
        img[cy:ch, cx:cw] = [240, 240, 240]

    pil = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 80, 16], fill=(220, 60, 0))
    draw.text((3, 1), "DEMO DATA", fill=(255, 255, 255))
    return _to_base64(pil)


def generate_reconstructed_image(width: int = 512, height: int = 512, seed: int = 42) -> str:
    """Generate a cloud-reconstructed image."""
    # Similar to base scene but with reconstruction artifacts slightly visible
    base_b64 = generate_urban_scene("2026", expansion_factor=0.5, width=width, height=height, seed=seed)
    img_bytes = base64.b64decode(base_b64)
    pil = Image.open(io.BytesIO(img_bytes))
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 80, 16], fill=(0, 120, 60))
    draw.text((3, 1), "DEMO DATA", fill=(255, 255, 255))
    draw.rectangle([width - 200, height - 22, width, height], fill=(0, 100, 60, 200))
    draw.text((width - 195, height - 18), "✓ RECONSTRUCTED", fill=(255, 255, 255))
    return _to_base64(pil)


def generate_sar_image(width: int = 512, height: int = 512, seed: int = 99) -> str:
    """Generate a SAR-like greyscale image with speckle noise."""
    rng = np.random.default_rng(seed)
    img = np.zeros((height, width), dtype=np.uint8)

    # Background (low backscatter)
    img[:, :] = 40

    # Urban bright returns (high backscatter)
    for _ in range(10):
        x = rng.integers(200, width - 50)
        y = rng.integers(50, height - 50)
        w = rng.integers(20, 60)
        h = rng.integers(20, 60)
        img[y:y+h, x:x+w] = rng.integers(180, 255)

    # Water (very low backscatter)
    img[int(height * 0.75):, :int(width * 0.3)] = rng.integers(5, 15, (int(height * 0.25), int(width * 0.3)))

    # Speckle noise
    speckle = rng.integers(-25, 25, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + speckle, 0, 255).astype(np.uint8)

    pil = Image.fromarray(img, mode='L').convert('RGB')
    pil = pil.filter(ImageFilter.SMOOTH)
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 80, 16], fill=(220, 60, 0))
    draw.text((3, 1), "DEMO DATA", fill=(255, 255, 255))
    draw.rectangle([width - 130, height - 22, width, height], fill=(30, 30, 80))
    draw.text((width - 125, height - 18), "SAR (C-band)", fill=(180, 220, 255))
    return _to_base64(pil)


def generate_confidence_heatmap(width: int = 512, height: int = 512, seed: int = 42) -> str:
    """Generate a confidence heatmap."""
    rng = np.random.default_rng(seed)
    river_x = int(width * 0.35)
    river_w = int(width * 0.06)
    urban_x_start = river_x + river_w + int(width * 0.05)

    conf = np.zeros((height, width), dtype=np.float32)

    # High confidence in urban change areas
    for _ in range(12):
        cx = rng.integers(urban_x_start, min(urban_x_start + int(width * 0.5), width - 40))
        cy = rng.integers(50, height - 50)
        cw = rng.integers(20, 50)
        ch = rng.integers(20, 50)
        conf[cy:cy+ch, cx:cx+cw] = rng.uniform(0.75, 0.95)

    # Medium confidence elsewhere
    conf += rng.uniform(0.1, 0.4, conf.shape)
    conf = np.clip(conf, 0, 1)

    # Apply colormap (green-yellow-red)
    r = (conf * 255).astype(np.uint8)
    g = ((1 - conf) * 200).astype(np.uint8)
    b = np.zeros_like(r)
    rgb = np.stack([r, g, b], axis=2)

    pil = Image.fromarray(rgb)
    pil = pil.filter(ImageFilter.GaussianBlur(radius=4))
    draw = ImageDraw.Draw(pil)
    draw.rectangle([0, 0, 80, 16], fill=(220, 60, 0))
    draw.text((3, 1), "DEMO DATA", fill=(255, 255, 255))
    return _to_base64(pil)
