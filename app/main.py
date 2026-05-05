from fastapi import FastAPI

from app.routers import klasse, schueler, schuljahr

app = FastAPI(title="Delta – Schülerleistungen")

app.include_router(schuljahr.router)
app.include_router(klasse.router)
app.include_router(schueler.router)


@app.get("/health")
def health():
    return {"status": "ok"}
