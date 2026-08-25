import os
import requests
from dotenv import load_dotenv
load_dotenv()
api_keys = []
raw_key = os.getenv("GEMINI_API_KEY", "")
if raw_key:
    api_keys.extend([k.strip() for k in raw_key.split(",") if k.strip()])
for env_key, value in os.environ.items():
    if env_key.startswith("GEMINI_API_KEY_") and value.strip():
        if value.strip() not in api_keys:
            api_keys.append(value.strip())
MODELS_TO_CHECK = [
    os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
    "gemini-1.5-flash",
    "gemini-2.0-flash"
]
MODELS_TO_CHECK = list(dict.fromkeys([m for m in MODELS_TO_CHECK if m]))
print("==================================================")
print("     DIAGNOSTIC: API QUOTA & RATE LIMIT STATUS    ")
print("==================================================")
if not api_keys:
    print("\n❌ Không tìm thấy GEMINI_API_KEY nào trong file .env!")
else:
    print(f"\n🔍 Tìm thấy {len(api_keys)} API Key để kiểm tra...\n")
    for idx, key in enumerate(api_keys, 1):
        masked_key = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        print(f"--------------------------------------------------")
        print(f"🔑 [Key #{idx}]: {masked_key}")
        for model in MODELS_TO_CHECK:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": "quota check"}]}]}
            try:
                resp = requests.post(url, json=payload, timeout=15)
                if resp.status_code == 200:
                    print(f"  ✅ Model [{model}]: HOẠT ĐỘNG BÌNH THƯỜNG")
                elif resp.status_code == 429:
                    print(f"  ❌ Model [{model}]: BỊ HẠN CHẾ QUOTA / RATE LIMIT (Mã 429)")
                elif resp.status_code == 403:
                    msg = ""
                    try: msg = resp.json().get('error', {}).get('message', '')
                    except: pass
                    print(f"  ❌ Model [{model}]: BỊ KHÓA HOẶC SAI KEY (Mã 403) -> {msg}")
                elif resp.status_code == 503:
                    msg = ""
                    try: msg = resp.json().get('error', {}).get('message', '')
                    except: pass
                    print(f"  ❌ Model [{model}]: LỖI 503 OVERLOAD / VPN CHẶN -> {msg}")
                else:
                    print(f"  ⚠️ Model [{model}]: Trạng thái {resp.status_code}")
            except Exception as e:
                print(f"  ❌ Model [{model}]: Lỗi kết nối -> {e}")
print("==================================================") 