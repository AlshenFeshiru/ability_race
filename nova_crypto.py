import os, time, random, struct, hashlib, sqlite3, subprocess
from Crypto.Hash import keccak as _keccak

def rotl(v: int, s: int, b: int = 64) -> int:
    s %= b
    return ((v << s) | (v >> (b - s))) & ((1 << b) - 1)

def rotr(v: int, s: int, b: int = 64) -> int:
    s %= b
    return ((v >> s) | (v << (b - s))) & ((1 << b) - 1)

def get_ram_state() -> int:
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        free = int(lines[1].split()[1])
        avail = int(lines[2].split()[1]) if len(lines) > 2 else free
        return (free ^ avail) * (free + avail + 1)
    except Exception:
        return id(object()) ^ os.getpid()

def vector_absorb(state: int, data: bytes) -> int:
    for i in range(0, len(data), 8):
        chunk = data[i:i+8].ljust(8, b'\x00')
        ci = int.from_bytes(chunk, 'big')
        state = rotl(state, 13) ^ ci
        state = rotl(state, 7) & 0xFFFFFFFFFFFFFFFF
    return state

def nova_fold(point_x: int, ram: int, iteration: int) -> bytes:
    folded = rotl(point_x ^ ram, 32) ^ rotl(iteration * 0xDEADBEEFCAFEBABE, 17)
    folded = vector_absorb(folded, struct.pack('>QQI', point_x, ram, iteration))
    k = _keccak.new(digest_bits=256)
    k.update(struct.pack('>Q', folded & 0xFFFFFFFFFFFFFFFF))
    k.update(b'\x4E\x4F\x56\x41\x5F\x53\x59\x41\x4D\x41\x49\x4C')
    return k.digest()

def nova_encrypt_success(px: int, py: int, pz: int, ram: int) -> str:
    seed = struct.pack('>QQQ', px, py, pz) + struct.pack('>Q', ram) + os.urandom(8)
    k = _keccak.new(digest_bits=256)
    k.update(seed)
    first = k.hexdigest()
    k2 = _keccak.new(digest_bits=256)
    k2.update(first.encode() + struct.pack('>Q', rotl(px ^ pz, 32)))
    return k2.hexdigest()

def nutshell_fallback(db_path: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ['sqlite3', db_path, 'PRAGMA integrity_check;'],
            capture_output=True, text=True, timeout=10
        )
        if 'ok' in result.stdout.lower():
            return True, hashlib.sha256(result.stdout.encode()).hexdigest()
        return False, ""
    except Exception:
        return False, ""

def nova_unlock(db_path: str) -> tuple[bool, str]:
    ram = get_ram_state()
    point_x = int.from_bytes(hashlib.sha256(db_path.encode()).digest()[:8], 'big')

    keys = [nova_fold(point_x, ram, i) for i in range(6)]

    for attempt, key in enumerate(keys):
        ki = int.from_bytes(key[:8], 'big')
        r90 = rotl(ki, 32)
        try:
            conn = sqlite3.connect(db_path, timeout=1.2)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=1200")
            res = conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
            conn.close()
            if res is not None:
                py = rotl(r90, 32)
                pz = rotl(py, 32)
                sig = nova_encrypt_success(point_x, py, pz, ram)
                return True, sig
        except sqlite3.OperationalError:
            if attempt == 5:
                for j in range(6):
                    time.sleep(1.1)
                    kj = int.from_bytes(keys[j][:8], 'big')
                    rj = rotl(kj, 32)
                    try:
                        conn = sqlite3.connect(db_path, timeout=0.8)
                        conn.execute("PRAGMA journal_mode=WAL")
                        conn.close()
                        sig = nova_encrypt_success(point_x, rotl(rj, 32), rotl(rj, 64 % 64 or 1), ram)
                        return True, sig
                    except Exception:
                        continue

    rk_bytes = nova_fold(point_x, random.getrandbits(64), random.getrandbits(8))
    for _ in range(20):
        rk = int.from_bytes(rk_bytes[:8], 'big')
        if random.random() < 0.5:
            rk = rotl(rk, random.randint(1, 31))
        else:
            rk = rotr(rk, random.randint(1, 31))
        rk_bytes = struct.pack('>Q', rk & 0xFFFFFFFFFFFFFFFF) + rk_bytes[8:]
        try:
            conn = sqlite3.connect(db_path, timeout=0.5)
            res = conn.execute("SELECT 1").fetchone()
            conn.close()
            if res:
                sig = nova_encrypt_success(point_x, rk, rotl(rk, 32), ram)
                return True, sig
        except Exception:
            time.sleep(0.15)
            continue

    return nutshell_fallback(db_path)

def nova_guard_db(db_path: str) -> bool:
    ok, sig = nova_unlock(db_path)
    if ok and sig:
        k = _keccak.new(digest_bits=256)
        k.update(sig.encode() + struct.pack('>Q', get_ram_state()))
        lock_1 = k.hexdigest()
        k2 = _keccak.new(digest_bits=256)
        k2.update(lock_1.encode() + os.urandom(4))
        lock_2 = k2.hexdigest()
        return True
    return False
