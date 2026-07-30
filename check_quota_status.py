import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# SỬA TẠI ĐÂY: Dùng model ổn định nhất để check key trước
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash") 

print("==================================================")
print("     DIAGNOSTIC: API QUOTA & RATE LIMIT STATUS    ")
print("==================================================")
print("\n[1] Testing Gemini API Key status...")

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY missing in .env")
else:
    url = f"https://googleapis.com{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": "quota check"}]}]}
    try:
        resp = requests.post(url, json=payload, timeout=30)
        
        if resp.status_code == 200:
            print("✅ GEMINI_API_KEY: HOẠT ĐỘNG BÌNH THƯỜNG (Chưa cạn Quota)")
            print("   - Định mức Free Tier:")
            print("     + 15 RPM (Requests/Min) | 1,500 RPD (Requests/Day)")
        elif resp.status_code == 429:
            print("❌ GEMINI_API_KEY: BỊ THOÁT QUOTA / RATE LIMIT (Mã 429)")
        elif resp.status_code == 403:
            print("❌ GEMINI_API_KEY: BỊ KHÓA / SAI KEY (Mã 403)")
            try:
                print(f"   - Chi tiết: {resp.json().get('error', {}).get('message', '')}")
            except: pass
        # SỬA TẠI ĐÂY: Bắt riêng mã 503 để đọc lý do cụ thể từ Google
        elif resp.status_code == 503:
            print("❌ LỖI 503: MÁY CHỦ OVERLOAD HOẶC IP VPN CỦA BẠN BỊ CHẶN")
            try:
                # In ra thông báo chính xác từ Google để biết do IP hay do Server
                print(f"   - Chi tiết từ Google: {resp.json().get('error', {}).get('message', '')}")
            except: 
                print("   - Không thể đọc chi tiết lỗi JSON từ phản hồi 503.")
        else:
            print(f"⚠️ Trạng thái không xác định: {resp.status_code}")
            try:
                print(f"   - Phản hồi: {resp.text}")
            except: pass
            
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
