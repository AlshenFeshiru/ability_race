import time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from database import get_db
from models import Payment, User
from security import verify_ctrl, keccak256, is_blacklisted, record_fail
from config import ADMIN_TOKEN, CHAMPIONSHIP_FIELDS

router = APIRouter()

def _ip(r: Request) -> str:
    fwd = r.headers.get("X-Forwarded-For","")
    return fwd.split(",")[0].strip() if fwd else (r.client.host if r.client else "0.0.0.0")

def _auth(token: str, ts: int, sig: str, endpoint: str, ip: str):
    if is_blacklisted(ip): raise HTTPException(429,"IP diblokir")
    if not verify_ctrl(endpoint, ts, sig): record_fail(ip); raise HTTPException(401,"KECCAK signature tidak valid atau expired")
    if token != ADMIN_TOKEN: record_fail(ip); raise HTTPException(403,"Token admin tidak valid")

class VerifyPay(BaseModel):
    payment_id: str; admin_token: str; timestamp: int; signature: str

class AdminReq(BaseModel):
    admin_token: str

@router.post("/verify-payment")
def verify_payment(data: VerifyPay, r: Request, db: Session = Depends(get_db)):
    _auth(data.admin_token, data.timestamp, data.signature, "/admin/verify-payment", _ip(r))
    p = db.query(Payment).filter(Payment.id == data.payment_id).first()
    if not p: raise HTTPException(404,"Payment tidak ditemukan")
    if p.verified: return {"success":False,"message":"Sudah diverifikasi"}
    p.verified = True; p.verified_at = datetime.now(timezone.utc)
    p.verified_by = keccak256(data.admin_token.encode())[:16]
    u = db.query(User).filter(User.id == p.user_id).first()
    if u: u.payment_verified = True
    db.commit()
    return {"success":True,"payment_id":data.payment_id,"user_id":p.user_id}

@router.post("/pending-payments")
def pending(data: AdminReq, r: Request, db: Session = Depends(get_db)):
    if data.admin_token != ADMIN_TOKEN: record_fail(_ip(r)); raise HTTPException(403,"Token tidak valid")
    payments = db.query(Payment).filter(Payment.verified == False).all()
    return {"count":len(payments),"payments":[{"payment_id":p.id,"user_id":p.user_id,"bank_reference":p.bank_reference,"amount":p.amount,"created_at":p.created_at.isoformat()} for p in payments]}

@router.post("/participants")
def participants(data: AdminReq, r: Request, db: Session = Depends(get_db)):
    if data.admin_token != ADMIN_TOKEN: record_fail(_ip(r)); raise HTTPException(403,"Token tidak valid")
    users = db.query(User).filter(User.registration_complete == True).all()
    return {"total":len(users),"participants":[{"nickname":u.nickname,"full_name":u.full_name,"status":u.status,"field":CHAMPIONSHIP_FIELDS.get(u.field_championship,"Belum dipilih"),"eliminated":u.eliminated} for u in users]}

@router.get("/sign")
def sign(endpoint: str, r: Request):
    if is_blacklisted(_ip(r)): raise HTTPException(429,"IP diblokir")
    from security import sign_ctrl
    ts = int(time.time())
    return {"endpoint":endpoint,"timestamp":ts,"signature":sign_ctrl(endpoint,ts),"valid_for":"5 menit"}
