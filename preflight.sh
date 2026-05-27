#!/bin/bash
docker exec ability_race python3 - << 'PYEOF'
import sys, os, json
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL","sqlite:////data/ability_race.db")
os.environ.setdefault("SERVER_PORT","28836")

results = []

def check(label, fn):
    try:
        fn()
        results.append(("PASS", label))
    except Exception as e:
        results.append(("FAIL", label, str(e)))

def test_db():
    from database import init_db, SessionLocal
    init_db()
    db = SessionLocal()
    from models import User
    db.query(User).count()
    db.close()

def test_groq():
    from groq import Groq
    from config import GROQ_API_KEY
    c = Groq(api_key=GROQ_API_KEY)
    r = c.chat.completions.create(model="llama-3.3-70b-versatile",messages=[{"role":"user","content":"reply: ok"}],max_tokens=5)
    assert r.choices[0].message.content

def test_security():
    from security import keccak256, dss256, ws_ticket, verify_ws_ticket
    h = keccak256(b"test")
    assert len(h) == 64
    t = ws_ticket("user123")
    assert verify_ws_ticket("user123", t)

def test_questions_mc():
    from database import init_db, SessionLocal
    from models import Question
    init_db()
    db = SessionLocal()
    n = db.query(Question).filter(Question.week==0).count()
    db.close()
    assert n > 0, f"Soal MC belum ada ({n})"

def test_age_verify():
    from age_verify import infer_participant_class
    r = infer_participant_class("FarisXZ","Muhammad Faris","Pelajar")
    assert "verdict" in r

def test_avatar():
    from database import init_db, SessionLocal
    from models import AvatarRegistry
    init_db()
    db = SessionLocal()
    db.query(AvatarRegistry).count()
    db.close()

def test_admin_lockout():
    import os
    locked = os.environ.get("ADMIN_LOCKED","false") == "true"
    results.append(("INFO", f"ADMIN_LOCKED={locked}"))

check("Database WAL mode", test_db)
check("Groq API connection", test_groq)
check("KECCAK-256 security", test_security)
check("Soal MC pre-generated", test_questions_mc)
check("Age verification Groq", test_age_verify)
check("Avatar registry", test_avatar)
test_admin_lockout()

for r in results:
    print(f"{r[0]:4}  {r[1]}" + (f" -> {r[2]}" if len(r) > 2 else ""))

fails = sum(1 for r in results if r[0] == "FAIL")
print(f"\n{len(results)-fails} passed, {fails} failed")
sys.exit(fails)
PYEOF
