import os, json, sys
sys.path.insert(0, '/app')
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL","sqlite:////data/ability_race.db"))
os.environ.setdefault("SERVER_PORT","7860")

from database import init_db, SessionLocal
from models import Question
import secrets

def run():
    init_db()
    db = SessionLocal()
    existing = db.query(Question).count()
    if existing > 0:
        db.close()
        return
    export_path = '/app/data/questions_export.json'
    if not os.path.exists(export_path):
        db.close()
        return
    with open(export_path) as f:
        questions = json.load(f)
    for q in questions:
        q.pop('id', None)
        obj = Question(
            id=secrets.token_hex(16),
            field=q.get('field',''),
            week=q.get('week',0),
            test_type=q.get('test_type',''),
            question_text=q.get('question_text',''),
            option_a=q.get('option_a'),
            option_b=q.get('option_b'),
            options_json=q.get('options_json'),
            correct_answer=q.get('correct_answer',''),
            sequence_index=q.get('sequence_index',0),
            sequence_group=q.get('sequence_group'),
            difficulty=q.get('difficulty','mahasiswa'),
            context_after=q.get('context_after')
        )
        db.add(obj)
    db.commit()
    db.close()

if __name__ == '__main__':
    run()
