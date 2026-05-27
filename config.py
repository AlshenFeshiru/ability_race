import os
from datetime import datetime
from zoneinfo import ZoneInfo

WIB = ZoneInfo("Asia/Jakarta")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "syamailcoin_PoE_SAI288_ar_2026_keccak")
DSS_KEY_ONE = os.environ.get("DSS_KEY_ONE", "dss_k1_ar_nsac288_2026").encode()
DSS_KEY_TWO = os.environ.get("DSS_KEY_TWO", "dss_k2_ar_blockrecursive_2026").encode()
KECCAK_CTRL = os.environ.get("KECCAK_CTRL", "keccak_ctrl_syamail_28836_2026").encode()
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "arysq_admin_ar_2026_poe")
BCA_ACCOUNT = "3741912102"
REGISTRATION_FEE = 100000
SERVER_PORT = 28836
CHAMPIONSHIPS_START = datetime(2026, 6, 21, 10, 0, 0, tzinfo=WIB)
CHAMPIONSHIPS_END   = datetime(2026, 7, 20, 23, 59, 59, tzinfo=WIB)
SEMIFINAL_DATE      = datetime(2026, 7, 19, 10, 0, 0, tzinfo=WIB)
FINAL_DATE          = datetime(2026, 7, 20, 10, 0, 0, tzinfo=WIB)
SCORE_REVEAL_DAYS   = [7, 14, 21, 28, 29, 30]
MULTIPLE_CHOICE_FIELDS = [
    "Elektro","Ekonomi","Akuntansi","Rekayasa Perangkat Lunak",
    "Fisika","Biologi","Kimia","Aktuaria","Komputer","Hukum",
    "Filsafat","Psikologi","Marketing","Geografi","Sosiologi"
]
CHAMPIONSHIP_FIELDS = {
    1:"Ekonomi",2:"Geografi",3:"IT",4:"Aktuaria",
    5:"Fisika",6:"Sosiologi",7:"Kimia",8:"Biologi"
}
ABILITY_POOL_GENERAL = [
    "steal_5","protect_5","steal_10","protect_10","invisible",
    "steal_ability","ability_protection","teleport","recovery",
    "darkness","lightness","freeze","rock","mirror"
]
ABILITY_POOL_IT      = ABILITY_POOL_GENERAL + ["logical_fallacy"]
ABILITY_POOL_EKONOMI = ABILITY_POOL_GENERAL + ["cheat_score"]
RARE_ABILITY        = "scorch"
SCORCH_PROBABILITY  = 0.05
ALGORITHM           = "HS256"
TOKEN_EXPIRE_MIN    = 1440
NODE_R              = 8.314
NODE_GAMMA          = 1.4
MC_QUESTIONS        = 25
MC_TIME_PER_Q       = 50
ELIM_THRESHOLD      = 51
GP_PG_COUNT         = 10
GP_PG_TIME          = 10
GP_PHASE2_H         = 3
GP_PHASE3_H         = 2
SCORE_CORRECT       = 5
SCORE_WRONG         = -1
SCORE_SKIP          = 0
STREAK_THRESHOLD    = 10
ABILITY_OPTIONS     = 4
FREEZE_DUR          = 300
ROCK_DUR            = 300
INVISIBLE_DUR       = 600
DARKNESS_DUR        = 12
TELEPORT_DUR        = 30
MIRROR_MAX          = 5
SCORCH_MAX          = 2
KECCAK_NONCE_TTL    = 300
MAX_FAIL            = 10
BLACKLIST_DUR       = 3600
