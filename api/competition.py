import secrets, hashlib
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel
from database import get_db
from models import User, Question, Score, AbilityEffect, Node
from championships import week_day, test_type, submit, ensure_state, ensure_score, is_open, check_elimination
from groq_questions import get_questions, eval_one_word, eval_flash
from abilities import (
    active_abilities, consume, grant, draw, META,
    apply_steal, apply_freeze, apply_invisible, apply_rock, apply_darkness,
    apply_teleport, apply_recovery, apply_mirror, apply_scorch, apply_steal_ability,
    apply_cheat_score, apply_logical_fallacy, frozen, in_darkness
)
from config import MULTIPLE_CHOICE_FIELDS, CHAMPIONSHIP_FIELDS, MC_QUESTIONS, MC_TIME_PER_Q, SCORE_CORRECT, SCORE_WRONG, SCORE_SKIP, SECRET_KEY, ALGORITHM
from jose import jwt

router = APIRouter()
def _id(): return secrets.token_hex(16)

def _u(r: Request, db: Session) -> User:
    auth = r.headers.get("Authorization","")
    if not auth.startswith("Bearer "): raise HTTPException(401,"Token diperlukan")
    try: uid = jwt.decode(auth[7:], SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except Exception: raise HTTPException(401,"Token tidak valid")
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404,"User tidak ditemukan")
    return u

def _seed(db: Session, uid: str) -> int:
    n = db.query(Node).filter(Node.user_id == uid).first()
    return n.question_seed if n else int(hashlib.sha256(uid.encode()).hexdigest()[:8], 16)

def _eval(q: Question, ans: str, tt: str) -> bool:
    if tt == "one_word":
        acc = q.options_json.get("accepted",[]) if q.options_json else []
        return eval_one_word(ans, q.correct_answer, acc)
    if tt == "flash_card":
        kws = q.options_json.get("keywords",[]) if q.options_json else []
        return eval_flash(ans, kws)
    if tt == "memory_test":
        ci = q.options_json.get("correct_index",0) if q.options_json else 0
        opts = q.options_json.get("options",[]) if q.options_json else []
        if opts and ans.isdigit(): return int(ans) == ci
        return ans.strip().lower() == q.correct_answer.strip().lower()
    return ans.upper().strip() == q.correct_answer.upper().strip()

def _dispatch(db, uid, field, atype, tid, week, day) -> dict:
    if atype == "steal_5":          return apply_steal(db, uid, field, week, day, 5)
    if atype == "steal_10":         return apply_steal(db, uid, field, week, day, 10)
    if atype in ["protect_5","protect_10"]: return {"success":True,"message":f"{atype} aktif"}
    if atype == "invisible":        return apply_invisible(db, uid)
    if atype == "rock":             return apply_rock(db, uid)
    if atype == "recovery":         return apply_recovery(db, uid)
    if atype == "lightness":        return apply_recovery(db, uid)
    if atype == "mirror":           return apply_mirror(db, uid, field, week, day)
    if atype == "cheat_score":      return apply_cheat_score(db, uid, field, week, day)
    if atype == "logical_fallacy":  return apply_logical_fallacy(db, uid, field)
    if atype == "steal_ability":    return apply_steal_ability(db, uid, field)
    if atype == "scorch":           return apply_scorch(db, uid, field)
    if atype == "teleport":         return apply_teleport(db, uid, field)
    if atype == "ability_protection": return {"success":True,"message":"Ability Protection aktif"}
    if atype == "freeze":
        if not tid: raise HTTPException(400,"Freeze butuh target_user_id")
        return apply_freeze(db, uid, tid, field)
    if atype == "darkness":
        if not tid: raise HTTPException(400,"Darkness butuh target_user_id")
        return apply_darkness(db, uid, tid)
    return {"success":False,"reason":f"Unknown ability: {atype}"}

class AnsReq(BaseModel): question_id: str; user_answer: str
class MCBatch(BaseModel): field: str; answers: list[AnsReq]
class AbUse(BaseModel): ability_id: str; target_user_id: str | None = None
class AbSelect(BaseModel): selected_ability: str

@router.get("/multiple-choice/questions/{field}")
def mc_questions(field: str, r: Request, db: Session = Depends(get_db)):
    u = _u(r, db)
    if field not in MULTIPLE_CHOICE_FIELDS: raise HTTPException(400,"Bidang tidak valid")
    qs = get_questions(db, field, 0, "multiple_choice", _seed(db, u.id), u.status)[:MC_QUESTIONS]
    return {"field":field,"total":len(qs),"time_per_q":MC_TIME_PER_Q,"status":u.status,
            "questions":[{"id":q.id,"question":q.question_text,"options":q.options_json,"seq":q.sequence_index} for q in qs]}

@router.post("/multiple-choice/submit")
def mc_submit(data: MCBatch, r: Request, db: Session = Depends(get_db)):
    u = _u(r, db)
    if data.field not in MULTIPLE_CHOICE_FIELDS: raise HTTPException(400,"Bidang tidak valid")
    sc = ensure_score(db, u.id, data.field, 0, 0); results = []
    for ans in data.answers:
        q = db.query(Question).filter(Question.id == ans.question_id).first()
        if not q: continue
        correct = ans.user_answer.upper() == q.correct_answer.upper()
        if ans.user_answer == "": pts = SCORE_SKIP; sc.skip_count += 1
        elif correct:             pts = SCORE_CORRECT; sc.correct_count += 1
        else:                     pts = SCORE_WRONG; sc.wrong_count += 1
        sc.raw_score += pts; sc.total_questions += 1
        results.append({"question_id":ans.question_id,"is_correct":correct,"points":pts})
    if sc.total_questions > 0: sc.percentage = sc.correct_count / sc.total_questions * 100
    sc.updated_at = datetime.now(timezone.utc); db.commit()
    return {"field":data.field,"raw_score":sc.raw_score,"correct":sc.correct_count,"wrong":sc.wrong_count,"percentage":round(sc.percentage,2),"results":results}

@router.get("/championship/status")
def champ_status(r: Request, db: Session = Depends(get_db)):
    u = _u(r, db); w, d = week_day(); open_ = is_open()
    st = ensure_state(db, u.id) if u.field_championship and open_ else None
    return {"championships_open":open_,"week":w,"day":d,
            "test_type":test_type(w) if w > 0 else None,
            "field":CHAMPIONSHIP_FIELDS.get(u.field_championship,"Belum dipilih"),
            "eliminated":u.eliminated,"is_frozen":frozen(db,u.id),
            "consecutive_correct":st.consecutive_correct if st else 0,
            "ability_pending":st.ability_selection_pending if st else False,
            "ability_options":st.ability_options if st else []}

@router.get("/championship/questions")
def champ_questions(r: Request, db: Session = Depends(get_db)):
    u = _u(r, db)
    if not is_open(): raise HTTPException(403,"Championships dibuka 21 Juni 2026 10:00 WIB")
    if not u.field_championship: raise HTTPException(400,"Pilih bidang Championship di Profil")
    if u.eliminated: raise HTTPException(403,"Anda telah tereliminasi")
    if frozen(db, u.id): raise HTTPException(423,"Anda sedang dibekukan (Freeze) — tunggu 5 menit")
    w, d = week_day(); st = ensure_state(db, u.id)
    fname = CHAMPIONSHIP_FIELDS[u.field_championship]
    tt = test_type(w, st.grand_prix_phase)
    if w == 2 and st.ability_selection_pending:
        return {"action_required":"ability_selection",
                "ability_options":[{"id":ab,"name":META[ab]["n"],"description":META[ab]["d"]} for ab in st.ability_options if ab in META]}
    qs = get_questions(db, fname, w, tt, _seed(db, u.id), u.status)
    remaining = qs[st.current_question_index:]
    out = []
    for q in remaining:
        d2 = {"id":q.id,"question":q.question_text,"seq":q.sequence_index}
        if tt in ["click_test","which_is_true"]:
            d2["option_a"]=q.option_a; d2["option_b"]=q.option_b
            if tt == "click_test": d2["context_after"]=q.context_after
        elif tt in ["multiple_choice","incoexistent","grand_prix_pg"]:
            d2["options"]=q.options_json
        elif tt == "one_word":
            d2["hint"]="(jawaban satu kata)"
        elif tt == "memory_test":
            d2["sequence_given"]=q.question_text
            d2["match_options"]=q.options_json.get("options",[]) if q.options_json else []
        elif tt == "matching_true_false":
            d2["statement"]=q.question_text; d2["format"]="TRUE atau FALSE"
        out.append(d2)
    return {"week":w,"day":d,"field":fname,"test_type":tt,"remaining":len(remaining),"current_index":st.current_question_index,"consecutive_correct":st.consecutive_correct,"questions":out}

@router.post("/championship/answer")
def champ_answer(data: AnsReq, r: Request, db: Session = Depends(get_db)):
    u = _u(r, db)
    if not is_open(): raise HTTPException(403,"Championships belum dibuka")
    if u.eliminated: raise HTTPException(403,"Anda telah tereliminasi")
    if frozen(db, u.id): raise HTTPException(423,"Anda sedang dibekukan")
    w, d = week_day(); fname = CHAMPIONSHIP_FIELDS.get(u.field_championship)
    if not fname: raise HTTPException(400,"Bidang Championship belum dipilih")
    q = db.query(Question).filter(Question.id == data.question_id).first()
    if not q: raise HTTPException(404,"Soal tidak ditemukan")
    tt = test_type(w); correct = _eval(q, data.user_answer, tt)
    now = datetime.now(timezone.utc)
    lf = db.query(AbilityEffect).filter(
        AbilityEffect.target_user_id == u.id, AbilityEffect.ability_type == "logical_fallacy",
        AbilityEffect.active == True, AbilityEffect.expires_at > now
    ).first()
    result = submit(db, u.id, data.question_id, data.user_answer, correct, fname, w, d)
    if not correct and lf and tt == "click_test":
        sc = ensure_score(db, u.id, fname, w, d)
        sc.raw_score -= abs(sc.raw_score) * 0.09; db.commit()
        result["logical_fallacy_applied"] = True
    if in_darkness(db, u.id) and correct:
        result["lightness_available"] = True
    return result

@router.post("/championship/ability/select")
def ab_select(data: AbSelect, r: Request, db: Session = Depends(get_db)):
    u = _u(r, db); st = ensure_state(db, u.id)
    if not st.ability_selection_pending: raise HTTPException(400,"Tidak ada ability pending")
    if data.selected_ability not in st.ability_options: raise HTTPException(400,"Ability tidak ada dalam opsi")
    w, d = week_day(); ab = grant(db, u.id, data.selected_ability, w, d)
    st.ability_selection_pending = False; st.ability_options = []; db.commit()
    return {"success":True,"ability_id":ab.id,"ability":data.selected_ability,
            "name":META.get(data.selected_ability,{}).get("n",""),"description":META.get(data.selected_ability,{}).get("d","")}

@router.post("/championship/ability/use")
def ab_use(data: AbUse, r: Request, db: Session = Depends(get_db)):
    u = _u(r, db)
    if u.eliminated: raise HTTPException(403,"Anda tereliminasi")
    ab = consume(db, data.ability_id, u.id)
    if not ab: raise HTTPException(404,"Ability tidak ditemukan atau sudah digunakan")
    w, d = week_day(); fname = CHAMPIONSHIP_FIELDS.get(u.field_championship,"")
    return _dispatch(db, u.id, fname, ab.ability_type, data.target_user_id, w, d)

@router.get("/championship/abilities")
def my_abilities(r: Request, db: Session = Depends(get_db)):
    u = _u(r, db); abs_ = active_abilities(db, u.id)
    return {"abilities":[{"id":a.id,"type":a.ability_type,"name":META.get(a.ability_type,{}).get("n",a.ability_type),
                          "description":META.get(a.ability_type,{}).get("d",""),
                          "expires_at":a.expires_at.isoformat() if a.expires_at else None} for a in abs_]}

@router.get("/championship/my-score")
def my_score(r: Request, db: Session = Depends(get_db)):
    u = _u(r, db); w, d = week_day()
    fname = CHAMPIONSHIP_FIELDS.get(u.field_championship)
    if not fname: raise HTTPException(400,"Belum memilih bidang Championship")
    scores = db.query(Score).filter(Score.user_id == u.id, Score.field == fname, Score.week == w).all()
    raw = sum(s.raw_score for s in scores); tc = sum(s.correct_count for s in scores); tq = sum(s.total_questions for s in scores)
    return {"field":fname,"week":w,"day":d,"raw_score":round(raw,2),"correct":tc,"total":tq,
            "percentage":round(tc/tq*100,2) if tq > 0 else 0,
            "eliminated":u.eliminated,"is_frozen":frozen(db,u.id),"in_darkness":in_darkness(db,u.id)}
