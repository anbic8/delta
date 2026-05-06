# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Delta** – Web-App zur Verwaltung von Schülerleistungen am bayerischen Gymnasium (Single-User, lokal).
Stack: FastAPI · PostgreSQL 16 · SQLAlchemy 2 · Alembic · Jinja2/HTMX · Docker Compose.
Buildplan in `Buildplan.md` – verbindliche Phasenreihenfolge, aktueller Stand: Phasen 0–5 fertig (MVP).

## Commands

```bash
# Container starten / stoppen
docker compose up -d --build
docker compose down

# Tests (laufen in SQLite, kein laufender Container nötig)
docker compose exec app pytest
docker compose exec app pytest tests/test_notenberechnung.py   # einzelne Datei
docker compose exec app pytest -k "test_schnitt"               # einzelner Test per Name

# Coverage
docker compose exec app pytest --cov=app --cov-report=term-missing

# Migrationen
docker compose exec app alembic upgrade head
docker compose exec app alembic revision --autogenerate -m "beschreibung"
docker compose exec app alembic current
```

Die App läuft unter `http://<VM-IP>:8045/`. UI-Einstiegspunkt: `/ui/schuljahre`.

## Architecture

### Layer-Aufteilung

```
app/
├── models/          SQLAlchemy ORM-Modelle (eine Datei pro Entität)
├── schemas/         Pydantic-Schemas für API (Create/Read/Update)
├── routers/         FastAPI-Router – API (JSON) und UI (HTML)
│   └── ui.py        Alle Jinja2-UI-Routen unter /ui/
├── services/        Berechnungslogik ohne HTTP-Abhängigkeit
│   ├── notenberechnung.py   Abiturschlüssel, Grenzfall-Erkennung
│   ├── notenschnitt.py      Schnitt-Aggregation mit erweiterbaren Quellen
│   └── kompetenzprofil.py   K1–K6 Profil-Aggregation
├── templates_config.py      Jinja2Templates-Singleton
└── main.py          App-Einstieg, Router-Registrierung, StaticFiles
templates/           Jinja2-Templates für die UI
migrations/versions/ Alembic-Migrationen (manuell geschrieben, kein autogenerate im Einsatz)
```

### Datenmodell-Hierarchie

```
Schuljahr → Klasse → Schüler
                  ↓
           SchriftlicheLeistung (art: schulaufgabe | kleiner_ln, detailliert: bool)
                  ↓
           LeistungAufgabe (M:N zu Aufgabe aus globalem Pool)
                  ↓
           SchuelerErgebnis (Variante A: erreichte_punkte per LeistungAufgabe;
                              Variante B: pauschalnote per SchriftlicheLeistung)

Aufgabe ←→ Kompetenz (via AufgabeKompetenz mit Gewichtung, Summe = 1.0 pro Aufgabe)
Schüler → MuendlicheNote (Soft-Delete via geloescht_am)
```

**Invarianten:**
- `Klasse.notensystem` wird automatisch aus `jahrgangsstufe` abgeleitet (5–11 → Sechserskala, 12–13 → Punkte) und ist danach unveränderlich.
- `SchriftlicheLeistung` mit `art=schulaufgabe` hat immer `detailliert=True`.
- `detailliert`-Flag ist nach der ersten Noteneintragung faktisch gesperrt (kein Endpoint zum Ändern).

### Notenberechnung

Bayerischer Abiturschlüssel (fest in `services/notenberechnung.py`):
≥85% → 1, ≥70% → 2, ≥55% → 3, ≥40% → 4, ≥20% → 5, <20% → 6.

**Schnittformel:**
- Schnitt kleine LN = gewichteter Ø aus **allen** `kleiner_ln`-Ergebnissen **plus** mündlichen Noten (gemeinsamer Pool)
- Schnitt große LN = gewichteter Ø aller `schulaufgabe`-Noten
- Gesamtschnitt = `(2 × große LN + kleine LN) / 3`

Die Quellenarchitektur in `notenschnitt.py` ist erweiterbar: `_KLEINE_LN_QUELLEN` ist eine Liste von `NoteQuelle`-Funktionen (Phase 4 hängte schriftliche kleine LN ein). Neue Quellen für Phase 6+ hier anhängen.

### Tests

Tests laufen gegen **SQLite** (in-memory-ähnlich via `test.db`), Produktion gegen PostgreSQL. Die `client`-Fixture in `tests/conftest.py` erstellt alle Tabellen via `Base.metadata.create_all()` und überschreibt die `get_db`-Dependency. Fixtures, die Kompetenzen seeden, müssen `client` als Parameter nehmen, damit die Tabellen vor dem Seeden existieren.

`test_phase4.py` enthält Handrechnung-Verifikationen der Schnittformel – diese Tests dokumentieren die exakten Berechnungserwartungen.

### UI vs. API

`/ui/*` Routen (in `app/routers/ui.py`) rendern Jinja2-Templates und rufen SQLAlchemy-Models **direkt** auf (kein HTTP-Roundtrip zur eigenen API). Die JSON-API unter `/schuljahre/`, `/klassen/` etc. bleibt parallel nutzbar (z.B. für `curl`-Tests oder `localhost:8045/docs`).

HTMX wird für die Punkte-Matrix (per-Zelle Autosave via `hx-post` + `name="punkte"` + `hx-vals` für schueler_id/la_id) und den Aufgabenpool-Live-Filter (`hx-get`, `hx-trigger="input changed delay:300ms"`) eingesetzt.

### Enum-Muster

Alle Enums erben von `(str, enum.Enum)` und werden mit `native_enum=False` gespeichert (VARCHAR statt PostgreSQL ENUM-Typ), damit Tests in SQLite funktionieren.

### Migrations

Migrationen sind manuell in `migrations/versions/` geschrieben (kein `alembic autogenerate` nach dem Build). K1–K6 Seed-Daten sind in Migration `0003`. Neue Migrationen: Revision-ID fortlaufend, `down_revision` auf Vorgänger setzen.
