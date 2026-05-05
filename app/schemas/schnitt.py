from pydantic import BaseModel


class SchuelerSchnittRead(BaseModel):
    schueler_id: int
    schnitt_kleine_ln: float | None
    schnitt_grosse_ln: float | None
    gesamtschnitt: float | None
