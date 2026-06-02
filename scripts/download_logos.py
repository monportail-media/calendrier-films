#!/usr/bin/env python3
"""
Script de creation des logos SVG locaux pour les plateformes.
A executer UNE SEULE FOIS depuis GitHub Actions ou en local.
Cree le dossier assets/logos/ avec tous les logos SVG.
"""
import os
from pathlib import Path

LOGOS = {
    "netflix":    ('#e50914', 'white', 'NETFLIX',    18),
    "prime":      ('#00a8e0', 'white', 'PRIME',       16),
    "disney":     ('#1a3eb5', 'white', 'DISNEY+',     14),
    "apple":      ('#000000', 'white', 'APPLE TV+',   12),
    "max":        ('#002be7', 'white', 'MAX',          20),
    "hulu":       ('#1ce783', '#000',  'HULU',         18),
    "paramount":  ('#0064ff', 'white', 'PARAMOUNT+',  10),
    "peacock":    ('#000000', 'white', 'PEACOCK',      14),
    "crave":      ('#a855f7', 'white', 'CRAVE',        18),
    "toutv":      ('#cc0000', 'white', 'ICI TOU.TV',  11),
    "tva":        ('#e11d48', 'white', 'TVA+',         20),
    "noovo":      ('#e11d48', 'white', 'NOOVO',        16),
    "telequebec": ('#10b981', 'white', 'TÉLÉ-QC',     13),
    "illico":     ('#f97316', 'white', 'ILLICO+',     14),
    "vrai":       ('#7c3aed', 'white', 'VRAI',         20),
    "historia":   ('#854d0e', 'white', 'HISTORIA',    13),
    "seriesplus": ('#1e40af', 'white', 'SÉRIES+',     13),
    "artv":       ('#374151', 'white', 'ARTV',         18),
    "tv5":        ('#1d4ed8', 'white', 'TV5',          20),
    "unis":       ('#0f766e', 'white', 'UNIS',         18),
    "onf":        ('#dc2626', 'white', 'ONF',          20),
    "cinema":     ('#4b5563', 'white', '🎬',           22),
    "default":    ('#374151', 'white', '📺',           22),
}

out = Path("assets/logos")
out.mkdir(parents=True, exist_ok=True)

for name, (bg, fg, label, size) in LOGOS.items():
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40">
  <rect width="100" height="40" fill="{bg}" rx="5"/>
  <text y="27" x="50" text-anchor="middle" font-size="{size}"
        font-weight="bold" font-family="system-ui,Arial,sans-serif"
        fill="{fg}">{label}</text>
</svg>'''
    path = out / f"{name}.svg"
    path.write_text(svg, encoding="utf-8")
    print(f"OK {name}.svg")

print(f"\n{len(LOGOS)} logos SVG crees dans assets/logos/")
