#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import math
import random
import struct
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
ASSETS, CACHE = ROOT / "assets", ROOT / ".fonts"
GOOGLE_FONTS = "https://raw.githubusercontent.com/google/fonts/main/ofl/"

try:
    import brotli  # noqa: F401
    FLAVOR = "woff2"
except ImportError:
    FLAVOR = "woff"

ABYSS = "#043f52"
PASTEL = dict(mint="#9ce0d9", sky="#a1dafc", lavender="#d4c8fe", rose="#fabdd3", peach="#fac3a5", butter="#f6e5a4")
THEMES = {
    "dark": dict(bg="#0e2024", raised="#1e343a", line="#26434a", line_strong="#5a8990", dot="#1d383e",
                 ink="#e6f2f1", overline=PASTEL["mint"], logo="da-logo-mint.png"),
    "light": dict(bg="#f4fcfb", raised="#eef8f7", line="#d6e8e6", line_strong="#678a90", dot="#cfe6e3",
                  ink=ABYSS, overline="#4a6a72", logo="da-logo-abyss.png"),
}

PROFILE = dict(
    greeting="Hola, soy Davinson",
    title="Data Scientist · AI Engineer",
    chips=[("Cali, Colombia", "mint"), ("MSc Data Science · ICESI", "sky")],
)
ABOUT = [
    "Estadístico de la Universidad del Valle; curso la Maestría en Ciencia de Datos en la Universidad ICESI.",
    "Construyo consultas SQL avanzadas, conciliaciones financieras y pipelines de reportes automatizados sobre NetSuite (SuiteQL).",
    "Desarrollo agentes de IA con tool use, MCP servers y RAG.",
    "Hago consultoría independiente en análisis estadístico, BI y visualización, y modelado.",
]
STACK = [
    ("Lenguajes", "mint", ["Python", "R", "SQL", "SAS"]),
    ("IA y machine learning", "lavender", ["PyTorch", "scikit-learn", "Optuna"]),
    ("Datos y plataformas", "sky", ["pandas", "NumPy", "PostgreSQL", "NetSuite"]),
    ("BI y visualización", "peach", ["Power BI", "Tableau", "Plotly"]),
    ("Infraestructura", None, ["Linux", "Docker", "Git"]),
]
CERTS = [
    ("Microsoft Certified: Azure Data Fundamentals (DP-900)",
     "https://www.credly.com/badges/dd83bed0-88a8-4cc8-bdea-702b794d8e25/public_url"),
    ("HackerRank: SQL (Advanced)", None),
]
CONTACT = [
    ("Escribir un correo", "mailto:arteagadavinson@gmail.com"),
    ("Ver LinkedIn", "https://linkedin.com/in/davinson-arteaga"),
    ("Abrir WhatsApp", "https://wa.me/573157032101"),
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


DISPLAY = Face("Space Grotesk", "spacegrotesk/SpaceGrotesk[wght].ttf", 600, "'IBM Plex Sans', system-ui, sans-serif")
SANS_600 = Face("IBM Plex Sans", "ibmplexsans/IBMPlexSans[wdth,wght].ttf", 600, "'Segoe UI', Helvetica, Arial, sans-serif")
MONO_500 = Face("IBM Plex Mono", "ibmplexmono/IBMPlexMono-Medium.ttf", 500, "ui-monospace, Menlo, Consolas, monospace")


@lru_cache
def instance_bytes(face: Face) -> bytes:
    path = CACHE / Path(face.source).name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        with urllib.request.urlopen(GOOGLE_FONTS + urllib.parse.quote(face.source), timeout=60) as r:
            path.write_bytes(r.read())
    font = TTFont(path)
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


def cap_offset(face: Face, size: float) -> float:
    _, _, upm, cap = metrics(face)
    return cap * size / upm / 2


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
    data = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'{face.family}';font-weight:{face.weight};"
            f"src:url(data:font/{FLAVOR};base64,{data}) format('{FLAVOR}')}}")


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
        ls = f' letter-spacing="{tracking * size:.2f}"' if tracking else ""
        self.add(f'<text x="{x:.1f}" y="{cy + cap_offset(face, size):.1f}" font-family="{face.css_family}" '
                 f'font-weight="{face.weight}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"{ls}>{escape(s)}</text>')

    def pill(self, x: float, y: float, s: str, face: Face, size: float, pad: float, height: float,
             fill: str, ink: str, stroke: str | None = None) -> float:
        w = text_width(face, s, size) + 2 * pad
        border = f' stroke="{stroke}" stroke-width="1.5"' if stroke else ""
        inset = 0.75 if stroke else 0
        self.add(f'<rect x="{x + inset:.1f}" y="{y + inset:.1f}" width="{w - 2 * inset:.1f}" height="{height - 2 * inset:.1f}" '
                 f'rx="{height / 2 - inset:.1f}" fill="{fill}"{border}/>')
        self.text(x + w / 2, y + height / 2, s, face, size, ink, anchor="middle")
        return w

    def save(self, path: Path) -> None:
        css = "".join(font_face(f, t) for f, t in self.glyphs.items())
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
            f'role="img" aria-label={quoteattr(self.label)}><title>{escape(self.label)}</title>'
            f'<style>{css}</style><defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>',
            encoding="utf-8",
        )


def chip_row(items: list[str], pastel: str | None, t: dict, size=13, pad=12, height=30, gap=8, face=MONO_500):
    widths = [text_width(face, s, size) + 2 * pad for s in items]
    c = Canvas(sum(widths) + gap * (len(items) - 1), height, ", ".join(items))
    x = 0.0
    for s in items:
        x += c.pill(x, 0, s, face, size, pad, height, PASTEL[pastel] if pastel else t["raised"],
                    ABYSS if pastel else t["ink"]) + gap
    return c


def button(label: str, primary: bool, t: dict):
    size, pad, height = 14, 24, 42
    c = Canvas(text_width(SANS_600, label, size) + 2 * pad, height, label)
    if primary:
        c.pill(0, 0, label, SANS_600, size, pad, height, PASTEL["mint"], ABYSS)
    else:
        c.pill(0, 0, label, SANS_600, size, pad, height, "none", t["ink"], stroke=t["line_strong"])
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
    W, H, pad = 1280, 360, 64
    c = Canvas(W, H, f"{PROFILE['greeting']}. {PROFILE['title']}.")
    c.defs.append(f'<clipPath id="card"><rect width="{W}" height="{H}" rx="24"/></clipPath>'
                  f'<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
                  f'<circle cx="12" cy="12" r="1.5" fill="{t["dot"]}"/></pattern>')
    c.add(f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{t["bg"]}"/>'
          f'<rect width="{W}" height="{H}" fill="url(#dots)"/>{ridges(W, H, t["bg"])}</g>'
          f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="23.5" fill="none" stroke="{t["line"]}"/>')
    tx, logo = pad, ASSETS / t["logo"]
    if logo.exists():
        png = logo.read_bytes()
        lw, lh = struct.unpack(">II", png[16:24])
        h = 150
        w = h * lw / lh
        c.add(f'<image x="{pad}" y="62" width="{w:.1f}" height="{h}" '
              f'href="data:image/png;base64,{base64.b64encode(png).decode()}"/>')
        tx = pad + w + 44
    c.text(tx, 84, PROFILE["title"].upper(), MONO_500, 20, t["overline"], tracking=.1)
    c.text(tx, 146, PROFILE["greeting"], DISPLAY, 72, t["ink"], tracking=-.02)
    x = tx
    for label, pastel in PROFILE["chips"]:
        x += c.pill(x, 196, label, MONO_500, 19, 18, 44, PASTEL[pastel], ABYSS) + 12
    return c


def slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in s.lower().translate(str.maketrans("áéíóú", "aeiou"))).strip("-")


def picture(stem: str, alt: str, width: str | None = None) -> str:
    w = f' width="{width}"' if width else ""
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.svg">'
            f'<img src="assets/{stem}-light.svg" alt={quoteattr(alt)}{w}></picture>')


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    for theme, t in THEMES.items():
        header(t).save(ASSETS / f"header-{theme}.svg")
        for title, pastel, items in STACK:
            chip_row(items, pastel, t).save(ASSETS / f"stack-{slug(title)}-{theme}.svg")
        for i, (label, _) in enumerate(CONTACT):
            button(label, i == 0, t).save(ASSETS / f"contact-{slug(label)}-{theme}.svg")

    certs = "\n".join(f"- [{n}]({u})" if u else f"- {n}" for n, u in CERTS)
    stack = "\n\n".join(f"**{title}**<br>\n{picture(f'stack-{slug(title)}', ', '.join(items))}" for title, _, items in STACK)
    contact = "\n".join(f'<a href="{u}">{picture(f"contact-{slug(label)}", label)}</a>' for label, u in CONTACT)
    readme = f"""{picture("header", f"{PROFILE['greeting']} — {PROFILE['title']}", "100%")}

## Sobre mí

{chr(10).join(f"- {line}" for line in ABOUT)}

## Stack y herramientas

{stack}

## Certificaciones

{certs}

## Contacto

<p>
{contact}
</p>
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
