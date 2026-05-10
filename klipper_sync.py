#!/usr/bin/env python3
"""
Klipper config sync script.
Pulls config files from the Klipper RPi to the local repo over SFTP.

Requirements:
    pip install paramiko python-dotenv

Usage:
    python klipper_sync.py pull
    python klipper_sync.py pull --dry-run
    python klipper_sync.py push
    python klipper_sync.py push --dry-run

Credentials are read from a .env file in the same directory as this script.
Any values not in .env are prompted interactively.

.env format:
    KLIPPER_HOST=voron2dot4.local
    KLIPPER_USER=voron
    KLIPPER_PASSWORD=yourpassword
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("ERROR: paramiko not installed. Run: pip install paramiko")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv optional — falls back to os.environ or prompts

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_DIR      = Path(__file__).parent
LOCAL_CONFIG  = REPO_DIR / "klipper"
REMOTE_CONFIG = "/home/voron/printer_data/config"

# ── Exclusions ────────────────────────────────────────────────────────────────
# Files matching these rules are skipped on pull.
# EXCLUDE_EXTENSIONS: exact extension match
# EXCLUDE_PATTERNS:   prefix match against filename

EXCLUDE_EXTENSIONS = {".bkp"}
EXCLUDE_PATTERNS   = [
    "printer-",   # Klipper dated backup files e.g. printer-20260422_195701.cfg
]

def is_excluded(rel_path: str) -> bool:
    name = Path(rel_path).name
    if Path(rel_path).suffix in EXCLUDE_EXTENSIONS:
        return True
    if any(name.startswith(p) for p in EXCLUDE_PATTERNS):
        return True
    return False

# ── Credentials ───────────────────────────────────────────────────────────────

def resolve_credentials(host_arg: str | None, user_arg: str | None, password_arg: str | None) -> tuple[str, str, str]:
    host     = host_arg     or os.environ.get("KLIPPER_HOST")
    user     = user_arg     or os.environ.get("KLIPPER_USER")
    password = password_arg or os.environ.get("KLIPPER_PASSWORD")

    if not host:
        host = input("Klipper hostname [voron2dot4.local]: ").strip() or "voron2dot4.local"
    if not user:
        user = input("SSH username [voron]: ").strip() or "voron"
    if not password:
        password = getpass.getpass(f"Password for {user}@{host}: ")

    return host, user, password

# ── Helpers ───────────────────────────────────────────────────────────────────

def connect(host: str, user: str, password: str):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {user}@{host}...")
    client.connect(host, username=user, password=password)
    print("Connected.")
    return client.open_sftp(), client

def list_remote(sftp, remote_dir: str) -> list[str]:
    """Recursively list all files under remote_dir, return relative paths."""
    import stat
    results = []
    def _walk(path: str) -> None:
        for entry in sftp.listdir_attr(path):
            full = f"{path}/{entry.filename}"
            if stat.S_ISDIR(entry.st_mode):
                _walk(full)
            else:
                results.append(full)
    _walk(remote_dir)
    return [p[len(remote_dir)+1:] for p in results]

def list_local(local_dir: Path) -> list[str]:
    """Recursively list all files under local_dir, return relative paths."""
    if not local_dir.exists():
        return []
    return [
        str(p.relative_to(local_dir)).replace("\\", "/")
        for p in local_dir.rglob("*")
        if p.is_file()
    ]

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_pull(host: str, user: str, password: str, dry_run: bool) -> None:
    sftp, client = connect(host, user, password)
    try:
        LOCAL_CONFIG.mkdir(parents=True, exist_ok=True)
        files = list_remote(sftp, REMOTE_CONFIG)

        if not files:
            print("No files found on remote.")
            return

        print(f"\nPulling from {host}:{REMOTE_CONFIG}")
        print(f"          to {LOCAL_CONFIG}")
        print()

        for rel_path in sorted(files):
            if is_excluded(rel_path):
                print(f"  SKIP {rel_path}")
                continue
            remote_path = f"{REMOTE_CONFIG}/{rel_path}"
            local_path  = LOCAL_CONFIG / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"  {rel_path}")
            if not dry_run:
                sftp.get(remote_path, str(local_path))

        if dry_run:
            print("\nDry run — no files written.")
        else:
            print("\nPull complete. Remember to git add + commit.")
    finally:
        sftp.close()
        client.close()


def cmd_push(host: str, user: str, password: str, dry_run: bool) -> None:
    sftp, client = connect(host, user, password)
    try:
        files = list_local(LOCAL_CONFIG)

        if not files:
            print(f"No files found in {LOCAL_CONFIG}")
            return

        print(f"\nPushing from {LOCAL_CONFIG}")
        print(f"          to {host}:{REMOTE_CONFIG}")
        print()

        for rel_path in sorted(files):
            local_path    = LOCAL_CONFIG / rel_path
            remote_path   = f"{REMOTE_CONFIG}/{rel_path}"
            remote_parent = str(Path(remote_path).parent).replace("\\", "/")
            if not dry_run:
                try:
                    sftp.stat(remote_parent)
                except FileNotFoundError:
                    sftp.mkdir(remote_parent)
            print(f"  {rel_path}")
            if not dry_run:
                sftp.put(str(local_path), remote_path)

        if dry_run:
            print("\nDry run — no files copied.")
        else:
            print("\nPush complete. Restart Klipper to apply changes.")
    finally:
        sftp.close()
        client.close()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Klipper config sync over SFTP.")
    parser.add_argument("command",     choices=["pull", "push"])
    parser.add_argument("--host",      default=None, help="RPi hostname (overrides .env)")
    parser.add_argument("--user",      default=None, help="SSH username (overrides .env)")
    parser.add_argument("--password",  default=None, help="SSH password (overrides .env)")
    parser.add_argument("--dry-run",   action="store_true", help="Preview without transferring files")
    args = parser.parse_args()

    host, user, password = resolve_credentials(args.host, args.user, args.password)

    if args.command == "pull":
        cmd_pull(host, user, password, args.dry_run)
    elif args.command == "push":
        cmd_push(host, user, password, args.dry_run)

if __name__ == "__main__":
    main()