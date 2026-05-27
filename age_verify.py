from groq import Groq
from config import GROQ_API_KEY
import json

_client = Groq(api_key=GROQ_API_KEY)

def infer_participant_class(nickname: str, full_name: str, status: str) -> dict:
    system = (
        "Kamu adalah sistem verifikasi peserta kompetisi pelajar Indonesia. "
        "Analisis nickname dan nama lengkap yang diberikan. "
        "Tentukan apakah kombinasi nama ini kemungkinan besar milik pelajar/mahasiswa aktif (usia 13-25 tahun) "
        "atau bukan. Perhatikan: nama Indonesia yang umum untuk usia sekolah, pola nickname yang digunakan generasi muda, "
        "pola nama yang mengindikasikan profesi dewasa atau usia tua. "
        "Kembalikan HANYA JSON: {\"verdict\": \"student\" atau \"adult\" atau \"uncertain\", "
        "\"confidence\": 0.0-1.0, \"reason\": \"alasan singkat\", \"risk_level\": \"low\"/\"medium\"/\"high\"}"
    )
    user = f"Nickname: {nickname}\nNama Lengkap: {full_name}\nStatus yang diklaim: {status}"
    try:
        r = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            max_tokens=200, temperature=0.1
        )
        raw = r.choices[0].message.content.strip()
        if raw.startswith("```"): raw = raw[raw.find("\n")+1:]
        if raw.endswith("```"): raw = raw[:raw.rfind("```")]
        return json.loads(raw.strip())
    except Exception:
        return {"verdict":"uncertain","confidence":0.5,"reason":"Verifikasi tidak dapat diselesaikan","risk_level":"medium"}

def is_likely_student(result: dict) -> bool:
    if result.get("verdict") == "adult" and result.get("confidence", 0) > 0.8:
        return False
    return True
