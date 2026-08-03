# ==========================================================
# V25.ULTIMATE - HYBRID EDITION (YouTube + OBS)
# ALL-IN-ONE: OBS UI | AUTO-CONFIG | TRIPLE-WATCHDOG | SECURITY
# ==========================================================

import os, json, time, logging, threading, requests, heapq, random, re, datetime, queue, sys
from pathlib import Path
import shutil

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    OAUTH_LIBS_AVAILABLE = True
except ImportError:
    OAUTH_LIBS_AVAILABLE = False

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
from collections import defaultdict, deque
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from threading import Lock

# ==========================================================
# 1. CONFIGURATION & AUTO-SETUP
# ==========================================================
def ensure_config():
    env_path = BASE_DIR / ".env"
    existing_config = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing_config[k.strip()] = v.strip()

required_configs = {
    # Optional
    "CUSTOM_API_URL": "",
    "CUSTOM_API_KEY": "",
    "MODEL_NAME": "gemma4",
    "GEMINI_MODEL": "gemini-2.5-flash",
    "GEMINI_API_KEY": "",

    # Required
    "YOUTUBE_API_KEY": None,
    "CHANNEL_ID": None,
    "TEN_KENH": "",
}

optional_keys = {
    "CUSTOM_API_URL",
    "CUSTOM_API_KEY",
    "MODEL_NAME",
    "GEMINI_MODEL",
    "GEMINI_API_KEY",
}
   for key, default in required_configs.items():
    if existing_config.get(key):
        continue

    if default:
        val = default

    # Nếu là cấu hình tùy chọn thì để trống, không hỏi
    elif key in optional_keys:
        val = ""

    # Chỉ hỏi với cấu hình bắt buộc
    elif interactive:
        val = input(f"👉 Please enter {key}: ").strip()

        if not val:
            print(f"⚠️ {key} is required!")
            val = "MISSING"

    else:
        print(f"⚠️ Missing required config: {key}")
        val = "MISSING"

    existing_config[key] = val

    # Chi ghi lai file neu co thay doi - giu nguyen moi key khac nguoi dung tu them
    # (vd: AUTO_POST_CHAT, OBS_AUTO_START, CUSTOM_API_BOOT_WAIT...), khong ghi de toan bo .env
    if updated or not env_path.exists():
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join([f"{k}={v}" for k, v in existing_config.items()]))
    load_dotenv(env_path, override=True)

# --- Khởi tạo config ban đầu ---
ensure_config()

CUSTOM_API_URL = os.getenv("CUSTOM_API_URL")
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY")
MODEL_NAME     = os.getenv("MODEL_NAME")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")  # key chinh (tuong thich cu)

# Ho tro nhieu Gemini key - doc GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3...
# Neu co key cu (GEMINI_API_KEY) thi tu dong them vao dau danh sach
def _load_gemini_keys():
    keys = []
    if GEMINI_API_KEY:
        keys.append(GEMINI_API_KEY)
    for i in range(1, 20):
        k = os.getenv(f"GEMINI_API_KEY_{i}")
        if k and k not in keys:
            keys.append(k)
    return keys

GEMINI_API_KEYS = _load_gemini_keys()
_gemini_key_index = 0
_gemini_key_lock = Lock()

def _get_next_gemini_key():
    """Lay key Gemini tiep theo theo vong tron. Thread-safe."""
    global _gemini_key_index
    if not GEMINI_API_KEYS:
        return None
    with _gemini_key_lock:
        key = GEMINI_API_KEYS[_gemini_key_index % len(GEMINI_API_KEYS)]
        _gemini_key_index = (_gemini_key_index + 1) % len(GEMINI_API_KEYS)
        return key

def _rotate_gemini_key_on_error(bad_key):
    """Khi 1 key bi 429/loi, danh dau va chuyen sang key khac ngay."""
    global _gemini_key_index
    if not GEMINI_API_KEYS or len(GEMINI_API_KEYS) <= 1:
        return
    with _gemini_key_lock:
        try:
            bad_idx = GEMINI_API_KEYS.index(bad_key)
            # Chuyen sang key ke tiep sau key bi loi
            _gemini_key_index = (bad_idx + 1) % len(GEMINI_API_KEYS)
            logger.warning(f"[GEMINI] Key bi loi, chuyen sang key #{_gemini_key_index + 1}/{len(GEMINI_API_KEYS)}")
        except ValueError:
            pass
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/v1/chat/completions")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "llama3")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID      = os.getenv("CHANNEL_ID")
TEN_KENH        = os.getenv("TEN_KENH")
CUSTOM_API_BOOT_WAIT = int(os.getenv("CUSTOM_API_BOOT_WAIT", "13"))
AUTO_POST_CHAT = os.getenv("AUTO_POST_CHAT", "1").lower() in ("1", "true", "yes", "on")
SKIP_EXISTING_CHAT_ON_CONNECT = os.getenv("SKIP_EXISTING_CHAT_ON_CONNECT", "1").lower() in ("1", "true", "yes", "on")
CLIENT_SECRET_FILE = str(BASE_DIR / "client_secret.json")
OAUTH_TOKEN_FILE = str(BASE_DIR / "token.json")
YOUTUBE_OAUTH_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

FILE_OUTPUT = str(BASE_DIR / "ai_reply.txt")
LOG_FILE = str(BASE_DIR / "bot.log")
BLACKLIST_FILE = str(BASE_DIR / "blacklist.json")
WORKER_COUNT = 3 
SPAM_LIMIT, SPAM_WINDOW = 5, 10 
MAX_MSG_LENGTH, SYMBOL_RATIO_LIMIT = 300, 0.3
KEYWORD_BLACKLIST = ["hack", "cheat", "free robux", "tăng sub", "http://", "www."]
BAN_LEVELS = {1: 120, 2: 300, 3: 3600, 4: 86400, 5: 2592000}
PERM_BAN_THRESHOLD = 10 

WARNING_MESSAGES = {
    1: "⚠️ {user}, bị ăn gậy lần 1! AI im lặng 2 phút.",
    2: "🚫 {user}, tái phạm lần 2! Cấm vận 5 phút.",
    3: "💀 {user}, lần 3 rồi! Ban 1 giờ.",
    4: "🔥 {user}, ban 24 giờ!",
    5: "☢️ {user}, ban 30 ngày.",
    "perm": "⛔ {user}, vào SỔ ĐEN VĨNH VIỄN!"
}

MAX_CACHE_TTL, MAX_CACHE_SIZE = 300, 5000
QUEUE_BRIEF_THRESHOLD, QUEUE_OVERFLOW_THRESHOLD = 50, 500
WATCHDOG_CHECK_INTERVAL, WORKER_FREEZE_TIMEOUT = 10, 45

# ==========================================================
# 2. LOGGER & SESSION
# ==========================================================
logger = logging.getLogger()
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
fh = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
fh.setFormatter(_fmt)
ch = logging.StreamHandler()
ch.setFormatter(_fmt)
logger.addHandler(fh); logger.addHandler(ch)

session = requests.Session()
retry = Retry(total=3, backoff_factor=1.2, status_forcelist=[500, 502, 504])
session.mount("http://", HTTPAdapter(max_retries=retry))
session.mount("https://", HTTPAdapter(max_retries=retry))

# ==========================================================
# 2B. OAUTH - GUI POST COMMENT VAO YOUTUBE LIVE CHAT
# ==========================================================
_oauth_creds = None
_oauth_lock = Lock()
_bot_channel_id = None
_bot_channel_id_lock = Lock()

def get_bot_own_channel_id():
    """Lay channelId cua chinh tai khoan OAuth dang dung de post comment.
    Dung de loc bo qua tin nhan do chinh bot dang, tranh echo loop (bot tu tra loi chinh minh)."""
    global _bot_channel_id
    with _bot_channel_id_lock:
        if _bot_channel_id:
            return _bot_channel_id
    creds = get_oauth_credentials()
    if not creds:
        return None
    try:
        resp = session.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "id", "mine": "true"},
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                cid = items[0].get("id")
                with _bot_channel_id_lock:
                    _bot_channel_id = cid
                logger.info(f"[OAUTH] Da xac dinh channelId cua bot (de loc echo): {cid}")
                return cid
        logger.warning(f"[OAUTH] Khong lay duoc channelId cua bot (HTTP {resp.status_code}).")
    except Exception as e:
        logger.warning(f"[OAUTH] Loi lay channelId cua bot: {e}")
    return None

def get_oauth_credentials():
    """Lay/refresh OAuth credentials. Chi hoi login 1 lan dau, sau do tu luu token.json."""
    global _oauth_creds
    if not OAUTH_LIBS_AVAILABLE:
        logger.warning("[OAUTH] Thieu thu vien google-auth-oauthlib. Chay: pip install google-auth-oauthlib google-api-python-client --break-system-packages")
        return None
    with _oauth_lock:
        if _oauth_creds and _oauth_creds.valid:
            return _oauth_creds
        creds = None
        if os.path.exists(OAUTH_TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, YOUTUBE_OAUTH_SCOPES)
            except Exception as e:
                logger.warning(f"[OAUTH] Loi doc token.json: {e}")
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
                logger.info("[OAUTH] Da refresh token thanh cong.")
            except Exception as e:
                logger.warning(f"[OAUTH] Loi refresh token: {e}. Can dang nhap lai.")
                creds = None
        if not creds or not creds.valid:
            if not os.path.exists(CLIENT_SECRET_FILE):
                logger.error(f"[OAUTH] Khong tim thay {CLIENT_SECRET_FILE}. Khong the dang nhap.")
                return None
            try:
                logger.info("[OAUTH] Can dang nhap Google. Trinh duyet se mo ra, hay bam Allow.")
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, YOUTUBE_OAUTH_SCOPES)
                creds = flow.run_local_server(port=0)
                logger.info("[OAUTH] Dang nhap thanh cong!")
            except Exception as e:
                logger.error(f"[OAUTH] Loi dang nhap: {e}")
                return None
            with open(OAUTH_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        _oauth_creds = creds
        return creds

_chat_send_queue = queue.Queue(maxsize=200)
CHAT_SEND_MIN_INTERVAL = 1.5  # giay/tin, theo khuyen nghi YouTube
_recently_sent_texts = {}  # text(normalized) -> expiry timestamp, de phong chong echo loop
_recently_sent_lock = Lock()
RECENTLY_SENT_TTL = 30  # giay

def _mark_recently_sent(text):
    norm = text.strip().lower()
    with _recently_sent_lock:
        _recently_sent_texts[norm] = time.time() + RECENTLY_SENT_TTL
        # don dep nhe cac entry het han - chi quet voi xac suat 10% de giam lock contention khi chat dong
        if len(_recently_sent_texts) > 200 and random.random() < 0.1:
            now = time.time()
            for k in list(_recently_sent_texts.keys()):
                if _recently_sent_texts[k] <= now:
                    del _recently_sent_texts[k]

def is_recently_sent_by_bot(text):
    norm = text.strip().lower()
    now = time.time()
    with _recently_sent_lock:
        for sent_text, exp in _recently_sent_texts.items():
            if exp <= now:
                continue
            # So khop theo prefix (toi thieu 20 ky tu) vi YouTube co the chinh nhe khi hien thi lai
            min_len = min(len(sent_text), len(norm), 20)
            if min_len >= 10 and sent_text[:min_len] == norm[:min_len]:
                return True
    return False

def post_comment_to_chat(live_chat_id, text):
    """Gui 1 comment that vao YouTube live chat. Tra ve True/False."""
    if not AUTO_POST_CHAT:
        return False
    if not text or not live_chat_id:
        return False
    creds = get_oauth_credentials()
    if not creds:
        return False
    text = text[:200]  # YouTube live chat gioi han ky tu
    url = "https://www.googleapis.com/youtube/v3/liveChat/messages?part=snippet"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }
    payload = {
        "snippet": {
            "liveChatId": live_chat_id,
            "type": "textMessageEvent",
            "textMessageDetails": {"messageText": text},
        }
    }
    try:
        resp = session.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            logger.info(f"[POST CHAT OK] {text[:60]}")
            _mark_recently_sent(text)
            return True
        logger.warning(f"[POST CHAT ERROR] HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.warning(f"[POST CHAT EXCEPTION] {e}")
        return False

def enqueue_chat_send(live_chat_id, text):
    """Day reply vao hang doi gui chat thay vi spawn thread truc tiep."""
    try:
        _chat_send_queue.put_nowait((live_chat_id, text))
    except queue.Full:
        logger.warning("[POST CHAT] Hang doi gui chat day, bo qua 1 tin.")

def chat_sender_loop():
    """Luong duy nhat tieu thu hang doi gui chat, dam bao khoang cach toi thieu giua cac tin
    de khong bi YouTube rate-limit khi nhieu worker tao reply cung luc."""
    logger.info("[CHAT SENDER] Da khoi dong.")
    last_sent = 0
    while not shutdown_event.is_set():
        try:
            live_chat_id, text = _chat_send_queue.get(timeout=2)
        except queue.Empty:
            continue
        elapsed = time.time() - last_sent
        if elapsed < CHAT_SEND_MIN_INTERVAL:
            time.sleep(CHAT_SEND_MIN_INTERVAL - elapsed)
        post_comment_to_chat(live_chat_id, text)
        last_sent = time.time()

# ==========================================================
# 3. QUEUE SYSTEM
# ==========================================================
_mem_queue = queue.Queue(maxsize=5000)
r = None
try:
    import redis
    r = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
    r.ping()
    USE_REDIS = True
except:
    USE_REDIS = False

def enqueue(data):
    payload = json.dumps(data, ensure_ascii=False)
    if USE_REDIS and r:
        try: r.lpush("chat_queue", payload)
        except: pass
    else:
        try: _mem_queue.put_nowait(payload)
        except: pass

def dequeue(timeout=2):
    if USE_REDIS and r:
        try:
            msg = r.brpop("chat_queue", timeout=timeout)
            return json.loads(msg[1]) if msg else None
        except: return None
    try:
        payload = _mem_queue.get(timeout=timeout)
        return json.loads(payload) if payload else None
    except: return None

def queue_length():
    return r.llen("chat_queue") if (USE_REDIS and r) else _mem_queue.qsize()

def trim_queue(keep=100):
    if USE_REDIS and r:
        try: r.ltrim("chat_queue", 0, keep)
        except: pass
    else:
        while _mem_queue.qsize() > keep:
            try: _mem_queue.get_nowait()
            except: break

def clear_work_queues():
    if USE_REDIS and r:
        try:
            r.delete("chat_queue")
        except Exception as e:
            logger.warning(f"[QUEUE] Khong xoa duoc Redis chat_queue: {e}")
    else:
        while True:
            try:
                _mem_queue.get_nowait()
            except queue.Empty:
                break
            except Exception:
                break
    while True:
        try:
            _chat_send_queue.get_nowait()
        except queue.Empty:
            break
        except Exception:
            break
    with cache_lock:
        reply_cache.clear()
        cache_expiry_heap.clear()
    logger.info("[QUEUE] Da don sach hang doi chat/reply cu.")

# ==========================================================
# 4. LOCKS & STATES
# ==========================================================
shutdown_event = threading.Event()
heartbeat_lock, _security_lock, _profile_lock = Lock(), Lock(), Lock()
cache_lock = threading.RLock()
_bl_lock = threading.RLock()
worker_heartbeat, worker_state = {}, {}
greeted_users, permanent_blacklist = set(), set()
blacklist = {}
spam_violation_count = defaultdict(int)
user_spam_tracker = defaultdict(deque)
user_profiles_cache, reply_cache, cache_expiry_heap = {}, {}, []
current_live_chat_id = None
_live_chat_id_lock = Lock()
seen_message_ids = deque(maxlen=2000)
seen_message_ids_set = set()
_seen_msg_lock = Lock()

def _is_duplicate_message(msg_id):
    """Kiem tra va danh dau message_id da xu ly chua. Tra ve True neu da thay (trung lap).
    Dung deque + set de gioi han bo nho (chi giu 2000 message gan nhat) ma van tra cuu O(1)."""
    if not msg_id:
        return False
    with _seen_msg_lock:
        if msg_id in seen_message_ids_set:
            return True
        if len(seen_message_ids) == seen_message_ids.maxlen:
            # deque(maxlen) se tu dong loai bo phan tu dau khi append, chi can dong bo set theo
            oldest_id = seen_message_ids[0]
            seen_message_ids_set.discard(oldest_id)
        seen_message_ids.append(msg_id)
        seen_message_ids_set.add(msg_id)
        return False

# ==========================================================
# 5. SECURITY & INVESTIGATION
# ==========================================================
def save_blacklists():
    try:
        with _bl_lock:
            data = {"blacklist": dict(blacklist), "permanent_blacklist": list(permanent_blacklist)}
            with open(BLACKLIST_FILE + ".tmp", "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
            os.replace(BLACKLIST_FILE + ".tmp", BLACKLIST_FILE)
    except Exception as e:
        logger.warning(f"[BLACKLIST] Loi luu file: {e}")

def load_blacklists():
    global blacklist, permanent_blacklist
    if not os.path.exists(BLACKLIST_FILE): return
    try:
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            with _bl_lock:
                blacklist.update(data.get("blacklist", {}))
                permanent_blacklist.update(data.get("permanent_blacklist", []))
    except: pass

def is_malicious(text):
    if not text or len(text) > MAX_MSG_LENGTH: return True
    pattern = r'[a-zA-Z0-9\s\u00C0-\u1EF9\u0102\u0103\u0110\u0111\u0128\u0129\u0168\u0169\u01A0\u01A1\u01AF\u01B0.,!?\-_]'
    specials = [c for c in text if not re.match(pattern, c)]
    if len(text) > 0 and (len(specials) / len(text)) > SYMBOL_RATIO_LIMIT: return True
    return bool(re.search(r'(.)\1{10,}', text))

def investigate_user(cid):
    if not cid or not YOUTUBE_API_KEY: return None
    with _profile_lock:
        if cid in user_profiles_cache: return user_profiles_cache[cid]
    try:
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id={cid}&key={YOUTUBE_API_KEY}"
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("items", [{}])[0]
            snip = data.get("snippet", {})
            ca = snip.get("publishedAt", "")
            days = 9999
            if ca:
                dt = datetime.datetime.strptime(ca[:10], "%Y-%m-%d")
                days = (datetime.datetime.now() - dt).days
            avatar = bool(snip.get("thumbnails", {}).get("default", {}).get("url"))
            prof = {"days_old": days, "has_avatar": avatar, "is_suspicious": (days < 7 and not avatar)}
            with _profile_lock: user_profiles_cache[cid] = prof
            return prof
    except: return None

def check_user_safety(user, text):
    now = time.time()
    with _bl_lock:
        if user in permanent_blacklist: return False
        if user in blacklist:
            if now < blacklist[user]: return False
            del blacklist[user]; save_blacklists()
    for word in KEYWORD_BLACKLIST:
        if word.lower() in text.lower():
            with _bl_lock: permanent_blacklist.add(user)
            save_blacklists(); ghi_file(WARNING_MESSAGES["perm"].format(user=user)); return False
    malicious = is_malicious(text)
    with _security_lock:
        dq = user_spam_tracker[user]
        while dq and (now - dq[0]) > SPAM_WINDOW: dq.popleft()
        spamming = len(dq) >= SPAM_LIMIT
        if not malicious and not spamming:
            dq.append(now); return True
        spam_violation_count[user] += 1
        count = spam_violation_count[user]
    if count >= PERM_BAN_THRESHOLD:
        with _bl_lock: permanent_blacklist.add(user)
        save_blacklists(); ghi_file(WARNING_MESSAGES["perm"].format(user=user)); return False
    dur = BAN_LEVELS.get(count, 3600 * (2 ** (count - 4)) if count > 4 else 0)
    if dur > 0:
        with _bl_lock: blacklist[user] = now + dur; save_blacklists()
        msg_key = count if count in WARNING_MESSAGES else 5
        ghi_file(WARNING_MESSAGES[msg_key].format(user=user))
    return False

# ==========================================================
# 6. AI ROUTER
# ==========================================================
def build_mod_prompt(is_new, profile, brief_mode):
    prompt = (
        f"Ban la Mita, AI mod cua kenh {TEN_KENH}. "
        "Hay xem moi nguoi chat nhu mot nguoi quen rieng. "
        "Doc cach user noi chuyen va tu suy doan vibe/tinh cach cua ho: vui, nhay, nghiem tuc, than mat, nga'u, hay ngai ngung. "
        "Tra loi nhu ban dang noi voi mot nguoi ban cua user do, hop voi vibe cua ho. "
        "Duoc dung slang/cach noi gan voi user neu phu hop, nhung KHONG duoc gia mao user, KHONG noi minh la user, KHONG tiet lo rang ban dang phan tich tinh cach. "
        "Neu user hoi/cap topic, uu tien tra loi dung topic truoc roi them chut ca tinh. "
        "Tra loi bang cung ngon ngu voi user, ngan gon 1-2 cau, toi da 150 ky tu."
    )
    if profile and profile["is_suspicious"]:
        prompt += " User acc moi/nghi van: than thien nhung giu ngan gon va can than."
    elif profile:
        prompt += " User tin cay: co the than mat hon, nhu ban quen trong stream."
    if brief_mode:
        prompt += " Dang dong chat: chi tra loi 1 cau cuc ngan."
    if is_new:
        prompt += " Neu hop ngu canh thi chao nhu gap ban moi, tu nhien, khong qua may moc."
    return prompt

def gemini_api(text, user, is_new, profile, brief_mode):
    """Priority 3 (fallback): Google Gemini voi nhieu key xoay vong."""
    if not GEMINI_API_KEYS: return None
    # Thu tat ca cac key truoc khi tu bo
    for _ in range(len(GEMINI_API_KEYS)):
        key = _get_next_gemini_key()
        if not key: return None
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
            prompt = build_mod_prompt(is_new, profile, brief_mode)
            payload = {
                "contents": [{"parts": [{"text": f"{prompt}\nUser {user}: {text}"}]}],
                "generationConfig": {"maxOutputTokens": 80 if brief_mode else 120},
            }
            resp = session.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                result = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()[:180]
                logger.info(f"[GEMINI OK] {user} (key #{GEMINI_API_KEYS.index(key)+1}): {result[:60]}")
                return result
            if resp.status_code == 429:
                logger.warning(f"[GEMINI] Key #{GEMINI_API_KEYS.index(key)+1} bi 429 (het quota), chuyen key...")
                _rotate_gemini_key_on_error(key)
                continue
            logger.warning(f"[GEMINI ERROR] HTTP {resp.status_code} cho {user}: {resp.text[:150]}")
        except Exception as e:
            logger.warning(f"[GEMINI EXCEPTION] {user}: {e}")
    logger.warning(f"[GEMINI] Tat ca {len(GEMINI_API_KEYS)} key deu that bai cho {user}.")
    return None

def friend_pc_api(text, user, is_new, profile, brief_mode):
    """Priority 2: May ban ban qua ngrok (hieu nang cao)"""
    if not CUSTOM_API_URL or not CUSTOM_API_KEY: return None
    try:
        prompt = build_mod_prompt(is_new, profile, brief_mode)
        payload = {"model": MODEL_NAME, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": f"{user}: {text}"}], "temperature": 0.7, "max_tokens": 150 if brief_mode else 200}
        headers = {"Authorization": f"Bearer {CUSTOM_API_KEY}", "Content-Type": "application/json", "ngrok-skip-browser-warning": "true"}
        resp = session.post(CUSTOM_API_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            raw = resp.json()
            choice = raw.get("choices", [{}])[0]
            result = choice.get("message", {}).get("content", "").strip()[:180]
            if not result:
                result = choice.get("message", {}).get("reasoning_content", "").strip()[:180]
            if result:
                logger.info(f"[FRIEND-PC OK] {user}: {result[:60]}")
                return result
            finish_reason = choice.get("finish_reason", "?")
            logger.warning(f"[FRIEND-PC] Tra ve rong cho {user} (finish_reason={finish_reason}).")
        else:
            logger.warning(f"[FRIEND-PC ERROR] HTTP {resp.status_code} cho {user}: {resp.text[:150]}")
    except Exception as e:
        logger.warning(f"[FRIEND-PC EXCEPTION] {user}: {e}")
    return None

def ollama_api(text, user, is_new, profile, brief_mode):
    """Priority 3: Local Ollama (du phong cuoi cung)"""
    if not OLLAMA_API_URL or not OLLAMA_MODEL: return None
    try:
        prompt = build_mod_prompt(is_new, profile, brief_mode)
        payload = {"model": OLLAMA_MODEL, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": f"{user}: {text}"}], "temperature": 0.7, "max_tokens": 150 if brief_mode else 200}
        headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}", "Content-Type": "application/json"}
        resp = session.post(OLLAMA_API_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            result = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()[:180]
            if result:
                logger.info(f"[OLLAMA OK] {user}: {result[:60]}")
                return result
            logger.warning(f"[OLLAMA] Tra ve rong cho {user}.")
        else:
            logger.warning(f"[OLLAMA ERROR] HTTP {resp.status_code} cho {user}: {resp.text[:150]}")
    except Exception as e:
        logger.warning(f"[OLLAMA EXCEPTION] {user}: {e}")
    return None

def route_ai(text, user, is_new, brief_mode, profile):
    """Uu tien AI mien phi truoc, Gemini chi dung khi ca 2 kia that bai.
    Tiet kiem quota Gemini toi da: Friend's PC → Ollama Local → Gemini."""
    # 1. May ban (mien phi, hieu nang cao nhat)
    res = friend_pc_api(text, user, is_new, profile, brief_mode)
    if res: return res
    # 2. Ollama local (mien phi, khong can internet)
    res = ollama_api(text, user, is_new, profile, brief_mode)
    if res: return res
    # 3. Gemini (chi dung khi ca 2 kia chet - tiet kiem quota)
    return gemini_api(text, user, is_new, profile, brief_mode)

# ==========================================================
# 7. WORKERS & RUNTIME
# ==========================================================
file_write_lock = Lock()

def ghi_file(content):
    try:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        output = f"[{ts}] {content}"
        with file_write_lock:
            with open(FILE_OUTPUT + ".tmp", "w", encoding="utf-8") as f: f.write(output)
            os.replace(FILE_OUTPUT + ".tmp", FILE_OUTPUT)
        logger.info(f"[GHI FILE] {output[:80]}")
    except Exception as e:
        logger.error(f"[GHI FILE ERROR] {e}")

def worker_loop(name, ai_func=None):
    """ai_func: ham AI duoc phan cong cho worker nay.
    None = dung route_ai mac dinh (Friend's PC -> Ollama -> Gemini)."""
    logger.info(f"[WORKER] {name} started (AI: {ai_func.__name__ if ai_func else 'route_ai'})")
    while not shutdown_event.is_set():
        try:
            q_len = queue_length()
            brief = (q_len > QUEUE_BRIEF_THRESHOLD)
            if q_len > QUEUE_OVERFLOW_THRESHOLD and random.random() > 0.3:
                trim_queue(100); continue
            data = dequeue(2)
            if not data:
                with heartbeat_lock: worker_heartbeat[name] = time.time(); worker_state[name] = "IDLE"
                continue
            user, text, cid = data.get("user"), data.get("text", "").strip(), data.get("channelId")
            if not text:
                continue
            safe = check_user_safety(user, text)
            if not safe:
                logger.info(f"[BLOCKED] {user}: '{text[:40]}' - bi block boi security")
                continue
            with _security_lock:
                is_new = False
                if user not in greeted_users: is_new = True; greeted_users.add(user)
            profile = investigate_user(cid)
            with heartbeat_lock: worker_state[name] = "PROCESSING"; worker_heartbeat[name] = time.time()
            reply = None
            if not is_new:
                with cache_lock:
                    if text.lower() in reply_cache:
                        v, e = reply_cache[text.lower()]
                        if time.time() < e:
                            reply = v
                            logger.info(f"[CACHE HIT] {user}: '{text[:30]}'")
            if not reply:
                logger.info(f"[AI REQUEST] {name} xu ly: {user} - '{text[:50]}'")
                # Dung AI duoc phan cong rieng cho worker nay, fallback ve route_ai neu that bai
                if ai_func:
                    reply = ai_func(text, user, is_new, profile, brief)
                    if not reply:
                        logger.info(f"[{name}] AI rieng that bai, fallback route_ai")
                        reply = route_ai(text, user, is_new, brief, profile)
                else:
                    reply = route_ai(text, user, is_new, brief, profile)
                if reply and not is_new:
                    with cache_lock:
                        if len(reply_cache) >= MAX_CACHE_SIZE: _evict_cache()
                        reply_cache[text.lower()] = (reply, time.time() + MAX_CACHE_TTL)
                        heapq.heappush(cache_expiry_heap, (time.time() + MAX_CACHE_TTL, text.lower()))
            if reply:
                ghi_file(reply)
                if AUTO_POST_CHAT:
                    with _live_chat_id_lock:
                        live_chat_id = current_live_chat_id
                    if live_chat_id:
                        enqueue_chat_send(live_chat_id, reply)
                    else:
                        logger.warning("[POST CHAT] Khong co live_chat_id, bo qua post comment that.")
            else:
                logger.warning(f"[NO REPLY] route_ai tra None cho {user}: '{text[:40]}'")
            with heartbeat_lock: worker_heartbeat[name] = time.time(); worker_state[name] = "IDLE"
        except Exception as e:
            logger.error(f"[WORKER ERROR] {name}: {e}")

def _evict_cache():
    with cache_lock:
        now = time.time()
        while cache_expiry_heap and cache_expiry_heap[0][0] <= now:
            _, k = heapq.heappop(cache_expiry_heap)
            reply_cache.pop(k, None)
        if len(reply_cache) >= MAX_CACHE_SIZE:
            oldest = sorted(reply_cache.items(), key=lambda x: x[1][1])
            for k, _ in oldest[:MAX_CACHE_SIZE // 4]: reply_cache.pop(k, None)

_system_running = False
_system_lock = Lock()

def start_full_system():
    """Khoi dong toan bo workers/fetcher/sender/watchdog. Idempotent - khong khoi dong lai neu da chay."""
    global _system_running
    with _system_lock:
        if _system_running:
            return
        logger.info("[OBS] Phat hien Start Streaming! Danh thuc he thong...")
        clear_work_queues()
        # Phan cong AI co dinh cho tung worker:
        # w0, w1 -> Friend's PC (hieu nang cao, xu ly bulk)
        # w2     -> Ollama local (mien phi, xu ly song song)
        # Gemini chi la fallback cuoi trong route_ai khi ca 2 kia chet
        worker_ai_map = {
            "w0": friend_pc_api,
            "w1": friend_pc_api,
            "w2": ollama_api,
        }
        for i in range(WORKER_COUNT):
            name = f"w{i}"
            ai_func = worker_ai_map.get(name)
            if not any(t.name == name and t.is_alive() for t in threading.enumerate()):
                threading.Thread(target=worker_loop, args=(name, ai_func), name=name, daemon=True).start()
                with heartbeat_lock: worker_heartbeat[name] = time.time(); worker_state[name] = "BOOTING"
        if not any(t.name == "youtube_fetcher" and t.is_alive() for t in threading.enumerate()):
            threading.Thread(target=fetch_youtube_chat, name="youtube_fetcher", daemon=True).start()
        if not any(t.name == "chat_sender" and t.is_alive() for t in threading.enumerate()):
            threading.Thread(target=chat_sender_loop, name="chat_sender", daemon=True).start()
        if not any(t.name == "watchdog" and t.is_alive() for t in threading.enumerate()):
            threading.Thread(target=self_healing, name="watchdog", daemon=True).start()
        _system_running = True

def stop_full_system():
    """Bao hieu dung he thong khi OBS bam Stop Streaming. Cac thread se tu thoat o vong lap ke tiep
    cua chung (kiem tra shutdown_event hoac _system_running). Workers/chat_sender la vong lap vo han
    nen duoc giu nguyen chay nen (it tai nguyen khi idle); chi youtube_fetcher thuc su dung han."""
    global _system_running, current_live_chat_id
    with _system_lock:
        if not _system_running:
            return
        logger.info("[OBS] Phat hien Stop Streaming. Quay ve che do CHO.")
        clear_work_queues()
        _system_running = False
        with _live_chat_id_lock:
            current_live_chat_id = None

STREAMING_FLAG_FILE = str(BASE_DIR / "streaming.flag")

def obs_signal_loop():
    """Vong lap nhe: cho file tin hieu 'streaming.flag' do obs_control.py tao ra khi Sensei
    bam nut Start Streaming trong OBS. File ton tai -> dang stream -> khoi dong he thong day du.
    File bi xoa (bam Stop Streaming) -> dung he thong, quay lai cho."""
    global _system_running
    logger.info("[STANDBY] Bot dang CHO tin hieu tu OBS. Bam 'Start Streaming' trong OBS de kich hoat.")
    while not shutdown_event.is_set():
        is_streaming = os.path.exists(STREAMING_FLAG_FILE)
        with _system_lock:
            running = _system_running
        if is_streaming and not running:
            start_full_system()
        elif not is_streaming and running:
            stop_full_system()
        time.sleep(2)


def _is_youtube_quota_error(resp):
    if resp.status_code not in (403, 429):
        return False
    body = (resp.text or "").lower()
    return "quota" in body or "quotaexceeded" in body or "exceeded" in body

def _sleep_after_youtube_quota():
    logger.warning("[YOUTUBE] Het quota API. Tam nghi 30 phut de tranh spam log.")
    time.sleep(1800)

def fetch_youtube_chat():
    global current_live_chat_id, _system_running
    chat_id, token = None, None
    just_connected = False
    while not shutdown_event.is_set():
        with _system_lock:
            if not _system_running:
                logger.info("[YOUTUBE] He thong da chuyen sang STOP. Fetcher thoat.")
                return
        try:
            if not chat_id:
                search_resp = session.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "channelId": CHANNEL_ID,
                        "eventType": "live",
                        "type": "video",
                        "maxResults": 1,
                        "key": YOUTUBE_API_KEY,
                    },
                    timeout=10,
                )
                if _is_youtube_quota_error(search_resp):
                    _sleep_after_youtube_quota()
                    continue
                if search_resp.status_code != 200:
                    logger.warning(f"[YOUTUBE] Không tìm được livestream active (HTTP {search_resp.status_code}): {search_resp.text[:200]}")
                    time.sleep(60)
                    continue
                items = search_resp.json().get("items", [])
                if not items:
                    logger.info("[YOUTUBE] Chưa thấy livestream active trên kênh. Chờ 60 giây...")
                    time.sleep(60)
                    continue
                video_id = items[0]["id"].get("videoId")
                video_resp = session.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "liveStreamingDetails",
                        "id": video_id,
                        "key": YOUTUBE_API_KEY,
                    },
                    timeout=10,
                )
                if _is_youtube_quota_error(video_resp):
                    _sleep_after_youtube_quota()
                    continue
                if video_resp.status_code != 200:
                    logger.warning(f"[YOUTUBE] Không lấy được liveChatId (HTTP {video_resp.status_code}): {video_resp.text[:200]}")
                    time.sleep(60)
                    continue
                videos = video_resp.json().get("items", [])
                if not videos:
                    logger.info("[YOUTUBE] Livestream vừa tìm thấy không còn khả dụng.")
                    time.sleep(60)
                    continue
                chat_id = videos[0].get("liveStreamingDetails", {}).get("activeLiveChatId")
                token = None
                if not chat_id:
                    logger.warning("[YOUTUBE] Livestream không có activeLiveChatId. Kiểm tra live chat có bật không.")
                    time.sleep(60)
                    continue
                with _live_chat_id_lock:
                    current_live_chat_id = chat_id
                just_connected = True
                logger.info(f"[YOUTUBE] Đã kết nối live chat của video {video_id}")
            url = f"https://www.googleapis.com/youtube/v3/liveChat/messages?liveChatId={chat_id}&part=snippet,authorDetails&key={YOUTUBE_API_KEY}"
            if token: url += f"&pageToken={token}"
            resp = session.get(url, timeout=10)
            if resp.status_code == 403 and "live chat is no longer live" in resp.text.lower():
                logger.warning("[YOUTUBE] Livestream da ket thuc. Chuyen ve che do standby.")
                with _live_chat_id_lock:
                    current_live_chat_id = None
                with _system_lock:
                    _system_running = False
                return
            if _is_youtube_quota_error(resp):
                _sleep_after_youtube_quota()
                continue
            if resp.status_code != 200:
                logger.warning(f"[YOUTUBE] Đọc live chat lỗi HTTP {resp.status_code}: {resp.text[:200]}")
                chat_id = None
                with _live_chat_id_lock:
                    current_live_chat_id = None
                time.sleep(30); continue
            data = resp.json()
            token = data.get("nextPageToken")
            bot_cid = get_bot_own_channel_id() if AUTO_POST_CHAT else None
            if just_connected:
                just_connected = False
                if SKIP_EXISTING_CHAT_ON_CONNECT:
                    skipped = 0
                    for item in data.get("items", []):
                        if _is_duplicate_message(item.get("id")):
                            continue
                        skipped += 1
                    logger.info(f"[YOUTUBE] Bo qua {skipped} tin chat cu khi moi ket noi; chi rep tin moi tu bay gio.")
                    time.sleep(max(data.get("pollingIntervalMillis", 2000)/1000, 1.5))
                    continue
            for item in data.get("items", []):
                msg_id = item.get("id")
                u, c, t = item["authorDetails"].get("displayName", "unknown"), item["authorDetails"].get("channelId"), item["snippet"].get("displayMessage", "")
                if not t:
                    continue
                if _is_duplicate_message(msg_id):
                    logger.info(f"[YOUTUBE] Bo qua message trung lap (id da xu ly): {t[:60]}")
                    continue
                if bot_cid and c == bot_cid:
                    logger.info(f"[YOUTUBE] Bo qua tin nhan do chinh bot dang (echo, theo channelId): {t[:60]}")
                    continue
                if AUTO_POST_CHAT and is_recently_sent_by_bot(t):
                    logger.info(f"[YOUTUBE] Bo qua tin nhan trung voi reply bot vua dang (echo, du phong): {t[:60]}")
                    continue
                logger.info(f"[YOUTUBE] Nhận chat từ {u}: {t[:80]}")
                enqueue({"user": u, "text": t, "channelId": c})
            time.sleep(max(data.get("pollingIntervalMillis", 2000)/1000, 1.5))
        except Exception as exc:
            logger.warning(f"[YOUTUBE] Fetcher lỗi: {exc}")
            time.sleep(5)

def self_healing():
    # Bang phan cong AI co dinh - phai khop voi worker_ai_map trong start_full_system
    _worker_ai_map = {
        "w0": friend_pc_api,
        "w1": friend_pc_api,
        "w2": ollama_api,
    }
    while not shutdown_event.is_set():
        try:
            time.sleep(WATCHDOG_CHECK_INTERVAL)
            with _system_lock:
                running = _system_running
            if not running:
                continue
            now = time.time()
            for name in list(worker_heartbeat.keys()):
                alive = any(t.name == name and t.is_alive() for t in threading.enumerate())
                hb = worker_heartbeat.get(name, 0)
                if not alive or (now - hb > WORKER_FREEZE_TIMEOUT):
                    ai_func = _worker_ai_map.get(name)
                    threading.Thread(target=worker_loop, args=(name, ai_func), name=name, daemon=True).start()
                    with heartbeat_lock: worker_heartbeat[name] = time.time(); worker_state[name] = "RECOVERED"
                    logger.warning(f"[WATCHDOG] Hoi sinh {name} (AI: {ai_func.__name__ if ai_func else 'route_ai'})")
            if not any(t.name == "youtube_fetcher" and t.is_alive() for t in threading.enumerate()):
                threading.Thread(target=fetch_youtube_chat, name="youtube_fetcher", daemon=True).start()
            if not any(t.name == "chat_sender" and t.is_alive() for t in threading.enumerate()):
                threading.Thread(target=chat_sender_loop, name="chat_sender", daemon=True).start()
        except Exception as e:
            logger.error(f"[WATCHDOG ERROR] {e}")


# ==========================================================
# 12. ALL-IN-ONE CHECKS (CUSTOM API | GEMINI | YOUTUBE | QUOTA)
# ==========================================================
def wait_for_custom_api_boot(seconds=CUSTOM_API_BOOT_WAIT):
    if seconds <= 0:
        return
    logger.info(f"[CHECK] Chờ Custom API server khởi động {seconds} giây trước khi test...")
    for left in range(seconds, 0, -1):
        print(f"\r[WAIT] Đợi Custom API server sẵn sàng: {left:02d}s ", end="", flush=True)
        time.sleep(1)
    print("\r[WAIT] Đợi Custom API server sẵn sàng: xong.   ")

def custom_api_request(model_name):
    if not CUSTOM_API_URL or not CUSTOM_API_KEY:
        return "MISSING_CONFIG", "Thiếu CUSTOM_API_URL hoặc CUSTOM_API_KEY"
    headers = {
        "Authorization": f"Bearer {CUSTOM_API_KEY}",
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 10,
    }
    try:
        resp = requests.post(CUSTOM_API_URL, headers=headers, json=payload, timeout=8)
        if resp.status_code == 200:
            return "OK", "Custom API trả lời OK"
        try:
            error = resp.json().get("error", {})
            message = str(error.get("message") or error).strip()
        except Exception:
            message = resp.text[:300].strip()
        low = message.lower()
        if resp.status_code == 401 or "auth" in low or "api key" in low:
            return "UNAUTHORIZED", message
        if "no connected db" in low:
            return "SERVER_CONFIG_ERROR", message
        if resp.status_code == 404:
            return "NOT_FOUND", message
        return f"ERROR_{resp.status_code}", message
    except Exception as exc:
        return "CONNECTION_ERROR", str(exc)

def check_custom_api(wait=True):
    if wait:
        wait_for_custom_api_boot()
    logger.info(f"[CHECK] Test Custom API model: {MODEL_NAME}")
    status, detail = custom_api_request(MODEL_NAME)
    if status == "OK":
        logger.info(f"[OK] Custom model hoạt động: {MODEL_NAME}")
        return MODEL_NAME
    if status == "SERVER_CONFIG_ERROR":
        logger.error(f"[CUSTOM] Server phản hồi nhưng chưa cấu hình xong: {detail}")
        return "SERVER_CONFIG_ERROR"
    if status == "UNAUTHORIZED":
        logger.error(f"[CUSTOM] Sai hoặc thiếu CUSTOM_API_KEY: {detail}")
        return None
    logger.warning(f"[CUSTOM] Model/API hiện chưa chạy được ({status}): {detail}")
    return None

def check_gemini_api():
    if not GEMINI_API_KEY or GEMINI_API_KEY == "MISSING":
        logger.error("[GEMINI] Thiếu GEMINI_API_KEY")
        return "Thiếu Key"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]}, timeout=8)
        if resp.status_code == 200:
            logger.info(f"[OK] Gemini hoạt động: {GEMINI_MODEL}")
            return "Hoạt động"
        if resp.status_code == 429:
            logger.warning("[GEMINI] Key đúng nhưng đang quá quota/rate limit")
            return "Quá tải/quota"
        logger.error(f"[GEMINI] Lỗi HTTP {resp.status_code}: {resp.text[:300]}")
        return f"Lỗi {resp.status_code}"
    except Exception as exc:
        logger.error(f"[GEMINI] Lỗi kết nối: {exc}")
        return "Lỗi kết nối"

def check_youtube_api():
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "MISSING":
        logger.error("[YOUTUBE] Thiếu YOUTUBE_API_KEY")
        return "Thiếu Key"
    if not CHANNEL_ID or CHANNEL_ID == "MISSING":
        logger.error("[YOUTUBE] Thiếu CHANNEL_ID")
        return "Thiếu Channel ID"
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {"part": "snippet", "id": CHANNEL_ID, "key": YOUTUBE_API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code == 200 and "error" not in resp.text.lower():
            logger.info("[OK] YouTube API hoạt động")
            return "Hoạt động"
        logger.error(f"[YOUTUBE] Lỗi HTTP {resp.status_code}: {resp.text[:300]}")
        return f"Lỗi {resp.status_code}"
    except Exception as exc:
        logger.error(f"[YOUTUBE] Lỗi kết nối: {exc}")
        return "Lỗi kết nối"

def check_quota_status():
    logger.info("=" * 60)
    logger.info("[QUOTA] Kiểm tra trạng thái Gemini và YouTube")
    gemini = check_gemini_api()
    youtube = check_youtube_api()
    logger.info(f"[QUOTA] Gemini: {gemini}")
    logger.info(f"[QUOTA] YouTube: {youtube}")
    return gemini, youtube

def run_full_check():
    logger.info("=" * 60)
    logger.info("[ALL-IN-ONE] BẮT ĐẦU QUÉT HỆ THỐNG")
    logger.info("=" * 60)
    custom = check_custom_api(wait=True)
    gemini = check_gemini_api()
    youtube = check_youtube_api()
    logger.info("=" * 60)
    logger.info("[TỔNG KẾT]")
    if custom and custom != "SERVER_CONFIG_ERROR":
        logger.info(f"Model custom: {custom} OK")
    elif custom == "SERVER_CONFIG_ERROR":
        logger.error("Model custom: CHƯA TEST ĐƯỢC - server custom lỗi cấu hình")
    else:
        logger.error("Model custom: CHƯA HOẠT ĐỘNG")
    logger.info(f"Gemini: {gemini}")
    logger.info(f"YouTube: {youtube}")
    logger.info("=" * 60)
    return bool(custom and custom != "SERVER_CONFIG_ERROR" and gemini == "Hoạt động" and youtube == "Hoạt động")

def run_custom_key_check():
    logger.info("=" * 60)
    logger.info("[CUSTOM ONLY] KIỂM TRA CUSTOM API / KEY / MODEL")
    logger.info("=" * 60)
    custom = check_custom_api(wait=True)
    logger.info("=" * 60)
    if custom and custom != "SERVER_CONFIG_ERROR":
        logger.info(f"[CUSTOM ONLY] OK - Custom API hoạt động đầy đủ với model: {custom}")
        logger.info("=" * 60)
        return True
    if custom == "SERVER_CONFIG_ERROR":
        logger.error("[CUSTOM ONLY] CHƯA OK - server custom phản hồi nhưng chưa cấu hình xong.")
    else:
        logger.error("[CUSTOM ONLY] CHƯA OK - kiểm tra CUSTOM_API_URL, CUSTOM_API_KEY, MODEL_NAME hoặc server.")
    logger.info("=" * 60)
    return False


# ==========================================================
# 13. OBS INTEGRATION (UI & CONTROL)
# ==========================================================
bot_process = None
OBS_AUTO_START = os.getenv("OBS_AUTO_START", "1").lower() in ("1", "true", "yes", "on")

def script_description():
    return "AI Mod Bot v25_GOD_UI - Hệ thống điều khiển tích hợp. Tự kích hoạt khi bấm Start Streaming."

def _obs_on_streaming_started():
    try:
        with open(STREAMING_FLAG_FILE, "w", encoding="utf-8") as f:
            f.write("streaming")
        import obspython as obs
        obs.script_log(obs.LOG_INFO, "Da bam Start Streaming -> bao hieu AI Bot kich hoat.")
    except Exception as e:
        logger.warning(f"[OBS] Loi tao streaming.flag: {e}")

def _obs_on_streaming_stopped():
    try:
        if os.path.exists(STREAMING_FLAG_FILE):
            os.remove(STREAMING_FLAG_FILE)
        import obspython as obs
        obs.script_log(obs.LOG_INFO, "Da bam Stop Streaming -> bao hieu AI Bot quay ve cho.")
    except Exception as e:
        logger.warning(f"[OBS] Loi xoa streaming.flag: {e}")

def _obs_on_frontend_event(event):
    try:
        import obspython as obs
        if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
            _obs_on_streaming_started()
        elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
            _obs_on_streaming_stopped()
    except Exception:
        pass

def script_properties():
    try:
        import obspython as obs
        props = obs.obs_properties_create()
        obs.obs_properties_add_button(props, "btn_start", "🚀 KHỞI ĐỘNG AI BOT", start_bot_callback)
        obs.obs_properties_add_button(props, "btn_stop", "🛑 DỪNG AI BOT", stop_bot_callback)
        return props
    except: return None

def start_bot_callback(props, prop):
    global bot_process
    import subprocess
    script_path = os.path.abspath(__file__)
    python_exe = sys.executable if "python" in sys.executable.lower() else shutil.which("python")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    possible_paths = [
        os.path.join(local_app_data, "Programs", "Python", "Python310", "python.exe"),
        os.path.join(local_app_data, "Programs", "Python", "Python311", "python.exe"),
        os.path.join(local_app_data, "Programs", "Python", "Python312", "python.exe"),
        os.path.join(local_app_data, "Programs", "Python", "Python313", "python.exe"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            python_exe = path
            break
    if not python_exe:
        msg = "Không tìm thấy Python để chạy bot. Cài Python 3.10+ hoặc load obs_control.py."
        logger.error(f"[OBS] {msg}")
        try:
            import obspython as obs
            obs.script_log(obs.LOG_ERROR, msg)
        except Exception:
            print(msg)
        return
    if bot_process is None or bot_process.poll() is not None:
        try:
            creation_flags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            bot_process = subprocess.Popen([python_exe, script_path], cwd=os.path.dirname(script_path), creationflags=creation_flags)
            msg = f"Bot đã chạy ngầm bằng {python_exe} (PID: {bot_process.pid})"
            logger.info(f"[OBS] {msg}")
            try:
                import obspython as obs
                obs.script_log(obs.LOG_INFO, msg)
            except Exception:
                print(f"[OBS] {msg}")
        except Exception as e:
            logger.error(f"[OBS] Lỗi khởi động: {e}")
            try:
                import obspython as obs
                obs.script_log(obs.LOG_ERROR, f"Lỗi khởi động: {e}")
            except Exception:
                print(f"Lỗi: {e}")

def stop_bot_callback(props, prop):
    global bot_process
    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
        bot_process = None
        print("[OBS] Bot đã dừng.")

def script_unload():
    try:
        import obspython as obs
        obs.obs_frontend_remove_event_callback(_obs_on_frontend_event)
    except Exception:
        pass
    stop_bot_callback(None, None)

def script_load(settings):
    try:
        if os.path.exists(STREAMING_FLAG_FILE):
            os.remove(STREAMING_FLAG_FILE)
    except Exception:
        pass
    try:
        import obspython as obs
        obs.obs_frontend_add_event_callback(_obs_on_frontend_event)
        if obs.obs_frontend_streaming_active():
            _obs_on_streaming_started()
    except Exception:
        pass
    if OBS_AUTO_START:
        start_bot_callback(None, None)


# ==========================================================
# MODULE CHẨN ĐOÁN BỆNH (DIAGNOSTIC SYSTEM)
# ==========================================================
def diagnose_system():
    """
    Hệ thống tự khám bệnh. Quét toàn bộ lỗi tiềm ẩn trước khi chạy.
    """
    logger.info("="*50)
    logger.info("🩺 ĐANG CHẠY CHẨN ĐOÁN HỆ THỐNG (DIAGNOSTICS)...")
    logger.info("="*50)
    
    diseases = []
    
    # 1. Kiểm tra Kết nối Internet
    try:
        requests.get("https://google.com", timeout=5)
        logger.info("[✓] Internet: Kết nối ổn định.")
    except:
        diseases.append("MẤT KẾT NỐI INTERNET: Vui lòng kiểm tra Wifi/Lan.")

    # 2. Kiểm tra Key (Sơ bộ)
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "MISSING":
        diseases.append("THIẾU YOUTUBE_API_KEY: Bot không thể đọc chat.")
    if not GEMINI_API_KEY:
        diseases.append("THIẾU GEMINI_API_KEY: Không có AI dự phòng khi Gemma sập.")

    # 3. Kiểm tra Redis
    if not USE_REDIS:
        logger.warning("[!] Redis không chạy. Bot sẽ dùng In-memory (chậm hơn).")

    # 4. Kiểm tra quyền ghi file OBS
    try:
        with open(FILE_OUTPUT, "w", encoding="utf-8") as f: f.write("")
        logger.info("[✓] Quyền ghi file OBS: Bình thường.")
    except Exception as e:
        diseases.append(f"LỖI QUYỀN GHI FILE: OBS không thể hiện chữ. Lỗi: {e}")

    # 5. Kiểm tra Custom API sau khi đợi server boot xong.
    custom_status = check_custom_api(wait=True)
    if custom_status == "SERVER_CONFIG_ERROR":
        diseases.append("SERVER CUSTOM LỖI CẤU HÌNH: API phản hồi nhưng LiteLLM/server chưa sẵn sàng.")
    elif not custom_status:
        diseases.append("SERVER CUSTOM CHƯA HOẠT ĐỘNG: Kiểm tra URL, key, model hoặc trạng thái server.")

    # 6. Kiểm tra OAuth (post comment that vao YouTube live chat)
    if AUTO_POST_CHAT:
        if not OAUTH_LIBS_AVAILABLE:
            logger.warning("[!] Thieu thu vien OAuth (google-auth-oauthlib). Chay: pip install -r requirements.txt --break-system-packages")
            logger.warning("[!] Bot van hoat dong nhung se KHONG tu dang comment that vao YouTube chat.")
        elif not os.path.exists(CLIENT_SECRET_FILE):
            logger.warning(f"[!] Khong tim thay {CLIENT_SECRET_FILE}. Bot se KHONG tu dang comment that vao YouTube chat.")
        else:
            logger.info("[✓] OAuth client_secret.json: Tim thay.")
            if not os.path.exists(OAUTH_TOKEN_FILE):
                logger.warning("[!] Chua dang nhap Google lan dau. Trinh duyet se mo ra khi bot can gui comment dau tien.")

    # --- TỔNG KẾT BỆNH ---
    if diseases:
        logger.error("\n" + "!"*20 + " PHÁT HIỆN BỆNH LÝ " + "!"*20)
        for i, d in enumerate(diseases, 1):
            logger.error(f"Bệnh {i}: {d}")
        logger.error("="*55)
        return False
    else:
        logger.info("\n✅ HỆ THỐNG KHỎE MẠNH. Sẵn sàng khởi động!")
        return True

def minimize_console_window():
    """Thu nho cua so CMD/Console sau khi check xong, bot van chay binh thuong o nen.
    Chi hoat dong tren Windows; bo qua an toan tren cac he dieu hanh khac."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            SW_MINIMIZE = 6
            ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
            logger.info("[SYSTEM] Da thu nho cua so console. Bot van chay nen, doi live.")
    except Exception as e:
        logger.warning(f"[SYSTEM] Khong the thu nho console: {e}")

def main():
    # Bước 1: Chẩn đoán bệnh trước khi chạy
    if not diagnose_system():
        logger.warning("Hệ thống phát hiện lỗi. Bot vẫn cố khởi động nhưng có thể không hoạt động.")

    # Bước 2: Da check xong, thu nho cua so de khong choan man hinh - bot van chay nen cho live
    minimize_console_window()

    load_blacklists()
    try:
        threading.Thread(target=obs_signal_loop, name="obs_signal", daemon=True).start()

        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_event.set()
    finally:
        logger.info("[SYSTEM] Tắt an toàn!")


if __name__ == "__main__":
    if "--custom-check" in sys.argv:
        ok = run_custom_key_check()
        sys.exit(0 if ok else 1)
    if "--check" in sys.argv:
        ok = run_full_check()
        sys.exit(0 if ok else 1)
    if "--quota" in sys.argv:
        check_quota_status()
        sys.exit(0)
    main()
