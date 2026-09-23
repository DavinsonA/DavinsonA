#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import math
import random
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
LOGO = ASSETS / "da-logo.svg"
SOURCES = {
    "font": "https://raw.githubusercontent.com/google/fonts/main/ofl/{}",
    "si": "https://cdn.jsdelivr.net/npm/simple-icons@16.32.0/icons/{}.svg",
    "lu": "https://cdn.jsdelivr.net/npm/lucide-static@1.47.0/icons/{}.svg",
}

try:
    import brotli  # noqa: F401
    FLAVOR = "woff2"
except ImportError:
    FLAVOR = "woff"

ABYSS = "#043f52"
PASTEL = dict(mint="#9ce0d9", sky="#a1dafc", lavender="#d4c8fe", rose="#fabdd3", peach="#fac3a5", butter="#f6e5a4")
THEMES = {
    "dark": dict(bg="#0e2024", surface="#152a2f", raised="#1e343a", line="#26434a", line_strong="#5a8990",
                 dot="#1d383e", ink="#e6f2f1", muted="#a2bfc2", accent="#a1dafc", overline=PASTEL["mint"],
                 logo=PASTEL["mint"]),
    "light": dict(bg="#f4fcfb", surface="#ffffff", raised="#eef8f7", line="#d6e8e6", line_strong="#678a90",
                  dot="#cfe6e3", ink=ABYSS, muted="#4a6a72", accent="#005477", overline="#4a6a72", logo=ABYSS),
}

PROFILE = dict(
    greeting="Hola, soy Davinson",
    title="Data Scientist · AI Engineer",
    tagline="Cali, Colombia · MSc Data Science, Universidad ICESI",
    pillars=[("Analítica y BI", "peach", "lu:chart-column"),
             ("Estadística y machine learning", "butter", "lu:sigma"),
             ("IA generativa y agentes", "lavender", "lu:bot")],
)
ABOUT = [
    "Estadístico de la Universidad del Valle y estudiante de la Maestría en Ciencia de Datos en ICESI.",
    "Trabajo con análisis de datos, modelos de machine learning y agentes de IA.",
    "Abierto a roles de Data Analyst, Data Scientist o AI Engineer.",
]
PROJECTS: list[tuple[str, str | None, str]] = []
STACK = [
    ("Lenguajes", "mint", [("Python", "si:python"), ("SQL", "lu:database"), ("R", "si:r")]),
    ("IA generativa", "lavender", [("MCP", "si:modelcontextprotocol"), ("Ollama", "si:ollama"), ("n8n", "si:n8n"),
                                   ("FAISS", "lu:scan-search"), ("ChromaDB", "lu:database-zap")]),
    ("Machine learning", "lavender", [("PyTorch", "si:pytorch"), ("scikit-learn", "si:scikitlearn"),
                                      ("XGBoost", "lu:trees"), ("Optuna", "si:optuna")]),
    ("Datos e integración", "sky", [("PostgreSQL", "si:postgresql"), ("BigQuery", "si:googlebigquery"),
                                    ("NetSuite", "lu:building-2"), ("Salesforce", "lu:users"), ("pandas", "si:pandas")]),
    ("BI y visualización", "peach", [("Power BI", "lu:chart-column"), ("Tableau", "lu:chart-area"),
                                     ("Looker Studio", "lu:chart-pie"), ("Plotly", "si:plotly")]),
    ("Infraestructura", None, [("Docker", "si:docker"), ("Git", "si:git"), ("Linux", "si:linux")]),
]
CERTS = [
    dict(slug="dp-900", title="Azure Data Fundamentals", issuer="Microsoft · DP-900",
         url="https://www.credly.com/badges/dd83bed0-88a8-4cc8-bdea-702b794d8e25/public_url",
         badge="https://images.credly.com/size/110x110/images/70eb1e3f-d4de-4377-a062-b20fb29594ea/"
               "azure-data-fundamentals-600x600.png",
         icon="si:credly", pastel="sky"),
    dict(slug="hackerrank-sql", title="SQL (Advanced)", issuer="HackerRank", url=None, badge=None,
         icon="si:hackerrank", pastel="mint"),
]
CONTACT = [
    ("Escribir un correo", "mailto:arteagadavinson@gmail.com", "lu:mail"),
    ("Ver LinkedIn", "https://linkedin.com/in/davinson-arteaga", "si:linkedin|lu:briefcase-business"),
    ("Abrir WhatsApp", "https://wa.me/573157032101", "si:whatsapp"),
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


PLEX = "ibmplexsans/IBMPlexSans[wdth,wght].ttf"
DISPLAY = Face("Space Grotesk", "spacegrotesk/SpaceGrotesk[wght].ttf", 600, "'IBM Plex Sans', system-ui, sans-serif")
SANS_400 = Face("IBM Plex Sans", PLEX, 400, "'Segoe UI', Helvetica, Arial, sans-serif")
SANS_600 = Face("IBM Plex Sans", PLEX, 600, "'Segoe UI', Helvetica, Arial, sans-serif")
MONO_500 = Face("IBM Plex Mono", "ibmplexmono/IBMPlexMono-Medium.ttf", 500, "ui-monospace, Menlo, Consolas, monospace")
SVG_ROOT = re.compile(r"<svg\b([^>]*)>(.*)</svg>", re.S)


def fetch(url: str) -> bytes:
    path = CACHE / hashlib.sha1(url.encode()).hexdigest()[:16]
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "build-profile"})
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


@lru_cache
def badge_image(url: str | None) -> tuple[bytes, str] | None:
    if not url:
        return None
    try:
        data = fetch(url)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"aviso: sin insignia {url} ({exc}); se usa el icono", file=sys.stderr)
        return None
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg" if data.startswith(b"\xff\xd8") else None
    return (data, mime) if mime else None


class Canvas:
    def __init__(self, width: float, height: float, label: str):
        self.w, self.h, self.label = math.ceil(width), math.ceil(height), label
        self.defs: list[str] = []
        self.body: list[str] = []
        self.glyphs: dict[Face, str] = defaultdict(str)

    def add(self, svg: str) -> None:
        self.body.append(svg)

    def text(self, x: float, cy: float, s: str, face: Face, size: float, fill: str,
             anchor: str = "start", tracking: float = 0.0) -> None:
        self.glyphs[face] += s
        _, _, upm, cap = metrics(face)
        ls = f' letter-spacing="{tracking * size:.2f}"' if tracking else ""
        self.add(f'<text x="{x:.1f}" y="{cy + cap * size / upm / 2:.1f}" font-family="{face.css_family}" '
                 f'font-weight="{face.weight}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{ls}>{escape(s)}</text>')

    def icon(self, refs: str, x: float, y: float, size: float, color: str) -> None:
        vb, stroked, inner = icon(refs)
        paint = ('fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
                 if stroked else 'fill="currentColor"')
        self.add(f'<g color="{color}" {paint} transform="translate({x:.2f} {y:.2f}) '
                 f'scale({size / max(vb[2], vb[3]):.4f}) translate({-vb[0]:g} {-vb[1]:g})">{inner}</g>')

    def pill(self, x: float, y: float, label: str, face: Face, size: float, pad: float, height: float,
             fill: str, ink: str, refs: str | None = None, icon_size: float = 0, gap: float = 0,
             stroke: str | None = None) -> float:
        w = pill_width(label, face, size, pad, refs, icon_size, gap)
        inset = 0.75 if stroke else 0
        border = f' stroke="{stroke}" stroke-width="1.5"' if stroke else ""
        self.add(f'<rect x="{x + inset:.1f}" y="{y + inset:.1f}" width="{w - 2 * inset:.1f}" '
                 f'height="{height - 2 * inset:.1f}" rx="{height / 2 - inset:.1f}" fill="{fill}"{border}/>')
        tx = x + pad
        if refs:
            self.icon(refs, tx, y + (height - icon_size) / 2, icon_size, ink)
            tx += icon_size + gap
        self.text(tx, y + height / 2, label, face, size, ink)
        return w

    def save(self, path: Path) -> None:
        css = "".join(font_face(f, t) for f, t in self.glyphs.items())
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
            f'role="img" aria-label={quoteattr(self.label)}><title>{escape(self.label)}</title>'
            f'<style>{css}</style><defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>',
            encoding="utf-8",
        )


def pill_width(label: str, face: Face, size: float, pad: float, refs: str | None, icon_size: float, gap: float) -> float:
    return text_width(face, label, size) + 2 * pad + (icon_size + gap if refs else 0)


CHIP = dict(face=MONO_500, size=13, pad=12, icon_size=14, gap=6)


def chip_row(items: list[tuple[str, str]], pastel: str | None, t: dict, height: float = 30, spacing: float = 8) -> Canvas:
    widths = [pill_width(label, refs=refs, **CHIP) for label, refs in items]
    c = Canvas(sum(widths) + spacing * (len(items) - 1), height, ", ".join(label for label, _ in items))
    x = 0.0
    for label, refs in items:
        x += c.pill(x, 0, label, fill=PASTEL[pastel] if pastel else t["raised"],
                    ink=ABYSS if pastel else t["ink"], refs=refs, height=height, **CHIP) + spacing
    return c


def button(label: str, refs: str, primary: bool, t: dict) -> Canvas:
    spec = dict(face=SANS_600, size=14, pad=24, icon_size=16, gap=8)
    c = Canvas(pill_width(label, refs=refs, **spec), 42, label)
    if primary:
        c.pill(0, 0, label, fill=PASTEL["mint"], ink=ABYSS, refs=refs, height=42, **spec)
    else:
        c.pill(0, 0, label, fill="none", ink=t["ink"], refs=refs, height=42, stroke=t["line_strong"], **spec)
    return c


def cert_lines(cert: dict) -> list[tuple[str, Face, float, str]]:
    lines = [(cert["title"], SANS_600, 16, "ink"), (cert["issuer"], SANS_400, 13, "muted")]
    return lines + ([("Ver credencial →", SANS_600, 13, "accent")] if cert["url"] else [])


def cert_card(cert: dict, t: dict, width: float) -> Canvas:
    H, media, pad = 96, 56, 20
    c = Canvas(width, H, f"{cert['title']}, {cert['issuer']}")
    c.add(f'<rect x=".5" y=".5" width="{width - 1:.1f}" height="{H - 1}" rx="15.5" fill="{t["surface"]}" stroke="{t["line"]}"/>')
    if img := badge_image(cert["badge"]):
        data, mime = img
        c.add(f'<image x="{pad}" y="{pad}" width="{media}" height="{media}" '
              f'href="data:{mime};base64,{base64.b64encode(data).decode()}"/>')
    else:
        c.add(f'<circle cx="{pad + media / 2}" cy="{pad + media / 2}" r="{media / 2}" fill="{PASTEL[cert["pastel"]]}"/>')
        c.icon(cert["icon"], pad + media / 4, pad + media / 4, media / 2, ABYSS)
    lines = cert_lines(cert)
    top = H / 2 - (len(lines) - 1) * 11
    for i, (s, face, size, role) in enumerate(lines):
        c.text(pad + media + 16, top + i * 22, s, face, size, t[role])
    return c


def ridges(width: int, height: int, fill: str, seed: int = 7) -> str:
    rng, out = random.Random(seed), []
    for i, name in enumerate(["butter", "rose", "peach", "sky", "lavender", "mint"]):
        comps = [(rng.uniform(.05, .95) * width, rng.uniform(30, 110), rng.uniform(.4, 1)) for _ in range(3)]
        base, amp = height - 46 + i * 8, rng.uniform(36, 56)
        dens = [sum(w * math.exp(-((x - m) ** 2) / (2 * s * s)) for m, s, w in comps) for x in range(0, width + 8, 8)]
        peak = max(dens)
        pts = " ".join(f"{x * 8},{base - amp * d / peak:.1f}" for x, d in enumerate(dens))
        out.append(f'<polygon points="0,{height} {pts} {width},{height}" fill="{fill}"/>'
                   f'<polyline points="{pts}" fill="none" stroke="{PASTEL[name]}" stroke-width="2.5" stroke-linejoin="round"/>')
    return "".join(out)


def header(t: dict) -> Canvas:
    W, H, pad = 1280, 400, 64
    c = Canvas(W, H, f"{PROFILE['greeting']}. {PROFILE['title']}.")
    c.defs.append(f'<clipPath id="card"><rect width="{W}" height="{H}" rx="24"/></clipPath>'
                  f'<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
                  f'<circle cx="12" cy="12" r="1.5" fill="{t["dot"]}"/></pattern>')
    c.add(f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{t["bg"]}"/>'
          f'<rect width="{W}" height="{H}" fill="url(#dots)"/>{ridges(W, H, t["bg"])}</g>'
          f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="23.5" fill="none" stroke="{t["line"]}"/>')
    tx = pad
    if LOGO.exists():
        vb, _, inner = parse_svg(LOGO.read_text("utf-8"))
        lh = 208
        lw = lh * vb[2] / vb[3]
        c.add(f'<svg x="{pad}" y="64" width="{lw:.1f}" height="{lh}" viewBox="{" ".join(f"{v:g}" for v in vb)}" '
              f'color="{t["logo"]}" overflow="visible">{inner}</svg>')
        tx = pad + lw + 48
    c.text(tx, 84, PROFILE["title"].upper(), MONO_500, 20, t["overline"], tracking=.1)
    c.text(tx, 148, PROFILE["greeting"], DISPLAY, 72, t["ink"], tracking=-.02)
    c.text(tx, 204, PROFILE["tagline"], SANS_400, 20, t["muted"])
    x = tx
    for label, pastel, refs in PROFILE["pillars"]:
        x += c.pill(x, 232, label, MONO_500, 18, 16, 44, PASTEL[pastel], ABYSS, refs=refs, icon_size=20, gap=8) + 12
    return c


def slug(s: str) -> str:
    return re.sub(r"-+", "-", "".join(ch if ch.isalnum() else "-" for ch in
                                      s.lower().translate(str.maketrans("áéíóúñ", "aeioun")))).strip("-")


def picture(stem: str, alt: str, width: str | None = None) -> str:
    w = f' width="{width}"' if width else ""
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.svg">'
            f'<img src="assets/{stem}-light.svg" alt={quoteattr(alt)}{w}></picture>')


def linked(url: str | None, html: str) -> str:
    return f'<a href="{url}">{html}</a>' if url else html


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    card_w = max(20 + 56 + 16 + max(text_width(f, s, z) for s, f, z, _ in cert_lines(cert)) + 24 for cert in CERTS)
    for theme, t in THEMES.items():
        header(t).save(ASSETS / f"header-{theme}.svg")
        for title, pastel, items in STACK:
            chip_row(items, pastel, t).save(ASSETS / f"stack-{slug(title)}-{theme}.svg")
        for cert in CERTS:
            cert_card(cert, t, card_w).save(ASSETS / f"cert-{cert['slug']}-{theme}.svg")
        for i, (label, _, refs) in enumerate(CONTACT):
            button(label, refs, i == 0, t).save(ASSETS / f"contact-{slug(label)}-{theme}.svg")

    about = "\n".join(f"- {line}" for line in ABOUT)
    projects = "" if not PROJECTS else "## Proyectos destacados\n\n" + "\n".join(f"- **{f'[{name}]({url})' if url else name}**. {desc}" for name, url, desc in PROJECTS) + "\n\n"
    stack = "\n\n".join(f"**{title}**<br>\n{picture(f'stack-{slug(title)}', ', '.join(l for l, _ in items))}"
                        for title, _, items in STACK)
    certs = "\n".join(linked(c["url"], picture(f"cert-{c['slug']}", f"{c['title']}, {c['issuer']}")) for c in CERTS)
    contact = "\n".join(linked(url, picture(f"contact-{slug(label)}", label)) for label, url, _ in CONTACT)
    (ROOT / "README.md").write_text(f"""{picture("header", f"{PROFILE['greeting']}. {PROFILE['title']}.", "100%")}

## Sobre mí

{about}

{projects}## Stack y herramientas

{stack}

## Certificaciones

<p>
{certs}
</p>

## Contacto

<p>
{contact}
</p>
""", encoding="utf-8")


if __name__ == "__main__":
    main()
