# Rezepte — Familien-Rezeptsammlung Becker-Staudt

Persönliches Rezept-System (à la ReCiMe): Rezepte importieren (Links, Fotos, eigene),
durchsuchbare Rezeptbuch-Seite, Wochenpläne und Einkaufslisten per E-Mail.

Das komplette Regelwerk (Formate, Workflows) liegt im Projekt-Skill:
`.claude/skills/private-recipes/SKILL.md`

## Struktur

| Pfad | Inhalt |
|---|---|
| `sammlung/` | Ein Markdown-File pro Rezept (Format siehe Skill) |
| `wochenplaene/` | Wochenpläne, eine Datei pro Woche (`2026-W29.md`) |
| `einkaufslisten/` | Generierte Einkaufslisten, eine Datei pro Woche |
| `build_rezeptbuch.py` | Baut aus `sammlung/` + aktuellem Wochenplan die HTML-Seite |
| `rezeptbuch_template.html` | HTML-Vorlage (Design der Rezeptbuch-Seite) |
| `rezeptbuch.html` | Generiert — nicht von Hand bearbeiten |

## Rezeptbuch-Seite

Wird als privates Artifact auf claude.ai veröffentlicht — auf jedem Gerät abrufbar
(Handy-Lesezeichen!). Nach Änderungen an der Sammlung:

```bash
python3 build_rezeptbuch.py
```

…und die Seite unter **derselben URL** neu veröffentlichen (URL steht im Skill).
