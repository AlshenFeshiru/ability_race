import secrets
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from database import get_db
from models import User, Score, AvatarRegistry, ViewerRating, AbilityEffect
from config import CHAMPIONSHIP_FIELDS
from championships import week_day, leaderboard

router = APIRouter()

def _fid(name: str) -> int | None:
    return next((k for k,v in CHAMPIONSHIP_FIELDS.items() if v == name), None)

def _fp_hash(request: Request) -> str:
    from security import keccak256
    ip = request.headers.get("X-Forwarded-For","") or (request.client.host if request.client else "anon")
    ua = request.headers.get("User-Agent","")
    return keccak256(f"{ip}{ua}".encode())[:32]

@router.get("/live/{field}")
def live_leaderboard(field: str, db: Session = Depends(get_db)):
    w, d = week_day()
    fid = _fid(field)
    if not fid: return {"leaderboard": [], "field": field, "week": w, "day": d}
    users = db.query(User).filter(
        User.field_championship == fid,
        User.registration_complete == True
    ).all()
    rows = []
    now = datetime.now(timezone.utc)
    for u in users:
        inv = db.query(AbilityEffect).filter(
            AbilityEffect.target_user_id == u.id,
            AbilityEffect.ability_type == "invisible",
            AbilityEffect.active == True,
            AbilityEffect.expires_at > now
        ).first() is not None
        scores = db.query(Score).filter(
            Score.user_id == u.id, Score.field == field, Score.week == w
        ).all()
        raw = sum(s.raw_score for s in scores)
        tc = sum(s.correct_count for s in scores)
        tq = sum(s.total_questions for s in scores)
        pct = (tc/tq*100) if tq > 0 else 0
        comp = max((s.composite_score for s in scores), default=0.0)
        av_rec = db.query(AvatarRegistry).filter(AvatarRegistry.user_id == u.id).first()
        ratings = db.query(ViewerRating).filter(ViewerRating.target_user_id == u.id).all()
        avg_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else 0
        rows.append({
            "nickname": "???" if inv else u.nickname,
            "avatar_id": u.avatar_id,
            "status": u.status,
            "raw_score": round(raw, 2) if not inv else None,
            "percentage": round(pct, 2) if not inv else None,
            "composite_score": round(comp, 2) if not inv else None,
            "eliminated": u.eliminated,
            "invisible": inv,
            "viewer_rating": round(avg_rating, 1),
            "rating_count": len(ratings)
        })
    rows.sort(key=lambda x: -(x["composite_score"] or 0))
    for i, r in enumerate(rows): r["rank"] = i+1
    return {"leaderboard": rows, "field": field, "week": w, "day": d, "total": len(rows)}

@router.get("/fields")
def fields():
    return {"fields": list(CHAMPIONSHIP_FIELDS.values())}

class RateReq(BaseModel):
    target_user_id: str
    rating: int
    lock: bool = False

@router.post("/rate")
def rate_participant(data: RateReq, r: Request, db: Session = Depends(get_db)):
    if not 1 <= data.rating <= 10: return {"error": "Rating 1-10"}
    fp = _fp_hash(r)
    existing = db.query(ViewerRating).filter(
        ViewerRating.viewer_fp == fp,
        ViewerRating.target_user_id == data.target_user_id
    ).first()
    my_ratings = db.query(ViewerRating).filter(
        ViewerRating.viewer_fp == fp
    ).count()
    if existing:
        if existing.locked: return {"error": "Rating sudah dikunci permanen"}
        existing.rating = data.rating
        existing.locked = data.lock
        existing.updated_at = datetime.now(timezone.utc)
    else:
        if my_ratings >= 3: return {"error": "Maksimal rating 3 peserta per hari"}
        db.add(ViewerRating(
            id=secrets.token_hex(16), viewer_fp=fp,
            target_user_id=data.target_user_id,
            rating=data.rating, locked=data.lock
        ))
    db.commit()
    return {"ok": True, "locked": data.lock}
