from fastapi import APIRouter, Request
from database import get_db_conn, get_community_tokens
import uuid

router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

@router.get("/list")
async def list_tokens():
    return get_community_tokens()

@router.post("/buy-request")
async def buy_request(request: Request):
    # Ta logique d'achat hybride ici
    return {"ok": True}
