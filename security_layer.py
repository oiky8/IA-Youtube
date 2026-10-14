"""Security helpers for IA-Youtube.

- Encrypts API credentials in an authenticated Fernet vault.
- Uses Windows DPAPI to protect the Fernet key on Windows.
- Migrates plaintext API keys from .env into the encrypted vault.
- Provides URL validation and log redaction helpers.

This is designed to be imported by AI_MOD_ALL_IN_ONE.py. Do not commit vault/key files.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, Mapping, Optional
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

SECRET_FILE_NAME = ".secrets.enc"
SECRET_KEY_NAME = ".security-vault.key"
FERNET_KEY_SUFFIX = ".dpapi"

_SECRET_NAME_RE = re.compile(
    r"^(?:CUSTOM_API_KEY|GEMINI_API_KEY(?:_\d+)?|YOUTUBE_API_KEY(?:_\d+)?|"
    r"OLLAMA_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|GOOGLE_API_KEY|"
    r"HF_TOKEN|HUGGINGFACEHUB_API_TOKEN)$",
    re.IGNORECASE,
)


def is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME_RE.fullmatch((name or "").strip()))


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        if os.name != "nt":
            os.chmod(temp_name, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        _secure_permissions(path, mode)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _secure_permissions(path: Path, mode: int = 0o600) -> None:
    # POSIX permission tightening. Windows secret keys are DPAPI protected.
    if os.name != "nt":
        try:
            os.chmod(path, mode)
        except OSError:
            pass


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_transform(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is available only on Windows")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    input_buffer = ctypes.create_string_buffer(data)
    input_blob = _DATA_BLOB(len(data), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output_blob = _DATA_BLOB()
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    if protect:
        fn = crypt32.CryptProtectData
        fn.argtypes = [ctypes.POINTER(_DATA_BLOB), ctypes.c_wchar_p,
                       ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_DATA_BLOB)]
        fn.restype = ctypes.c_int
        ok = fn(ctypes.byref(input_blob), "IA-Youtube local secret", None, None, None,
                flags, ctypes.byref(output_blob))
    else:
        description = ctypes.c_wchar_p()
        fn = crypt32.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(_DATA_BLOB), ctypes.POINTER(ctypes.c_wchar_p),
                       ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_DATA_BLOB)]
        fn.restype = ctypes.c_int
        ok = fn(ctypes.byref(input_blob), ctypes.byref(description), None, None, None,
                flags, ctypes.byref(output_blob))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))


def _key_for_file(key_path: Path) -> bytes:
    """Load/create a Fernet key; DPAPI-wrap it on Windows and migrate old raw keys."""
    protected_path = Path(str(key_path) + FERNET_KEY_SUFFIX)
    if os.name == "nt":
        if protected_path.exists():
            return _dpapi_transform(protected_path.read_bytes(), protect=False)
        if key_path.exists():
            # Compatibility migration for a key created by the old app version.
            legacy_key = key_path.read_bytes().strip()
            protected = _dpapi_transform(legacy_key, protect=True)
            _atomic_write(protected_path, protected)
            try:
                key_path.unlink()
            except OSError:
                # Never report a successful full migration if the plaintext key remains.
                raise RuntimeError(f"Protected key created, but legacy key could not be removed: {key_path}")
            return legacy_key
        key = Fernet.generate_key()
        _atomic_write(protected_path, _dpapi_transform(key, protect=True))
        return key

    # Non-Windows fallback: restrict the key file to the current user (0600).
    if key_path.exists():
        _secure_permissions(key_path)
        return key_path.read_bytes().strip()
    key = Fernet.generate_key()
    _atomic_write(key_path, key)
    return key


def get_fernet_key(key_file: str | os.PathLike[str]) -> bytes:
    return _key_for_file(Path(key_file).resolve())


def _vault_paths(base_dir: str | os.PathLike[str]) -> tuple[Path, Path]:
    root = Path(base_dir).resolve()
    return root / SECRET_FILE_NAME, root / SECRET_KEY_NAME


def _read_vault(base_dir: str | os.PathLike[str]) -> Dict[str, str]:
    vault_path, key_path = _vault_paths(base_dir)
    if not vault_path.exists():
        return {}
    key = _key_for_file(key_path)
    try:
        payload = Fernet(key).decrypt(vault_path.read_bytes())
        data = json.loads(payload.decode("utf-8"))
    except (InvalidToken, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Cannot decrypt the secrets vault; refusing to overwrite it") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Invalid secrets vault format")
    return {str(k): str(v) for k, v in data.items() if is_secret_name(str(k)) and isinstance(v, str)}


def store_secure_secrets(values: Mapping[str, str], base_dir: str | os.PathLike[str]) -> None:
    clean = {str(k): str(v) for k, v in values.items()
             if is_secret_name(str(k)) and isinstance(v, str) and v and v != "MISSING"}
    if not clean:
        return
    all_values = _read_vault(base_dir)
    all_values.update(clean)
    vault_path, key_path = _vault_paths(base_dir)
    key = _key_for_file(key_path)
    encrypted = Fernet(key).encrypt(json.dumps(all_values, ensure_ascii=False).encode("utf-8"))
    _atomic_write(vault_path, encrypted)


def set_secure_secret(name: str, value: str, base_dir: str | os.PathLike[str]) -> None:
    if not is_secret_name(name):
        raise ValueError(f"Refusing to store non-secret field in vault: {name}")
    store_secure_secrets({name: value}, base_dir)


def load_secure_secrets(base_dir: str | os.PathLike[str]) -> Dict[str, str]:
    return _read_vault(base_dir)


def load_secure_secrets_into_env(base_dir: str | os.PathLike[str]) -> None:
    for name, value in load_secure_secrets(base_dir).items():
        os.environ[name] = value


def migrate_env_config(config: dict, env_path: str | os.PathLike[str]) -> None:
    """Move recognized plaintext secrets out of parsed .env config and blank file values."""
    path = Path(env_path)
    found = {str(k): str(v).strip() for k, v in config.items()
             if is_secret_name(str(k)) and isinstance(v, str) and v.strip() and v.strip() != "MISSING"}
    if not found:
        return
    store_secure_secrets(found, path.parent)
    for key in found:
        config[key] = ""
    if path.exists():
        rewritten = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in line:
                name = line.split("=", 1)[0].strip()
                if name in found:
                    line = f"{name}="
            rewritten.append(line)
        _atomic_write(path, ("\n".join(rewritten) + "\n").encode("utf-8"))


def is_safe_api_url(url: str, allow_loopback_http: bool = True) -> bool:
    """Require HTTPS for remote endpoints; permit HTTP only to loopback services."""
    try:
        parsed = urlsplit((url or "").strip())
        if parsed.username or parsed.password or not parsed.hostname:
            return False
        if parsed.scheme.lower() == "https":
            return True
        if parsed.scheme.lower() != "http" or not allow_loopback_http:
            return False
        host = parsed.hostname.rstrip(".").lower()
        return host in {"localhost", "127.0.0.1", "::1"}
    except (ValueError, AttributeError):
        return False


def redact_sensitive(message: str) -> str:
    text = str(message)
    # Remove known secrets first, including secrets injected from the encrypted vault.
    for name, value in list(os.environ.items()):
        if is_secret_name(name) and value and len(value) >= 4:
            text = text.replace(value, "[REDACTED]")
    # Catch common formats even if a key was not loaded into this process environment.
    patterns = [
        (r"(?i)([?&](?:key|api_key|access_token|token)=)[^&#\s]+", r"\1[REDACTED]"),
        (r"(?i)(authorization\s*[:=]\s*['\"]?Bearer\s+)[^'\"\s,;]+", r"\1[REDACTED]"),
        (r"(?i)((?:CUSTOM_API_KEY|GEMINI_API_KEY(?:_\d+)?|YOUTUBE_API_KEY(?:_\d+)?|OLLAMA_API_KEY)\s*=\s*)[^\s,;]+", r"\1[REDACTED]"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


class SecretRedactionFilter:
    """Logging filter that prevents known API keys from reaching log files or console."""
    def filter(self, record) -> bool:
        try:
            record.msg = redact_sensitive(record.getMessage())
            record.args = ()
        except Exception:
            record.msg = "[SECURITY] Log message suppressed because redaction failed"
            record.args = ()
        return True
