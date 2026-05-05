# Buildplan: Schülerleistungen verwalten

**Projekt:** Web-App zur Verwaltung von Schülerleistungen am bayerischen Gymnasium
**Stack:** FastAPI + PostgreSQL + Jinja2/HTMX + WeasyPrint + Docker Compose
**Nutzung:** Single-User, lokal
**Fach (Start):** Mathematik, später Sport
**LLM-Anbindung:** Ollama über Netzwerk

---

## Allgemeine Hinweise

- Jede Phase ist eigenständig lauffähig und testbar
- Reihenfolge ist bindend – Phasen 0–5 sind das MVP, Phasen 6–10 die volle Vision, 11 optional
- Pro Phase: **Ziel · Umfang · Akzeptanzkriterien · Deliverable · Nicht enthalten**
- Akzeptanzkriterien müssen vor Beginn der nächsten Phase erfüllt sein

---

## Phase 0 – Projekt-Setup & Infrastruktur

**Ziel:** Lauffähiges Skelett im Docker Compose, leere App antwortet auf HTTP.

**Umfang:**
- Repo-Struktur (`app/`, `tests/`, `migrations/`, `templates/`, `static/`, `docker/`)
- `docker-compose.yml` mit Services: `app` (FastAPI/Uvicorn), `db` (Postgres 16), `backup` (Cron-Container, später aktiv)
- `.env`-Datei für DB-Credentials, kein Hardcoding
- FastAPI-App mit `/health`-Endpoint
- Alembic für DB-Migrationen initialisieren
- pytest-Setup mit einem Dummy-Test
- `README.md` mit Start-/Stop-Befehlen

**Akzeptanzkriterien:**
- `docker compose up -d` startet ohne Fehler
- `curl localhost:8000/health` liefert `{"status":"ok"}`
- `docker compose exec app pytest` läuft grün durch (mind. 1 Dummy-Test)
- `docker compose exec app alembic current` funktioniert

**Deliverable:** Repo + lauffähiger Container.

**Nicht enthalten:** Auth, Datenmodell, UI.

---

## Phase 1 – Datenmodell Stammdaten (Schuljahr → Klasse → Schüler)

**Ziel:** CRUD für die Hierarchie Schuljahr/Klasse/Schüler über REST-API.

**Umfang:**
- Modelle:
  - `Schuljahr` (z.B. „2025/26")
  - `Klasse` (Jahrgangsstufe 5–13, Buchstabe z.B. „a", ergibt Anzeigename „6a"; Fach=Mathe-fix für jetzt; FK Schuljahr)
    - Notensystem wird automatisch abgeleitet: Jahrgangsstufe 5–11 → Sechserskala (1–6), 12–13 → Punkte (0–15)
    - Notensystem ist nach Anlage unveränderlich
  - `Schueler` (Vorname, Nachname, FK Klasse, optional Pseudonym-ID)
- Alembic-Migration
- Pydantic-Schemas (Create, Read, Update)
- REST-Endpoints: GET/POST/PATCH/DELETE für alle drei Ebenen
- Soft-Delete für Schüler (Schüler verlassen Klassen, Daten bleiben)
- Tests: pro Endpoint mind. ein Happy-Path + ein Validierungsfehler

**Akzeptanzkriterien:**
- Ein Schuljahr anlegen, darin eine Klasse, darin 3 Schüler – alles über API
- Liste aller Schüler einer Klasse abrufbar
- Pseudonym-ID wird automatisch generiert (z.B. UUID-kurz), für späteren Export
- Tests grün (`pytest` mit mind. 80% Coverage auf den Modulen)

**Deliverable:** API + Tests + aktualisiertes Schema.

**Nicht enthalten:** UI, Noten.

---

## Phase 2 – Mündliche Noten + Notenschnitt-Berechnung

**Ziel:** Mündliche LN erfassen, Berechnungs-Service für Gesamtschnitt vorbereiten (schriftliche kommen in Phase 3/4).

**Umfang:**
- Modell `MuendlicheNote`: FK Schüler, Datum, Note, Notensystem (`sechserskala`|`punkte`), Gewichtung (`0.5`|`1`|`2`), Beschreibung, `geloescht_am`
- API CRUD
- Service `Notenschnitt`: berechnet Gesamtschnitt, holt sich Daten von späteren Modellen über Interface (Dependency Injection vorbereiten)
- Notensystem wird aus Jahrgangsstufe abgeleitet (5–11 → Sechserskala, 12–13 → Punkte), nicht manuell wählbar und nach Anlage unveränderlich
- Zunächst nur mündlicher Schnitt verfügbar
- Tests: Berechnungs-Edgecases (keine Noten, nur eine Note, gemischte Gewichtungen)

**Akzeptanzkriterien:**
- Mündliche Noten anlegbar, Schnitt korrekt
- Validierung: Note außerhalb Range wird abgelehnt
- Schnitt-Service ist so gebaut, dass schriftliche LN später ergänzt werden können, ohne ihn umzuschreiben

**Deliverable:** API + Tests + Skelett des Schnitt-Service.

**Nicht enthalten:** Schriftliche LN, Schulaufgaben.

---

## Phase 3 – Datenmodell „Schriftliche Leistung" (vereinheitlicht)

**Ziel:** Schulaufgaben *und* schriftliche kleine LN als ein gemeinsames Modell, mit oder ohne Aufgaben-Detaillierung.

**Umfang:**
- Modell `Kompetenz`: K1–K6 nach ISB als Seed-Daten in Migration
- Modell `Aufgabe` (Pool, wiederverwendbar):
  - Titel, Aufgabenstellung (Markdown), Lösung (Markdown)
  - max_punkte, Anforderungsniveau (`AFB_I`|`AFB_II`|`AFB_III`)
  - Tags, erstellt_am
  - Volltext-Index (Postgres `tsvector` auf Aufgabenstellung+Lösung+Tags)
- Modell `AufgabeKompetenz` (M:N zwischen Aufgabe und Kompetenz mit Gewichtung; Summe = 1.0 pro Aufgabe)
- Modell `SchriftlicheLeistung`:
  - FK Klasse, Datum, Titel
  - **`art`**: `schulaufgabe` | `kleiner_ln` (Enum)
  - **`detailliert`**: Boolean – ob Aufgaben/Punkte einzeln erfasst werden oder nur Pauschalnote; bei `art=schulaufgabe` immer `True` (Constraint)
  - Notenschluessel (JSON, optional bei `detailliert=False`)
  - Gewichtung (`0.5`|`1`|`2`)
- Modell `LeistungAufgabe` (M:N): verbindet `SchriftlicheLeistung` mit `Aufgabe`, Reihenfolge, Aufgabennummer (z.B. „1a")
- Validierung:
  - bei `detailliert=True` müssen Aufgaben + Notenschlüssel vorhanden sein
  - bei `detailliert=False` Pauschalnote-Eingabe pro Schüler in Phase 4
- API: CRUD Aufgaben, CRUD Schriftliche Leistungen, Aufgabe-zu-Leistung zuordnen, Suche im Aufgabenpool

**Akzeptanzkriterien:**
- Eine Schulaufgabe (`art=schulaufgabe`, `detailliert=True`) mit 6 Aufgaben anlegbar
- Ein kleiner schriftlicher LN (`art=kleiner_ln`, `detailliert=True`) mit 2 Aufgaben anlegbar
- Ein kleiner schriftlicher LN (`art=kleiner_ln`, `detailliert=False`) ohne Aufgaben anlegbar
- Validierung greift: SA ohne Aufgaben → Fehler
- Suche „quadratische Funktion" findet relevante Aufgaben (auch nach Synonym-Tags)
- Constraint: Kompetenz-Gewichtungen einer Aufgabe summieren auf 1.0 (±0.01)
- Tests grün

**Deliverable:** Migration + API + Tests + K1–K6 Seed.

**Nicht enthalten:** Schülerergebnisse, Notenberechnung.

---

## Phase 4 – Schülerergebnisse, Notenberechnung & Kompetenzprofil

**Ziel:** Punkte/Pauschalnoten erfassen, alle Schnitte korrekt berechnen, Kompetenzprofil aus *allen* detaillierten schriftlichen Leistungen ableiten.

**Umfang:**
- Modell `SchuelerErgebnis`:
  - Variante A (detailliert): FK Schüler, FK `LeistungAufgabe`, erreichte_punkte
  - Variante B (pauschal): FK Schüler, FK `SchriftlicheLeistung`, pauschalnote
  - Constraint: entweder Aufgaben-Ergebnisse *oder* Pauschalnote, nicht beides für dieselbe Leistung
- API:
  - Bulk-Eingabe Punkte (für detaillierte LN: Matrix Schüler × Aufgabe)
  - Einzeleingabe Pauschalnote
- Notenberechnung pro schriftlicher Leistung:
  - Detailliert: Punktesumme → Note via Notenschlüssel
  - Pauschal: direkt eingegebene Note
- Schnitte:
  - **Schnitt große LN** = gewichteter Ø aller `art=schulaufgabe`
  - **Schnitt kleine LN** = ein gemeinsamer gewichteter Ø aus allen `art=kleiner_ln` (detailliert + pauschal) **und** allen mündlichen Noten (jede Einzelnote mit ihrer eigenen Gewichtung)
  - **Gesamtschnitt** = `(2 × Ø große LN + Ø kleine LN) / 3`
- Kompetenzprofil:
  - Aggregiert über *alle* detaillierten schriftlichen Leistungen (Schulaufgabe + detaillierter kleiner LN gleichermaßen)
  - Pauschal-LN fließen *nicht* ins Kompetenzprofil ein (nur in Schnitt)
  - Endpoint zeigt Metadaten: „Profil basiert auf X von Y schriftlichen LN" (Transparenz)
- Endpoints:
  - `/schueler/{id}/kompetenzprofil`
  - `/schueler/{id}/gesamtschnitt`

**Akzeptanzkriterien:**
- Schüler mit 2 SAs (detailliert) + 3 kleinen LN (1 detailliert, 2 pauschal) + 4 mündlichen Noten → alle drei Schnitte korrekt nach Handrechnung
- Kompetenzprofil zieht Daten aus SA *und* detailliertem kleinem LN, ignoriert pauschale
- API liefert Metadaten zur Profil-Datenbasis
- Edgecase: Schüler hat nur Pauschal-LN, keine Detail-Daten → Profil leer, aber Schnitt korrekt
- Berechnungslogik mit Handrechnung in Tests verifiziert

**Deliverable:** API + ausführliche Tests.

**Nicht enthalten:** UI, Buchaufgaben, Empfehlungen.

---

## Phase 5 – Web-UI (Jinja2 + HTMX)

**Ziel:** Bedienbare Oberfläche für alle bisherigen Funktionen.

**Umfang:**
- Layout mit Navigation: Schuljahre → Klassen → Schüler → Schriftliche Leistungen → Aufgabenpool
- Listen- und Detailseiten pro Entität
- Formulare:
  - Mündliche Noten: schnell pro Schüler
  - Schriftliche Leistung anlegen: Auswahl `art` (SA/kleiner LN) + Toggle „detailliert ja/nein"
  - Bei `detailliert=False`: einfaches Pauschalnoten-Eingabeformular pro Schüler (Liste)
  - Bei `detailliert=True`: Punkte-Matrix (Schüler × Aufgabe)
- Aufgabenpool-Suche mit Live-Filter (HTMX)
- Schüler-Dashboard:
  - Drei Schnitte separat (große LN, kleine LN, Gesamt)
  - Notenliste
  - Kompetenz-Radar (einfaches SVG)
  - Hinweis: auf wie vielen LN das Profil basiert
- Minimal-CSS (Pico.css oder ähnlich, kein eigenes Design)

**Akzeptanzkriterien:**
- Kompletter Workflow per UI machbar: Schuljahr anlegen → Klasse → Schüler → Schriftliche Leistung mit Aufgaben → Punkte eintragen → Schnitt sehen
- Beide Eingabe-Modi (detailliert/pauschal) per UI nutzbar
- Wechsel zwischen Modi nicht erlaubt nach erster Noteneintragung (Datenintegrität) – UI zeigt das deutlich
- Punkte-Eingabematrix: Tab-Navigation funktioniert, Zwischenspeicherung pro Zeile
- Browser-Test (Playwright oder manuell dokumentiert) für den Hauptworkflow

**Deliverable:** UI im Container erreichbar unter `localhost:8000/`.

**Nicht enthalten:** PDF, Buchaufgaben, Ollama.

---

## Phase 6 – Buchaufgaben-Katalog

**Ziel:** Importierten Buchaufgaben-Katalog verwalten, durchsuchbar machen.

**Umfang:**
- Modell `Buchaufgabe`:
  - Buch (z.B. „Lambacher Schweizer 9 Bayern"), Kapitel, Seite, Aufgabennummer
  - Kurzbeschreibung
  - Anforderungsniveau (`AFB_I/II/III`)
  - Wichtigkeit (1–3)
  - M:N zu Kompetenz (analog zu `Aufgabe` aus Phase 3)
- Bulk-Import-Endpoint (CSV/JSON), idempotent
- UI: Listenansicht mit Filter (Buch, Kapitel, Kompetenz, AFB)
- Suche

**Akzeptanzkriterien:**
- Import von 50 Test-Aufgaben aus CSV läuft fehlerfrei
- Filter „K2 + AFB II + Buch X" liefert erwartete Treffermenge
- Zweiter Import mit identischen Daten erzeugt keine Duplikate

**Deliverable:** API + UI + Beispiel-CSV.

**Nicht enthalten:** Empfehlungslogik.

---

## Phase 7 – Empfehlungs-Engine (regelbasiert)

**Ziel:** Aus Kompetenzprofil eines Schülers passende Buchaufgaben auswählen.

**Umfang:**
- Service `Empfehlung`: Input Schüler-ID + Anzahl Aufgaben + optional Zielkompetenzen
- Algorithmus (deterministisch):
  1. Schwächste Kompetenzen ermitteln (unterhalb 60% z.B.)
  2. Buchaufgaben filtern, die diese Kompetenzen abdecken
  3. AFB-Mix: erst AFB I für sehr schwache (<40%), dann AFB II, AFB III nur wenn Kompetenz >70%
  4. Wichtigkeit als Tiebreaker
  5. Diversität sicherstellen (nicht alle aus einem Kapitel)
- Begründung pro Aufgabe als strukturierter Text (welche Kompetenz, warum dieses Niveau)
- Konfigurierbare Schwellenwerte in `.env` oder Settings-Tabelle
- API + UI-Seite „Empfehlung für Schüler X"

**Akzeptanzkriterien:**
- Synthetischer Schüler mit klarem Profil (K2 schwach, Rest stark) → Empfehlungen sind primär K2-Aufgaben mit niedrigem AFB
- Reproduzierbarkeit: gleicher Input → gleicher Output
- Mind. 5 Tests mit unterschiedlichen Profilen

**Deliverable:** Engine + UI + Tests.

**Nicht enthalten:** PDF, LLM.

---

## Phase 8 – PDF-Export

**Ziel:** Aufgabenplan und Schüleranalyse als PDF exportieren.

**Umfang:**
- WeasyPrint-Integration
- Template 1: Aufgabenplan (Schülername, Datum, nummerierte Aufgabenliste mit Buch/Seite/Aufgabe, optional Lösungen separat)
- Template 2: Kompetenzanalyse (Name, Datum, Schnitte, Kompetenzprofil als Balken/Radar, Begründungstext, Hinweis auf Datenbasis)
- API-Endpoints:
  - `/schueler/{id}/aufgabenplan.pdf`
  - `/schueler/{id}/analyse.pdf`
- UI-Buttons auf Schüler-Dashboard

**Akzeptanzkriterien:**
- Beide PDFs werden korrekt generiert, enthalten alle geforderten Felder
- Umlaute, lange Aufgabenstellungen, mehrseitige Layouts funktionieren
- Snapshot-Test (PDF→Text-Extraktion, Vergleich Schlüsselfelder)

**Deliverable:** Endpoints + Templates + Tests.

**Nicht enthalten:** LLM-Texte.

---

## Phase 9 – Ollama-Integration

**Ziel:** Empfehlungs-Begründungen und Analyse-Texte durch LLM verbessern.

**Umfang:**
- HTTP-Client für Ollama (Netzwerk-Adresse aus `.env`)
- Service `LLMEnhancer`: nimmt regelbasierte Begründung + Schülerprofil, gibt verbesserten Text zurück
- Klare Trennung: Daten kommen immer aus DB, LLM formuliert nur (kein Halluzinieren von Noten)
- Prompts versioniert in `prompts/` als Textdateien
- Fallback: Wenn Ollama nicht erreichbar → regelbasierter Text wird verwendet, Logging
- Toggle pro Export (LLM ja/nein)
- Tests mit gemocktem Ollama-Endpoint

**Akzeptanzkriterien:**
- Bei Ollama-Ausfall (Netzwerk down) bleibt App voll funktionsfähig
- Generierte Texte enthalten keine erfundenen Zahlen (Test mit Regex/Vergleich gegen Inputdaten)
- Latenz-Limit: max. 30s pro Request, danach Timeout + Fallback

**Deliverable:** Service + Tests + Beispiel-Prompts.

**Nicht enthalten:** MCP, Streaming.

---

## Phase 10 – Backup & Datenschutz

**Ziel:** Automatische lokale Backups, DSGVO-konforme Pseudonymisierung beim Export.

**Umfang:**
- Backup-Container mit Cron: täglicher `pg_dump` ins lokale Volume `./backups/`
- Retention: 14 tägliche, 8 wöchentliche, 12 monatliche
- Restore-Skript dokumentiert
- Pseudonymisierungs-Schalter beim PDF-Export (Echtname → Pseudonym-ID)
- Audit-Log: Wer hat wann welche Schülerdaten exportiert (auch wenn nur du existierst – für später)
- README-Abschnitt: DSGVO-Hinweise, Speicherort, Löschkonzept

**Akzeptanzkriterien:**
- Backup läuft automatisch, Restore aus Backup wiederhergestellt verifiziert
- Pseudonymisierter PDF-Export enthält keinen Klarnamen
- Audit-Log-Einträge bei jedem Export

**Deliverable:** Backup-Container + Restore-Doku + Audit-Log.

**Nicht enthalten:** Multi-User-Auth.

---

## Phase 11 – Sport-Erweiterung (optional, später)

**Ziel:** Datenmodell so generalisieren, dass Sport als zweites Fach möglich wird.

**Umfang:**
- Refactoring: `Fach` als eigene Entität, Klasse bekommt FK zu Fach
- Sport hat andere Notenstruktur (z.B. praktisch/theoretisch statt SA/kleine LN) → Strategy-Pattern für Notenberechnung pro Fach
- `art`-Enum erweitern um sportspezifische Typen
- Migration der Bestandsdaten

**Akzeptanzkriterien:**
- Bestehende Mathe-Daten bleiben unverändert nutzbar
- Sport-Klasse anlegbar mit eigener Notenlogik
- Tests für beide Fächer grün

**Deliverable:** Refactoring + Migration.

**Nicht enthalten:** Sport-spezifische UI-Optimierungen.

---

## Anhang: Hinweise zur Abarbeitung durch eine KI

1. Jede Phase mit eigenem Branch / Commit-Set, am Ende Akzeptanzkriterien als Testliste durchgehen
2. Reihenfolge ist bindend – Phasen 0–5 sind das MVP, Phasen 6–10 die volle Vision, 11 optional
3. Realistische Schätzung: Phasen 0–5 in 2–3 vollen Arbeitstagen mit guter KI-Unterstützung machbar; Phasen 6–10 nochmal so viel
4. Schwachpunkte:
   - Kompetenz-Gewichtung pro Aufgabe (Phase 3) ist konzeptionell sauber, aber im Eingabe-UI fummelig – mehr Zeit einplanen
   - Phase 9 (LLM) hat das höchste Risiko, dass Output unbrauchbar wird – regelbasierten Pfad als Hauptpfad behalten
5. Eingabe-Aufwand bedenken: nicht jeder kleine schriftliche LN muss detailliert erfasst werden – `detailliert=False` ist der pragmatische Default

---

## Kompetenzbereiche (K1–K6 nach ISB Bayern)

Zur Referenz für Seed-Daten in Phase 3:

- **K1** Mathematisch argumentieren
- **K2** Probleme mathematisch lösen
- **K3** Mathematisch modellieren
- **K4** Mathematische Darstellungen verwenden
- **K5** Mit symbolischen, formalen und technischen Elementen der Mathematik umgehen
- **K6** Mathematisch kommunizieren

> Hinweis: Genaue Bezeichnungen sind vor Phase 3 mit dem aktuellen ISB-Lehrplan zu verifizieren.