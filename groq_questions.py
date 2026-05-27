import json, random, secrets, time
from groq import Groq
from sqlalchemy.orm import Session
from models import Question
import config

# Otomatis deteksi daftar kunci (GROQ_KEYS), jika tidak ada pakai kunci tunggal (GROQ_API_KEY)
GROQ_KEYS = getattr(config, "GROQ_KEYS", [getattr(config, "GROQ_API_KEY", "")])
GROQ_KEYS = [k for k in GROQ_KEYS if k] # Bersihkan data kosong
current_key_idx = 0

MODEL  = "llama-3.3-70b-versatile"

def _id(): return secrets.token_hex(16)

def _g(sys_prompt: str, usr: str, mt: int = 4096) -> str:
    global current_key_idx
    for attempt in range(12):
        try:
            # Menggunakan kunci aktif sesuai indeks rotasi
            kunci_aktif = GROQ_KEYS[current_key_idx]
            client = Groq(api_key=kunci_aktif)
            
            r = client.chat.completions.create(
                model=MODEL, max_tokens=mt, temperature=0.7,
                messages=[
                    {"role":"system","content":sys_prompt},
                    {"role":"user","content":usr}
                ]
            )
            return r.choices[0].message.content
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate_limit" in msg or "rate limit" in msg:
                if len(GROQ_KEYS) > 1:
                    current_key_idx = (current_key_idx + 1) % len(GROQ_KEYS)
                    print(f"\n[!] Rate Limit Terdeteksi! Otomatis rotasi ke API Key indeks ke-{current_key_idx}...")
                    time.sleep(1)
                else:
                    wait = (2 ** attempt) * 3
                    print(f"\n[!] Rate Limit Terdeteksi! Hanya ada 1 key, ngerem dulu {wait} detik...")
                    time.sleep(wait)
                continue
            raise
    raise Exception("Groq rate limit: semua retry dan semua key habis")

def _j(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw[raw.find("\n")+1:]
    if raw.endswith("```"):
        raw = raw[:raw.rfind("```")]
    raw = raw.strip()
    start = raw.find("[")
    if start == -1:
        start = raw.find("{")
    if start > 0:
        raw = raw[start:]
    return json.loads(raw)

def _diff(status: str) -> str:
    return "SMA/SMK/sederajat" if status == "Pelajar" else "Perguruan Tinggi"

def gen_mc(field: str, status: str, n: int = 25) -> list:
    s = "Pembuat soal kompetisi Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain, tanpa markdown."
    u = f"Buat {n} soal pilihan ganda {field} tingkat {_diff(status)}. JSON array: question, option_a, option_b, option_c, option_d, correct_answer (A/B/C/D). Bahasa Indonesia."
    return _j(_g(s, u))

def gen_flash(field: str, status: str, n: int = 20) -> list:
    s = "Pembuat Flash Card kompetisi Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = f"Buat {n} soal 'Berikan Contoh' {field} tingkat {_diff(status)}. JSON: question, example_answer, keywords (array kata kunci)."
    return _j(_g(s, u))

def gen_click(field: str, status: str, n: int = 30) -> list:
    ctx = {
        "IT":"merangkai kode website HTML→CSS→JS secara berkesinambungan",
        "Ekonomi":"menganalisis skenario investasi dari awal hingga keputusan",
        "Fisika":"menyelesaikan masalah mekanika langkah demi langkah",
        "Kimia":"merancang dan menyelesaikan eksperimen kimia",
        "Biologi":"menganalisis siklus kehidupan makhluk hidup",
        "Geografi":"fenomena alam dari penyebab hingga dampak",
        "Aktuaria":"menghitung risiko asuransi dari data mentah",
        "Sosiologi":"menganalisis perubahan sosial dari individu ke kebijakan"
    }
    s = "Pembuat Click Test berkesinambungan Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = (f"Buat {n} soal Click Test berkesinambungan {field} tingkat {_diff(status)}. "
         f"Tema: {ctx.get(field,field)}. Setiap soal adalah lanjutan dari soal sebelumnya. "
         f"JSON: sequence_index (1..{n}), question, option_a, option_b, correct_answer (A/B), context_after.")
    return _j(_g(s, u, 6000))

def gen_incoexistent(field: str, status: str, n: int = 25) -> list:
    s = "Pembuat soal Which is Incoexistent Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = (f"Buat {n} soal pilihan ganda {field} tingkat {_diff(status)}. "
         f"Aturan: jawaban BENAR secara akademis adalah PILIHAN YANG SALAH untuk dipilih peserta. "
         f"JSON: question, option_a, option_b, option_c, option_d, "
         f"academically_correct (A/B/C/D), incoexistent_answer (yang HARUS dipilih).")
    return _j(_g(s, u))

def gen_one_word(field: str, status: str, n: int = 25) -> list:
    s = "Pembuat One Word Test Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = (f"Buat {n} soal jawaban satu kata {field} tingkat {_diff(status)}. "
         f"JSON: question, correct_answer (lowercase satu kata), accepted_variations (array lowercase).")
    return _j(_g(s, u))

def gen_memory(field: str, n: int = 20) -> list:
    types = {
        "IT":"kode pseudocode","Ekonomi":"rumus atau deret angka finansial",
        "Fisika":"persamaan fisika dalam urutan logis","Kimia":"reaksi kimia berurutan",
        "Biologi":"taksonomi atau siklus biologis","Geografi":"urutan fenomena geografis",
        "Aktuaria":"deret probabilitas atau mortalitas","Sosiologi":"tahapan teori sosial"
    }
    s = "Pembuat Memory Test kompetisi Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = (f"Buat {n} Memory Test {field}. Jenis: {types.get(field,field)}. "
         f"JSON: sequence_given (urutan yang ditampilkan), next_element (yang harus dicocokkan), "
         f"options (4 pilihan termasuk jawaban benar), correct_index (0-3).")
    return _j(_g(s, u))

def gen_gp_pg(field: str, n: int = 10) -> list:
    s = "Pembuat soal Grand Prix Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = (f"Buat {n} soal pilihan ganda TINGKAT RENDAH (jawab 10 detik) {field}. "
         f"JSON: question, option_a, option_b, option_c, option_d, correct_answer (A/B/C/D).")
    return _j(_g(s, u))

def gen_which_true(field: str, n: int = 80) -> list:
    s = "Pembuat Which Is True Grand Prix Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = (f"Buat {n} soal Which is True {field}. 2 pernyataan, pilih BENAR. "
         f"JSON: statement_a, statement_b, correct_answer (A/B).")
    return _j(_g(s, u, 8000))

def gen_matching(field: str, n: int = 50) -> list:
    s = "Pembuat Matching TRUE/FALSE Grand Prix Indonesia. Kembalikan HANYA JSON array valid tanpa teks lain."
    u = (f"Buat {n} soal Matching {field}. Pernyataan, rumus, atau perhitungan. "
         f"JSON: statement, correct_answer (TRUE/FALSE), source_context.")
    return _j(_g(s, u, 6000))

def gen_reasoning(field: str, status: str) -> list:
    rtypes = {
        "Ekonomi":"Jika-Maka keputusan ekonomi atau perhitungan investasi",
        "IT":"Merangkai potongan logika kode menjadi urutan yang benar",
        "Fisika":"Urutan langkah penyelesaian masalah fisika yang tepat",
        "Kimia":"Urutan langkah reaksi kimia yang valid",
        "Biologi":"Urutan proses biologis yang benar",
        "Geografi":"Hubungan sebab-akibat fenomena geografis",
        "Aktuaria":"Memilih metode perhitungan risiko yang tepat",
        "Sosiologi":"Urutan premis hingga kesimpulan teori sosial"
    }
    s = "Pembuat Reasoning Test Indonesia. Kembalikan HANYA JSON array valid tepat 3 soal tanpa teks lain."
    u = (f"Buat 3 Reasoning Test {field} tingkat {_diff(status)}. "
         f"Tipe: {rtypes.get(field,field)}. "
         f"JSON: question, type, option_a, option_b, correct_answer (A/B), explanation.")
    return _j(_g(s, u))

def _save(db: Session, data: list, field: str, week: int, ttype: str, diff: str) -> list[Question]:
    saved = []
    for idx, q in enumerate(data):
        obj = Question(
            id=_id(), field=field, week=week, test_type=ttype, difficulty=diff,
            sequence_index=idx, sequence_group=f"{field}_{week}_{ttype}"
        )
        if ttype in ["multiple_choice","grand_prix_pg"]:
            obj.question_text  = q.get("question","")
            obj.options_json   = {"a":q.get("option_a",""),"b":q.get("option_b",""),"c":q.get("option_c",""),"d":q.get("option_d","")}
            obj.correct_answer = q.get("correct_answer","").upper()
        elif ttype == "flash_card":
            obj.question_text  = q.get("question","")
            obj.correct_answer = q.get("example_answer","")
            obj.options_json   = {"keywords":q.get("keywords",[])}
        elif ttype == "click_test":
            obj.question_text  = q.get("question","")
            obj.option_a       = q.get("option_a","")
            obj.option_b       = q.get("option_b","")
            obj.correct_answer = q.get("correct_answer","").upper()
            obj.context_after  = q.get("context_after","")
        elif ttype == "incoexistent":
            obj.question_text  = q.get("question","")
            obj.options_json   = {"a":q.get("option_a",""),"b":q.get("option_b",""),"c":q.get("option_c",""),"d":q.get("option_d","")}
            obj.correct_answer = q.get("incoexistent_answer","").upper()
        elif ttype == "one_word":
            obj.question_text  = q.get("question","")
            obj.correct_answer = q.get("correct_answer","").lower()
            obj.options_json   = {"accepted":q.get("accepted_variations",[])}
        elif ttype == "memory_test":
            obj.question_text  = q.get("sequence_given","")
            obj.correct_answer = q.get("next_element","")
            obj.options_json   = {"options":q.get("options",[]),"correct_index":q.get("correct_index",0)}
        elif ttype == "which_is_true":
            obj.question_text  = "Pilih pernyataan yang BENAR:"
            obj.option_a       = q.get("statement_a","")
            obj.option_b       = q.get("statement_b","")
            obj.correct_answer = q.get("correct_answer","").upper()
        elif ttype == "matching_true_false":
            obj.question_text  = q.get("statement","")
            obj.correct_answer = q.get("correct_answer","").upper()
            obj.options_json   = {"context":q.get("source_context","")}
        elif ttype == "reasoning":
            obj.question_text  = q.get("question","")
            obj.option_a       = q.get("option_a","")
            obj.option_b       = q.get("option_b","")
            obj.correct_answer = q.get("correct_answer","").upper()
            obj.options_json   = {"type":q.get("type",""),"explanation":q.get("explanation","")}
        db.add(obj)
        saved.append(obj)
    db.commit()
    return saved

def get_questions(db: Session, field: str, week: int, ttype: str, seed: int, status: str = "mahasiswa") -> list[Question]:
    qs = db.query(Question).filter(
        Question.field==field, Question.week==week, Question.test_type==ttype
    ).order_by(Question.sequence_index).all()
    if not qs:
        diff = "pelajar" if status == "Pelajar" else "mahasiswa"
        gen_map = {
            "multiple_choice":      lambda: gen_mc(field, status),
            "flash_card":           lambda: gen_flash(field, status),
            "click_test":           lambda: gen_click(field, status),
            "incoexistent":         lambda: gen_incoexistent(field, status),
            "one_word":             lambda: gen_one_word(field, status),
            "memory_test":          lambda: gen_memory(field),
            "grand_prix_pg":        lambda: gen_gp_pg(field),
            "which_is_true":        lambda: gen_which_true(field),
            "matching_true_false":  lambda: gen_matching(field),
            "reasoning":            lambda: gen_reasoning(field, status),
        }
        gen_fn = gen_map.get(ttype, lambda: [])
        data = gen_fn()
        qs = _save(db, data, field, week, ttype, diff)
    out = list(qs)
    if ttype not in ["click_test","memory_test"]:
        random.Random(seed).shuffle(out)
    return out

def eval_one_word(ans: str, correct: str, accepted: list) -> bool:
    n = ans.strip().lower()
    return n == correct.lower() or n in [a.lower() for a in accepted]

def eval_flash(ans: str, keywords: list) -> bool:
    n = ans.lower()
    matched = sum(1 for kw in keywords if kw.lower() in n)
    return matched >= max(1, len(keywords)//2)
