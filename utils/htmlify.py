#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transformă un raport text (.txt) într-un HTML compatibil cu formatul WarEra.

Botul folosește `convert` pentru articolele guvernului (cogs/tasks/gov_rankings.py), postate ca .html.
Utilizare din linia de comandă:
    python utils/htmlify.py ro2026-11-08.txt
    python utils/htmlify.py ro2026-11-08.txt -o raport-generat.html
"""

from pathlib import Path
import argparse
import html
import json
import re

LOGO_URL = "https://i.imgur.com/RAALj4G.png"
TITLE = "Raport săptămânal România"

URL_RE = re.compile(r"https?://[^\s<>]+")
SECTION_RE = re.compile(r"^\W*\S.*$")


def warera_element(url: str) -> str:
    """Generează elementul special folosit de WarEra pentru profiluri și MU-uri."""
    match = re.fullmatch(r"https://app\.warera\.io/(user|mu)/([A-Za-z0-9]+)", url.rstrip(".,;"))
    if not match:
        return f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>'

    kind, item_id = match.groups()
    data_key = "userId" if kind == "user" else "muId"
    data = {data_key: item_id, "fullMatch": url.rstrip(".,;")}
    encoded_data = html.escape(json.dumps(data, ensure_ascii=False, separators=(",", ":")), quote=True)
    original = html.escape(url.rstrip(".,;"), quote=True)
    return (
        f'<span data-content-link="" data-content-type="{kind}" '
        f'data-content-data="{encoded_data}" data-original-text="{original}"></span>'
    )


def inline(text: str) -> str:
    """Păstrează URL-urile originale și escapează doar caracterele HTML."""
    return html.escape(text, quote=False)


def is_section_heading(line: str) -> bool:
    """Spune dacă `line` e titlul unei secțiuni: scurt (sub 65 de caractere), fără „-” și fără literă/cifră la început."""
    # În raportul sursă, secțiunile principale încep cu un emoji.
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("-") and len(stripped) < 65 and (
        stripped[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    )


def convert(text: str) -> str:
    """Întoarce documentul HTML al raportului `text`, între două logo-uri.

    Primul rând nevid devine titlul (h2), după avertismentele „[ATENȚIE…”, care rămân paragrafe; rândurile scurte care nu încep cu literă sau cifră devin secțiuni (hr + h2),
    „- Level …” subtitluri (h3), celelalte rânduri „- ” elemente de listă, iar restul paragrafe.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output = [
        "<!DOCTYPE html>",
        '<html lang="ro">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{html.escape(TITLE)}</title>",
        "</head>",
        "<body>",
        f'<p><img src="{LOGO_URL}" alt="România"></p>',
    ]

    list_open = False
    title_done = False

    def close_list():
        nonlocal list_open
        if list_open:
            output.append("</ul>")
            list_open = False

    for raw in lines:
        line = raw.strip()

        if not line:
            close_list()
            continue

        # Primul rând este titlul raportului; avertismentele botului („[ATENȚIE, ștergeți înainte de publicare: …]”)
        # stau deasupra lui și rămân paragrafe, ca titlul să nu ajungă secțiune după ștergerea lor.
        if not title_done:
            close_list()
            if line.startswith("[ATENȚIE"):
                output.append(f"<p>{inline(line)}</p>")
            else:
                output.append(f"<h2>{inline(line)}</h2>")
                title_done = True
            continue

        # Secțiuni principale: Damage, Donații, Top Unități etc.
        if is_section_heading(line):
            close_list()
            output.append(f"<hr><h2>{inline(line)}</h2>")
            continue

        # Categorii precum „Level 6-15 [Wannabes]”.
        if line.startswith("- Level "):
            close_list()
            category = line[2:].rstrip(":")
            output.append(f"<h3>{inline(category)}</h3>")
            continue

        # Liste cu jucători / unități.
        if line.startswith("- "):
            if not list_open:
                output.append("<ul>")
                list_open = True
            output.append(f"<li>{inline(line[2:])}</li>")
            continue

        close_list()

        # Rânduri descriptive sau subtitluri explicative.
        if line.endswith(":"):
            output.append(f"<p><strong>{inline(line)}</strong></p>")
        elif line.startswith("Top ") or line.startswith("Unitățile "):
            output.append(f"<p><strong>{inline(line)}</strong></p>")
        elif line.startswith("Cu apreciere,"):
            # semnătura botului are guvernul pe același rând ("Cu apreciere, Guvernul României 🇷🇴"); nu-l dublăm
            signer = line[len("Cu apreciere,"):].strip() or "Guvernul României 🇷🇴"
            output.append(f"<p>Cu apreciere,<br>{inline(signer)}</p>")
        else:
            output.append(f"<p>{inline(line)}</p>")

    close_list()

    output.extend([
        "<hr>",
        f'<p><img src="{LOGO_URL}" alt="România"></p>',
        "</body>",
        "</html>",
    ])
    return "\n".join(output) + "\n"


def main():
    """Convertește fișierul .txt dat în linia de comandă și scrie HTML-ul lângă el (sau în --output)."""
    parser = argparse.ArgumentParser(description="Transformă un fișier TXT într-un raport HTML.")
    parser.add_argument("input", help="Fișierul .txt sursă")
    parser.add_argument("-o", "--output", help="Fișierul HTML rezultat")
    args = parser.parse_args()

    source = Path(args.input)
    destination = Path(args.output) if args.output else source.with_suffix(".html")

    content = source.read_text(encoding="utf-8-sig")
    destination.write_text(convert(content), encoding="utf-8")
    print(f"HTML generat cu succes: {destination.resolve()}")


if __name__ == "__main__":
    main()