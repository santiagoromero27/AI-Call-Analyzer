"""Model selection settings endpoint."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..services.model_settings import get_model_key, set_model_key

router = APIRouter()


class ModelSwitchRequest(BaseModel):
    key: str


@router.get("/settings/model")
def get_model_setting():
    return {"key": get_model_key()}


@router.post("/settings/model")
def set_model_setting(req: ModelSwitchRequest, db: Session = Depends(get_db)):
    if not set_model_key(req.key):
        return {"ok": False, "error": "Unknown model key"}
    row = db.query(models.Setting).filter(models.Setting.key == "model").first()
    if row:
        row.value = req.key
    else:
        db.add(models.Setting(key="model", value=req.key))
    db.commit()
    return {"ok": True, "key": req.key}
