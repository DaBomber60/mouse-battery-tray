from typing import Tuple, Dict
from PIL import Image, ImageDraw, ImageFont
from config import is_light_mode

_FONT_CACHE = {}


def get_font(size: int):
    """Reuse loaded ImageFont handles to avoid repeated disk reads and RAM allocations."""
    if size not in _FONT_CACHE:
        try:
            _FONT_CACHE[size] = ImageFont.truetype("arialbd.ttf", size)
        except OSError:
            try:
                _FONT_CACHE[size] = ImageFont.truetype("arial.ttf", size)
            except OSError:
                _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]


def create_image(text: str, text_color: Tuple[int, int, int], icon_cache: Dict) -> Image.Image:
    cache_key = (text, text_color)
    if cache_key in icon_cache:
        return icon_cache[cache_key]

    width, height = 64, 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    font = get_font(54 if len(text) <= 2 else 34)
        
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    text_height = bottom - top
    
    x = (width - text_width) / 2 - left
    y = (height - text_height) / 2 - top
        
    draw.text((x, y), text, fill=text_color, font=font)

    if len(icon_cache) > 60:
        icon_cache.clear()
    icon_cache[cache_key] = image
    return image


# Lightning bolt outline, normalised to the icon box.
_BOLT_POINTS = [
    (0.66, 0.03), (0.18, 0.58), (0.44, 0.58),
    (0.34, 0.97), (0.82, 0.40), (0.56, 0.40),
]
_BOLT_STEPS = 20


def create_bolt_image(pct: int, icon_cache: Dict) -> Image.Image:
    """Charging bolt: red at/below 5%, green at 100%, blue between. Filled from
    the bottom so 5% shows a single step and 95% is already solid."""
    light = is_light_mode()

    if pct >= 100:
        color = (30, 140, 60) if light else (46, 204, 113)
        step = _BOLT_STEPS
    else:
        if 0 <= pct <= 5:
            color = (192, 57, 43) if light else (231, 76, 60)
        else:
            color = (21, 101, 192) if light else (52, 152, 219)
        # Spread 5-95% across the full range of steps rather than 0-100%, so
        # neither end of the usable range looks empty or full by accident.
        step = 0 if pct <= 0 else min(
            _BOLT_STEPS, max(1, round(1 + (pct - 5) * (_BOLT_STEPS - 1) / 90)))

    cache_key = ("\x00bolt", step, color)
    if cache_key in icon_cache:
        return icon_cache[cache_key]

    size = 64
    outline = Image.new('L', (size, size), 0)
    ImageDraw.Draw(outline).polygon(
        [(x * size, y * size) for x, y in _BOLT_POINTS], fill=255)

    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    solid = Image.new('RGBA', (size, size), color + (255,))

    if step >= _BOLT_STEPS:
        image.paste(solid, (0, 0), outline)
    else:
        image.paste(Image.new('RGBA', (size, size), color + (90,)), (0, 0), outline)
        if step > 0:
            # Fill by area rather than height, so each step covers equal ink
            # despite the bolt tapering towards its tail.
            px = outline.load()
            rows = [sum(1 for x in range(size) if px[x, y]) for y in range(size)]
            target = sum(rows) * step / _BOLT_STEPS
            acc = 0
            cut = 0
            for y in range(size - 1, -1, -1):
                acc += rows[y]
                if acc >= target:
                    cut = y
                    break
            filled = outline.copy()
            ImageDraw.Draw(filled).rectangle([0, 0, size, cut], fill=0)
            image.paste(solid, (0, 0), filled)

    if len(icon_cache) > 60:
        icon_cache.clear()
    icon_cache[cache_key] = image
    return image


def get_icon_data(status: str, last_battery: int, icon_cache: Dict) -> Image.Image:
    light = is_light_mode()
    if status == "disconnected":
        color = (70, 70, 70) if light else (170, 170, 170)
        return create_image("??", color, icon_cache)
    elif status == "charging":
        return create_bolt_image(last_battery, icon_cache)
    elif status == "connected" and last_battery < 0:
        color = (70, 70, 70) if light else (170, 170, 170)
        return create_image("--", color, icon_cache)
    elif status == "unknown":
        color = (142, 68, 173) if light else (155, 89, 182)
        return create_image("?", color, icon_cache)
    else:
        pct = last_battery
        if pct >= 50:
            color = (30, 140, 60) if light else (46, 204, 113)
        elif pct >= 20:
            color = (211, 84, 0) if light else (230, 126, 34)
        else:
            color = (192, 57, 43) if light else (231, 76, 60)
        return create_image(str(pct), color, icon_cache)
