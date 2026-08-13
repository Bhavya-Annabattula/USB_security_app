"""
manage_users.py
----------------
Standalone admin CLI for managing USB Physical Security Tool user accounts.

Run this instead of hand-editing source code to add, remove, or list users,
or to reset a password. Shares the same PBKDF2-HMAC-SHA256 hashing logic
and the same users_data.json store used by code.py at runtime.

Usage:
    python manage_users.py add <username>
    python manage_users.py remove <username>
    python manage_users.py list
    python manage_users.py passwd <username>
"""

import sys
import getpass
import user_store as store


def cmd_add(args):
    if len(args) != 1:
        print("Usage: python manage_users.py add <username>")
        return 1
    username = args[0]
    if username in store.list_users():
        print(f"User '{username}' already exists. Use 'passwd' to change their password.")
        return 1

    password = getpass.getpass("New password (min 8 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return 1

    try:
        store.add_user(username, password)
    except store.UserError as e:
        print(f"Error: {e}")
        return 1

    print(f"User '{username}' created successfully.")
    return 0


def cmd_remove(args):
    if len(args) != 1:
        print("Usage: python manage_users.py remove <username>")
        return 1
    username = args[0]
    confirm = input(f"Type '{username}' again to confirm deletion: ")
    if confirm != username:
        print("Confirmation did not match. Aborted.")
        return 1
    try:
        store.remove_user(username)
    except store.UserError as e:
        print(f"Error: {e}")
        return 1
    print(f"User '{username}' removed.")
    return 0


def cmd_list(args):
    users = store.list_users()
    print(f"{len(users)} user(s):")
    for u in users:
        print(f"  - {u}")
    return 0


def cmd_passwd(args):
    if len(args) != 1:
        print("Usage: python manage_users.py passwd <username>")
        return 1
    username = args[0]
    if username not in store.list_users():
        print(f"User '{username}' does not exist.")
        return 1

    password = getpass.getpass("New password (min 8 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return 1

    try:
        store.change_password(username, password)
    except store.UserError as e:
        print(f"Error: {e}")
        return 1

    print(f"Password for '{username}' updated.")
    return 0


COMMANDS = {
    "add": cmd_add,
    "remove": cmd_remove,
    "list": cmd_list,
    "passwd": cmd_passwd,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
