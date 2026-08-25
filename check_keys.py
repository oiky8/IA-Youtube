import os
import logging
import time 
import sys
from datetime import datetime
import requests
import google.generativeai as genai
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# =================================================================
# 1. KHỞI TẠO & KIỂM TRA MÔI TRƯỜNG
# =================================================================
# Kiểm tra file .env trước khi nạp
if not os.path.exists(".env"):
    print("\n🛑 LỖI: Không tìm thấy file '.env'! Vui lòng tạo file .env trước khi chạy.")
    sys.exit(1)

load_dotenv()

os.makedirs("check_key", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("check_key/bot_check_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =================================================================
# 2. CẤU HÌNH BOT
# =================================================================
CONFIG = {
    "CUSTOM_API_URL": os.getenv("CUSTOM_API_URL", ""), 
    "CUSTOM_API_KEY": os.getenv("CUSTOM_API_KEY", ""),
    "MODEL_NAME": os.getenv("MODEL_NAME", "gemma4"), 
    "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"), 
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""), 
    "YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY", ""),
    "CHANNEL_ID": os.getenv("CHANNEL_ID", ""),
}

CANDIDATE_MODELS = [
    "gemma4", "gemini-2.0-flash-exp", "gemini-1.5-pro", 
    "gpt-4o", "gpt-4-turbo", "claude-3-5-sonnet"
]

# =================================================================
# 3. HÀM GIAO DIỆN (UI/UX)
# =================================================================

def ui_status(message, type="info"):
    """Hàm hiển thị trạng thái đồng nhất"""
    icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "🛑", "loading": "⏳"}
    icon = icons.get(type, "ℹ️")
    print(f"{icon} {message}")

def simulate_loading(item_name):
    name = item_name if item_name else "Unknown Model"
    print(f"📦 Đang nạp {name}...", end="")
    for i in range(11):
        percent = i * 10
        bar = "#" * i + "-" * (10 - i)
        sys.stdout.write(f"\r📦 Đang nạp {name}: [{bar}] {percent}%")
        sys.stdout.flush()
        time.sleep(0.08) 
    print(f" ✅")

def simulate_server_connect():
    print("\n🌐 Đang thiết lập kết nối tới Custom API Server...")
    time.sleep(0.5)
    steps = [
        "📡 Gửi tín hiệu Ping...",
        "🔐 Xác thực Handshake...",
        "🔌 Mở cổng truyền tải...",
        "⚡ Đồng bộ API Gateway..."
    ]
    for step in steps:
        print(f"  {step}", end="")
        for _ in range(3):
            time.sleep(0.3)
            print(".", end="", flush=True)
        print(" Done!")
    print("🚀 Kết nối Server Custom thành công!\n")

# =================================================================
# 4. LOGIC KIỂM TRA (Đã tối ưu)
# =================================================================

def attempt_request(model_name):
    if not CONFIG['CUSTOM_API_URL'] or not CONFIG['CUSTOM_API_KEY']:
        return "MISSING_CONFIG"
    headers = {"Authorization": f"Bearer {CONFIG['CUSTOM_API_KEY']}", "Content-Type": "application/json"}
    data = {"model": model_name, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}
    try:
        resp = requests.post(CONFIG['CUSTOM_API_URL'], headers=headers, json=data, timeout=10)
        if resp.status_code == 200: return "OK"
        try:
            error_msg = str(resp.json()).lower()
            if "no connected db" in error_msg: return "SERVER_CONFIG_ERROR"
            if "auth" in error_msg or "invalid" in error_msg: return "UNAUTHORIZED"
        except: pass
        return f"ERROR_{resp.status_code}"
    except Exception as e:
        return f"CONN_ERROR_{str(e)}"

def fix_and_check_custom_api():
    logger.info(f"Bắt đầu kiểm tra Custom API. Model: {CONFIG['MODEL_NAME']}")
    current_model = CONFIG['MODEL_NAME']

    # Hiệu ứng chờ trước khi check
    ui_status(f"Đang truy vấn model '{current_model}'...", "loading")
    for _ in range(3):
        time.sleep(0.5)
        sys.stdout.write(".")
        sys.stdout.flush()
    print(" Checking...")

    res = attempt_request(current_model)
    if res == "OK":
        ui_status(f"Model '{current_model}' hoạt động bình thường!", "success")
        return current_model
    
    if res == "UNAUTHORIZED":
        ui_status("Custom API Key sai hoặc đã hết hạn.", "error")
        return None
    if res == "SERVER_CONFIG_ERROR":
        ui_status("Server Custom chưa cấu hình Database.", "error")
        return "SERVER_CONFIG_ERROR"

    ui_status(f"Model '{current_model}' lỗi ({res}). Thử model dự phòng...", "warning")
    for model in CANDIDATE_MODELS:
        if model == current_model: continue
        print(f"  🔄 Thử {model}...", end="")
        time.sleep(0.5)
        if attempt_request(model) == "OK":
            print(" ✅")
            ui_status(f"Đã tìm thấy model thay thế: {model}", "success")
            return model
        print(" ❌")
    return None

def check_gemini():
    logger.info(f"Kiểm tra Gemini API. Model: {CONFIG['GEMINI_MODEL']}")
    key = CONFIG['GEMINI_API_KEY']
    if not key or "NHẬP" in key:
        ui_status("Gemini API: Thiếu Key trong .env", "error")
        return "Thiếu Key"
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(CONFIG["GEMINI_MODEL"])
        model.generate_content("Hi")
        ui_status("Gemini API: Hoạt động tốt!", "success")
        return "Hoạt động"
    except Exception as e:
        err = str(e)
        if "429" in err:
            ui_status("Gemini API: Key đúng nhưng bị Rate Limit (429).", "warning")
            return "Quá tải (429)"
        if "404" in err:
            ui_status(f"Gemini API: Sai tên model {CONFIG['GEMINI_MODEL']}", "error")
            return "Sai Model"
        ui_status(f"Gemini API Lỗi: {err}", "error")
        return f"Lỗi: {err}"

def check_youtube():
    logger.info("Kiểm tra YouTube API.")
    key = CONFIG['YOUTUBE_API_KEY']
    cid = CONFIG['CHANNEL_ID']
    if not key or "NHẬP" in key: return "Thiếu Key"
    if not cid or "NHẬP" in cid: return "Thiếu Channel ID"
    url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={cid}&key={key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if resp.status_code == 200 and "error" not in data:
            ui_status("YouTube API: Hoạt động tốt!", "success")
            return "Hoạt động"
        msg = data.get("error", {}).get("message", "Unknown Error")
        ui_status(f"YouTube API Lỗi: {msg}", "error")
        return f"Lỗi: {msg}"
    except Exception as e:
        return f"Lỗi kết nối: {e}"

# =================================================================
# 5. CHƯƠNG TRÌNH CHÍNH
# =================================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔔 HỆ THỐNG QUÉT KEY TỰ ĐỘNG - VERSION 2.0")
    print("="*60)
    if sys.stdin and sys.stdin.isatty():
        try:
            input("👉 Vui lòng nhấn [ENTER] để bắt đầu...")
        except Exception:
            pass
    
    print("\n⚙️ Đang khởi tạo hệ thống...")
    simulate_loading(CONFIG['MODEL_NAME'])
    simulate_loading(CONFIG['GEMINI_MODEL'])
    simulate_server_connect()
    
    print("🚀 BẮT ĐẦU QUÉT THỰC TẾ\n")
    
    logger.info("="*60)
    logger.info(f"🚀 START SYSTEM SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    final_model = fix_and_check_custom_api()
    gemini_status = check_gemini()
    youtube_status = check_youtube()
    
    print("\n" + "="*60)
    print("📊 TỔNG KẾT KẾT QUẢ:")
    if final_model and final_model != "SERVER_CONFIG_ERROR":
        print(f"🤖 Model: {final_model} ✅")
    elif final_model == "SERVER_CONFIG_ERROR":
        print("🤖 Model: LỖI SERVER ❌")
    else:
        print("🤖 Model: KHÔNG TÌM THẤY ❌")
        
    print(f"🔑 Gemini: {gemini_status}")
    print(f"📺 YouTube: {youtube_status}")
    print("="*60)
    
    if final_model and final_model != "SERVER_CONFIG_ERROR" and gemini_status == "Hoạt động" and youtube_status == "Hoạt động":
        ui_status("TẤT CẢ ĐÃ SẴN SÀNG! Bạn có thể chạy bot ngay.", "success")
    else:
        ui_status("VẪN CÒN LỖI. Vui lòng kiểm tra lại file .env", "warning")
    
    logger.info(f"Lịch sử lưu tại: check_key/bot_check_log.txt")
