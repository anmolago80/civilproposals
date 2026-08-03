"""
divider_designer.py

Generates REAL section-divider and cover-hero banner images -- not
placeholders -- by compositing the user's own uploaded project photos and
typed pull-quotes onto one of a small set of code-drawn layout templates.

This deliberately stays inside the tool's no-invention rule: every photo and
every quote that appears in a rendered banner is something the user actually
supplied (an uploaded photo, a typed testimonial). Nothing here invents a
project image or puts words in anyone's mouth -- if there's no real asset for
a section, the "Solid colour" layout (title text on a themed background, no
photo/quote) is the honest fallback, not a stock or AI-generated substitute.

Four layouts:
  - Solid colour   -- themed background + title. No photo needed. Safe default.
  - Photo + gradient -- user's photo, cropped to the banner, with a dark
    gradient for text legibility and the title on top.
  - Photo + quote  -- same photo treatment, plus a typed pull-quote/testimonial
    with attribution in a semi-transparent panel.
  - Split          -- half themed colour block (title), half user's photo.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BANNER_W, BANNER_H = 2000, 620
_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

DIVIDER_LAYOUTS = ["Solid colour", "Photo + gradient", "Photo + quote", "Split (colour + photo)"]

# One primary/accent colour pair per proposal theme -- keeps the generated
# banners visually consistent with whatever theme the user picked in Project
# Setup, without needing any design input from them.
THEME_COLOURS = {
    "Corporate": {"primary": (24, 42, 74), "accent": (58, 110, 196)},
    "Modern": {"primary": (28, 28, 30), "accent": (0, 191, 165)},
    "Government": {"primary": (13, 58, 44), "accent": (177, 148, 68)},
    "Infrastructure": {"primary": (54, 42, 26), "accent": (224, 122, 39)},
    "Minimalist": {"primary": (235, 235, 232), "accent": (60, 60, 60)},
}
_DEFAULT_THEME = "Corporate"

WHITE = (255, 255, 255, 255)


def render_banner(
    title: str,
    layout: str,
    theme_name: str = _DEFAULT_THEME,
    photo_bytes: bytes | None = None,
    quote_text: str | None = None,
    quote_attribution: str | None = None,
    size: tuple[int, int] = (BANNER_W, BANNER_H),
) -> bytes | None:
    """Render one banner and return PNG bytes, or None if rendering fails for any reason
    (callers should fall back to a text placeholder rather than let this raise)."""
    try:
        colours = THEME_COLOURS.get(theme_name, THEME_COLOURS[_DEFAULT_THEME])
        w, h = size

        needs_photo = layout in ("Photo + gradient", "Photo + quote", "Split (colour + photo)")
        photo = _load_cropped_photo(photo_bytes, w, h) if (needs_photo and photo_bytes) else None

        if layout == "Photo + gradient" and photo is not None:
            img = _layout_photo_gradient(photo, title, colours)
        elif layout == "Photo + quote" and photo is not None:
            img = _layout_photo_quote(photo, title, quote_text, quote_attribution, colours)
        elif layout == "Split (colour + photo)" and photo is not None:
            img = _layout_split(photo, title, colours, size)
        else:
            # Solid colour, or a photo-dependent layout picked with no photo available.
            img = _layout_solid(title, colours, size)

        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


# Cover band -- the coloured title block at the top of the cover page, sized
# to insert at full content width (see export_docx._build_cover_page).
BAND_W, BAND_H = 2000, 780


def render_cover_band(
    tender_name: str,
    project_name: str,
    client_name: str,
    submission_date: str,
    theme_name: str = _DEFAULT_THEME,
    size: tuple[int, int] = (BAND_W, BAND_H),
) -> bytes | None:
    """
    Renders the coloured title block for the cover page -- theme colour
    background, a placeholder box for the user's own company logo (this tool
    has no reliable single "this is the logo" asset to draw on, so it never
    guesses; the user pastes their real logo in over the placeholder), the
    submission date, tender title/project name, a rule, and a "Response to
    Tender" / client line. Same THEME_COLOURS every other generated graphic
    in this tool uses, so the cover reads as part of the same document.
    Returns PNG bytes, or None on any failure (caller falls back to plain
    text, same as every other renderer here).
    """
    try:
        colours = THEME_COLOURS.get(theme_name, THEME_COLOURS[_DEFAULT_THEME])
        w, h = size
        primary = colours["primary"]
        accent = colours["accent"]
        # Minimalist's primary is a light background -- everything else here
        # is dark enough for white text/lines to read clearly.
        light_bg = sum(primary) / 3 > 150
        ink = (40, 40, 40, 255) if light_bg else WHITE
        muted_ink = (90, 90, 90, 255) if light_bg else (255, 255, 255, 200)
        box_line = (90, 90, 90, 255) if light_bg else (255, 255, 255, 220)

        img = Image.new("RGBA", (w, h), primary + (255,))
        draw = ImageDraw.Draw(img)

        margin = 70

        # Logo placeholder, top-left -- an empty box, never a guessed image.
        logo_w, logo_h = 340, 130
        logo_box = [margin, margin, margin + logo_w, margin + logo_h]
        draw.rectangle(logo_box, outline=box_line, width=3)
        logo_font = _font(bold=False, size=26)
        logo_text = "[COMPANY LOGO]"
        tw = draw.textlength(logo_text, font=logo_font)
        draw.text((margin + (logo_w - tw) / 2, margin + logo_h / 2 - 16), logo_text,
                   font=logo_font, fill=muted_ink)

        # Date, top-right.
        if submission_date:
            date_font = _font(bold=False, size=30)
            date_text = str(submission_date)
            tw = draw.textlength(date_text, font=date_font)
            draw.text((w - margin - tw, margin + logo_h / 2 - 18), date_text, font=date_font, fill=ink)

        # Title + subtitle, vertically centred in the space below the logo row.
        content_top = margin + logo_h + 60
        title_font_size = 74
        title_font = _font(bold=True, size=title_font_size)
        title_lines = _wrap_text(draw, tender_name or "Tender Response Pack", title_font, w - 2 * margin)
        if len(title_lines) > 2:
            title_font_size = 56
            title_font = _font(bold=True, size=title_font_size)
            title_lines = _wrap_text(draw, tender_name or "Tender Response Pack", title_font, w - 2 * margin)
        ty = content_top
        line_h = int(title_font_size * 1.18)
        for line in title_lines[:2]:
            draw.text((margin, ty), line, font=title_font, fill=ink)
            ty += line_h

        if project_name and project_name.strip() and project_name.strip() != (tender_name or "").strip():
            sub_font = _font(bold=False, size=32)
            sub_lines = _wrap_text(draw, project_name.strip(), sub_font, w - 2 * margin)
            ty += 14
            for line in sub_lines[:2]:
                draw.text((margin, ty), line, font=sub_font, fill=muted_ink)
                ty += 42

        # Rule + "Response to Tender" / client line, anchored to the bottom
        # of the band so they land consistently regardless of title length.
        rule_y = h - 150
        draw.rectangle([margin, rule_y, w - margin, rule_y + 3], fill=accent)

        resp_font = _font(bold=False, size=30)
        draw.text((margin, rule_y + 24), "Response to Tender", font=resp_font, fill=ink)
        if client_name and client_name.strip():
            client_font = _font(bold=False, size=30)
            draw.text((margin, rule_y + 66), client_name.strip(), font=client_font, fill=muted_ink)

        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


def render_full_bleed_cover(
    tender_name: str,
    project_name: str,
    client_name: str,
    submission_date: str,
    photo_bytes: bytes | None = None,
    theme_name: str = _DEFAULT_THEME,
    disclaimer_text: str | None = None,
    size: tuple[int, int] | None = None,
) -> bytes | None:
    """
    Renders a TRUE full-bleed cover page as a single A4 image: a themed colour
    band across the top (logo placeholder, date, title, subtitle, rule,
    "Response to Tender" / client line) and the user's own project photo
    filling the rest of the page all the way to the bottom edge -- no white
    space anywhere on the page, matching the reference cover the user
    supplied. If no photo is available the theme colour is simply extended
    down the page (never a stock/invented image) with a subtle accent wedge
    for depth. `disclaimer_text`, if given, is baked in as a translucent
    strip near the bottom, since a full-bleed image page leaves no room for a
    separate native-docx paragraph. Same THEME_COLOURS every other generated
    graphic in this tool uses, so the cover reads as part of the same
    document. Returns PNG bytes, or None on any failure (caller falls back
    to a plain text cover, same as every other renderer here).
    """
    try:
        colours = THEME_COLOURS.get(theme_name, THEME_COLOURS[_DEFAULT_THEME])
        w, h = size or (PAGE_W, PAGE_H)
        primary = colours["primary"]
        accent = colours["accent"]
        # Minimalist's primary is a light background -- everything else here
        # is dark enough for white text/lines to read clearly.
        light_bg = sum(primary) / 3 > 150
        ink = (40, 40, 40, 255) if light_bg else WHITE
        muted_ink = (90, 90, 90, 255) if light_bg else (255, 255, 255, 200)
        box_line = (90, 90, 90, 255) if light_bg else (255, 255, 255, 220)

        band_h = int(h * 0.34)

        img = Image.new("RGBA", (w, h), primary + (255,))
        photo = _load_cropped_photo(photo_bytes, w, h - band_h) if photo_bytes else None
        if photo is not None:
            img.paste(photo, (0, band_h))
        else:
            # No photo supplied -- extend the theme colour to the bottom edge
            # (never a stock/invented image), with a subtle diagonal accent
            # wedge so the lower page isn't completely flat.
            wedge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(wedge).polygon(
                [(w * 0.66, h), (w, h), (w, band_h + int((h - band_h) * 0.35))],
                fill=accent + (55,),
            )
            img = Image.alpha_composite(img, wedge)

        draw = ImageDraw.Draw(img)
        # Paint the band solid after the photo paste, so it's a crisp block
        # regardless of what's beneath it.
        draw.rectangle([0, 0, w, band_h], fill=primary + (255,))

        margin = 58

        # Logo placeholder, top-left -- an empty box, never a guessed image.
        logo_w, logo_h = 220, 82
        logo_box = [margin, margin, margin + logo_w, margin + logo_h]
        draw.rectangle(logo_box, outline=box_line, width=2)
        logo_font = _font(bold=False, size=17)
        logo_text = "[COMPANY LOGO]"
        tw = draw.textlength(logo_text, font=logo_font)
        draw.text((margin + (logo_w - tw) / 2, margin + logo_h / 2 - 10), logo_text,
                   font=logo_font, fill=muted_ink)

        # Date, top-right.
        if submission_date:
            date_font = _font(bold=False, size=21)
            date_text = str(submission_date)
            tw = draw.textlength(date_text, font=date_font)
            draw.text((w - margin - tw, margin + logo_h / 2 - 12), date_text, font=date_font, fill=ink)

        # Title + subtitle, in the space below the logo row.
        content_top = margin + logo_h + 40
        max_w = w - 2 * margin
        max_title_bottom = band_h - 92  # keep clear of the rule/response line

        title_font_size = 46
        title_font = _font(bold=True, size=title_font_size)
        title_lines = _wrap_text(draw, tender_name or "Tender Response Pack", title_font, max_w)
        if len(title_lines) > 2:
            title_font_size = 36
            title_font = _font(bold=True, size=title_font_size)
            title_lines = _wrap_text(draw, tender_name or "Tender Response Pack", title_font, max_w)
        ty = content_top
        line_h = int(title_font_size * 1.18)
        for line in title_lines[:2]:
            if ty + line_h > max_title_bottom:
                break
            draw.text((margin, ty), line, font=title_font, fill=ink)
            ty += line_h

        if project_name and project_name.strip() and project_name.strip() != (tender_name or "").strip():
            sub_font = _font(bold=False, size=22)
            sub_lines = _wrap_text(draw, project_name.strip(), sub_font, max_w)
            ty += 8
            for line in sub_lines[:1]:
                if ty + 28 > max_title_bottom:
                    break
                draw.text((margin, ty), line, font=sub_font, fill=muted_ink)
                ty += 28

        # Rule + "Response to Tender" / client line, anchored to the bottom
        # of the band so they land consistently regardless of title length.
        rule_y = band_h - 66
        draw.rectangle([margin, rule_y, w - margin, rule_y + 3], fill=accent)
        resp_font = _font(bold=False, size=21)
        draw.text((margin, rule_y + 16), "Response to Tender", font=resp_font, fill=ink)
        if client_name and client_name.strip():
            client_font = _font(bold=False, size=21)
            client_text = client_name.strip()
            tw = draw.textlength(client_text, font=client_font)
            draw.text((w - margin - tw, rule_y + 16), client_text, font=client_font, fill=muted_ink)

        # Optional disclaimer, baked in as a translucent strip at the very
        # bottom of the page -- a full-bleed image leaves no room for a
        # separate native-docx paragraph underneath it.
        if disclaimer_text and disclaimer_text.strip():
            warn_text = disclaimer_text.strip()
            warn_max_w = w - 2 * margin
            warn_size = 16
            warn_font = _font(bold=True, size=warn_size)
            warn_lines = _wrap_text(draw, warn_text, warn_font, warn_max_w)
            # Shrink until it wraps to no more than 2 lines and each line fits.
            while (len(warn_lines) > 2 or any(draw.textlength(l, font=warn_font) > warn_max_w
                   for l in warn_lines)) and warn_size > 10:
                warn_size -= 1
                warn_font = _font(bold=True, size=warn_size)
                warn_lines = _wrap_text(draw, warn_text, warn_font, warn_max_w)
            warn_lines = warn_lines[:2]
            warn_line_h = int(warn_size * 1.3)
            strip_h = warn_line_h * len(warn_lines) + 24
            strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(strip).rectangle([0, h - strip_h, w, h], fill=(0, 0, 0, 195))
            img = Image.alpha_composite(img, strip)
            draw = ImageDraw.Draw(img)
            ty = h - strip_h + (strip_h - warn_line_h * len(warn_lines)) / 2
            for line in warn_lines:
                tw = draw.textlength(line, font=warn_font)
                draw.text(((w - tw) / 2, ty), line, font=warn_font, fill=(255, 140, 140, 255))
                ty += warn_line_h

        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


# A4 portrait at ~150 DPI -- the canvas for full-page section dividers.
PAGE_W, PAGE_H = 1240, 1754


def render_full_page_divider(
    title: str,
    layout: str,
    theme_name: str = _DEFAULT_THEME,
    photo_bytes: bytes | None = None,
    section_label: str | None = None,
    font_paths: dict | None = None,
    size: tuple[int, int] = (PAGE_W, PAGE_H),
) -> bytes | None:
    """
    Render a FULL A4 PAGE section divider (not the thin banner strip) -- the kind
    of divider a real proposal uses between major sections. Two looks, matching
    the examples the user supplied:

      - Solid colour: a full page in the theme colour, big section title low-left,
        a large ghosted section number bottom-right (like the "Appendix D" page).
      - Photo: a real uploaded project photo filling the upper ~70% of the page,
        with a solid colour band across the bottom carrying the title and number
        (like the "Delivering the service 02" page).

    Returns PNG bytes, or None on any failure (caller falls back to the banner or
    a text divider). `section_label` is the big number/letter (e.g. "02").
    """
    try:
        colours = THEME_COLOURS.get(theme_name, THEME_COLOURS[_DEFAULT_THEME])
        w, h = size
        wants_photo = layout != "Solid colour"
        photo = _load_cropped_photo(photo_bytes, w, int(h * 0.72)) if (wants_photo and photo_bytes) else None
        if photo is not None:
            img = _full_page_photo(photo, title, colours, section_label, font_paths, size)
        else:
            img = _full_page_solid(title, colours, section_label, font_paths, size)
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


def _full_page_solid(title, colours, section_label, font_paths, size):
    w, h = size
    img = Image.new("RGBA", (w, h), colours["primary"] + (255,))
    # Diagonal darker wedge bottom-right for depth (subtle, like the examples).
    band = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(band).polygon([(w * 0.70, h), (w, h), (w, h * 0.55)], fill=colours["accent"] + (70,))
    img = Image.alpha_composite(img, band)
    draw = ImageDraw.Draw(img)

    _big_ghost_number(draw, section_label, colours, font_paths, size)

    # Title block, lower-left, with an accent underline above it.
    ty = int(h * 0.62)
    draw.rectangle([90, ty - 34, 90 + 150, ty - 34 + 10], fill=colours["accent"])
    _draw_page_title(draw, title, (90, ty), w - 260, font_paths)
    return img


def _full_page_photo(photo, title, colours, section_label, font_paths, size):
    w, h = size
    band_top = int(h * 0.70)
    img = Image.new("RGBA", (w, h), colours["primary"] + (255,))
    img.paste(photo, (0, 0))
    # Solid colour band across the bottom carrying the text.
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, band_top, w, h], fill=colours["primary"] + (255,))
    # A thin accent line at the very top of the band.
    draw.rectangle([0, band_top, w, band_top + 8], fill=colours["accent"])

    # Big solid-white section number, bottom-right of the band.
    _big_number_solid(draw, section_label, font_paths, size)

    # Title near the top of the band, left-aligned, kept clear of the number zone.
    ty = band_top + 70
    draw.rectangle([90, ty - 34, 90 + 150, ty - 34 + 9], fill=colours["accent"])
    _draw_page_title(draw, title, (90, ty), int(w * 0.60), font_paths)
    return img


def _big_number_solid(draw, section_label, font_paths, size):
    if not section_label:
        return
    w, h = size
    num_font = _page_font(font_paths, bold=True, size=300)
    text = str(section_label)
    try:
        bbox = draw.textbbox((0, 0), text, font=num_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        off_y = bbox[1]
    except Exception:
        tw, th, off_y = 200, 240, 0
    x = w - tw - 80
    y = h - th - off_y - 40
    draw.text((x, y), text, font=num_font, fill=WHITE)


def _big_ghost_number(draw, section_label, colours, font_paths, size, y_center=None):
    if not section_label:
        return
    w, h = size
    num_font = _page_font(font_paths, bold=True, size=340)
    text = str(section_label)
    try:
        bbox = draw.textbbox((0, 0), text, font=num_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = 200, 260
    x = w - tw - 90
    y = (y_center - th // 2) if y_center is not None else int(h * 0.66)
    draw.text((x, y), text, font=num_font, fill=(255, 255, 255, 60))


def _draw_page_title(draw, title, xy, max_width, font_paths):
    x, y = xy
    font = _page_font(font_paths, bold=True, size=68)
    # Shrink to fit within two lines if very long.
    lines = _wrap_text(draw, title, font, max_width)
    if len(lines) > 2:
        font = _page_font(font_paths, bold=True, size=52)
        lines = _wrap_text(draw, title, font, max_width)
    line_h = int(font.size * 1.15)
    for i, line in enumerate(lines[:3]):
        draw.text((x, y + i * line_h), line, font=font, fill=WHITE)


def _page_font(font_paths, bold=False, size=48):
    """Font for full-page dividers -- honours a caller-supplied font (e.g. Arial)
    with a graceful fallback to the bundled DejaVu."""
    if font_paths:
        path = font_paths.get("bold" if bold else "regular")
        if path:
            key = ("page", path, size)
            if key in _FONT_CACHE:
                return _FONT_CACHE[key]
            try:
                f = ImageFont.truetype(path, size=size)
                _FONT_CACHE[key] = f
                return f
            except Exception:
                pass
    return _font(bold=bold, size=size)


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------

def _layout_solid(title: str, colours: dict, size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), colours["primary"] + (255,))
    draw = ImageDraw.Draw(img)

    # Subtle diagonal accent band, bottom-right, for visual interest without a photo.
    band = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band)
    band_draw.polygon(
        [(w * 0.62, h), (w, h), (w, 0), (w * 0.82, h)], fill=colours["accent"] + (60,)
    )
    img = Image.alpha_composite(img, band)
    draw = ImageDraw.Draw(img)

    accent_h = 8
    draw.rectangle([80, h // 2 - 46, 80 + 120, h // 2 - 46 + accent_h], fill=colours["accent"])
    _draw_fitted_text(draw, title, (80, h // 2 - 20), w - 160, colours=(255, 255, 255, 255), bold=True, max_size=64)
    return img


def _layout_photo_gradient(photo: Image.Image, title: str, colours: dict) -> Image.Image:
    img = photo.convert("RGBA")
    w, h = img.size
    gradient = _vertical_gradient(w, h, (0, 0, 0, 0), (0, 0, 0, 200), start=0.35)
    img = Image.alpha_composite(img, gradient)
    draw = ImageDraw.Draw(img)
    accent_h = 8
    draw.rectangle([80, h - 130, 80 + 120, h - 130 + accent_h], fill=colours["accent"])
    _draw_fitted_text(draw, title, (80, h - 110), w - 160, colours=WHITE, bold=True, max_size=64)
    return img


def _layout_photo_quote(
    photo: Image.Image, title: str, quote_text: str | None, quote_attribution: str | None, colours: dict
) -> Image.Image:
    img = photo.convert("RGBA")
    w, h = img.size
    gradient = _vertical_gradient(w, h, (0, 0, 0, 60), (0, 0, 0, 215), start=0.0)
    img = Image.alpha_composite(img, gradient)
    draw = ImageDraw.Draw(img)

    accent_h = 8
    draw.rectangle([80, 60, 80 + 120, 60 + accent_h], fill=colours["accent"])
    _draw_fitted_text(draw, title, (80, 78), w - 160, colours=WHITE, bold=True, max_size=52)

    if quote_text:
        quote_font = _font(bold=False, italic=True, size=34)
        mark_font = _font(bold=True, size=90)
        draw.text((78, h - 300), "“", font=mark_font, fill=colours["accent"] + (255,))
        wrapped = _wrap_text(draw, f"{quote_text.strip()}", quote_font, w - 220)
        ty = h - 230
        for line in wrapped[:3]:
            draw.text((130, ty), line, font=quote_font, fill=WHITE)
            ty += 44
        if quote_attribution:
            attr_font = _font(bold=True, size=26)
            draw.text((130, ty + 10), f"— {quote_attribution.strip()}", font=attr_font,
                       fill=colours["accent"] + (255,))
    return img


def _layout_split(photo: Image.Image, title: str, colours: dict, size: tuple[int, int]) -> Image.Image:
    w, h = size
    split_x = int(w * 0.38)
    img = Image.new("RGBA", (w, h), colours["primary"] + (255,))
    photo_half = _cover_crop(photo, w - split_x, h)
    img.paste(photo_half, (split_x, 0))
    draw = ImageDraw.Draw(img)
    accent_h = 8
    draw.rectangle([70, h // 2 - 46, 70 + 100, h // 2 - 46 + accent_h], fill=colours["accent"])
    _draw_fitted_text(draw, title, (70, h // 2 - 20), split_x - 110, colours=WHITE, bold=True, max_size=48)
    return img


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cropped_photo(photo_bytes: bytes, w: int, h: int) -> Image.Image | None:
    try:
        photo = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
        return _cover_crop(photo, w, h)
    except Exception:
        return None


def _cover_crop(photo: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+centre-crop an image to exactly (w, h), preserving aspect (cover-fit)."""
    src_w, src_h = photo.size
    target_ratio = w / h
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_h = h
        new_w = int(src_ratio * new_h)
    else:
        new_w = w
        new_h = int(new_w / src_ratio)
    resized = photo.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _vertical_gradient(w: int, h: int, top_rgba, bottom_rgba, start: float = 0.0) -> Image.Image:
    grad = Image.new("RGBA", (1, h), (0, 0, 0, 0))
    for y in range(h):
        t = max(0.0, (y / h - start) / max(1e-6, 1 - start))
        t = min(1.0, t)
        r = int(top_rgba[0] + (bottom_rgba[0] - top_rgba[0]) * t)
        g = int(top_rgba[1] + (bottom_rgba[1] - top_rgba[1]) * t)
        b = int(top_rgba[2] + (bottom_rgba[2] - top_rgba[2]) * t)
        a = int(top_rgba[3] + (bottom_rgba[3] - top_rgba[3]) * t)
        grad.putpixel((0, y), (r, g, b, a))
    return grad.resize((w, h))


_FONT_CACHE: dict[tuple, ImageFont.FreeTypeFont] = {}


def _font(bold: bool = False, italic: bool = False, size: int = 40) -> ImageFont.FreeTypeFont:
    key = (bold, italic, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    if italic:
        path = _FONT_DIR / "DejaVuSans-Oblique.ttf"
    elif bold:
        path = _FONT_DIR / "DejaVuSans-Bold.ttf"
    else:
        path = _FONT_DIR / "DejaVuSans.ttf"
    try:
        font = ImageFont.truetype(str(path), size=size)
    except Exception:
        font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_fitted_text(draw, text: str, xy, max_width: int, colours, bold: bool, max_size: int = 64, min_size: int = 28):
    """Shrink font size until the (possibly two-line) title fits max_width, then draw it."""
    size = max_size
    while size > min_size:
        font = _font(bold=bold, size=size)
        lines = _wrap_text(draw, text, font, max_width)
        if len(lines) <= 2 and all(draw.textlength(l, font=font) <= max_width for l in lines):
            break
        size -= 4
    x, y = xy
    line_height = int(size * 1.25)
    for line in lines[:2]:
        draw.text((x, y), line, font=font, fill=colours)
        y += line_height
