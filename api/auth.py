import os, secrets, time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from database import get_db
from models import User, Payment, MachineRegistry, AvatarRegistry
from security import keccak256, dss256, is_blacklisted, record_fail, hash_machine, hash_subnet, ws_ticket as make_ws_ticket
from config import SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_MIN, MULTIPLE_CHOICE_FIELDS, CHAMPIONSHIP_FIELDS, DSS_KEY_ONE, DSS_KEY_TWO
from age_verify import infer_participant_class, is_likely_student
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from jose import jwt

router = APIRouter()
ORGANIZER_TOKEN = os.environ.get("ORGANIZER_TOKEN", "")
ADMIN_LOCKED    = os.environ.get("ADMIN_LOCKED", "false").lower() == "true"

def _id(): return secrets.token_hex(32)

def _ip(r: Request) -> str:
    fwd = r.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (r.client.host if r.client else "0.0.0.0")

def _gen_kp():
    priv = Ed25519PrivateKey.generate()
    pb = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pu = priv.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return pb.decode(), pu.decode()

def _verify_kp(priv: str, pub: str) -> bool:
    try:
        p = serialization.load_pem_private_key(priv.encode(), password=None)
        d = p.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        return d.decode().strip() == pub.strip()
    except Exception: return False

def _token(data: dict) -> str:
    d = data.copy()
    d["exp"] = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MIN)
    return jwt.encode(d, SECRET_KEY, algorithm=ALGORITHM)

def _user(r: Request, db: Session) -> User:
    auth = r.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): raise HTTPException(401, "Token diperlukan")
    try: uid = jwt.decode(auth[7:], SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except Exception: raise HTTPException(401, "Token tidak valid")
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404, "User tidak ditemukan")
    return u

def _assign_avatar(db: Session, uid: str) -> int:
    used = {r.avatar_id for r in db.query(AvatarRegistry).all()}
    for av_id in range(1, 1001):
        if av_id not in used:
            db.add(AvatarRegistry(user_id=uid, avatar_id=av_id))
            db.commit()
            return av_id
    raise HTTPException(409, "Kapasitas peserta penuh (1000)")

class PreReg(BaseModel):
    nickname: str
    full_name: str
    status: str
    machine_fingerprint: str
    is_root_device: bool = False
    organizer_token: str = ""

class AutoLogin(BaseModel):
    private_key_pem: str
    machine_fingerprint: str

class FieldSel(BaseModel):
    championship_field: int | None = None
    multiple_choice_fields: list[str] = []

class AudioGrant(BaseModel):
    granted: bool

class ExitEvent(BaseModel):
    count: int

@router.post("/register")
def register(data: PreReg, r: Request, db: Session = Depends(get_db)):
    if ADMIN_LOCKED: raise HTTPException(403, "Sistem terkunci")
    ip = _ip(r)
    if is_blacklisted(ip): raise HTTPException(429, "IP diblokir")
    is_org = ORGANIZER_TOKEN and data.organizer_token == ORGANIZER_TOKEN

    if data.is_root_device and not is_org:
        raise HTTPException(403, "Perangkat root tidak diizinkan mengikuti kompetisi")

    if data.status not in ["Pelajar","Mahasiswa","Mahasiswi"]:
        raise HTTPException(400, "Status harus Pelajar, Mahasiswa, atau Mahasiswi")

    if db.query(User).filter(User.nickname == data.nickname).first():
        raise HTTPException(409, "Nickname sudah digunakan")

    if db.query(MachineRegistry).filter(MachineRegistry.machine_fingerprint == data.machine_fingerprint).first():
        raise HTTPException(409, "Perangkat ini sudah terdaftar")

    age_result = infer_participant_class(data.nickname, data.full_name, data.status)
    if not is_likely_student(age_result) and not is_org:
        raise HTTPException(403, f"Pendaftaran ditolak: {age_result.get('reason','Profil tidak sesuai pelajar/mahasiswa')}")

    priv, pub = _gen_kp()
    uid = _id()
    avatar_id = _assign_avatar(db, uid) if not is_org else 0

    u = User(
        id=uid, nickname=data.nickname, full_name=data.full_name,
        status=data.status, public_key_pem=pub,
        payment_verified=True, registration_complete=True,
        machine_id=hash_machine(data.machine_fingerprint),
        ip_subnet=hash_subnet(ip),
        avatar_id=avatar_id,
        is_root_device=data.is_root_device,
        age_verified=age_result.get("verdict","uncertain"),
        age_inference=age_result.get("reason","")
    )
    db.add(u)
    db.add(Payment(
        id=secrets.token_hex(16), user_id=uid, amount=0,
        bank_reference="FREE", payment_hash=dss256(uid.encode()),
        verified=True, verified_by="FREE_TIER"
    ))
    db.add(MachineRegistry(
        id=secrets.token_hex(16), machine_fingerprint=data.machine_fingerprint,
        user_id=uid, ip_address=ip
    ))
    db.commit()
    return {
        "private_key_pem": priv,
        "user_id": uid,
        "nickname": data.nickname,
        "avatar_id": avatar_id,
        "age_verdict": age_result.get("verdict"),
        "WARNING": "Simpan Private Key. Tidak bisa dikembalikan. Hapus browser data = kehilangan akses."
    }

@router.post("/auto-login")
def auto_login(data: AutoLogin, r: Request, db: Session = Depends(get_db)):
    ip = _ip(r)
    if is_blacklisted(ip): raise HTTPException(429, "IP diblokir")
    try:
        priv_key = serialization.load_pem_private_key(data.private_key_pem.encode(), password=None)
        pub_bytes = priv_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode().strip()
    except Exception:
        record_fail(ip); raise HTTPException(401, "Private key tidak valid")

    u = db.query(User).filter(User.registration_complete == True).filter(
        (User.public_key_pem == pub_bytes) | (User.public_key_pem == pub_bytes + "\n")
    ).first()
    if not u: record_fail(ip); raise HTTPException(404, "Akun tidak ditemukan untuk private key ini")

    mr = db.query(MachineRegistry).filter(MachineRegistry.user_id == u.id).first()
    if mr and mr.machine_fingerprint != data.machine_fingerprint:
        record_fail(ip); raise HTTPException(403, "Akun hanya dapat diakses dari perangkat yang digunakan saat pendaftaran")

    tok = _token({"sub": u.id, "nickname": u.nickname})
    ticket = make_ws_ticket(u.id)
    return {
        "access_token": tok, "token_type": "bearer", "ws_ticket": ticket,
        "nickname": u.nickname, "full_name": u.full_name, "status": u.status,
        "championship_field": u.field_championship, "eliminated": u.eliminated,
        "avatar_id": u.avatar_id, "audio_granted": u.audio_granted,
        "exit_count": u.exit_count, "age_verified": u.age_verified
    }

@router.post("/audio-grant")
def audio_grant(data: AudioGrant, r: Request, db: Session = Depends(get_db)):
    u = _user(r, db)
    u.audio_granted = data.granted
    db.commit()
    return {"ok": True}

@router.post("/exit-event")
def exit_event(data: ExitEvent, r: Request, db: Session = Depends(get_db)):
    from championships import is_open
    u = _user(r, db)
    if not is_open(): return {"penalty": False}
    u.exit_count = data.count
    penalty_applied = False
    if data.count > 3:
        from championships import ensure_score, week_day
        from config import CHAMPIONSHIP_FIELDS
        w, d = week_day()
        fname = CHAMPIONSHIP_FIELDS.get(u.field_championship)
        if fname:
            sc = ensure_score(db, u.id, fname, w, d)
            penalty = sc.raw_score * 0.08
            sc.raw_score -= penalty
            penalty_applied = True
    db.commit()
    return {"exit_count": u.exit_count, "penalty": penalty_applied}

@router.post("/select-fields")
def select_fields(data: FieldSel, r: Request, db: Session = Depends(get_db)):
    u = _user(r, db)
    if data.multiple_choice_fields:
        inv = [f for f in data.multiple_choice_fields if f not in MULTIPLE_CHOICE_FIELDS]
        if inv: raise HTTPException(400, f"Bidang tidak valid: {inv}")
        u.field_multiple_choice = data.multiple_choice_fields
    if data.championship_field is not None:
        if data.championship_field not in CHAMPIONSHIP_FIELDS:
            raise HTTPException(400, "Bidang 1-8")
        if u.field_championship and u.field_championship != data.championship_field:
            raise HTTPException(409, "Bidang sudah dipilih")
        u.field_championship = data.championship_field
    db.commit()
    return {
        "success": True,
        "multiple_choice_fields": u.field_multiple_choice,
        "championship_field": u.field_championship,
        "championship_field_name": CHAMPIONSHIP_FIELDS.get(u.field_championship, "Belum dipilih")
    }

@router.get("/profile")
def profile(r: Request, db: Session = Depends(get_db)):
    u = _user(r, db)
    from championships import mc_profile_stats
    stats = [mc_profile_stats(db, u.id, f) for f in (u.field_multiple_choice or [])]
    return {
        "nickname": u.nickname, "full_name": u.full_name, "status": u.status,
        "championship_field": CHAMPIONSHIP_FIELDS.get(u.field_championship, "Belum dipilih"),
        "eliminated": u.eliminated, "multiple_choice_stats": stats,
        "avatar_id": u.avatar_id, "audio_granted": u.audio_granted,
        "exit_count": u.exit_count, "age_verified": u.age_verified
    }
