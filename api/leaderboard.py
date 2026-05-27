from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from championships import leaderboard, week_day
from config import CHAMPIONSHIP_FIELDS, MULTIPLE_CHOICE_FIELDS, SCORE_REVEAL_DAYS

router = APIRouter()

@router.get("/championship/{field}")
def champ_lb(field: str, week: int = 0, db: Session = Depends(get_db)):
    w, d = week_day(); week = week or w
    if d not in SCORE_REVEAL_DAYS and w < 5 and week >= w:
        return {"message":"Skor ditampilkan setiap hari ke-7 per minggu dan Semi Final/Final","leaderboard":[]}
    rows = leaderboard(db, field, week)
    return {"field":field,"week":week,"total":len(rows),"leaderboard":rows}

@router.get("/overall")
def overall_lb(week: int = 0, db: Session = Depends(get_db)):
    from models import User, Score
    from abilities import invisible
    from config import SCORE_CORRECT
    w, d = week_day(); week = week or w
    if d not in SCORE_REVEAL_DAYS and w < 5:
        return {"message":"Belum waktunya pengumuman","leaderboard":[]}
    users = db.query(User).filter(User.registration_complete == True).all()
    rows = []
    for u in users:
        if not u.field_championship: continue
        fname = CHAMPIONSHIP_FIELDS.get(u.field_championship,"")
        inv = invisible(db, u.id)
        scores = db.query(Score).filter(Score.user_id == u.id, Score.field == fname, Score.week == week).all()
        raw = sum(s.raw_score for s in scores); tc = sum(s.correct_count for s in scores); tq = sum(s.total_questions for s in scores)
        pct = tc/tq*100 if tq > 0 else 0
        max_r = tq * SCORE_CORRECT
        comp = round(pct*0.6 + (max(0,raw)/max(1,max_r))*100*0.4, 2)
        rows.append({"nickname":"???" if inv else u.nickname,"field":fname,"status":u.status,
                     "composite_score":comp if not inv else None,"percentage":round(pct,2) if not inv else None,"eliminated":u.eliminated})
    rows.sort(key=lambda x: -(x["composite_score"] or 0))
    for i,r in enumerate(rows): r["rank"] = i+1
    return {"week":week,"leaderboard":rows}

@router.get("/fields")
def fields():
    return {"championship":list(CHAMPIONSHIP_FIELDS.values()),"multiple_choice":MULTIPLE_CHOICE_FIELDS}
