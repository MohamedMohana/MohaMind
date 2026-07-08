"""Generate MohaMind's GitHub social preview banner (1280x640).

Hermes-style: blue field #0000f2, off-white #f5f5f5 text, chartreuse
#edff45 accents — same identity as docs/assets/banner.svg and
moha_mind/cli/themes.py.
Regenerate with:
  uv run --with pillow --with arabic-reshaper --with python-bidi \
      python .github/social_preview_generator.py
"""

import pathlib

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 640

# ---------- Hermes palette (moha_mind/cli/themes.py) ----------
FIELD = (0, 0, 242)  # #0000f2 — the blue field
PANEL = (0, 0, 190)  # deeper blue terminal panel
HEADER = (20, 20, 210)  # header strip, a step lighter than the panel
DIVIDER = (53, 53, 184)  # #3535b8 — internal hairlines, chip outlines
ACCENT = (237, 255, 69)  # #edff45 — electric chartreuse
ACCENT_DIM = (185, 197, 62)  # #b9c53e
FG = (245, 245, 245)  # #f5f5f5
PAPER = (255, 255, 255)  # #ffffff
BLUE_SOFT = (138, 138, 255)  # #8a8aff
WM_TOP = (255, 255, 255)  # wordmark gradient, top (banner.svg #wmg)
WM_BOT = (201, 201, 255)  # #c9c9ff, bottom
TEXT_DIM = (201, 201, 255)
TEXT_FAINT = (157, 157, 199)  # #9d9dc7

ORNAMENT = r"/\-_=+|<  -/=  ~:*-/"

ASCII_LOGO = [
    "███╗   ███╗ ██████╗ ██╗  ██╗ █████╗ ███╗   ███╗██╗███╗   ██╗██████╗         ▄▄███▄  ▄███▄▄",
    "████╗ ████║██╔═══██╗██║  ██║██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗      ▄██╭╮╭╮██  ██╭╮╭╮██▄",
    "██╔████╔██║██║   ██║███████║███████║██╔████╔██║██║██╔██╗ ██║██║  ██║     ██▌╰╯╭╯██▌▐██╰╮╰╯▐██",
    "██║╚██╔╝██║██║   ██║██╔══██║██╔══██║██║╚██╔╝██║██║██║╚██╗██║██║  ██║     ██▌╭╮╰╮██▌▐██╭╯╭╮▐██",
    "██║ ╚═╝ ██║╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██████╔╝      ▀██╰╯╰╯██▌▐██╰╯╰╯██▀",
    "╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝         ▀▀██▄▄▐▌▄▄██▀▀",
]
BRAIN_COL = 70  # columns past the wordmark are the brain — drawn in accent

MENLO = "/System/Library/Fonts/Menlo.ttc"
SANS = "/System/Library/Fonts/SFNS.ttf"
ARABIC = "/System/Library/Fonts/GeezaPro.ttc"


def lerp(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def ar(text):
    return get_display(arabic_reshaper.reshape(text))


img = Image.new("RGB", (W, H), FIELD)
draw = ImageDraw.Draw(img)

# faint dot grid on the field
for gy in range(70, H, 46):
    for gx in range(40, W, 46):
        draw.point((gx, gy), fill=lerp(FIELD, BLUE_SOFT, 0.45))

# ---------- terminal panel ----------
PX0, PY0, PX1, PY1 = 56, 56, W - 56, H - 56
# drop shadow
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle([PX0 + 6, PY0 + 14, PX1 + 6, PY1 + 14], radius=18, fill=(0, 0, 90, 170))
shadow = shadow.filter(ImageFilter.GaussianBlur(18))
img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
draw = ImageDraw.Draw(img)

draw.rounded_rectangle([PX0, PY0, PX1, PY1], radius=18, fill=PANEL, outline=ACCENT, width=3)
# header bar
draw.rounded_rectangle([PX0 + 2, PY0 + 2, PX1 - 2, PY0 + 44], radius=16, fill=HEADER)
draw.rectangle([PX0 + 2, PY0 + 26, PX1 - 2, PY0 + 44], fill=HEADER)
draw.line([(PX0 + 2, PY0 + 44), (PX1 - 2, PY0 + 44)], fill=DIVIDER, width=2)
for i, c in enumerate([ACCENT, BLUE_SOFT, FG]):
    cx = PX0 + 26 + i * 26
    draw.ellipse([cx, PY0 + 15, cx + 14, PY0 + 29], fill=c)
f_title = ImageFont.truetype(MENLO, 15)
title = "mohamind — always on · always remembering"
tw = draw.textlength(title, font=f_title)
draw.text(((W - tw) / 2, PY0 + 14), title, font=f_title, fill=TEXT_FAINT)
# ornament glyph run from the Hermes hero section
f_orn = ImageFont.truetype(MENLO, 13)
ow = draw.textlength(ORNAMENT, font=f_orn)
draw.text((PX1 - ow - 26, PY0 + 15), ORNAMENT, font=f_orn, fill=BLUE_SOFT)

# ---------- ASCII logo: off-white wordmark, chartreuse brain ----------
f_logo = ImageFont.truetype(MENLO, 18)
char_w = draw.textlength("█", font=f_logo)
line_h = 20
logo_w = char_w * max(len(line) for line in ASCII_LOGO)
lx0 = (W - logo_w) / 2
ly0 = PY0 + 78

for row, line in enumerate(ASCII_LOGO):
    wm_color = lerp(WM_TOP, WM_BOT, row / (len(ASCII_LOGO) - 1))
    for col, ch in enumerate(line):
        if ch == " ":
            continue
        color = ACCENT if col >= BRAIN_COL else wm_color
        draw.text((lx0 + col * char_w, ly0 + row * line_h), ch, font=f_logo, fill=color)

# ---------- taglines ----------
f_tag = ImageFont.truetype(SANS, 27)
tag = "Your personal AI agent  ·  plain-Markdown memory  ·  runs on your own server"
tw = draw.textlength(tag, font=f_tag)
ty = ly0 + 6 * line_h + 30
draw.text(((W - tw) / 2, ty), tag, font=f_tag, fill=FG)

f_ar = ImageFont.truetype(ARABIC, 25)
tag_ar = ar("مساعدك الشخصي يفهمك بالعربي والإنجليزي، وبياناتك تبقى عندك")
tw = draw.textlength(tag_ar, font=f_ar)
draw.text(((W - tw) / 2, ty + 44), tag_ar, font=f_ar, fill=TEXT_DIM)

# ---------- live prompt line ----------
f_prompt = ImageFont.truetype(MENLO, 20)
f_prompt_ar = ImageFont.truetype(ARABIC, 21)

def is_arabic(text):
    return any("\u0600" <= c <= "\u06ff" for c in text)

def seg_font(text, latin=f_prompt, arabic=f_prompt_ar):
    return arabic if is_arabic(text) else latin

py = ty + 104
prompt_parts = [
    ("◐ mohamind > ", ACCENT),
    ("ذكرني بكره ٩ الصبح أتصل بأحمد", FG),
]
total = sum(draw.textlength(ar(p) if is_arabic(p) else p, font=seg_font(p)) for p, _ in prompt_parts) + 16
px = (W - total) / 2
for part, color in prompt_parts:
    shaped = ar(part) if is_arabic(part) else part
    draw.text((px, py), shaped, font=seg_font(part), fill=color)
    px += draw.textlength(shaped, font=seg_font(part))
draw.rectangle([px + 4, py + 2, px + 16, py + 24], fill=ACCENT)  # cursor

# agent reply line (storytelling: it understood the dialect and scheduled it)
f_reply = ImageFont.truetype(MENLO, 17)
reply = "✓ reminder set — tomorrow 09:00 · Asia/Riyadh"
rw = draw.textlength(reply, font=f_reply)
draw.text(((W - rw) / 2, py + 40), reply, font=f_reply, fill=ACCENT_DIM)

# ---------- feature chips ----------
f_chip = ImageFont.truetype(SANS, 19)
f_chip_ar = ImageFont.truetype(ARABIC, 19)
chips = [
    ([("Markdown memory", f_chip)], ACCENT),
    ([("Proactive Telegram", f_chip)], BLUE_SOFT),
    ([("Owner-locked", f_chip)], PAPER),
    ([("English + ", f_chip), ("عربي", f_chip_ar)], ACCENT_DIM),
]

def chip_segments_width(segments):
    return sum(
        draw.textlength(ar(text) if is_arabic(text) else text, font=font) for text, font in segments
    )

pad_x, gap, chip_h = 18, 14, 42
widths = [chip_segments_width(segments) + pad_x * 2 + 18 for segments, _ in chips]
total_w = sum(widths) + gap * (len(chips) - 1)
cx = (W - total_w) / 2
cy = PY1 - chip_h - 34
for (segments, color), cw in zip(chips, widths):
    draw.rounded_rectangle([cx, cy, cx + cw, cy + chip_h], radius=chip_h // 2, outline=DIVIDER, width=2)
    draw.ellipse([cx + pad_x, cy + chip_h / 2 - 5, cx + pad_x + 10, cy + chip_h / 2 + 5], fill=color)
    sx = cx + pad_x + 18
    for text, font in segments:
        shaped = ar(text) if is_arabic(text) else text
        draw.text((sx, cy + (chip_h - 26) / 2), shaped, font=font, fill=FG)
        sx += draw.textlength(shaped, font=font)
    cx += cw + gap

out = pathlib.Path(__file__).resolve().parent / "social-preview.png"
img.save(out, optimize=True)
print("saved", out)
