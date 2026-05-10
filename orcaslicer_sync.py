#!/usr/bin/env python3
"""
Voron config management script.

Commands:
    sync-machine --nozzle 0.4     Read machine-level settings from one OrcaSlicer
                                  profile and sync to all other Voron profiles in
                                  OrcaSlicer.

    pull-machine                  Copy all Voron profiles from OrcaSlicer into repo.

    push-machine                  Copy all Voron profiles from repo into OrcaSlicer.

Usage:
    python voron.py sync-machine --nozzle 0.4
    python voron.py pull-machine
    python voron.py push-machine
    python voron.py pull-machine --dry-run
"""

import json
import shutil
import argparse
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_DIR      = Path(__file__).parent
MACHINE_REPO  = REPO_DIR / "orcaslicer" / "machine"
MACHINE_ORCA  = Path.home() / "AppData" / "Roaming" / "OrcaSlicer" / "user" / "default" / "machine"

# ── Settings ──────────────────────────────────────────────────────────────────

PRINTER_LEVEL_FIELDS = {
    "inherits",
    "from",
    "instantiation",
    "version",
    "machine_max_acceleration_x",
    "machine_max_acceleration_y",
    "machine_max_acceleration_z",
    "machine_max_speed_x",
    "machine_max_speed_y",
    "machine_max_speed_z",
    "machine_start_gcode",
    "machine_end_gcode",
    "change_filament_gcode",
    "printable_area",
    "printable_height",
    "extruder_clearance_height_to_rod",
    "extruder_clearance_radius",
    "support_multi_bed_types",
    "printer_extruder_id",
    "printer_extruder_variant",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        f.write("\n")

def voron_profiles(directory: Path) -> list[Path]:
    return sorted(directory.glob("Voron *.json"))

def nozzle_to_filename(nozzle: str) -> str:
    return f"Voron {nozzle}.json"

def copy_profiles(src_dir: Path, dst_dir: Path, dry_run: bool) -> None:
    if not dst_dir.exists():
        print(f"ERROR: destination not found: {dst_dir}")
        return

    profiles = voron_profiles(src_dir)
    if not profiles:
        print(f"No Voron profiles found in {src_dir}")
        return

    for json_path in profiles:
        info_path = json_path.with_suffix(".info")
        print(f"  {json_path.name}")
        if not dry_run:
            shutil.copy2(json_path, dst_dir / json_path.name)
        if info_path.exists():
            print(f"  {info_path.name}")
            if not dry_run:
                shutil.copy2(info_path, dst_dir / info_path.name)
        else:
            print(f"  WARNING: no .info for {json_path.name}")

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_sync_machine(nozzle: str, dry_run: bool) -> None:
    source_path = MACHINE_ORCA / nozzle_to_filename(nozzle)
    if not source_path.exists():
        print(f"ERROR: profile not found in OrcaSlicer: {source_path.name}")
        return

    source = load_json(source_path)
    targets = [p for p in voron_profiles(MACHINE_ORCA) if p.resolve() != source_path.resolve()]

    if not targets:
        print("No other Voron profiles found in OrcaSlicer to sync to.")
        return

    printer_values = {k: v for k, v in source.items() if k in PRINTER_LEVEL_FIELDS}

    print(f"Source:  {source_path.name}")
    print(f"Targets: {[t.name for t in targets]}")
    print()

    for target_path in targets:
        target = load_json(target_path)
        changes = {}

        for field, value in printer_values.items():
            if field not in target or target[field] != value:
                changes[field] = (target.get(field, "(missing)"), value)
                target[field] = value

        if changes:
            print(f"  {target_path.name}:")
            for field, (old, new) in changes.items():
                print(f"    {field}: {old!r} -> {new!r}")
            if not dry_run:
                save_json(target_path, target)
        else:
            print(f"  {target_path.name}: no changes")

    if dry_run:
        print("\nDry run — no files written.")
    else:
        print("\nSync complete.")


def cmd_pull_machine(dry_run: bool) -> None:
    print(f"Pulling from: {MACHINE_ORCA}")
    print(f"         to: {MACHINE_REPO}")
    print()
    MACHINE_REPO.mkdir(parents=True, exist_ok=True)
    copy_profiles(MACHINE_ORCA, MACHINE_REPO, dry_run)
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPull complete. Remember to git add + commit.")


def cmd_push_machine(dry_run: bool) -> None:
    print(f"Pushing from: {MACHINE_REPO}")
    print(f"          to: {MACHINE_ORCA}")
    print()
    copy_profiles(MACHINE_REPO, MACHINE_ORCA, dry_run)
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPush complete. Restart OrcaSlicer to see changes.")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Voron config management.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync-machine", help="Sync machine settings from one OrcaSlicer profile to all others.")
    p_sync.add_argument("--nozzle", required=True, help="Nozzle size to use as source e.g. 0.4")

    sub.add_parser("pull-machine", help="Copy Voron profiles from OrcaSlicer into repo.")
    sub.add_parser("push-machine", help="Copy Voron profiles from repo into OrcaSlicer.")

    args = parser.parse_args()

    if args.command == "sync-machine":
        cmd_sync_machine(args.nozzle, args.dry_run)
    elif args.command == "pull-machine":
        cmd_pull_machine(args.dry_run)
    elif args.command == "push-machine":
        cmd_push_machine(args.dry_run)

if __name__ == "__main__":
    main()
