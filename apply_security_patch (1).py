"""Apply the IA-Youtube security hardening patch to a local checkout.

Run from the repository folder:
    python apply_security_patch.py

The script makes a timestamped backup and refuses unknown/already-patched sources.
"""
from __future__ import annotations
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "AI_MOD_ALL_IN_ONE.py"
GITIGNORE = ROOT / ".gitignore"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match for {label}, found {count}; no changes written.")
    return source.replace(old, new, 1)


def replace_in_function(source: str, function_name: str, next_function: str, old: str, new: str, label: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        raise RuntimeError(f"Cannot find function {function_name}; no changes written.")
    end = source.find(f"\ndef {next_function}(", start + 1)
    if end < 0:
        end = len(source)
    body = source[start:end]
    if body.count(old) != 1:
        raise RuntimeError(f"Expected exactly one match in {function_name} for {label}, found {body.count(old)}; no changes written.")
    body = body.replace(old, new, 1)
    return source[:start] + body + source[end:]


def main() -> int:
    if not TARGET.exists():
        print("ERROR: Put apply_security_patch.py and security_layer.py beside AI_MOD_ALL_IN_ONE.py.")
        return 2
    source = TARGET.read_text(encoding="utf-8")
    if "from security_layer import" in source:
        print("Security patch appears to be already installed; leaving files unchanged.")
        return 0

    updated = source
    updated = replace_once(
        updated,
        "from dotenv import load_dotenv\nfrom logging.handlers import RotatingFileHandler",
        "from dotenv import load_dotenv\nfrom security_layer import (\n"
        "    SecretRedactionFilter, get_fernet_key, is_safe_api_url,\n"
        "    load_secure_secrets_into_env, migrate_env_config, set_secure_secret,\n"
        ")\nfrom logging.handlers import RotatingFileHandler",
        "security imports",
    )
    updated = replace_once(
        updated,
        "    required_configs = {\n",
        "    # Migrate any API credentials from legacy plaintext .env into the encrypted vault.\n"
        "    migrate_env_config(existing_config, env_path)\n\n"
        "    required_configs = {\n",
        "configuration migration hook",
    )
    updated = replace_once(
        updated,
        "        existing_config[key] = val\n        updated = True\n",
        "        if key in (\"CUSTOM_API_KEY\", \"GEMINI_API_KEY\", \"YOUTUBE_API_KEY\"):\n"
        "            if val and val != \"MISSING\":\n"
        "                set_secure_secret(key, val, BASE_DIR)\n"
        "            existing_config[key] = \"\"\n"
        "        else:\n"
        "            existing_config[key] = val\n"
        "        updated = True\n",
        "store prompted credentials in vault",
    )
    updated = replace_once(
        updated,
        "    load_dotenv(env_path, override=True)\n",
        "    load_dotenv(env_path, override=True)\n"
        "    # Encrypted vault wins over blank legacy .env entries.\n"
        "    load_secure_secrets_into_env(BASE_DIR)\n",
        "load encrypted secrets",
    )

    # Migrate the old plaintext Fernet key to a DPAPI-protected key on Windows.
    key_func = re.compile(r"def _get_encryption_key\(\):\n.*?(?=\ndef save_encrypted_json\()", re.S)
    matches = list(key_func.finditer(updated))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one legacy token-key function, found {len(matches)}; no changes written.")
    updated = key_func.sub("def _get_encryption_key():\n    return get_fernet_key(SECRET_KEY_FILE)\n", updated, count=1)

    # Do not put Gemini API keys in query strings (query strings commonly enter logs).
    updated = replace_in_function(
        updated, "gemini_api", "friend_pc_api",
        'url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"',
        'url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"',
        "Gemini URL query-key removal",
    )
    updated = replace_in_function(
        updated, "gemini_api", "friend_pc_api",
        "resp = session.post(url, json=payload, timeout=20)",
        'resp = session.post(url, json=payload, headers={"x-goog-api-key": key}, timeout=20)',
        "Gemini API-key header",
    )
    updated = replace_in_function(
        updated, "check_gemini_api", "check_youtube_api",
        'url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"',
        'url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"',
        "Gemini diagnostic URL query-key removal",
    )
    updated = replace_in_function(
        updated, "check_gemini_api", "check_youtube_api",
        'resp = requests.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]}, timeout=8)',
        'resp = requests.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]}, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=8)',
        "Gemini diagnostic API-key header",
    )

    # Keep YouTube API key in request params, not a hand-built URL.
    updated = replace_in_function(
        updated, "investigate_user", "check_user_safety",
        'url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id={cid}&key={yt_key}"\n'
        "        resp = session.get(url, timeout=10)",
        'url = "https://www.googleapis.com/youtube/v3/channels"\n'
        '        resp = session.get(url, params={"part": "snippet,statistics", "id": cid, "key": yt_key}, timeout=10)',
        "YouTube API-key query handling",
    )

    # Validate custom/remote model URLs; plaintext HTTP is permitted only for loopback services.
    updated = replace_in_function(
        updated, "friend_pc_api", "ollama_api",
        "    if not CUSTOM_API_URL or not CUSTOM_API_KEY: return None\n",
        "    if not CUSTOM_API_URL or not CUSTOM_API_KEY: return None\n"
        "    if not is_safe_api_url(CUSTOM_API_URL):\n"
        "        logger.error(\"[SECURITY] Custom API URL rejected: HTTPS is required for remote hosts.\")\n"
        "        return None\n",
        "custom API HTTPS guard",
    )
    updated = replace_in_function(
        updated, "ollama_api", "route_ai",
        "    if not OLLAMA_API_URL or not OLLAMA_MODEL: return None\n",
        "    if not OLLAMA_API_URL or not OLLAMA_MODEL: return None\n"
        "    if not is_safe_api_url(OLLAMA_API_URL):\n"
        "        logger.error(\"[SECURITY] Ollama URL rejected: use HTTPS or a loopback HTTP address.\")\n"
        "        return None\n",
        "Ollama URL guard",
    )
    updated = replace_in_function(
        updated, "custom_api_request", "check_custom_api",
        "    if not CUSTOM_API_URL or not CUSTOM_API_KEY:\n"
        '        return "MISSING_CONFIG", "Thiếu CUSTOM_API_URL hoặc CUSTOM_API_KEY"\n',
        "    if not CUSTOM_API_URL or not CUSTOM_API_KEY:\n"
        '        return "MISSING_CONFIG", "Thiếu CUSTOM_API_URL hoặc CUSTOM_API_KEY"\n'
        "    if not is_safe_api_url(CUSTOM_API_URL):\n"
        '        return "UNSAFE_URL", "Custom API must use HTTPS unless it is a loopback service"\n',
        "custom API diagnostic URL guard",
    )

    updated = replace_once(
        updated,
        "logger.addHandler(fh); logger.addHandler(ch)\n",
        "_redaction_filter = SecretRedactionFilter()\n"
        "fh.addFilter(_redaction_filter); ch.addFilter(_redaction_filter)\n"
        "logger.addHandler(fh); logger.addHandler(ch)\n",
        "log redaction filter",
    )

    # Fail closed: the configured remote model must not silently use an unsafe cleartext URL.
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_name(TARGET.name + f".backup-{timestamp}")
    shutil.copy2(TARGET, backup)
    TARGET.write_text(updated, encoding="utf-8", newline="\n")

    if GITIGNORE.exists():
        gi = GITIGNORE.read_text(encoding="utf-8")
        additions = [".secrets.enc", ".security-vault.key", ".security-vault.key.dpapi", ".secret.key.dpapi"]
        if not all(item in gi for item in additions):
            with GITIGNORE.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write("\n# Security vault / OS-protected key material\n")
                for item in additions:
                    if item not in gi:
                        handle.write(item + "\n")
    print(f"Security patch applied. Backup: {backup.name}")
    print("Next: python -m py_compile AI_MOD_ALL_IN_ONE.py security_layer.py")
    print("Then test with --diagnose/--custom-check before streaming.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("No target changes were written unless the success message appeared.", file=sys.stderr)
        raise SystemExit(1)
