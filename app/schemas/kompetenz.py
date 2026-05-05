from pydantic import BaseModel


class KompetenzRead(BaseModel):
    id: int
    kuerzel: str
    bezeichnung: str

    model_config = {"from_attributes": True}
