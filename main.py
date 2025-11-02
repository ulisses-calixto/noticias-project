import os
from typing import Optional, List
from uuid import UUID
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
import httpx

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
TABLE = os.getenv("TABLE_NEWS", "news")
POSTGREST_URL = f"{SUPABASE_URL}/rest/v1"

if not SUPABASE_URL or not ANON_KEY:
    raise RuntimeError("Configure SUPABASE_URL e SUPABASE_ANON_KEY no .env")

app = FastAPI(title="News API (FastAPI + Supabase)")

class NewsCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    content: str
    author_id: UUID

class NewsUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=160)
    content: Optional[str] = None

class NewsOut(BaseModel):
    id: UUID
    title: str
    content: str
    author_id: UUID
    created_at: str
    updated_at: str

async def get_user_token(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    return authorization

def postgrest_headers(user_authorization: str):
    return {
        "apikey": ANON_KEY,
        "Authorization": user_authorization,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation",
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/news", response_model=List[NewsOut])
async def list_news(auth=Depends(get_user_token), limit: int = 50, offset: int = 0, search: Optional[str] = None):
    params = {"select": "*", "limit": str(min(limit, 100)), "offset": str(max(offset, 0)), "order": "created_at.desc"}
    if search:
        params["title"] = f"ilike.*{search}*"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{POSTGREST_URL}/{TABLE}", headers=postgrest_headers(auth), params=params)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@app.get("/news/{news_id}", response_model=List[NewsOut])
async def get_news(news_id: UUID, auth=Depends(get_user_token)):
    params = {"select": "*", "id": f"eq.{news_id}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{POSTGREST_URL}/{TABLE}", headers=postgrest_headers(auth), params=params)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@app.post("/news", response_model=List[NewsOut], status_code=201)
async def create_news(payload: NewsCreate, auth=Depends(get_user_token)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{POSTGREST_URL}/{TABLE}",
            headers=postgrest_headers(auth),
            json=payload.model_dump(mode="json")  # <- transforma UUID em string
        )
        
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@app.put("/news/{news_id}", response_model=List[NewsOut])
async def update_news(news_id: UUID, payload: NewsUpdate, auth=Depends(get_user_token)):

    data = {k: v for k, v in payload.model_dump(mode="json").items() if v is not None}

    if not data:
        raise HTTPException(400, "No fields to update")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(
            f"{POSTGREST_URL}/{TABLE}",
            headers=postgrest_headers(auth),
            params={"id": f"eq.{news_id}"},
            json=data,
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@app.delete("/news/{news_id}", status_code=204)
async def delete_news(news_id: UUID, auth=Depends(get_user_token)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(
            f"{POSTGREST_URL}/{TABLE}",
            headers=postgrest_headers(auth),
            params={"id": f"eq.{news_id}"},
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return {}