#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent
ASSETS, CACHE = ROOT / "assets", ROOT / ".cache"
AVATAR = ASSETS / "da-avatar.png"
SOURCES = {
    "font": "https://raw.githubusercontent.com/google/fonts/main/ofl/{}",
    "si": "https://cdn.jsdelivr.net/npm/simple-icons@16.32.0/icons/{}.svg",
    "si11": "https://cdn.jsdelivr.net/npm/simple-icons@11.15.0/icons/{}.svg",
    "lu": "https://cdn.jsdelivr.net/npm/lucide-static@1.47.0/icons/{}.svg",
}

try:
    import brotli  # noqa: F401
    FLAVOR = "woff2"
except ImportError:
    FLAVOR = "woff"

ABYSS = "#043f52"
PASTEL = dict(mint="#9ce0d9", lavender="#d4c8fe", peach="#fac3a5")
THEMES = {
    "dark": dict(surface="#152a2f", line="#26434a", line_strong="#5a8990", ink="#e6f2f1", muted="#a2bfc2",
                 accent="#a1dafc", role=PASTEL["mint"], shadow=None),
    "light": dict(surface="#ffffff", line="#d6e8e6", line_strong="#678a90", ink=ABYSS, muted="#4a6a72",
                  accent="#005477", role="#4a6a72", shadow=(ABYSS, .08)),
}

INTRO = dict(
    greeting="Hola, soy Davinson",
    role="Data Scientist · AI Engineer",
    avatar_alt="Retrato en acuarela de Davinson Arteaga",
    chips=[("Estadística y machine learning", "lavender", "lu:sigma"),
           ("IA generativa y agentes", "lavender", "lu:bot"),
           ("Analítica y BI", "peach", "lu:chart-column")],
    body="Estadístico de la Universidad del Valle, en Cali, y estudiante de la Maestría en Ciencia de Datos en ICESI. "
         "Trabajo con análisis de datos, modelos de machine learning y agentes de IA, y estoy abierto a roles "
         "de Data Analyst, Data Scientist o AI Engineer.",
)
CONTACT = [
    ("Escribir un correo", "mailto:arteagadavinson@gmail.com", "lu:mail"),
    ("Ver LinkedIn", "https://linkedin.com/in/davinson-arteaga", "si11:linkedin"),
    ("Abrir WhatsApp", "https://wa.me/573157032101", "si:whatsapp"),
]
PROJECTS: list[tuple[str, str | None, str]] = []
STACK = [
    ("Lenguajes y datos", "mint", [("Python", "si:python"), ("R", "si:r"), ("SQL", "lu:database"),
                                   ("SAS", "lu:chart-scatter"), ("pandas", "si:pandas"),
                                   ("PostgreSQL", "si:postgresql"), ("BigQuery", "si:googlebigquery")]),
    ("IA generativa", "lavender", [("MCP", "si:modelcontextprotocol"), ("Ollama", "si:ollama"), ("n8n", "si:n8n"),
                                   ("FAISS", "lu:scan-search"), ("ChromaDB", "lu:database-zap")]),
    ("Machine learning", "lavender", [("PyTorch", "si:pytorch"), ("scikit-learn", "si:scikitlearn"),
                                      ("XGBoost", "lu:trees"), ("Optuna", "si:optuna")]),
    ("BI y visualización", "peach", [("Power BI", "si11:powerbi"), ("Tableau", "si11:tableau"), ("Plotly", "si:plotly")]),
    ("Plataformas y herramientas", None, [("NetSuite", "lu:building-2"), ("Salesforce", "si11:salesforce"),
                                          ("Docker", "si:docker"), ("Git", "si:git"), ("Linux", "si:linux")]),
]
CERTS = [
    dict(slug="dp-900", title="Azure Data Fundamentals", issuer="Microsoft · DP-900", icon="si11:microsoftazure",
         url="https://www.credly.com/badges/dd83bed0-88a8-4cc8-bdea-702b794d8e25/public_url",
         badges=["https://images.credly.com/size/110x110/images/70eb1e3f-d4de-4377-a062-b20fb29594ea/"
                 "azure-data-fundamentals-600x600.png",
                 "https://learn.microsoft.com/en-us/media/learn/certification/badges/microsoft-certified-fundamentals-badge.svg"]),
    dict(slug="hackerrank-sql", title="SQL (Advanced)", issuer="HackerRank", icon="si:hackerrank",
         url="https://www.hackerrank.com/certificates/f3d20ca33ed3", badges=[]),
]


@dataclass(frozen=True)
class Face:
    family: str
    source: str
    weight: int
    fallback: str

    @property
    def css_family(self) -> str:
        return f"'{self.family}', {self.fallback}"


PLEX, SANS_FB = "ibmplexsans/IBMPlexSans[wdth,wght].ttf", "'Segoe UI', Helvetica, Arial, sans-serif"
DISPLAY = Face("Space Grotesk", "spacegrotesk/SpaceGrotesk[wght].ttf", 600, "'IBM Plex Sans', system-ui, sans-serif")
SANS_400, SANS_500, SANS_600 = (Face("IBM Plex Sans", PLEX, w, SANS_FB) for w in (400, 500, 600))
MONO_500 = Face("IBM Plex Mono", "ibmplexmono/IBMPlexMono-Medium.ttf", 500, "ui-monospace, Menlo, Consolas, monospace")
SVG_ROOT = re.compile(r"<svg\b([^>]*)>(.*)</svg>", re.S)


def fetch(url: str) -> bytes:
    path = CACHE / hashlib.sha1(url.encode()).hexdigest()[:16]
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) build-profile"})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
    return path.read_bytes()


@lru_cache
def instance_bytes(face: Face) -> bytes:
    font = TTFont(io.BytesIO(fetch(SOURCES["font"].format(urllib.parse.quote(face.source)))))
    if "fvar" in font:
        axes = {a.axisTag for a in font["fvar"].axes}
        pins = {k: v for k, v in {"wght": face.weight, "wdth": 100}.items() if k in axes}
        font = instancer.instantiateVariableFont(font, pins, updateFontNames=False)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


@lru_cache
def metrics(face: Face) -> tuple[dict, dict, int, int]:
    font = TTFont(io.BytesIO(instance_bytes(face)))
    return font.getBestCmap(), {g: m[0] for g, m in font["hmtx"].metrics.items()}, font["head"].unitsPerEm, font["OS/2"].sCapHeight


def text_width(face: Face, text: str, size: float, tracking: float = 0.0) -> float:
    cmap, adv, upm, _ = metrics(face)
    return sum(adv[cmap.get(ord(c), ".notdef")] for c in text) * size / upm + tracking * size * max(len(text) - 1, 0)


def font_face(face: Face, text: str) -> str:
    font = TTFont(io.BytesIO(instance_bytes(face)))
    opts = Options()
    opts.flavor, opts.layout_features = FLAVOR, ["kern", "liga", "calt"]
    opts.drop_tables += ["meta"]
    sub = Subsetter(opts)
    sub.populate(text=text + " ")
    sub.subset(font)
    font.flavor = FLAVOR
    buf = io.BytesIO()
    font.save(buf)
    return (f"@font-face{{font-family:'{face.family}';font-weight:{face.weight};"
            f"src:url(data:font/{FLAVOR};base64,{base64.b64encode(buf.getvalue()).decode()}) format('{FLAVOR}')}}")


def parse_svg(raw: str) -> tuple[list[float], str, str]:
    attrs, inner = SVG_ROOT.search(raw).groups()
    inner = re.sub(r"<title>.*?</title>|<metadata>.*?</metadata>|<!--.*?-->", "", inner, flags=re.S).strip()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', attrs).group(1).replace(",", " ").split()]
    return vb, attrs, inner


@lru_cache
def icon(refs: str) -> tuple[list[float], bool, str]:
    for ref in refs.split("|"):
        kind, name = ref.split(":", 1)
        local = ASSETS / "icons" / f"{name}.svg"
        try:
            raw = local.read_text("utf-8") if local.exists() else fetch(SOURCES[kind].format(name)).decode()
        except urllib.error.HTTPError:
            continue
        vb, attrs, inner = parse_svg(raw)
        return vb, 'stroke="currentColor"' in attrs, inner
    raise FileNotFoundError(f"Ningún icono disponible para {refs}")


def image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return "image/svg+xml" if b"<svg" in data[:512] else None


@lru_cache
def badge_image(slug: str, urls: tuple[str, ...]) -> tuple[bytes, str] | None:
    for local in sorted((ASSETS / "badges").glob(f"{slug}.*")):
        if mime := image_mime(local.read_bytes()):
            return local.read_bytes(), mime
    for url in urls:
        try:
            data = fetch(url)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"aviso: sin insignia {url} ({exc})", file=sys.stderr)
            continue
        if mime := image_mime(data):
            return data, mime
    return None


class Canvas:
    def __init__(self, width: float, height: float, label: str):
        self.w, self.h, self.label = math.ceil(width), math.ceil(height), label
        self.defs: list[str] = []
        self.body: list[str] = []
        self.glyphs: dict[Face, str] = defaultdict(str)

    def add(self, svg: str) -> None:
        self.body.append(svg)

    def text(self, x: float, cy: float, s: str, face: Face, size: float, fill: str, tracking: float = 0.0) -> None:
        self.glyphs[face] += s
        _, _, upm, cap = metrics(face)
        ls = f' letter-spacing="{tracking * size:.2f}"' if tracking else ""
        self.add(f'<text x="{x:.1f}" y="{cy + cap * size / upm / 2:.1f}" font-family="{face.css_family}" '
                 f'font-weight="{face.weight}" font-size="{size}" fill="{fill}"{ls}>{escape(s)}</text>')

    def image(self, x: float, y: float, w: float, h: float, data: bytes, mime: str, clip: str = "") -> None:
        self.add(f'<image x="{x}" y="{y}" width="{w}" height="{h}"{clip} '
                 f'href="data:{mime};base64,{base64.b64encode(data).decode()}"/>')

    def icon(self, refs: str, x: float, y: float, size: float, color: str) -> None:
        vb, stroked, inner = icon(refs)
        paint = ('fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"'
                 if stroked else 'fill="currentColor"')
        self.add(f'<g color="{color}" {paint} transform="translate({x:.2f} {y:.2f}) '
                 f'scale({size / max(vb[2], vb[3]):.4f}) translate({-vb[0]:g} {-vb[1]:g})" aria-hidden="true">{inner}</g>')

    def pill(self, x: float, y: float, label: str, spec: dict, fill: str, ink: str,
             refs: str | None = None, stroke: tuple[str, float] | None = None) -> float:
        w, h = pill_width(label, refs, **spec), spec["height"]
        inset = stroke[1] / 2 if stroke else 0
        border = f' stroke="{stroke[0]}" stroke-width="{stroke[1]}"' if stroke else ""
        self.add(f'<rect x="{x + inset:.2f}" y="{y + inset:.2f}" width="{w - 2 * inset:.2f}" '
                 f'height="{h - 2 * inset:.2f}" rx="{h / 2 - inset:.2f}" fill="{fill}"{border}/>')
        tx = x + spec["pad"]
        if refs:
            self.icon(refs, tx, y + (h - spec["icon_size"]) / 2, spec["icon_size"], ink)
            tx += spec["icon_size"] + spec["gap"]
        self.text(tx, y + h / 2, label, spec["face"], spec["size"], ink)
        return w

    def save(self, path: Path) -> None:
        css = "".join(font_face(f, t) for f, t in self.glyphs.items())
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
            f'role="img" aria-label={quoteattr(self.label)}><title>{escape(self.label)}</title>'
            f'<style>{css}</style><defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>',
            encoding="utf-8",
        )


CHIP = dict(face=MONO_500, size=13, pad=12, icon_size=14, gap=6, height=30)
BUTTON = dict(face=SANS_600, size=14, pad=24, icon_size=16, gap=8, height=42)


def pill_width(label: str, refs: str | None, face: Face, size: float, pad: float, icon_size: float,
               gap: float, height: float) -> float:
    return text_width(face, label, size) + 2 * pad + (icon_size + gap if refs else 0)


def chip(c: Canvas, x: float, y: float, label: str, family: str | None, refs: str, t: dict) -> float:
    if family:
        return c.pill(x, y, label, CHIP, PASTEL[family], ABYSS, refs)
    return c.pill(x, y, label, CHIP, "none", t["ink"], refs, stroke=(t["line_strong"], 1))


def chip_row(items: list[tuple[str, str]], family: str | None, t: dict, spacing: float = 8) -> Canvas:
    widths = [pill_width(label, refs, **CHIP) for label, refs in items]
    c = Canvas(sum(widths) + spacing * (len(items) - 1), CHIP["height"], ", ".join(label for label, _ in items))
    x = 0.0
    for label, refs in items:
        x += chip(c, x, 0, label, family, refs, t) + spacing
    return c


def button(label: str, refs: str, primary: bool, t: dict) -> Canvas:
    c = Canvas(pill_width(label, refs, **BUTTON), BUTTON["height"], label)
    if primary:
        c.pill(0, 0, label, BUTTON, PASTEL["mint"], ABYSS, refs)
    else:
        c.pill(0, 0, label, BUTTON, "none", t["ink"], refs, stroke=(t["line_strong"], 1.5))
    return c


def card_frame(c: Canvas, x: float, y: float, w: float, h: float, radius: float, t: dict) -> None:
    if t["shadow"]:
        color, alpha = t["shadow"]
        c.defs.append(f'<filter id="soft" x="-20%" y="-20%" width="140%" height="160%">'
                      f'<feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="{color}" flood-opacity="{alpha}"/></filter>')
        c.add(f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{radius}" fill="{t["surface"]}" filter="url(#soft)"/>')
    else:
        c.add(f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1:.1f}" height="{h - 1}" rx="{radius - .5}" '
              f'fill="{t["surface"]}" stroke="{t["line"]}"/>')


def intro(t: dict) -> Canvas:
    m, pad, av, gap_x, gap_y = (24 if t["shadow"] else 0), 32, 128, 32, 24
    name_w = text_width(DISPLAY, INTRO["greeting"], 44, -.015)
    chips_w = sum(pill_width(label, refs, **CHIP) for label, _, refs in INTRO["chips"]) + 8 * (len(INTRO["chips"]) - 1)
    w = 2 * pad + max(av + gap_x + max(name_w, text_width(SANS_500, INTRO["role"], 18)), chips_w)
    h = 2 * pad + av + gap_y + CHIP["height"]
    c = Canvas(w + 2 * m, h + 2 * m, f"{INTRO['greeting']}. {INTRO['role']}.")
    card_frame(c, m, m, w, h, 24, t)
    x0, y0 = m + pad, m + pad
    tx = x0
    if AVATAR.exists():
        cx, cy, r = x0 + av / 2, y0 + av / 2, av / 2
        c.defs.append(f'<clipPath id="avatar"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>')
        c.image(x0, y0, av, av, AVATAR.read_bytes(), "image/png", clip=' clip-path="url(#avatar)"')
        tx = x0 + av + gap_x
    mid = y0 + av / 2
    c.text(tx, mid - 14, INTRO["greeting"], DISPLAY, 44, t["ink"], tracking=-.015)
    c.text(tx, mid + 26, INTRO["role"], SANS_500, 18, t["role"])
    x, y = x0, y0 + av + gap_y
    for label, family, refs in INTRO["chips"]:
        x += chip(c, x, y, label, family, refs, t) + 8
    return c


def cert_card(cert: dict, t: dict) -> Canvas:
    pad, media, glyph = 24, 56, 14
    img = badge_image(cert["slug"], tuple(cert["badges"]))
    tx = pad + (media + 16 if img else 0)
    lines = [(cert["title"], SANS_600, 16, t["ink"], None),
             (cert["issuer"], SANS_400, 13, t["muted"], cert["icon"]),
             ("Ver credencial", SANS_600, 13, t["accent"], None)][: 3 if cert["url"] else 2]
    text_w = max(text_width(f, s, z) + (glyph + 6 if ic else 0) for s, f, z, _, ic in lines)
    H = 2 * pad + 22 * (len(lines) - 1) + 16
    c = Canvas(tx + text_w + pad, H, f"{cert['title']}, {cert['issuer']}")
    card_frame(c, 0, 0, c.w, H, 16, dict(t, shadow=None))
    if img:
        c.image(pad, (H - media) / 2, media, media, *img)
    for i, (s, face, size, color, ic) in enumerate(lines):
        cy, x = pad + 8 + i * 22, tx
        if ic:
            c.icon(ic, x, cy - glyph / 2, glyph, color)
            x += glyph + 6
        c.text(x, cy, s, face, size, color)
    return c


def slug(s: str) -> str:
    return re.sub(r"-+", "-", "".join(ch if ch.isalnum() else "-" for ch in
                                      s.lower().translate(str.maketrans("áéíóúñ", "aeioun")))).strip("-")


def picture(stem: str, alt: str) -> str:
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.svg">'
            f'<img src="assets/{stem}-light.svg" alt={quoteattr(alt)}></picture>')


def linked(url: str | None, html: str) -> str:
    return f'<a href="{url}">{html}</a>' if url else html


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    for old in ASSETS.glob("*.svg"):
        if old.name.startswith(("header-", "intro-", "contact-", "stack-", "cert-")):
            old.unlink()
    for theme, t in THEMES.items():
        intro(t).save(ASSETS / f"intro-{theme}.svg")
        for label, _, refs in CONTACT:
            button(label, refs, label == CONTACT[0][0], t).save(ASSETS / f"contact-{slug(label)}-{theme}.svg")
        for title, family, items in STACK:
            chip_row(items, family, t).save(ASSETS / f"stack-{slug(title)}-{theme}.svg")
        for cert in CERTS:
            cert_card(cert, t).save(ASSETS / f"cert-{cert['slug']}-{theme}.svg")

    contact = "\n".join(linked(url, picture(f"contact-{slug(label)}", label)) for label, url, _ in CONTACT)
    projects = "" if not PROJECTS else "## Proyectos destacados\n\n" + "\n".join(
        f"- **{f'[{name}]({url})' if url else name}**. {desc}" for name, url, desc in PROJECTS) + "\n\n"
    stack = "\n\n".join(f"**{title}**<br>\n{picture(f'stack-{slug(title)}', ', '.join(l for l, _ in items))}"
                        for title, _, items in STACK)
    certs = "\n".join(linked(c["url"], picture(f"cert-{c['slug']}", f"{c['title']}, {c['issuer']}")) for c in CERTS)
    intro_alt = f"{INTRO['avatar_alt']}. {INTRO['greeting']}. {INTRO['role']}."
    (ROOT / "README.md").write_text(f"""{picture("intro", intro_alt)}

{INTRO["body"]}

<p>
{contact}
</p>

{projects}## Stack y herramientas

{stack}

## Certificaciones

<p>
{certs}
</p>
""", encoding="utf-8")


if __name__ == "__main__":
    main()
