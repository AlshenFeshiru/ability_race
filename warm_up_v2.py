import sys, os, time, json
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DATABASE_URL", "sqlite:////data/ability_race.db")
os.environ.setdefault("SERVER_PORT", "28836")

from database import init_db, SessionLocal
from models import Question
from config import CHAMPIONSHIP_FIELDS, MULTIPLE_CHOICE_FIELDS
from block_verify import BLOCK_TARGETS, lock_block, verify_all_blocks
from security import keccak256, dss256
import groq_questions as gq

MODELS_FALLBACK = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

WEEK_TYPES = {
    1: "flash_card",
    2: "click_test",
    3: "incoexistent",
    4: "one_word",
    5: "memory_test",
    6: "grand_prix_pg",
}

GEN_FN = {
    "flash_card":       lambda f, s: gq.gen_flash(f, s),
    "click_test":       lambda f, s: gq.gen_click(f, s),
    "incoexistent":     lambda f, s: gq.gen_incoexistent(f, s),
    "one_word":         lambda f, s: gq.gen_one_word(f, s),
    "memory_test":      lambda f, s: gq.gen_memory(f),
    "grand_prix_pg":    lambda f, s: gq.gen_gp_pg(f),
    "multiple_choice":  lambda f, s: gq.gen_mc(f, s),
}

def switch_model(model_idx: int) -> int:
    next_idx = (model_idx + 1) % len(MODELS_FALLBACK)
    gq.MODEL = MODELS_FALLBACK[next_idx]
    return next_idx

def exists(db, field, week, ttype):
    return db.query(Question).filter(
        Question.field == field, Question.week == week, Question.test_type == ttype
    ).count() > 0

def run():
    init_db()
    db = SessionLocal()
    model_idx = 0
    gq.MODEL = MODELS_FALLBACK[model_idx]
    done = skip = fail = 0

    print(f"Model: {gq.MODEL}")

    for field in MULTIPLE_CHOICE_FIELDS:
        if exists(db, field, 0, "multiple_choice"):
            skip += 1
            continue
        for attempt in range(3):
            try:
                data = gq.gen_mc(field, "Mahasiswa")
                saved = gq._save(db, data, field, 0, "multiple_choice", "mahasiswa")
                b = lock_block(field, len(saved), 0, "multiple_choice")
                done += 1
                time.sleep(3)
                break
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    model_idx = switch_model(model_idx)
                    time.sleep(4 * (attempt + 1))
                else:
                    fail += 1
                    break

    fields_order = sorted(
        CHAMPIONSHIP_FIELDS.items(),
        key=lambda x: BLOCK_TARGETS.get(x[1], 25),
        reverse=True
    )

    for fid, fname in fields_order:
        target = BLOCK_TARGETS.get(fname, 25)
        for week, ttype in WEEK_TYPES.items():
            if exists(db, fname, week, ttype):
                count = db.query(Question).filter(
                    Question.field == fname, Question.week == week, Question.test_type == ttype
                ).count()
                skip += 1
                continue
            for attempt in range(3):
                try:
                    gen_fn = GEN_FN.get(ttype, lambda f, s: [])
                    data = gen_fn(fname, "Mahasiswa")
                    saved = gq._save(db, data, fname, week, ttype, "mahasiswa")
                    b = lock_block(fname, len(saved), week, ttype)
                    lock_chain = keccak256((b["lock_1"] + b["lock_2"]).encode())
                    print(f"DONE {fname}/W{week}/{ttype}: {len(saved)} soal | LK:{lock_chain[:8]}")
                    done += 1
                    time.sleep(3)
                    break
                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        model_idx = switch_model(model_idx)
                        print(f"  switch → {gq.MODEL}")
                        time.sleep(5 * (attempt + 1))
                    else:
                        print(f"FAIL {fname}/W{week}/{ttype}: {e}")
                        fail += 1
                        break

    report = verify_all_blocks(db)
    db.close()

    print(f"\nDone:{done} Skip:{skip} Fail:{fail}")
    print(f"All blocks PASS: {report['__all_pass__']}")

    if not report["__all_pass__"]:
        print("Ada blok yang FAIL — jalankan ulang, skip otomatis yang sudah ada")

if __name__ == "__main__":
    run()
