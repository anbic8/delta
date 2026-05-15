from __future__ import annotations
import json


# ── Prompt ────────────────────────────────────────────────────

_AFB_HINWEIS = (
    "AFB_I (Reproduzieren): Fakten, Definitionen, Standardverfahren direkt abrufen. "
    "AFB_II (Anwenden): bekannte Methoden auf neue Situationen übertragen. "
    "AFB_III (Verallgemeinern): Probleme lösen, modellieren, Zusammenhänge erkennen."
)

_JSON_SCHEMA = (
    '{"loesung":"...","afb_niveau":"AFB_I|AFB_II|AFB_III",'
    '"kapitel":"...","unterkapitel":"...","kompetenzen":["K1",...]}'
)


def _system_prompt(kapitel_liste: list[str], kompetenzen: list[dict]) -> str:
    komp = ", ".join(f"{k['kuerzel']}={k['bezeichnung']}" for k in kompetenzen)
    kap = " | ".join(kapitel_liste[:40])
    return (
        "Du bist Mathematiklehrer am bayerischen Gymnasium. "
        "Antworte NUR mit gültigem JSON, kein Text davor oder danach.\n"
        f"Schema: {_JSON_SCHEMA}\n\n"
        f"AFB: {_AFB_HINWEIS}\n\n"
        f"Kompetenzen (wähle passende): {komp}\n\n"
        f"Kapitel (wähle das passendste): {kap}"
    )


def _user_msg(aufgabenstellung: str) -> str:
    return f"Aufgabe:\n{aufgabenstellung.strip()}"


# ── Backends ──────────────────────────────────────────────────

async def _ollama(system: str, user: str) -> str:
    import httpx
    from app.config import settings
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": system,
                "prompt": user,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.2},
            },
        )
        resp.raise_for_status()
        return resp.json()["response"]


async def _claude(system: str, user: str) -> str:
    import anthropic
    from app.config import settings
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


# ── Hauptfunktion ─────────────────────────────────────────────

async def aufgabe_vorschlag(
    aufgabenstellung: str,
    kapitel_liste: list[str],
    kompetenzen: list[dict],
) -> dict:
    """
    Gibt Vorschläge zurück:
      loesung, afb_niveau, kapitel, unterkapitel, kompetenzen (list[str])
    oder {"error": "..."} bei Fehler.
    """
    from app.config import settings

    system = _system_prompt(kapitel_liste, kompetenzen)
    user = _user_msg(aufgabenstellung)

    try:
        if settings.llm_backend == "claude":
            raw = await _claude(system, user)
        else:
            raw = await _ollama(system, user)

        # JSON extrahieren (Modell könnte trotzdem extra Text liefern)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end] if start >= 0 and end > start else raw)

        return {
            "loesung": str(data.get("loesung") or ""),
            "afb_niveau": data.get("afb_niveau", "AFB_II"),
            "kapitel": str(data.get("kapitel") or ""),
            "unterkapitel": str(data.get("unterkapitel") or ""),
            "kompetenzen": [str(k) for k in data.get("kompetenzen") or []],
        }
    except Exception as e:
        return {"error": str(e)}
