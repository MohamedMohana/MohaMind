"""Generate the animated MohaMind README banner (docs/assets/banner.svg).

Hermes-style, inverted: chartreuse field #edff45, hermes-blue #0000f2
wordmark and slogan, and an animated brain (breathing pulse, glow,
neural sparks).  Regenerate with:

    uv run python .github/readme_banner_generator.py
"""

import pathlib

import pyfiglet

lines = pyfiglet.figlet_format("MohaMind", font="ansi_shadow", width=200).split("\n")
lines = [line for line in lines if line.strip()]
width = max(len(line) for line in lines)
lines = [line.ljust(width) for line in lines]
print("figlet:", len(lines), "rows x", width, "cols")

FS = 20          # wordmark font size
LH = 18.6        # line height
X0, Y0 = 52, 96  # wordmark origin
TEXTLEN = width * FS * 0.6


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


wordmark = "\n".join(
    f'<text x="{X0}" y="{Y0 + i * LH:.1f}" xml:space="preserve" class="wm" '
    f'textLength="{TEXTLEN:.0f}" lengthAdjust="spacingAndGlyphs">{esc(line)}</text>'
    for i, line in enumerate(lines)
)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1200 320"
     font-family="ui-monospace, 'Menlo', 'Consolas', 'Courier New', monospace">
  <defs>
    <linearGradient id="wmg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0000f2"/>
      <stop offset="1" stop-color="#2a2ac0"/>
    </linearGradient>
    <linearGradient id="brg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#8fb0ff"/>
      <stop offset="0.55" stop-color="#7a7aff"/>
      <stop offset="1" stop-color="#b07cf0"/>
    </linearGradient>
    <radialGradient id="glow">
      <stop offset="0" stop-color="#7a7aff" stop-opacity="0.5"/>
      <stop offset="0.65" stop-color="#b07cf0" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#edff45" stop-opacity="0"/>
    </radialGradient>
    <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3"/>
    </filter>
  </defs>
  <style>
    .wm {{ font-size: {FS}px; fill: url(#wmg); font-weight: bold; }}
    .slogan {{ font-size: 23px; font-style: italic; fill: #0000f2; font-weight: bold; }}
    .orn {{ font-size: 16px; fill: #0000f2; opacity: 0.55; }}
    .gyri {{ fill: none; stroke: #232399; stroke-width: 4.5; stroke-linecap: round; }}
    .hilite {{ fill: none; stroke: #f5f5f5; stroke-width: 2; stroke-linecap: round; opacity: 0.35; }}
    .spark {{ fill: #ffffff; stroke: #0000f2; stroke-width: 1; }}
  </style>

  <rect x="2" y="2" width="1196" height="316" rx="14" fill="#edff45" stroke="#0000f2" stroke-width="4"/>

  <text x="52" y="48" xml:space="preserve" class="orn">/\\-_=+|&lt;  -/=  ~:*-/
    <animate attributeName="opacity" values="0.35;0.75;0.35" dur="6s" repeatCount="indefinite"/>
  </text>

{wordmark}

  <text x="52" y="268" class="slogan">your personal agent · always on · always remembering</text>

  <!-- ══ Brain ══ (local coords translated into place, breathing pulse) -->
  <g transform="translate(990,155)">
    <g transform="scale(0.88)">
      <animateTransform attributeName="transform" type="scale" values="1;1.035;1"
                        dur="4s" additive="sum" repeatCount="indefinite"/>
      <g transform="translate(-110,-92)">

        <ellipse cx="110" cy="92" rx="128" ry="104" fill="url(#glow)">
          <animate attributeName="opacity" values="0.55;1;0.55" dur="4s" repeatCount="indefinite"/>
        </ellipse>

        <!-- coral fronds (echo of the watercolor reference) -->
        <g filter="url(#soft)" opacity="0.85">
          <path d="M28,132 C18,112 26,96 20,80 C34,92 40,112 36,132 Z" fill="#c98aff"/>
          <path d="M192,118 C204,102 200,86 208,74 C214,92 208,112 198,124 Z" fill="#e08ae0"/>
          <path d="M96,178 C90,164 96,152 92,142 C104,150 108,166 104,178 Z" fill="#a97cff"/>
        </g>

        <!-- cerebellum -->
        <path d="M138,138 C146,158 170,162 186,150 C196,142 196,128 188,122 C172,116 148,122 138,138 Z"
              fill="#8f7ae8" stroke="#232399" stroke-width="4"/>
        <path class="gyri" stroke-width="2.5" d="M150,146 C156,136 166,132 178,134 M156,152 C162,142 172,138 182,140"/>
        <!-- brainstem -->
        <path d="M136,150 C134,162 126,168 118,172 C128,174 140,170 144,158 Z"
              fill="#7a6ad0" stroke="#232399" stroke-width="3.5"/>

        <!-- hemisphere silhouette -->
        <path d="M18,94 C12,74 22,56 38,50 C42,30 62,18 78,24 C88,6 114,2 128,14 C144,2 166,8 174,24
                 C194,26 206,42 202,60 C216,72 216,94 204,104 C208,120 196,134 180,136
                 C172,150 152,156 140,148 C128,160 106,162 94,150 C78,160 56,154 50,140
                 C32,142 18,128 20,112 C10,106 12,100 18,94 Z"
              fill="url(#brg)" stroke="#232399" stroke-width="5" stroke-linejoin="round"/>

        <!-- gyri -->
        <path class="gyri" d="M34,92 C48,78 62,90 56,106"/>
        <path class="gyri" d="M50,58 C68,46 84,60 74,78"/>
        <path class="gyri" id="gy3" d="M88,32 C104,24 118,36 108,54 C100,66 112,74 122,66"/>
        <path class="gyri" d="M132,22 C150,18 160,34 150,48"/>
        <path class="gyri" d="M170,40 C186,44 190,62 176,70"/>
        <path class="gyri" d="M186,88 C198,96 194,112 180,114"/>
        <path class="gyri" id="gy7" d="M118,82 C134,74 148,86 140,102 C134,114 146,122 156,114"/>
        <path class="gyri" d="M66,112 C82,102 96,114 88,130"/>
        <!-- highlights -->
        <path class="hilite" d="M40,86 C52,76 62,84 58,96"/>
        <path class="hilite" d="M94,38 C106,32 114,40 110,50"/>
        <path class="hilite" d="M138,28 C150,26 156,36 150,44"/>

        <!-- neural sparks travelling the folds -->
        <circle class="spark" r="4.5" opacity="0">
          <animateMotion dur="3.2s" repeatCount="indefinite"><mpath xlink:href="#gy3"/></animateMotion>
          <animate attributeName="opacity" values="0;1;1;0" dur="3.2s" repeatCount="indefinite"/>
        </circle>
        <circle class="spark" r="4" opacity="0">
          <animateMotion dur="4.1s" begin="1.2s" repeatCount="indefinite"><mpath xlink:href="#gy7"/></animateMotion>
          <animate attributeName="opacity" values="0;1;1;0" dur="4.1s" begin="1.2s" repeatCount="indefinite"/>
        </circle>
        <circle class="spark" r="3.5" opacity="0">
          <animateMotion dur="5s" begin="2.4s" repeatCount="indefinite" path="M34,92 C48,78 62,90 56,106"/>
          <animate attributeName="opacity" values="0;1;1;0" dur="5s" begin="2.4s" repeatCount="indefinite"/>
        </circle>
      </g>
    </g>
  </g>
</svg>
'''

out = pathlib.Path("docs/assets")
out.mkdir(parents=True, exist_ok=True)
(out / "banner.svg").write_text(svg, encoding="utf-8")
print("wrote docs/assets/banner.svg", len(svg), "bytes")
