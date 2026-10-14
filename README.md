# IA-Youtube security hardening patch

This patch kit is designed for the repository `oiky8/IA-Youtube`. It does not alter your GitHub repository until you apply it locally.

## Protections added

- Encrypt API keys in `.secrets.enc` using Fernet authenticated encryption.
- On Windows, protect the vault encryption key using Windows DPAPI (bound to the current Windows user). Migrate existing `.secret.key` to DPAPI-protected storage when the existing OAuth-token encryption code first loads it.
- Automatically migrate recognized API keys from `.env` into the encrypted vault and blank those values in `.env`.
- Redact known API keys, bearer tokens, and common `?key=` parameters from logs.
- Require HTTPS for remote custom-model endpoints; allow HTTP only for loopback addresses such as `localhost` and `127.0.0.1` (needed for local Ollama).
- Send the Gemini API key in `x-goog-api-key` headers instead of URL query strings, and keep the YouTube key in request parameters rather than manually interpolating it into the URL.
- Add vault/key paths to `.gitignore`.

## Apply it

1. Download this patch kit and copy `security_layer.py` and `apply_security_patch.py` into the root of your local `IA-Youtube` checkout, beside `AI_MOD_ALL_IN_ONE.py`.
2. Close the bot. Make a copy of your repository or ensure Git has no unrelated uncommitted changes.
3. From that folder run:

   ```powershell
   python apply_security_patch.py
   python -m py_compile AI_MOD_ALL_IN_ONE.py security_layer.py
   ```

4. Start with `python AI_MOD_ALL_IN_ONE.py --diagnose` and then `python AI_MOD_ALL_IN_ONE.py --custom-check`. Confirm the custom API endpoint uses HTTPS unless it is on loopback.
5. Inspect the migration: `.env` should have blank values for migrated API-key fields; encrypted secrets should be in `.secrets.enc`. Keep `.secrets.enc`, `.security-vault.key*`, `.secret.key*`, `token.enc`, `client_secret.json`, and `.env` private and never commit them.
6. Review the generated `AI_MOD_ALL_IN_ONE.py.backup-<timestamp>` before deleting it. If anything behaves unexpectedly, restore that backup.
7. Commit the changes on your own `security-hardening` branch after local tests pass.

## Important compatibility notes

- The patcher makes a timestamped backup and checks exact source anchors before writing, to reduce the risk of patching an incompatible file. If it reports an unexpected match count, it stops without patching; inspect the current source and update the patch manually rather than forcing it.
- On Windows, DPAPI-protected keys can be decrypted only by the same Windows user on that machine. Back up your OAuth client configuration safely and sign in again if moving the app to another computer/user account.
- On non-Windows systems, the key file is restricted to owner read/write permissions where supported, but OS-native secret protection is preferable.
- Encryption at rest does not protect secrets from malware or someone already running code as your Windows account. Use least-privilege API keys, rotate any key that may have leaked, and restrict YouTube API key referrers/IPs where Google permits it.
- This is a security hardening patch, not a guarantee that the whole app is vulnerability-free. Test it in a non-live session first.
