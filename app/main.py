from fastapi import FastAPI

app = FastAPI(title="Delta – Schülerleistungen")


@app.get("/health")
def health():
    return {"status": "ok"}
