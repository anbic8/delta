from __future__ import annotations
import json


# ── Kompetenz-Beschreibungen ──────────────────────────────────
# Merkmale die aus dem Aufgabentext erkennbar sind

_KOMP_BESCHREIBUNGEN = {
    "K1": "Mathematisch argumentieren: Begründungen, Beweise, 'Zeige dass', 'Warum gilt...', Zusammenhänge erklären",
    "K2": "Probleme mathematisch lösen: unbekannter Lösungsweg, Strategie selbst entwickeln, nicht-routinemäßig",
    "K3": "Mathematisch modellieren: Sachaufgabe mit realem Kontext, Übersetzung Realität↔Mathematik",
    "K4": "Mathematische Darstellungen verwenden: Graph, Tabelle, Diagramm, geometrische Figur zeichnen oder lesen",
    "K5": "Mit symbolischen, formalen und technischen Elementen umgehen: Formel anwenden, Gleichung lösen, Algorithmus, Rechnung",
    "K6": "Mathematisch kommunizieren: Ergebnisse beschreiben, Fachbegriffe, mathematische Texte lesen oder verfassen",
}

_AFB_BESCHREIBUNGEN = (
    "AFB_I (Reproduzieren): Formel direkt einsetzen, Definition nennen, "
    "Standardverfahren ohne Variation anwenden (z.B. 'Berechne...', 'Gib an...').\n"
    "AFB_II (Anwenden): bekannte Methode auf neue Situation übertragen, "
    "mehrere Schritte kombinieren (z.B. 'Löse...', 'Bestimme...', Sachaufgaben).\n"
    "AFB_III (Verallgemeinern): Zusammenhänge erkennen, begründen, modellieren, "
    "Strategie selbst entwickeln (z.B. 'Begründe...', 'Untersuche...', 'Beweise...')."
)


def _system_prompt(uk_paare: list[tuple[str, str]], kompetenzen: list[dict]) -> str:
    # Kompetenz-Beschreibungen (nutzt eigene Texte oder DB-Bezeichnung als Fallback)
    komp_lines = []
    for k in kompetenzen:
        beschr = _KOMP_BESCHREIBUNGEN.get(k["kuerzel"], k["bezeichnung"])
        komp_lines.append(f"  {k['kuerzel']}: {beschr}")
    komp_str = "\n".join(komp_lines)

    # Kapitel/Unterkapitel-Paare (max 60 um Tokens zu sparen)
    kap_uk_lines = []
    seen_kap = set()
    for kap, uk in uk_paare[:60]:
        if kap not in seen_kap:
            kap_uk_lines.append(f"  Kapitel: \"{kap}\"")
            seen_kap.add(kap)
        if uk:
            kap_uk_lines.append(f"    Unterkapitel: \"{uk}\"")
    kap_str = "\n".join(kap_uk_lines)

    return f"""Du bist Mathematiklehrer am bayerischen Gymnasium (Klasse 5–13).
Analysiere die Aufgabe und antworte NUR mit gültigem JSON – kein Text davor oder danach.

JSON-Schema (alle Felder PFLICHT):
{{"loesung":"Musterlösung mit Rechenweg","afb_niveau":"AFB_I|AFB_II|AFB_III","kapitel":"exakt wie unten","unterkapitel":"exakt wie unten","kompetenzen":["K1","K6"]}}

AFB-Niveau – wähle anhand dieser Merkmale:
{_AFB_BESCHREIBUNGEN}

Kompetenzen – wähle ALLE zutreffenden (meist 1–3):
{komp_str}

Verfügbare Kapitel und Unterkapitel (wähle exakt passende Bezeichnung):
{kap_str}"""


def _clean_llm_json(s: str) -> str:
    """
    Bereinigt LLM-JSON:
    - Escapet Steuerzeichen (\\n, \\t …) innerhalb von String-Werten
    - Escapet ungültige Backslash-Sequenzen (LaTeX: \\frac, \\cdot …)
    """
    import re
    result: list[str] = []
    in_string = False
    skip_next = False
    for i, ch in enumerate(s):
        if skip_next:
            result.append(ch)
            skip_next = False
            continue
        if ch == '\\' and in_string:
            # nächstes Zeichen prüfen
            nxt = s[i + 1] if i + 1 < len(s) else ''
            if nxt in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u'):
                result.append(ch)   # gültiges Escape – unverändert
            else:
                result.append('\\\\')  # LaTeX o.ä. – doppelt escapen
            skip_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ord(ch) < 0x20:
            # Steuerzeichen innerhalb eines Strings escapen
            result.append({'\\n': '\\n', '\n': '\\n',
                           '\r': '\\r', '\t': '\\t'}.get(ch, f'\\u{ord(ch):04x}'))
            continue
        result.append(ch)
    return ''.join(result)


def _user_msg(aufgabenstellung: str) -> str:
    return f"Aufgabe:\n{aufgabenstellung.strip()}"


# ── Backends ──────────────────────────────────────────────────

def _llm_config(db=None) -> dict:
    """Liest LLM-Einstellungen aus DB (Vorrang) oder .env (Fallback)."""
    from app.config import settings as cfg
    if db is None:
        return {"backend": cfg.llm_backend, "url": cfg.ollama_url,
                "model": cfg.ollama_model, "api_key": cfg.anthropic_api_key}
    from app.models.app_einstellung import AppEinstellung
    def _get(key, fallback):
        row = db.get(AppEinstellung, key)
        return row.wert if row and row.wert else fallback
    return {
        "backend": _get("llm_backend",  cfg.llm_backend),
        "url":     _get("ollama_url",   cfg.ollama_url),
        "model":   _get("ollama_model", cfg.ollama_model),
        "api_key": cfg.anthropic_api_key,
    }


async def _ollama(system: str, user: str, cfg: dict) -> str:
    import httpx
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{cfg['url']}/v1/chat/completions",
            json={
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _claude(system: str, user: str, cfg: dict) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=cfg["api_key"])
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
    uk_paare: list[tuple[str, str]],
    kompetenzen: list[dict],
    db=None,
) -> dict:
    """
    uk_paare: Liste von (kapitel, unterkapitel) aus den Buchaufgaben.
    Gibt zurück: {loesung, afb_niveau, kapitel, unterkapitel, kompetenzen}
    oder {"error": "..."} bei Fehler.
    """
    cfg = _llm_config(db)
    system = _system_prompt(uk_paare, kompetenzen)
    user = _user_msg(aufgabenstellung)

    try:
        if cfg["backend"] == "claude":
            raw = await _claude(system, user, cfg)
        else:
            raw = await _ollama(system, user, cfg)

        start = raw.find("{")
        end = raw.rfind("}") + 1
        snippet = raw[start:end] if start >= 0 and end > start else raw
        data = json.loads(_clean_llm_json(snippet))

        return {
            "loesung": str(data.get("loesung") or ""),
            "afb_niveau": data.get("afb_niveau", "AFB_II"),
            "kapitel": str(data.get("kapitel") or ""),
            "unterkapitel": str(data.get("unterkapitel") or ""),
            "kompetenzen": [str(k) for k in data.get("kompetenzen") or []],
        }
    except Exception as e:
        return {"error": str(e)}
