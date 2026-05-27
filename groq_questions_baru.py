import json, secrets, time
from groq import Groq
from sqlalchemy.orm import Session
from models import Question
import config

GROQ_KEYS = getattr(config, "GROQ_KEYS", [getattr(config, "GROQ_API_KEY", "")])
GROQ_KEYS = [k for k in GROQ_KEYS if k]
current_key_idx = 0
MODEL = "llama-3.1-8b-instant"

def _id(): return secrets.token_hex(16)

def _g(sys_prompt: str, usr: str, mt: int = 5500) -> str:
    global current_key_idx
    client = Groq(api_key=GROQ_KEYS[current_key_idx])
    r = client.chat.completions.create(
        model=MODEL, max_tokens=mt, temperature=0.7,
        messages=[{"role":"system","content":sys_prompt},{"role":"user","content":usr}]
    )
    return r.choices[0].message.content

def _save(db: Session, data: list, field: str, week: int, ttype: str, diff: str) -> list[Question]:
    saved = []
    if not isinstance(data, list): return saved
    for idx, q in enumerate(data):
        val = q.get("question") or q.get("sequence_given") or q.get("statement") or ""
        q_text = json.dumps(val) if isinstance(val, (list, dict)) else str(val)
        
        obj = Question(
            id=_id(), field=field, week=week, test_type=ttype, difficulty=diff,
            sequence_index=idx, sequence_group=f"{field}_{week}_{ttype}",
            question_text=q_text
        )
        
        if ttype in ["multiple_choice", "grand_prix_pg"]:
            obj.options_json = {"a":str(q.get("option_a","")),"b":str(q.get("option_b","")),"c":str(q.get("option_c","")),"d":str(q.get("option_d",""))}
            obj.correct_answer = str(q.get("correct_answer","")).upper()
        elif ttype == "memory_test":
            obj.correct_answer = str(q.get("next_element",""))
            obj.options_json = {"options": [str(x) for x in q.get("options",[])], "correct_index": int(q.get("correct_index", 0))}
        elif ttype == "click_test":
            obj.option_a = str(q.get("option_a",""))
            obj.option_b = str(q.get("option_b",""))
            obj.correct_answer = str(q.get("correct_answer","")).upper()
            obj.context_after = str(q.get("context_after",""))
        elif ttype == "flash_card":
            obj.correct_answer = str(q.get("example_answer",""))
            obj.options_json = {"keywords": [str(x) for x in q.get("keywords",[])]}
        elif ttype == "incoexistent":
            obj.options_json = {"a":str(q.get("option_a","")),"b":str(q.get("option_b","")),"c":str(q.get("option_c","")),"d":str(q.get("option_d",""))}
            obj.correct_answer = str(q.get("incoexistent_answer","")).upper()
        elif ttype == "one_word":
            obj.correct_answer = str(q.get("correct_answer","")).lower()
            obj.options_json = {"accepted": [str(x) for x in q.get("accepted_variations",[])]}
        
        db.add(obj)
        saved.append(obj)
    db.commit()
    return saved

def get_questions(db: Session, field: str, week: int, ttype: str, seed: int, status: str = "mahasiswa") -> list[Question]:
    qs = db.query(Question).filter(Question.field==field, Question.week==week, Question.test_type==ttype).all()
    if not qs:
        diff = "pelajar" if status == "Pelajar" else "mahasiswa"
        raw = _g("Hanya JSON array.", f"Buat soal {ttype} {field} tingkat {diff}. Output JSON array.")
        
        data = []
        try:
            start, end = raw.find("["), raw.rfind("]")
            if start != -1 and end != -1:
                data = json.loads(raw[start:end+1])
        except:
            data = []
            
        qs = _save(db, data, field, week, ttype, diff)
    return list(qs)import json, secrets, time
from groq import Groq
from sqlalchemy.orm import Session
from models import Question
import config

GROQ_KEYS = getattr(config, "GROQ_KEYS", [getattr(config, "GROQ_API_KEY", "")])
GROQ_KEYS = [k for k in GROQ_KEYS if k]
current_key_idx = 0
MODEL = "llama-3.1-8b-instant"

def _id(): return secrets.token_hex(16)

def _g(sys_prompt: str, usr: str, mt: int = 5500) -> str:
    global current_key_idx
    client = Groq(api_key=GROQ_KEYS[current_key_idx])
    r = client.chat.completions.create(
        model=MODEL, max_tokens=mt, temperature=0.7,
        messages=[{"role":"system","content":sys_prompt},{"role":"user","content":usr}]
    )
    return r.choices[0].message.content

def _save(db: Session, data: list, field: str, week: int, ttype: str, diff: str) -> list[Question]:
    saved = []
    if not isinstance(data, list): return saved
    for idx, q in enumerate(data):
        val = q.get("question") or q.get("sequence_given") or q.get("statement") or ""
        q_text = json.dumps(val) if isinstance(val, (list, dict)) else str(val)
        
        obj = Question(
            id=_id(), field=field, week=week, test_type=ttype, difficulty=diff,
            sequence_index=idx, sequence_group=f"{field}_{week}_{ttype}",
            question_text=q_text
        )
        
        if ttype in ["multiple_choice", "grand_prix_pg"]:
            obj.options_json = {"a":str(q.get("option_a","")),"b":str(q.get("option_b","")),"c":str(q.get("option_c","")),"d":str(q.get("option_d",""))}
            obj.correct_answer = str(q.get("correct_answer","")).upper()
        elif ttype == "memory_test":
            obj.correct_answer = str(q.get("next_element",""))
            obj.options_json = {"options": [str(x) for x in q.get("options",[])], "correct_index": int(q.get("correct_index", 0))}
        elif ttype == "click_test":
            obj.option_a = str(q.get("option_a",""))
            obj.option_b = str(q.get("option_b",""))
            obj.correct_answer = str(q.get("correct_answer","")).upper()
            obj.context_after = str(q.get("context_after",""))
        elif ttype == "flash_card":
            obj.correct_answer = str(q.get("example_answer",""))
            obj.options_json = {"keywords": [str(x) for x in q.get("keywords",[])]}
        elif ttype == "incoexistent":
            obj.options_json = {"a":str(q.get("option_a","")),"b":str(q.get("option_b","")),"c":str(q.get("option_c","")),"d":str(q.get("option_d",""))}
            obj.correct_answer = str(q.get("incoexistent_answer","")).upper()
        elif ttype == "one_word":
            obj.correct_answer = str(q.get("correct_answer","")).lower()
            obj.options_json = {"accepted": [str(x) for x in q.get("accepted_variations",[])]}
        
        db.add(obj)
        saved.append(obj)
    db.commit()
    return saved

def get_questions(db: Session, field: str, week: int, ttype: str, seed: int, status: str = "mahasiswa") -> list[Question]:
    qs = db.query(Question).filter(Question.field==field, Question.week==week, Question.test_type==ttype).all()
    if not qs:
        diff = "pelajar" if status == "Pelajar" else "mahasiswa"
        raw = _g("Hanya JSON array.", f"Buat soal {ttype} {field} tingkat {diff}. Output JSON array.")
        
        data = []
        try:
            start, end = raw.find("["), raw.rfind("]")
            if start != -1 and end != -1:
                data = json.loads(raw[start:end+1])
        except:
            data = []
            
        qs = _save(db, data, field, week, ttype, diff)
    return list(qs)
