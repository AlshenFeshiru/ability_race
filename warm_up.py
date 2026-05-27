import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DATABASE_URL", "sqlite:////data/ability_race.db")
os.environ.setdefault("SERVER_PORT", "28836")

from database import init_db, SessionLocal
from models import Question
from config import CHAMPIONSHIP_FIELDS, MULTIPLE_CHOICE_FIELDS
from groq_questions import (
    gen_mc, gen_flash, gen_click, gen_incoexistent, gen_one_word,
    gen_memory, gen_gp_pg, gen_which_true, gen_matching, _save, _diff
)

WEEK_TYPES = {
    1: "flash_card",
    2: "click_test",
    3: "incoexistent",
    4: "one_word",
    5: "memory_test",
    6: "grand_prix_pg",
}

GEN_MAP = {
    "flash_card":       lambda f, s: gen_flash(f, s),
    "click_test":       lambda f, s: gen_click(f, s),
    "incoexistent":     lambda f, s: gen_incoexistent(f, s),
    "one_word":         lambda f, s: gen_one_word(f, s),
    "memory_test":      lambda f, s: gen_memory(f),
    "grand_prix_pg":    lambda f, s: gen_gp_pg(f),
    "multiple_choice":  lambda f, s: gen_mc(f, s),
}

DELAY_BETWEEN = 4

def already_exists(db, field, week, ttype):
    return db.query(Question).filter(
        Question.field == field,
        Question.week == week,
        Question.test_type == ttype
    ).count() > 0

def warm_up():
    init_db()
    db = SessionLocal()
    statuses = ["Pelajar", "Mahasiswa"]
    total_done = 0
    total_skip = 0
    total_fail = 0

    for field in MULTIPLE_CHOICE_FIELDS:
        for status in statuses:
            if already_exists(db, field, 0, "multiple_choice"):
                n = db.query(Question).filter(
                    Question.field==field, Question.week==0, Question.test_type=="multiple_choice"
                ).count()
                print(f"SKIP  MC {field}/{status}: {n} soal sudah ada")
                total_skip += 1
                continue
            try:
                data = gen_mc(field, status)
                diff = _diff(status)
                qs = _save(db, data, field, 0, "multiple_choice", diff)
                print(f"DONE  MC {field}/{status}: {len(qs)} soal")
                total_done += 1
                time.sleep(DELAY_BETWEEN)
            except Exception as e:
                print(f"FAIL  MC {field}/{status}: {e}")
                total_fail += 1
                time.sleep(DELAY_BETWEEN * 2)

    for fid, fname in CHAMPIONSHIP_FIELDS.items():
        for week, ttype in WEEK_TYPES.items():
            if already_exists(db, fname, week, ttype):
                n = db.query(Question).filter(
                    Question.field==fname, Question.week==week, Question.test_type==ttype
                ).count()
                print(f"SKIP  Champ {fname}/W{week}/{ttype}: {n} soal sudah ada")
                total_skip += 1
                continue
            for status in ["Mahasiswa"]:
                try:
                    gen_fn = GEN_MAP.get(ttype, lambda f, s: [])
                    data = gen_fn(fname, status)
                    diff = _diff(status)
                    qs = _save(db, data, fname, week, ttype, diff)
                    print(f"DONE  Champ {fname}/W{week}/{ttype}: {len(qs)} soal")
                    total_done += 1
                    time.sleep(DELAY_BETWEEN)
                except Exception as e:
                    print(f"FAIL  Champ {fname}/W{week}/{ttype}: {e}")
                    total_fail += 1
                    time.sleep(DELAY_BETWEEN * 3)

    db.close()
    print(f"\nDone: {total_done} | Skip: {total_skip} | Fail: {total_fail}")
    print("Jalankan ulang warm_up.py jika ada FAIL — skip otomatis yang sudah ada")

if __name__ == "__main__":
    warm_up()
