# Delta – Schülerleistungen verwalten

Web-App zur Verwaltung von Schülerleistungen am bayerischen Gymnasium.

**Stack:** FastAPI · PostgreSQL 16 · Jinja2/HTMX · WeasyPrint · Docker Compose

---

## Voraussetzungen

- Docker Desktop (inkl. Compose)
- `.env` nach `.env.example` anlegen (bereits enthalten für lokale Entwicklung)

---

## Starten / Stoppen

```bash
# Starten (im Hintergrund)
docker compose up -d

# Logs anzeigen
docker compose logs -f app

# Stoppen
docker compose down

# Stoppen + Datenbank-Volume löschen
docker compose down -v
```

---

## Health-Check

```bash
curl http://localhost:45/health
# → {"status":"ok"}
```

---

## Tests

```bash
docker compose exec app pytest
```

---

## Datenbankmigrationen (Alembic)

```bash
# Aktuellen Migrationsstatus anzeigen
docker compose exec app alembic current

# Neue Migration erstellen
docker compose exec app alembic revision --autogenerate -m "beschreibung"

# Migrationen anwenden
docker compose exec app alembic upgrade head
```
