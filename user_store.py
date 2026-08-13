"""
user_store.py
--------------
Shared user-management logic for the USB Physical Security Tool.

Users are persisted in `users_data.json` (NOT plain Python source) so that
both the GUI ("Create Account" button, admin-only) and the standalone
`manage_users.py` CLI script can add/remove/list users without editing
or regenerating source code.

Passwords are salted + hashed with PBKDF2-HMAC-SHA256 (260,000 iterations),
matching the scheme already used in code.py. Plaintext passwords are never
stored.

JSON on disk looks like:
{
    "admin": {"salt": "<hex>", "hash": "<hex>"},
    "bhavya": {"salt": "<hex>", "hash": "<hex>"}
}
"""

import hashlib
import hmac
import os
import json
import datetime

PBKDF2_ITERATIONS = 260_000
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users_data.json")


# ---------- Hashing ----------

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return salt, derived


def verify_password(password, salt, expected_hash):
    _, derived = hash_password(password, salt)
    return hmac.compare_digest(derived, expected_hash)


# ---------- Persistence ----------

def _default_users():
    """Used only the very first time the app runs and no users_data.json exists yet."""
    users = {}
    for username, password in [("admin", "adminpass123"), ("bhavya", "mypassword456")]:
        salt, digest = hash_password(password)
        users[username] = {"salt": salt.hex(), "hash": digest.hex()}
    return users


def load_users():
    """Returns dict: username -> (salt_bytes, hash_bytes)"""
    if not os.path.exists(USERS_FILE):
        users = _default_users()
        _write_raw(users)
    else:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)

    result = {}
    for username, record in users.items():
        result[username] = (bytes.fromhex(record["salt"]), bytes.fromhex(record["hash"]))
    return result


def _write_raw(users_dict_hex):
    """users_dict_hex: username -> {"salt": hex, "hash": hex}"""
    tmp_path = USERS_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(users_dict_hex, f, indent=2, sort_keys=True)
    os.replace(tmp_path, USERS_FILE)  # atomic write, avoids corruption on crash


def save_users(users):
    """users: username -> (salt_bytes, hash_bytes)"""
    out = {}
    for username, (salt, digest) in users.items():
        out[username] = {"salt": salt.hex(), "hash": digest.hex()}
    _write_raw(out)


# ---------- User management operations ----------

class UserError(Exception):
    pass


def add_user(username, password, allow_overwrite=False):
    username = username.strip()
    if not username:
        raise UserError("Username cannot be empty.")
    if len(password) < 8:
        raise UserError("Password must be at least 8 characters.")

    users = load_users()
    if username in users and not allow_overwrite:
        raise UserError(f"User '{username}' already exists.")

    salt, digest = hash_password(password)
    users[username] = (salt, digest)
    save_users(users)
    return True


def remove_user(username):
    users = load_users()
    if username not in users:
        raise UserError(f"User '{username}' does not exist.")
    if len(users) == 1:
        raise UserError("Refusing to remove the last remaining user.")
    del users[username]
    save_users(users)
    return True


def list_users():
    return sorted(load_users().keys())


def change_password(username, new_password):
    users = load_users()
    if username not in users:
        raise UserError(f"User '{username}' does not exist.")
    if len(new_password) < 8:
        raise UserError("Password must be at least 8 characters.")
    salt, digest = hash_password(new_password)
    users[username] = (salt, digest)
    save_users(users)
    return True
