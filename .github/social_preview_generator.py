"""Generate MohaMind's GitHub social preview banner (1280x640)."""

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 640

# ---------- palette ----------
BG_TOP = (7, 10, 20)
BG_BOT = (13, 20, 36)
PANEL = (11, 16, 28)
PANEL_BORDER = (34, 48, 72)
HEADER = (15, 22, 38)
GREEN = (0, 255, 135)
CYAN = (77, 201, 255)
VIOLET = (183, 148, 246)
AMBER = (255, 184, 107)
TEXT_MAIN = (226, 236, 250)
TEXT_DIM = (143, 163, 191)
TEXT_FAINT = (96, 114, 140)

ASCII_LOGO = [
    "███╗   ███╗ ██████╗ ██╗  ██╗ █████╗ ███╗   ███╗██╗███╗   ██╗██████╗         ▄▄███▄  ▄███▄▄",
    "████╗ ████║██╔═══██╗██║  ██║██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗      ▄██╭╮╭╮██  ██╭╮╭╮██▄",
    "██╔████╔██║██║   ██║███████║███████║██╔████╔██║██║██╔██╗ ██║██║  ██║     ██▌╰╯╭╯██▌▐██╰╮╰╯▐██",
    "██║╚██╔╝██║██║   ██║██╔══██║██╔══██║██║╚██╔╝██║██║██║╚██╗██║██║  ██║     ██▌╭╮╰╮██▌▐██╭╯╭╮▐██",
    "██║ ╚═╝ ██║╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██████╔╝      ▀██╰╯╰╯██▌▐██╰╯╰╯██▀",
    "╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝         ▀▀██▄▄▐▌▄▄██▀▀",
]

MENLO = "/System/Library/Fonts/Menlo.ttc"
SANS = "/System/Library/Fonts/SFNS.ttf"
ARABIC = "/System/Library/Fonts/GeezaPro.ttc"


def lerp(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def ar(text):
    return get_display(arabic_reshaper.reshape(text))


img = Image.new("RGB", (W, H), BG_TOP)
draw = ImageDraw.Draw(img)

# ---------- background: vertical gradient ----------
for y in range(H):
    draw.line([(0, y), (W, y)], fill=lerp(BG_TOP, BG_BOT, y / H))

# soft radial glow behind the logo (green->transparent)
glow = Image.new("RGB", (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse([W // 2 - 430, 90, W // 2 + 430, 400], fill=(0, 62, 42))
gd.ellipse([W // 2 + 150, 120, W // 2 + 640, 380], fill=(10, 46, 70))
glow = glow.filter(ImageFilter.GaussianBlur(120))
img = Image.blend(img, Image.composite(glow, img, Image.new("L", (W, H), 255)), 0.0)
# simpler additive glow:
import numpy as np  # noqa: E402

img = Image.fromarray(np.clip(np.asarray(img).astype(int) + np.asarray(glow).astype(int), 0, 255).astype("uint8"))
draw = ImageDraw.Draw(img)

# faint dot grid
for gy in range(70, H, 46):
    for gx in range(40, W, 46):
        draw.point((gx, gy), fill=lerp(BG_BOT, (30, 42, 64), 0.55))

# ---------- terminal panel ----------
PX0, PY0, PX1, PY1 = 56, 56, W - 56, H - 56
# drop shadow
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle([PX0 + 6, PY0 + 14, PX1 + 6, PY1 + 14], radius=18, fill=(0, 0, 0, 160))
shadow = shadow.filter(ImageFilter.GaussianBlur(18))
img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
draw = ImageDraw.Draw(img)

draw.rounded_rectangle([PX0, PY0, PX1, PY1], radius=18, fill=PANEL, outline=PANEL_BORDER, width=2)
# header bar
draw.rounded_rectangle([PX0, PY0, PX1, PY0 + 44], radius=18, fill=HEADER)
draw.rectangle([PX0, PY0 + 26, PX1, PY0 + 44], fill=HEADER)
draw.line([(PX0, PY0 + 44), (PX1, PY0 + 44)], fill=PANEL_BORDER, width=2)
for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    cx = PX0 + 26 + i * 26
    draw.ellipse([cx, PY0 + 15, cx + 14, PY0 + 29], fill=c)
f_title = ImageFont.truetype(MENLO, 15)
title = "mohamind — always on · always remembering"
tw = draw.textlength(title, font=f_title)
draw.text(((W - tw) / 2, PY0 + 14), title, font=f_title, fill=TEXT_FAINT)

# ---------- ASCII logo with horizontal gradient ----------
f_logo = ImageFont.truetype(MENLO, 18)
char_w = draw.textlength("█", font=f_logo)
line_h = 20
logo_w = char_w * max(len(line) for line in ASCII_LOGO)
lx0 = (W - logo_w) / 2
ly0 = PY0 + 78

for row, line in enumerate(ASCII_LOGO):
    for col, ch in enumerate(line):
        if ch == " ":
            continue
        t = col / max(len(line) - 1, 1)
        color = lerp(GREEN, CYAN, t)
        draw.text((lx0 + col * char_w, ly0 + row * line_h), ch, font=f_logo, fill=color)

# ---------- taglines ----------
f_tag = ImageFont.truetype(SANS, 27)
tag = "Your personal AI agent  ·  plain-Markdown memory  ·  runs on your own server"
tw = draw.textlength(tag, font=f_tag)
ty = ly0 + 6 * line_h + 30
draw.text(((W - tw) / 2, ty), tag, font=f_tag, fill=TEXT_MAIN)

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
    ("◐ mohamind > ", GREEN),
    ("ذكرني بكره ٩ الصبح أتصل بأحمد", TEXT_MAIN),
]
total = sum(draw.textlength(ar(p) if is_arabic(p) else p, font=seg_font(p)) for p, _ in prompt_parts) + 16
px = (W - total) / 2
for part, color in prompt_parts:
    shaped = ar(part) if is_arabic(part) else part
    draw.text((px, py), shaped, font=seg_font(part), fill=color)
    px += draw.textlength(shaped, font=seg_font(part))
draw.rectangle([px + 4, py + 2, px + 16, py + 24], fill=GREEN)  # cursor

# agent reply line (storytelling: it understood the dialect and scheduled it)
f_reply = ImageFont.truetype(MENLO, 17)
reply = "✓ reminder set — tomorrow 09:00 · Asia/Riyadh"
rw = draw.textlength(reply, font=f_reply)
draw.text(((W - rw) / 2, py + 40), reply, font=f_reply, fill=lerp(CYAN, TEXT_FAINT, 0.35))

# ---------- feature chips ----------
f_chip = ImageFont.truetype(SANS, 19)
f_chip_ar = ImageFont.truetype(ARABIC, 19)
chips = [
    ([("Markdown memory", f_chip)], GREEN),
    ([("Proactive Telegram", f_chip)], CYAN),
    ([("Owner-locked", f_chip)], AMBER),
    ([("English + ", f_chip), ("عربي", f_chip_ar)], VIOLET),
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
    draw.rounded_rectangle([cx, cy, cx + cw, cy + chip_h], radius=chip_h // 2, outline=PANEL_BORDER, width=2)
    draw.ellipse([cx + pad_x, cy + chip_h / 2 - 5, cx + pad_x + 10, cy + chip_h / 2 + 5], fill=color)
    sx = cx + pad_x + 18
    for text, font in segments:
        shaped = ar(text) if is_arabic(text) else text
        draw.text((sx, cy + (chip_h - 26) / 2), shaped, font=font, fill=TEXT_MAIN)
        sx += draw.textlength(shaped, font=font)
    cx += cw + gap

img.save("/Users/mohana/Documents/CODE/opencode/MohaMind/.github/social-preview.png", optimize=True)
print("saved")
