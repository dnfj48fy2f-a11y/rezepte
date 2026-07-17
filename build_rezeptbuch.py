#!/usr/bin/env python3
"""Baut rezeptbuch.html aus sammlung/*.md, dem neuesten Wochenplan und dem Template.

Aufruf:  python3 build_rezeptbuch.py   (im Ordner ~/Claude/rezepte)
Keine Abhängigkeiten außer der Standardbibliothek.
"""
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

BASIS = Path(__file__).parent
TEMPLATE = BASIS / "rezeptbuch_template.html"
AUSGABE = BASIS / "rezeptbuch.html"

KATEGORIEN = {"fruehstueck", "vorspeise", "suppe", "salat", "hauptgericht",
              "beilage", "dessert", "backen", "getraenk", "snack", "grundrezept"}


def parse_frontmatter(text: str):
    m = re.match(r"\A---\n(.*?)\n---\n?(.*)\Z", text, re.DOTALL)
    if not m:
        return {}, text
    meta = {}
    for zeile in m.group(1).splitlines():
        if ":" not in zeile:
            continue
        key, _, wert = zeile.partition(":")
        key, wert = key.strip(), wert.strip()
        if not wert:
            meta[key] = None
        elif wert.startswith("[") and wert.endswith("]"):
            meta[key] = [t.strip() for t in wert[1:-1].split(",") if t.strip()]
        else:
            meta[key] = wert
    return meta, m.group(2)


def split_sections(body: str, ebene: str):
    """Zerlegt Markdown in {überschrift(kleingeschrieben): text} auf einer Heading-Ebene."""
    pattern = rf"^{ebene}\s+(.+?)\s*$"
    sections, aktuell, name = {}, [], None
    for zeile in body.splitlines():
        m = re.match(pattern, zeile)
        if m:
            if name is not None:
                sections[name] = "\n".join(aktuell).strip()
            name, aktuell = m.group(1).strip().lower(), []
        elif name is not None:
            aktuell.append(zeile)
    if name is not None:
        sections[name] = "\n".join(aktuell).strip()
    return sections


def als_liste(text: str):
    """Listenzeilen (- / 1.) als Strings; **Gruppen**-Zeilen bleiben erhalten."""
    zeilen = []
    for z in (text or "").splitlines():
        z = z.strip()
        if not z:
            continue
        m = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)$", z)
        zeilen.append(m.group(1) if m else z)
    return zeilen


def foto_data_uri(foto_pfad: str, name: str):
    """Verkleinert das Foto (max. 640 px, JPEG) via sips und liefert eine data:-URI.

    Artifacts erlauben keine externen Bild-URLs (CSP), daher werden Fotos eingebettet.
    """
    quelle = BASIS / foto_pfad
    if not quelle.exists():
        print(f"WARNUNG: {name}: Foto fehlt: {foto_pfad}", file=sys.stderr)
        return None
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_pfad = Path(tmp.name)
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "45",
             "-Z", "520", str(quelle), "--out", str(tmp_pfad)],
            check=True, capture_output=True)
        daten = tmp_pfad.read_bytes()
    except subprocess.CalledProcessError as e:
        print(f"WARNUNG: {name}: Foto nicht konvertierbar ({e.stderr.decode(errors='replace').strip()})",
              file=sys.stderr)
        return None
    finally:
        tmp_pfad.unlink(missing_ok=True)
    return "data:image/jpeg;base64," + base64.b64encode(daten).decode()


def parse_rezept(pfad: Path):
    meta, body = parse_frontmatter(pfad.read_text(encoding="utf-8"))
    sec = split_sections(body, "##")

    en = {}
    if "english" in sec:
        en_sec = split_sections(sec["english"], "###")
        en = {
            "zutaten": als_liste(en_sec.get("ingredients", "")),
            "zubereitung": als_liste(en_sec.get("instructions", "")),
            "notizen": en_sec.get("notes", "") or None,
        }

    kategorie = (meta.get("kategorie") or "hauptgericht").lower()
    if kategorie not in KATEGORIEN:
        print(f"WARNUNG: {pfad.name}: unbekannte Kategorie '{kategorie}'", file=sys.stderr)

    portionen = meta.get("portionen")
    try:
        portionen = float(str(portionen).replace(",", ".")) if portionen else None
        if portionen and portionen == int(portionen):
            portionen = int(portionen)
    except ValueError:
        portionen = None

    bewertung = meta.get("bewertung")
    bewertung = int(bewertung) if bewertung and str(bewertung).isdigit() else None

    return {
        "id": pfad.stem,
        "titel": meta.get("titel") or pfad.stem,
        "title_en": meta.get("title_en"),
        "kategorie": kategorie,
        "tags": meta.get("tags") or [],
        "portionen": portionen,
        "zeit_aktiv": meta.get("zeit_aktiv"),
        "zeit_gesamt": meta.get("zeit_gesamt"),
        "quelle": meta.get("quelle"),
        "sprache_original": meta.get("sprache_original") or "de",
        "hinzugefuegt": meta.get("hinzugefuegt"),
        "bewertung": bewertung,
        "foto": foto_data_uri(meta["foto"], pfad.name) if meta.get("foto") else None,
        "zutaten": als_liste(sec.get("zutaten", "")),
        "zubereitung": als_liste(sec.get("zubereitung", "")),
        "notizen": sec.get("notizen") or None,
        "en": en,
    }


def parse_wochenplan(rezept_ids):
    plaene = sorted((BASIS / "wochenplaene").glob("*.md"))
    if not plaene:
        return None
    pfad = plaene[-1]
    meta, body = parse_frontmatter(pfad.read_text(encoding="utf-8"))
    eintraege = []
    for z in als_liste(body):
        if ":" not in z:
            continue
        tag, _, rest = z.partition(":")
        rest, _, notiz = rest.partition("|")
        rest, notiz = rest.strip(), notiz.strip()
        eintrag = {"tag": tag.strip(), "notiz": notiz or None}
        if rest in rezept_ids:
            eintrag["rezept_id"] = rest
        else:
            eintrag["text"] = rest
        eintraege.append(eintrag)
    return {"woche": meta.get("woche") or pfad.stem, "von": meta.get("von"),
            "bis": meta.get("bis"), "eintraege": eintraege}


def main():
    rezepte = [parse_rezept(p) for p in sorted((BASIS / "sammlung").glob("*.md"))]
    rezepte.sort(key=lambda r: r["titel"].lower())
    daten = {
        "generiert": date.today().isoformat(),
        "rezepte": rezepte,
        "wochenplan": parse_wochenplan({r["id"] for r in rezepte}),
    }
    js = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA_JSON__", js)
    AUSGABE.write_text(html, encoding="utf-8")
    plan = daten["wochenplan"]
    print(f"OK: {len(rezepte)} Rezepte, Wochenplan: {plan['woche'] if plan else '—'} → {AUSGABE.name}")

    # Offline-Kopie für alle Geräte (Dateien-App auf iPhone/iPad)
    icloud = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Rezeptbuch.html"
    if icloud.parent.is_dir():
        shutil.copyfile(AUSGABE, icloud)
        print(f"Offline-Kopie: {icloud}")


if __name__ == "__main__":
    main()
