import hashlib
import hmac
import os
import re

PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 260000


def hash_password(password, iterations=PBKDF2_ITERATIONS):
    salt = os.urandom(16).hex()
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    ).hex()
    return f"{PBKDF2_SCHEME}${iterations}${salt}${derived_key}"


def verify_password(password, stored_hash):
    if not stored_hash:
        return False

    if stored_hash.startswith(f"{PBKDF2_SCHEME}$"):
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False

        try:
            _, iterations, salt, expected_hash = parts
            iterations = int(iterations)
            computed_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt),
                iterations,
            ).hex()
            return hmac.compare_digest(computed_hash, expected_hash)
        except Exception:
            return False

    # Legacy compatibility: existing SHA-256 records.
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


def needs_password_upgrade(stored_hash):
    return bool(stored_hash) and not stored_hash.startswith(f"{PBKDF2_SCHEME}$")


def validate_password_strength(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must include at least one number."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must include at least one special character."
    return True, "Strong password"
