import obspython as obs
import subprocess
import os
import sys
import shutil
ENGINE_FILE = "AI_MOD_ALL_IN_ONE.py"
STREAMING_FLAG_FILE = os.path.join(os.path.dirname(__file__), "streaming.flag")
bot_process = None
OBS_AUTO_START = os.environ.get("OBS_AUTO_START", "1").lower() in ("1", "true", "yes", "on")
def script_description():
    return "AI Mod Bot v25_ULTIMATE - Bảng điều khiển chuyên dụng. Bot tự kích hoạt khi bấm Start Streaming."
def on_streaming_started():
    try:
        with open(STREAMING_FLAG_FILE, "w", encoding="utf-8") as f:
            f.write("streaming")
        obs.script_log(obs.LOG_INFO, "Da bam Start Streaming -> bao hieu AI Bot kich hoat.")
    except Exception as e:
        obs.script_log(obs.LOG_ERROR, f"Loi tao streaming.flag: {e}")
def on_streaming_stopped():
    try:
        if os.path.exists(STREAMING_FLAG_FILE):
            os.remove(STREAMING_FLAG_FILE)
        obs.script_log(obs.LOG_INFO, "Da bam Stop Streaming -> bao hieu AI Bot quay ve cho.")
    except Exception as e:
        obs.script_log(obs.LOG_ERROR, f"Loi xoa streaming.flag: {e}")
def on_obs_frontend_event(event):
    if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
        on_streaming_started()
    elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
        on_streaming_stopped()
def start_bot_callback(props, prop):
    global bot_process
    script_path = os.path.join(os.path.dirname(__file__), ENGINE_FILE)
    if not os.path.exists(script_path):
        obs.script_log(obs.LOG_ERROR, f"KHÔNG TÌM THẤY FILE: {ENGINE_FILE}. Vui lòng kiểm tra lại thư mục!")
        return
    python_exe = shutil.which("python")
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
        obs.script_log(obs.LOG_ERROR, "Khong tim thay Python. Cai Python 3.10+ va chay: py -3 -m pip install -r requirements.txt")
        return
    if bot_process is None or bot_process.poll() is not None:
        try:
            creation_flags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            obs.script_log(obs.LOG_INFO, f"Khởi động Engine: {ENGINE_FILE} bằng {python_exe}")
            bot_process = subprocess.Popen(
                [python_exe, script_path],
                cwd=os.path.dirname(script_path),
                creationflags=creation_flags
            )
            obs.script_log(obs.LOG_INFO, f"AI Bot đã khởi chạy thành công (PID: {bot_process.pid})")
        except Exception as e:
            obs.script_log(obs.LOG_ERROR, f"Lỗi khởi động: {e}")
def stop_bot_callback(props, prop):
    global bot_process
    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
        bot_process = None
        obs.script_log(obs.LOG_INFO, "AI Bot đã được dừng.")
    else:
        obs.script_log(obs.LOG_WARNING, "Bot hiện không chạy.")
def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_button(props, "btn_start", "🚀 KHỞI ĐỘNG AI BOT", start_bot_callback)
    obs.obs_properties_add_button(props, "btn_stop", "🛑 DỪNG AI BOT", stop_bot_callback)
    return props
def script_unload():
    obs.obs_frontend_remove_event_callback(on_obs_frontend_event)
    stop_bot_callback(None, None)
def script_load(settings):
    # Don file flag cu (phong khi OBS bi tat dot ngot lan truoc, flag con sot lai)
    try:
        if os.path.exists(STREAMING_FLAG_FILE):
            os.remove(STREAMING_FLAG_FILE)
    except Exception:
        pass
    obs.obs_frontend_add_event_callback(on_obs_frontend_event)
    # Neu OBS dang stream san luc script vua duoc nap, kich hoat ngay khong cho su kien tuong lai
    try:
        if obs.obs_frontend_streaming_active():
            on_streaming_started()
    except Exception:
        pass
    if OBS_AUTO_START:
        start_bot_callback(None, None)