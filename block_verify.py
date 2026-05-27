import json
from security import dss256, keccak256
from config import CHAMPIONSHIP_FIELDS, DSS_KEY_ONE, DSS_KEY_TWO

BLOCK_TARGETS = {
    "Ekonomi":  50,
    "IT":       45,
    "Fisika":   42,
    "Kimia":    40,
    "Biologi":  38,
    "Aktuaria": 35,
    "Geografi": 32,
    "Sosiologi":30,
}

def lock_block(field: str, question_count: int, week: int, ttype: str) -> dict:
    payload = json.dumps({
        "field": field,
        "question_count": question_count,
        "week": week,
        "ttype": ttype,
        "target": BLOCK_TARGETS.get(field, 25)
    }, sort_keys=True).encode()
    lock_1 = dss256(payload)
    lock_2 = keccak256((lock_1 + field + str(week)).encode())
    return {"lock_1": lock_1, "lock_2": lock_2, "field": field, "week": week, "count": question_count}

def verify_all_blocks(db) -> dict:
    from models import Question
    from config import CHAMPIONSHIP_FIELDS
    WEEK_TYPES = {1:"flash_card",2:"click_test",3:"incoexistent",4:"one_word",5:"memory_test",6:"grand_prix_pg"}
    results = {}
    all_pass = True
    for fid, fname in CHAMPIONSHIP_FIELDS.items():
        field_blocks = {}
        for week, ttype in WEEK_TYPES.items():
            count = db.query(Question).filter(
                Question.field == fname, Question.week == week, Question.test_type == ttype
            ).count()
            target = BLOCK_TARGETS.get(fname, 25)
            locked = lock_block(fname, count, week, ttype)
            status = "PASS" if count >= min(5, target // 4) else "FAIL"
            if status == "FAIL":
                all_pass = False
            field_blocks[f"W{week}_{ttype}"] = {**locked, "status": status}
        results[fname] = field_blocks
    results["__all_pass__"] = all_pass
    return results
