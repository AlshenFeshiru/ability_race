import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from models import Ability, AbilityEffect, Score, User
from config import CHAMPIONSHIP_FIELDS

ALL_ABILITIES = [
    "steal_5","steal_10","protect_5","protect_10",
    "invisible","freeze","rock","darkness","lightness",
    "teleport","recovery","mirror","steal_ability",
    "ability_protection","cheat_score","logical_fallacy","scorch"
]
RARE = {"scorch"}
FIELD_RESTRICTED = {"cheat_score":"Ekonomi","logical_fallacy":"IT"}

def _id(): return secrets.token_hex(16)
def _now(): return datetime.now(timezone.utc)

def pick_4_random(user_field_name: str) -> list[str]:
    import random
    pool = [a for a in ALL_ABILITIES if a not in RARE]
    restricted = [a for a,f in FIELD_RESTRICTED.items() if f != user_field_name]
    pool = [a for a in pool if a not in restricted]
    if random.random() < 0.05:
        pool.append("scorch")
    random.shuffle(pool)
    return pool[:4]

def grant_ability(db: Session, user_id: str, ability_type: str, week: int, day: int) -> Ability:
    expires = _now() + timedelta(hours=20)
    ab = Ability(
        id=_id(), user_id=user_id, ability_type=ability_type,
        week=week, day=day, expires_at=expires, used=False
    )
    db.add(ab)
    db.commit()
    return ab

def get_active_abilities(db: Session, user_id: str, week: int, day: int) -> list[Ability]:
    return db.query(Ability).filter(
        Ability.user_id == user_id,
        Ability.week == week,
        Ability.day == day,
        Ability.used == False
    ).all()

def is_protected(db: Session, target_id: str, protection_type: str = "protect_5") -> bool:
    now = _now()
    ef = db.query(AbilityEffect).filter(
        AbilityEffect.target_user_id == target_id,
        AbilityEffect.ability_type.in_(["protect_5","protect_10","ability_protection"]),
        AbilityEffect.active == True,
        AbilityEffect.expires_at > now
    ).first()
    return ef is not None

def is_frozen(db: Session, target_id: str) -> bool:
    now = _now()
    ef = db.query(AbilityEffect).filter(
        AbilityEffect.target_user_id == target_id,
        AbilityEffect.ability_type == "freeze",
        AbilityEffect.active == True,
        AbilityEffect.expires_at > now
    ).first()
    if not ef:
        return False
    rock_ef = db.query(AbilityEffect).filter(
        AbilityEffect.target_user_id == target_id,
        AbilityEffect.ability_type == "rock",
        AbilityEffect.active == True,
        AbilityEffect.expires_at > now
    ).first()
    return rock_ef is None

def is_invisible(db: Session, user_id: str) -> bool:
    now = _now()
    return db.query(AbilityEffect).filter(
        AbilityEffect.target_user_id == user_id,
        AbilityEffect.ability_type == "invisible",
        AbilityEffect.active == True,
        AbilityEffect.expires_at > now
    ).first() is not None

def execute_ability(
    db: Session, ability_id: str, user_id: str,
    target_user_id: str | None, field: str, week: int, day: int
) -> dict:
    ab = db.query(Ability).filter(
        Ability.id == ability_id,
        Ability.user_id == user_id,
        Ability.used == False
    ).first()
    if not ab:
        return {"ok": False, "reason": "Ability tidak ditemukan atau sudah digunakan"}

    user = db.query(User).filter(User.id == user_id).first()
    atype = ab.ability_type
    now = _now()
    result = {"ok": True, "ability": atype, "effect": {}}

    # ── STEAL 5 / STEAL 10
    if atype in ("steal_5", "steal_10"):
        if not target_user_id:
            return {"ok": False, "reason": "Target diperlukan"}
        if is_protected(db, target_user_id):
            return {"ok": False, "reason": "Target terlindungi"}
        pts = 5 if atype == "steal_5" else 10
        t_score = db.query(Score).filter(Score.user_id == target_user_id, Score.field == field, Score.week == week, Score.day == day).first()
        m_score = db.query(Score).filter(Score.user_id == user_id, Score.field == field, Score.week == week, Score.day == day).first()
        if t_score and m_score and t_score.raw_score >= pts:
            t_score.raw_score -= pts
            m_score.raw_score += pts
            result["effect"] = {"stolen": pts, "from": target_user_id}
        else:
            return {"ok": False, "reason": "Poin target tidak cukup"}

    # ── PROTECT 5 / PROTECT 10
    elif atype in ("protect_5", "protect_10"):
        dur = 5 * 60 if atype == "protect_5" else 10 * 60
        db.add(AbilityEffect(
            id=_id(), source_user_id=user_id, target_user_id=user_id,
            ability_type=atype, expires_at=now + timedelta(seconds=dur), active=True
        ))
        result["effect"] = {"protected_minutes": dur // 60}

    # ── INVISIBLE (10 menit)
    elif atype == "invisible":
        db.add(AbilityEffect(
            id=_id(), source_user_id=user_id, target_user_id=user_id,
            ability_type="invisible", expires_at=now + timedelta(minutes=10), active=True
        ))
        result["effect"] = {"hidden_minutes": 10}

    # ── FREEZE (5 menit ke target)
    elif atype == "freeze":
        if not target_user_id:
            return {"ok": False, "reason": "Target diperlukan"}
        if is_protected(db, target_user_id):
            return {"ok": False, "reason": "Target terlindungi"}
        db.add(AbilityEffect(
            id=_id(), source_user_id=user_id, target_user_id=target_user_id,
            ability_type="freeze", expires_at=now + timedelta(minutes=5), active=True
        ))
        result["effect"] = {"frozen_user": target_user_id, "minutes": 5}

    # ── ROCK (imunitas terhadap freeze, 15 menit)
    elif atype == "rock":
        db.add(AbilityEffect(
            id=_id(), source_user_id=user_id, target_user_id=user_id,
            ability_type="rock", expires_at=now + timedelta(minutes=15), active=True
        ))
        result["effect"] = {"immune_minutes": 15}

    # ── DARKNESS (12 detik — frontend effect, server catat)
    elif atype == "darkness":
        if not target_user_id:
            return {"ok": False, "reason": "Target diperlukan"}
        db.add(AbilityEffect(
            id=_id(), source_user_id=user_id, target_user_id=target_user_id,
            ability_type="darkness", expires_at=now + timedelta(seconds=12), active=True,
            effect_data={"duration_sec": 12}
        ))
        result["effect"] = {"darkness_sec": 12, "target": target_user_id}

    # ── LIGHTNESS (counter darkness)
    elif atype == "lightness":
        removed = db.query(AbilityEffect).filter(
            AbilityEffect.target_user_id == user_id,
            AbilityEffect.ability_type == "darkness",
            AbilityEffect.active == True
        ).all()
        for ef in removed:
            ef.active = False
        result["effect"] = {"darkness_removed": len(removed)}

    # ── TELEPORT (skip soal saat ini, 30 detik cooldown)
    elif atype == "teleport":
        result["effect"] = {"action": "skip_current_question", "skip": True}

    # ── RECOVERY (+poin dari wrong yang pernah dikurangi)
    elif atype == "recovery":
        sc = db.query(Score).filter(
            Score.user_id == user_id, Score.field == field,
            Score.week == week, Score.day == day
        ).first()
        if sc:
            recovered = sc.wrong_count * 1
            sc.raw_score += recovered
            result["effect"] = {"recovered_points": recovered}

    # ── MIRROR (lihat 5 skor lawan)
    elif atype == "mirror":
        others = db.query(Score).filter(
            Score.field == field, Score.week == week, Score.day == day,
            Score.user_id != user_id
        ).order_by(Score.raw_score.desc()).limit(5).all()
        result["effect"] = {"scores": [{"user_id": s.user_id, "score": round(s.raw_score, 2)} for s in others]}

    # ── STEAL ABILITY
    elif atype == "steal_ability":
        if not target_user_id:
            return {"ok": False, "reason": "Target diperlukan"}
        if is_protected(db, target_user_id):
            return {"ok": False, "reason": "Target terlindungi"}
        t_ab = db.query(Ability).filter(
            Ability.user_id == target_user_id,
            Ability.used == False,
            Ability.week == week, Ability.day == day
        ).first()
        if t_ab:
            new_ab = Ability(
                id=_id(), user_id=user_id, ability_type=t_ab.ability_type,
                week=week, day=day, used=False,
                expires_at=now + timedelta(hours=10)
            )
            db.add(new_ab)
            t_ab.used = True
            result["effect"] = {"stolen_ability": t_ab.ability_type}
        else:
            return {"ok": False, "reason": "Target tidak punya ability"}

    # ── ABILITY PROTECTION
    elif atype == "ability_protection":
        db.add(AbilityEffect(
            id=_id(), source_user_id=user_id, target_user_id=user_id,
            ability_type="ability_protection", expires_at=now + timedelta(hours=12), active=True
        ))
        result["effect"] = {"ability_protected_hours": 12}

    # ── CHEAT SCORE (+50, Ekonomi only)
    elif atype == "cheat_score":
        if field != "Ekonomi":
            return {"ok": False, "reason": "Cheat Score hanya untuk bidang Ekonomi"}
        sc = db.query(Score).filter(
            Score.user_id == user_id, Score.field == field,
            Score.week == week, Score.day == day
        ).first()
        if sc:
            sc.raw_score += 50
            result["effect"] = {"bonus_points": 50}

    # ── LOGICAL FALLACY (-9% target, IT only)
    elif atype == "logical_fallacy":
        if field != "IT":
            return {"ok": False, "reason": "Logical Fallacy hanya untuk bidang IT"}
        if not target_user_id:
            return {"ok": False, "reason": "Target diperlukan"}
        if is_protected(db, target_user_id):
            return {"ok": False, "reason": "Target terlindungi"}
        sc = db.query(Score).filter(
            Score.user_id == target_user_id, Score.field == field,
            Score.week == week, Score.day == day
        ).first()
        if sc:
            penalty = sc.raw_score * 0.09
            sc.raw_score -= penalty
            result["effect"] = {"penalized": target_user_id, "penalty_pct": 9}

    # ── SCORCH (RARE: burn 2 opponents)
    elif atype == "scorch":
        targets = db.query(Score).filter(
            Score.field == field, Score.week == week, Score.day == day,
            Score.user_id != user_id
        ).order_by(Score.raw_score.desc()).limit(2).all()
        burned = []
        for t in targets:
            if not is_protected(db, t.user_id):
                burn = t.raw_score * 0.15
                t.raw_score -= burn
                burned.append({"user_id": t.user_id, "burned_pct": 15})
        result["effect"] = {"scorched": burned}

    ab.used = True
    ab.used_at = now
    db.commit()
    return result

def deactivate_expired(db: Session):
    now = _now()
    db.query(AbilityEffect).filter(
        AbilityEffect.expires_at < now,
        AbilityEffect.active == True
    ).update({"active": False})
    db.commit()

def check_streak_and_offer(db: Session, user_id: str, consecutive: int, field: str, week: int, day: int) -> dict | None:
    if consecutive > 0 and consecutive % 10 == 0:
        field_name = CHAMPIONSHIP_FIELDS.get(field, field) if isinstance(field, int) else field
        options = pick_4_random(field_name)
        return {"offer": True, "options": options, "streak": consecutive}
    return None
