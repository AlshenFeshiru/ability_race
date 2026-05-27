import math, secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from models import User, ChampionshipState, Score, AbilityEffect
from config import (
    CHAMPIONSHIPS_START, CHAMPIONSHIPS_END, WIB, SCORE_REVEAL_DAYS,
    CHAMPIONSHIP_FIELDS, SCORE_CORRECT, SCORE_WRONG, SCORE_SKIP,
    STREAK_THRESHOLD, ABILITY_OPTIONS,
    ELIM_THRESHOLD, GP_PG_COUNT, GP_PG_TIME, GP_PHASE2_H, GP_PHASE3_H
)
from abilities import draw, deactivate_expired, reset_daily, frozen

GAMMA_BASE   = 1.0
GAMMA_GROWTH = 0.05
GAMMA_MAX    = 1.1
GAMMA_MIN    = 1.0
PHI_DECAY    = 0.9

def _id(): return secrets.token_hex(16)

def gamma(streak: int) -> float:
    g = GAMMA_BASE + GAMMA_GROWTH * math.floor(streak / 10)
    return min(max(g, GAMMA_MIN), GAMMA_MAX)

def phi_weighted(answer_log: list) -> float:
    if not answer_log: return 0.0
    total = 0.0; weight_sum = 0.0
    for i, entry in enumerate(reversed(answer_log)):
        w = PHI_DECAY ** i
        total += entry.get("pts", 0) * w
        weight_sum += w
    return total / weight_sum if weight_sum > 0 else 0.0

def week_day() -> tuple[int, int]:
    now = datetime.now(WIB)
    if now < CHAMPIONSHIPS_START: return 0, 0
    d = (now - CHAMPIONSHIPS_START).days + 1
    if d >= 30: return 6, 30
    if d == 29: return 5, 29
    return min(math.ceil(d / 7), 4), d

def test_type(week: int, gp_phase: int = 1) -> str:
    m = {1:"flash_card",2:"click_test",3:"incoexistent",4:"one_word",5:"memory_test"}
    if week == 6: return {1:"grand_prix_pg",2:"which_is_true",3:"matching_true_false"}.get(gp_phase,"grand_prix_pg")
    return m.get(week, "flash_card")

def is_open() -> bool:
    now = datetime.now(WIB)
    return CHAMPIONSHIPS_START <= now <= CHAMPIONSHIPS_END

def ensure_state(db: Session, uid: str) -> ChampionshipState:
    s = db.query(ChampionshipState).filter(ChampionshipState.user_id == uid).first()
    if not s:
        w, d = week_day()
        s = ChampionshipState(
            id=_id(), user_id=uid,
            current_week=max(1,w), current_day=max(1,d),
            current_question_index=0, answers_log=[],
            consecutive_correct=0, ability_selection_pending=False,
            ability_options=[], grand_prix_phase=1
        )
        db.add(s); db.commit(); db.refresh(s)
    return s

def ensure_score(db: Session, uid: str, field: str, week: int, day: int) -> Score:
    sc = db.query(Score).filter(
        Score.user_id == uid, Score.field == field,
        Score.week == week, Score.day == day
    ).first()
    if not sc:
        sc = Score(id=_id(), user_id=uid, field=field, week=week, day=day)
        db.add(sc); db.commit(); db.refresh(sc)
    return sc

def _composite(sc: Score, answer_log: list, streak: int) -> float:
    if sc.total_questions == 0: return 0.0
    g = gamma(streak)
    phi_score = phi_weighted(answer_log)
    acc = sc.percentage * 0.6
    max_r = sc.total_questions * SCORE_CORRECT
    raw_pct = (max(0, sc.raw_score) / max(1, max_r)) * 100
    base = acc * 0.6 + raw_pct * 0.4
    if phi_score != 0:
        phi_component = ((phi_score + SCORE_CORRECT) / (2 * SCORE_CORRECT)) * 100
        base = base * 0.7 + phi_component * 0.3
    return round(base * g, 2)

def submit(db: Session, uid: str, qid: str, answer: str, correct: bool, field: str, week: int, day: int) -> dict:
    deactivate_expired(db)
    if frozen(db, uid): return {"success":False,"frozen":True,"message":"Anda sedang dibekukan (Freeze)"}
    sc = ensure_score(db, uid, field, week, day)
    st = ensure_state(db, uid)
    if correct:
        pts = SCORE_CORRECT; sc.correct_count += 1; st.consecutive_correct += 1
    elif answer == "":
        pts = SCORE_SKIP; sc.skip_count += 1; st.consecutive_correct = 0
    else:
        pts = SCORE_WRONG; sc.wrong_count += 1; st.consecutive_correct = 0
    sc.raw_score += pts; sc.total_questions += 1
    sc.updated_at = datetime.now(timezone.utc)
    new_log = (st.answers_log or []) + [{"qid":qid,"correct":correct,"pts":pts,"ts":datetime.now(timezone.utc).isoformat()}]
    st.answers_log = new_log
    st.current_question_index += 1
    st.last_active = datetime.now(timezone.utc)
    ab_triggered = False; ab_opts = []
    if week == 2 and st.consecutive_correct >= STREAK_THRESHOLD:
        u = db.query(User).filter(User.id == uid).first()
        fname = CHAMPIONSHIP_FIELDS.get(u.field_championship if u else 0, "IT")
        ab_opts = draw(fname, ABILITY_OPTIONS)
        st.ability_selection_pending = True
        st.ability_options = ab_opts
        st.consecutive_correct = 0
        ab_triggered = True
    if sc.total_questions > 0:
        sc.percentage = (sc.correct_count / sc.total_questions) * 100
        sc.composite_score = _composite(sc, st.answers_log, st.consecutive_correct)
    db.commit()
    g_val = gamma(st.consecutive_correct)
    return {
        "success": True,
        "points_earned": pts,
        "raw_score": sc.raw_score,
        "percentage": round(sc.percentage, 2),
        "composite_score": sc.composite_score,
        "consecutive_correct": st.consecutive_correct,
        "gamma": round(g_val, 4),
        "ability_triggered": ab_triggered,
        "ability_options": ab_opts
    }

def check_elimination(db: Session, uid: str, week: int, field: str) -> dict:
    if week not in range(1,6): return {"eliminated":False}
    scores = db.query(Score).filter(Score.user_id == uid, Score.field == field, Score.week == week).all()
    if not scores: return {"eliminated":False}
    tc = sum(s.correct_count for s in scores); tq = sum(s.total_questions for s in scores)
    if tq == 0: return {"eliminated":False}
    pct = tc / tq * 100; elim = pct < ELIM_THRESHOLD
    if elim:
        u = db.query(User).filter(User.id == uid).first()
        if u: u.eliminated = True; db.commit()
    return {"eliminated":elim,"percentage":round(pct,2),"threshold":ELIM_THRESHOLD}

def leaderboard(db: Session, field: str, week: int) -> list[dict]:
    from abilities import invisible
    fid = next((k for k,v in CHAMPIONSHIP_FIELDS.items() if v == field), None)
    if not fid: return []
    users = db.query(User).filter(User.field_championship == fid, User.registration_complete == True).all()
    rows = []
    for u in users:
        inv = invisible(db, u.id)
        scores = db.query(Score).filter(Score.user_id == u.id, Score.field == field, Score.week == week).all()
        raw = sum(s.raw_score for s in scores)
        tc = sum(s.correct_count for s in scores)
        tq = sum(s.total_questions for s in scores)
        pct = (tc/tq*100) if tq > 0 else 0
        comp = max(s.composite_score for s in scores) if scores else 0.0
        rows.append({
            "nickname": "???" if inv else u.nickname,
            "status": u.status,
            "raw_score": round(raw,2) if not inv else None,
            "percentage": round(pct,2) if not inv else None,
            "composite_score": round(comp,2) if not inv else None,
            "eliminated": u.eliminated,
            "invisible": inv
        })
    rows.sort(key=lambda x: -(x["composite_score"] or 0))
    for i,r in enumerate(rows): r["rank"] = i+1
    return rows

def mc_profile_stats(db: Session, uid: str, field: str) -> dict:
    scores = db.query(Score).filter(Score.user_id == uid, Score.field == field, Score.week == 0).all()
    if not scores: return {"field":field,"total_questions":0,"correct":0,"percentage":0.0,"composite_score":0.0}
    tq = sum(s.total_questions for s in scores)
    tc = sum(s.correct_count for s in scores)
    tr = sum(s.raw_score for s in scores)
    pct = (tc/tq*100) if tq > 0 else 0
    max_r = tq * SCORE_CORRECT
    raw_pct = (max(0,tr)/max(1,max_r))*100
    comp = round(pct*0.6 + raw_pct*0.4, 2)
    return {"field":field,"total_questions":tq,"correct":tc,"percentage":round(pct,2),"composite_score":comp}
