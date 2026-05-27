import random, secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from models import Ability, AbilityEffect, User, Score
from config import (
    ABILITY_POOL_GENERAL, ABILITY_POOL_IT, ABILITY_POOL_EKONOMI,
    RARE_ABILITY, SCORCH_PROBABILITY, ABILITY_OPTIONS,
    FREEZE_DUR, ROCK_DUR, INVISIBLE_DUR, DARKNESS_DUR,
    TELEPORT_DUR, MIRROR_MAX, SCORCH_MAX, CHAMPIONSHIP_FIELDS
)

META = {
    "steal_5":           {"n":"Stealing Scores -5",     "d":"Curi 5 poin lawan acak",               "rare":False},
    "protect_5":         {"n":"Scores Protection +5",   "d":"Proteksi pencurian 5 poin",             "rare":False},
    "steal_10":          {"n":"Stealing Score -10",     "d":"Curi 10 poin lawan acak",              "rare":False},
    "protect_10":        {"n":"Scores Protection +10",  "d":"Proteksi pencurian 10 poin",           "rare":False},
    "invisible":         {"n":"Invisible",              "d":"Ranking tersembunyi 10 menit",          "rare":False},
    "logical_fallacy":   {"n":"Logical Fallacy",        "d":"Kode lawan salah = -9% (IT saja)",     "rare":False},
    "cheat_score":       {"n":"Cheat Score",            "d":"+50 soal investasi (Ekonomi saja)",    "rare":False},
    "steal_ability":     {"n":"Stealing Ability",       "d":"Curi satu ability acak lawan",         "rare":False},
    "ability_protection":{"n":"Ability Protection",     "d":"Lindungi ability dari pencurian",      "rare":False},
    "teleport":          {"n":"Teleport",               "d":"Tukar posisi lawan acak 30 detik",     "rare":False},
    "recovery":          {"n":"Recovery",               "d":"Hapus semua efek negatif diri sendiri","rare":False},
    "darkness":          {"n":"Darkness",               "d":"Jawaban lawan kabur 12 detik",         "rare":False},
    "lightness":         {"n":"Lightness",              "d":"Counter Darkness, muncul setelah jawab benar saat Darkness","rare":False},
    "freeze":            {"n":"Freeze",                 "d":"Bekukan satu lawan 5 menit",           "rare":False},
    "rock":              {"n":"Rock",                   "d":"Imun Freeze selama 5 menit",           "rare":False},
    "mirror":            {"n":"Mirror",                 "d":"Lihat skor 5 lawan acak saat ini",     "rare":False},
    "scorch":            {"n":"Scorch ★ RARE",          "d":"Hanguskan semua ability 2 lawan kecuali Protection","rare":True},
}

def _id() -> str: return secrets.token_hex(16)

def _fid(name: str) -> int | None:
    for fid, fname in CHAMPIONSHIP_FIELDS.items():
        if fname == name: return fid
    return None

def pool(field: str) -> list[str]:
    if field == "IT": return ABILITY_POOL_IT
    if field == "Ekonomi": return ABILITY_POOL_EKONOMI
    return ABILITY_POOL_GENERAL

def draw(field: str, count: int = ABILITY_OPTIONS) -> list[str]:
    p = list(pool(field))
    if random.random() < SCORCH_PROBABILITY: p.append(RARE_ABILITY)
    return random.sample(p, min(count, len(p)))

def grant(db: Session, uid: str, atype: str, week: int, day: int) -> Ability:
    dur_map = {"invisible": INVISIBLE_DUR, "freeze": FREEZE_DUR, "rock": ROCK_DUR,
               "darkness": DARKNESS_DUR, "teleport": TELEPORT_DUR}
    dur = dur_map.get(atype)
    exp = datetime.now(timezone.utc) + timedelta(seconds=dur) if dur else None
    ab = Ability(id=_id(), user_id=uid, ability_type=atype, week=week, day=day, expires_at=exp)
    db.add(ab); db.commit(); db.refresh(ab); return ab

def active_abilities(db: Session, uid: str) -> list[Ability]:
    now = datetime.now(timezone.utc)
    return db.query(Ability).filter(
        Ability.user_id == uid, Ability.used == False
    ).filter((Ability.expires_at == None) | (Ability.expires_at > now)).all()

def consume(db: Session, ab_id: str, uid: str) -> Ability | None:
    ab = db.query(Ability).filter(Ability.id == ab_id, Ability.user_id == uid, Ability.used == False).first()
    if not ab: return None
    ab.used = True; ab.used_at = datetime.now(timezone.utc); db.commit(); return ab

def _active_effect(db: Session, uid: str, atype: str) -> bool:
    now = datetime.now(timezone.utc)
    return db.query(AbilityEffect).filter(
        AbilityEffect.target_user_id == uid, AbilityEffect.ability_type == atype,
        AbilityEffect.active == True, AbilityEffect.expires_at > now
    ).first() is not None

def frozen(db: Session, uid: str) -> bool:    return _active_effect(db, uid, "freeze")
def in_darkness(db: Session, uid: str) -> bool: return _active_effect(db, uid, "darkness")
def invisible(db: Session, uid: str) -> bool:  return _active_effect(db, uid, "invisible")

def deactivate_expired(db: Session):
    now = datetime.now(timezone.utc)
    rows = db.query(AbilityEffect).filter(
        AbilityEffect.active == True, AbilityEffect.expires_at != None, AbilityEffect.expires_at <= now
    ).all()
    for r in rows: r.active = False
    if rows: db.commit()

def reset_daily(db: Session, uid: str, week: int, day: int):
    rows = db.query(Ability).filter(
        Ability.user_id == uid, Ability.week == week, Ability.day < day, Ability.used == False
    ).all()
    for r in rows: r.used = True
    db.commit()

def _add_effect(db, src, tgt, atype, dur=None, data=None):
    exp = datetime.now(timezone.utc) + timedelta(seconds=dur) if dur else None
    ef = AbilityEffect(id=_id(), source_user_id=src, target_user_id=tgt,
                       ability_type=atype, expires_at=exp, active=True, effect_data=data or {})
    db.add(ef); db.commit(); return ef

def _opponents(db: Session, uid: str, field: str) -> list[User]:
    return db.query(User).filter(
        User.id != uid, User.field_championship == _fid(field),
        User.eliminated == False, User.registration_complete == True
    ).all()

def apply_steal(db: Session, uid: str, field: str, week: int, day: int, amt: int) -> dict:
    opps = [o for o in _opponents(db, uid, field)
            if not any(a.ability_type == f"protect_{amt}" for a in active_abilities(db, o.id))]
    if not opps: return {"success": False, "reason": "Semua lawan dilindungi Protection"}
    t = random.choice(opps)
    ts = db.query(Score).filter(Score.user_id == t.id, Score.field == field, Score.week == week, Score.day == day).first()
    ss = db.query(Score).filter(Score.user_id == uid, Score.field == field, Score.week == week, Score.day == day).first()
    if ts: ts.raw_score -= amt
    if ss: ss.raw_score += amt
    _add_effect(db, uid, t.id, f"steal_{amt}", data={"amount": amt})
    db.commit()
    return {"success": True, "target": t.nickname, "amount": amt}

def apply_freeze(db: Session, uid: str, tid: str, field: str) -> dict:
    if any(a.ability_type == "rock" for a in active_abilities(db, tid)): return {"success": False, "reason": "Target memiliki Rock aktif"}
    if _active_effect(db, tid, "rock"): return {"success": False, "reason": "Target imun Rock"}
    _add_effect(db, uid, tid, "freeze", FREEZE_DUR)
    return {"success": True, "target_user_id": tid, "duration": FREEZE_DUR}

def apply_invisible(db: Session, uid: str) -> dict:
    _add_effect(db, uid, uid, "invisible", INVISIBLE_DUR)
    return {"success": True, "duration": INVISIBLE_DUR}

def apply_rock(db: Session, uid: str) -> dict:
    _add_effect(db, uid, uid, "rock", ROCK_DUR)
    return {"success": True, "duration": ROCK_DUR}

def apply_darkness(db: Session, uid: str, tid: str) -> dict:
    _add_effect(db, uid, tid, "darkness", DARKNESS_DUR)
    return {"success": True, "target_user_id": tid, "duration": DARKNESS_DUR}

def apply_teleport(db: Session, uid: str, field: str) -> dict:
    opps = _opponents(db, uid, field)
    if not opps: return {"success": False, "reason": "Tidak ada lawan"}
    t = random.choice(opps)
    _add_effect(db, uid, t.id, "teleport", TELEPORT_DUR, {"source": uid})
    return {"success": True, "target_user_id": t.id, "target": t.nickname, "duration": TELEPORT_DUR}

def apply_recovery(db: Session, uid: str) -> dict:
    neg = ["freeze","darkness","teleport","logical_fallacy"]
    efs = db.query(AbilityEffect).filter(
        AbilityEffect.target_user_id == uid, AbilityEffect.active == True, AbilityEffect.ability_type.in_(neg)
    ).all()
    for e in efs: e.active = False
    db.commit()
    return {"success": True, "cleared": len(efs)}

def apply_mirror(db: Session, uid: str, field: str, week: int, day: int) -> dict:
    opps = _opponents(db, uid, field)
    if not opps: return {"success": False, "reason": "Tidak ada peserta"}
    targets = random.sample(opps, min(MIRROR_MAX, len(opps)))
    result = []
    for t in targets:
        if invisible(db, t.id): continue
        sc = db.query(Score).filter(Score.user_id == t.id, Score.field == field, Score.week == week, Score.day == day).first()
        result.append({"nickname": t.nickname, "raw_score": sc.raw_score if sc else 0})
    return {"success": True, "mirror_data": result}

def apply_scorch(db: Session, uid: str, field: str) -> dict:
    opps = _opponents(db, uid, field)
    if not opps: return {"success": False, "reason": "Tidak ada lawan"}
    targets = random.sample(opps, min(SCORCH_MAX, len(opps)))
    scorched = []
    for t in targets:
        abs_ = db.query(Ability).filter(
            Ability.user_id == t.id, Ability.used == False,
            ~Ability.ability_type.in_(["protect_5","protect_10","ability_protection"])
        ).all()
        for ab in abs_: ab.used = True; ab.used_at = datetime.now(timezone.utc)
        scorched.append({"nickname": t.nickname, "burned": len(abs_)})
    db.commit()
    return {"success": True, "scorched": scorched}

def apply_steal_ability(db: Session, uid: str, field: str) -> dict:
    for opp in _opponents(db, uid, field):
        opp_abs = active_abilities(db, opp.id)
        if any(a.ability_type == "ability_protection" for a in opp_abs): continue
        stealable = [a for a in opp_abs if a.ability_type != "ability_protection"]
        if stealable:
            stolen = random.choice(stealable); stolen.user_id = uid; db.commit()
            return {"success": True, "stolen": stolen.ability_type, "from": opp.nickname}
    return {"success": False, "reason": "Tidak ada ability yang bisa dicuri"}

def apply_cheat_score(db: Session, uid: str, field: str, week: int, day: int) -> dict:
    if field != "Ekonomi": return {"success": False, "reason": "Hanya untuk Ekonomi"}
    sc = db.query(Score).filter(Score.user_id == uid, Score.field == field, Score.week == week, Score.day == day).first()
    if sc: sc.raw_score += 50; db.commit()
    return {"success": True, "bonus": 50}

def apply_logical_fallacy(db: Session, uid: str, field: str) -> dict:
    if field not in ["IT","Komputer"]: return {"success": False, "reason": "Hanya untuk IT/Komputer"}
    opps = _opponents(db, uid, field)
    from datetime import timedelta
    exp = datetime.now(timezone.utc) + timedelta(hours=24)
    for opp in opps:
        ef = AbilityEffect(id=_id(), source_user_id=uid, target_user_id=opp.id,
                           ability_type="logical_fallacy", expires_at=exp, active=True, effect_data={"pct":9})
        db.add(ef)
    db.commit()
    return {"success": True, "targets": len(opps)}
