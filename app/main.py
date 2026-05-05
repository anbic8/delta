from fastapi import FastAPI

from app.routers import aufgabe, klasse, kompetenz, muendliche_note, schueler, schuljahr, schriftliche_leistung

app = FastAPI(title="Delta – Schülerleistungen")

app.include_router(schuljahr.router)
app.include_router(klasse.router)
app.include_router(schueler.router)
app.include_router(muendliche_note.router)
app.include_router(kompetenz.router)
app.include_router(aufgabe.router)
app.include_router(schriftliche_leistung.router)


@app.get("/health")
def health():
    return {"status": "ok"}
