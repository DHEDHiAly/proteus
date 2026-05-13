import json
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/targets", tags=["Targets"])


PROTEUS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def load_targets_metadata() -> list:
    meta_path = os.path.join(PROTEUS_ROOT, "data", "targets_metadata.json")
    with open(meta_path, "r") as f:
        data = json.load(f)
    return data.get("targets", [])


@router.get("")
async def list_targets(current_user: User = Depends(get_current_user)):
    targets = load_targets_metadata()
    return {"targets": targets, "total": len(targets)}


@router.get("/{target_name}")
async def get_target(target_name: str, current_user: User = Depends(get_current_user)):
    targets = load_targets_metadata()
    for t in targets:
        if t["name"] == target_name:
            return t
    raise HTTPException(status_code=404, detail=f"Target {target_name} not found")


@router.get("/{target_name}/binders")
async def get_known_binders(target_name: str, current_user: User = Depends(get_current_user)):
    csv_path = os.path.join(settings.KNOWN_BINDERS_DIR, f"{target_name.lower()}_binders.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join(settings.KNOWN_BINDERS_DIR, f"{target_name}_binders.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail=f"No known binders for {target_name}")

    import csv
    binders = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            binders.append(row)
    return {"target": target_name, "binders": binders, "total": len(binders)}
