from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

Path("uploads/aufgaben").mkdir(parents=True, exist_ok=True)

from app.models import grundwissen_abfrage, app_einstellung, sitzplan, live_bewertung  # noqa: F401
from app.routers import aufgabe, buchaufgabe, klasse, kompetenz, muendliche_note, schueler, schuljahr, schriftliche_leistung, ui

app = FastAPI(title="Delta – Schülerleistungen")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/material", StaticFiles(directory="material"), name="material")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(schuljahr.router)
app.include_router(klasse.router)
app.include_router(schueler.router)
app.include_router(muendliche_note.router)
app.include_router(kompetenz.router)
app.include_router(aufgabe.router)
app.include_router(buchaufgabe.router)
app.include_router(schriftliche_leistung.router)
app.include_router(ui.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/schuljahre")


@app.get("/health")
def health():
    return {"status": "ok"}
