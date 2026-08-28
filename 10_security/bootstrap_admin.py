import sys
import uuid
import getpass
import argparse
from datetime import datetime, timezone

from .models import User, UserRole
from .password import hash_password, PasswordPolicy
from .repository import get_security_repository


def bootstrap_admin(username: str, display_name: str, password: str | None = None) -> User:
    """Creates an administrator user account without hard-coded credentials."""
    repo = get_security_repository()
    clean_username = username.strip().lower()

    existing = repo.get_user_by_username(clean_username)
    if existing:
        print(f"[!] User '{clean_username}' already exists (role={existing.role.value}).")
        return existing

    if not password:
        password = getpass.getpass(f"Enter password for admin '{clean_username}' (min 15 chars): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("[-] Error: Passwords do not match.")
            sys.exit(1)

    valid, err_msg = PasswordPolicy.validate(password)
    if not valid:
        print(f"[-] Password policy violation: {err_msg}")
        sys.exit(1)

    pwd_hash = hash_password(password)
    now = datetime.now(timezone.utc)
    user = User(
        user_id=str(uuid.uuid4()),
        username=clean_username,
        display_name=display_name.strip() or clean_username.capitalize(),
        password_hash=pwd_hash,
        role=UserRole.ADMIN,
        enabled=True,
        must_change_password=False,
        created_at=now,
        updated_at=now
    )

    repo.save_user(user)
    print(f"[+] Administrator '{clean_username}' successfully provisioned (ID: {user.user_id}).")
    return user


def main():
    parser = argparse.ArgumentParser(description="SentinelTrack Administrator Bootstrap CLI")
    parser.add_argument("--username", "-u", default="admin", help="Admin username")
    parser.add_argument("--display-name", "-n", default="System Administrator", help="Display name")
    parser.add_argument("--password", "-p", default=None, help="Password (optional, prompted if omitted)")
    args = parser.parse_args()

    bootstrap_admin(username=args.username, display_name=args.display_name, password=args.password)


if __name__ == "__main__":
    main()

