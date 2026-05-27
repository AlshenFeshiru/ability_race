mkdir -p ~/ability_race/data
docker cp ability_race:/data/ability_race.db ~/ability_race/data/ability_race.db
python3 - << 'PYEOF'
import sqlite3, json, os

db_path = os.path.expanduser('~/ability_race/data/ability_race.db')
export_path = os.path.expanduser('~/ability_race/data/questions_export.json')

db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row
questions = [dict(r) for r in db.execute("SELECT * FROM questions").fetchall()]

with open(export_path, 'w') as f:
    json.dump(questions, f)

db.close()
print(f"Exported {len(questions)} questions")
PYEOF
