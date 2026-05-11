#!/usr/bin/env python3
"""
OrcaSlicer config management script.

Commands:
    sync-machine --nozzle 0.4     Read machine-level settings from one OrcaSlicer
                                  profile and sync to all other Voron profiles in
                                  OrcaSlicer.

    sync-process --source NAME    Sync process-level settings from one process profile to all others.

    pull-machine                  Copy all Voron machine profiles from OrcaSlicer into repo.
    push-machine                  Copy all Voron machine profiles from repo into OrcaSlicer.

    pull-process                  Copy all process profiles from OrcaSlicer into repo.
    push-process                  Copy all process profiles from repo into OrcaSlicer.

    sync-filament --filament NAME --nozzle 0.4
                              Sync filament-level settings from one nozzle variant to all others.

    pull-filament                 Copy all filament profiles from OrcaSlicer into repo.
    push-filament                 Copy all filament profiles from repo into OrcaSlicer.

Usage:
    python orcaslicer_sync.py sync-machine --nozzle 0.4
    python orcaslicer_sync.py sync-process --source "0.20mm Standard @MyKlipper"
    python orcaslicer_sync.py pull-machine
    python orcaslicer_sync.py push-machine
    python orcaslicer_sync.py pull-process
    python orcaslicer_sync.py push-process
    python orcaslicer_sync.py sync-filament --filament "SUNLU PLA+ 2.0" --nozzle 0.4
    python orcaslicer_sync.py pull-filament
    python orcaslicer_sync.py push-filament
    python orcaslicer_sync.py sync-process --source "0.20mm Standard @MyKlipper"
    python orcaslicer_sync.py pull-machine --dry-run
"""

import json
import shutil
import argparse
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_DIR       = Path(__file__).parent
ORCA_USER      = Path.home() / "AppData" / "Roaming" / "OrcaSlicer" / "user" / "default"

MACHINE_REPO   = REPO_DIR / "orcaslicer" / "machine"
PROCESS_REPO   = REPO_DIR / "orcaslicer" / "process"
FILAMENT_REPO  = REPO_DIR / "orcaslicer" / "filament"

MACHINE_ORCA   = ORCA_USER / "machine"
PROCESS_ORCA   = ORCA_USER / "process"
FILAMENT_ORCA  = ORCA_USER / "filament"

# ── Settings ──────────────────────────────────────────────────────────────────

PROCESS_LEVEL_FIELDS = {
    "filename_format",
}

FILAMENT_LEVEL_FIELDS = {
    "inherits",
    "from",
    "version",
    "filament_extruder_variant",
    "filament_cost",
    "fan_max_speed",
    "overhang_fan_speed",
    "eng_plate_temp_initial_layer",
    "hot_plate_temp_initial_layer",
    "textured_plate_temp_initial_layer",
    "filament_flow_ratio",
    "enable_pressure_advance",
}

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

def all_profiles(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.json"))

def nozzle_to_filename(nozzle: str) -> str:
    return f"Voron {nozzle}.json"

def copy_profiles(src_dir: Path, dst_dir: Path, dry_run: bool, glob: str = "*.json") -> None:
    if not dst_dir.exists():
        print(f"ERROR: destination not found: {dst_dir}")
        return

    profiles = sorted(src_dir.glob(glob))
    if not profiles:
        print(f"No profiles found in {src_dir}")
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

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_sync_machine(nozzle: str, dry_run: bool) -> None:
    source_path = MACHINE_ORCA / nozzle_to_filename(nozzle)
    if not source_path.exists():
        print(f"ERROR: profile not found in OrcaSlicer: {source_path.name}")
        return

    source  = load_json(source_path)
    targets = [p for p in voron_profiles(MACHINE_ORCA) if p.resolve() != source_path.resolve()]

    if not targets:
        print("No other Voron profiles found in OrcaSlicer to sync to.")
        return

    printer_values = {k: v for k, v in source.items() if k in PRINTER_LEVEL_FIELDS}

    print(f"Source:  {source_path.name}")
    print(f"Targets: {[t.name for t in targets]}")
    print()

    for target_path in targets:
        target  = load_json(target_path)
        changes = {}

        for field, value in printer_values.items():
            if field not in target or target[field] != value:
                changes[field] = (target.get(field, "(missing)"), value)
                target[field]  = value

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



def cmd_sync_process(source_name: str, dry_run: bool) -> None:
    source_path = PROCESS_ORCA / source_name
    if not source_path.exists():
        # try adding .json
        source_path = PROCESS_ORCA / (source_name + ".json")
    if not source_path.exists():
        print(f"ERROR: process profile not found in OrcaSlicer: {source_name}")
        print(f"Available profiles:")
        for p in sorted(PROCESS_ORCA.glob("*.json")):
            print(f"  {p.name}")
        return

    source  = load_json(source_path)
    targets = [p for p in sorted(PROCESS_ORCA.glob("*.json")) if p.resolve() != source_path.resolve()]

    if not targets:
        print("No other process profiles found in OrcaSlicer to sync to.")
        return

    process_values = {k: v for k, v in source.items() if k in PROCESS_LEVEL_FIELDS}

    print(f"Source:  {source_path.name}")
    print(f"Targets: {[t.name for t in targets]}")
    print()

    for target_path in targets:
        target  = load_json(target_path)
        changes = {}

        for field, value in process_values.items():
            if field not in target or target[field] != value:
                changes[field] = (target.get(field, "(missing)"), value)
                target[field]  = value

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


def cmd_sync_filament(filament: str, nozzle: str, dry_run: bool) -> None:
    source_name = f"{filament} {nozzle}.json"
    source_path = FILAMENT_ORCA / source_name
    if not source_path.exists():
        print(f"ERROR: filament profile not found in OrcaSlicer: {source_name}")
        print("Available profiles:")
        for p in sorted(FILAMENT_ORCA.glob("*.json")):
            print(f"  {p.stem}")
        return

    # Find all nozzle variants of this filament (same base name, different nozzle suffix)
    targets = [
        p for p in sorted(FILAMENT_ORCA.glob(f"{filament} *.json"))
        if p.resolve() != source_path.resolve()
    ]

    if not targets:
        print(f"No other variants of '{filament}' found in OrcaSlicer.")
        return

    source = load_json(source_path)
    filament_values = {k: v for k, v in source.items() if k in FILAMENT_LEVEL_FIELDS}

    print(f"Source:  {source_path.name}")
    print(f"Targets: {[t.name for t in targets]}")
    print()

    for target_path in targets:
        target  = load_json(target_path)
        changes = {}

        for field, value in filament_values.items():
            if field not in target or target[field] != value:
                changes[field] = (target.get(field, "(missing)"), value)
                target[field]  = value

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
    print(f"          to: {MACHINE_REPO}")
    print()
    MACHINE_REPO.mkdir(parents=True, exist_ok=True)
    copy_profiles(MACHINE_ORCA, MACHINE_REPO, dry_run, glob="Voron *.json")
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPull complete. Remember to git add + commit.")


def cmd_push_machine(dry_run: bool) -> None:
    print(f"Pushing from: {MACHINE_REPO}")
    print(f"          to: {MACHINE_ORCA}")
    print()
    copy_profiles(MACHINE_REPO, MACHINE_ORCA, dry_run, glob="Voron *.json")
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPush complete. Restart OrcaSlicer to see changes.")


def cmd_pull_process(dry_run: bool) -> None:
    print(f"Pulling from: {PROCESS_ORCA}")
    print(f"          to: {PROCESS_REPO}")
    print()
    PROCESS_REPO.mkdir(parents=True, exist_ok=True)
    copy_profiles(PROCESS_ORCA, PROCESS_REPO, dry_run)
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPull complete. Remember to git add + commit.")


def cmd_push_process(dry_run: bool) -> None:
    print(f"Pushing from: {PROCESS_REPO}")
    print(f"          to: {PROCESS_ORCA}")
    print()
    copy_profiles(PROCESS_REPO, PROCESS_ORCA, dry_run)
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPush complete. Restart OrcaSlicer to see changes.")


def cmd_pull_filament(dry_run: bool) -> None:
    print(f"Pulling from: {FILAMENT_ORCA}")
    print(f"          to: {FILAMENT_REPO}")
    print()
    FILAMENT_REPO.mkdir(parents=True, exist_ok=True)
    copy_profiles(FILAMENT_ORCA, FILAMENT_REPO, dry_run)
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPull complete. Remember to git add + commit.")


def cmd_push_filament(dry_run: bool) -> None:
    print(f"Pushing from: {FILAMENT_REPO}")
    print(f"          to: {FILAMENT_ORCA}")
    print()
    copy_profiles(FILAMENT_REPO, FILAMENT_ORCA, dry_run)
    if dry_run:
        print("\nDry run — no files copied.")
    else:
        print("\nPush complete. Restart OrcaSlicer to see changes.")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OrcaSlicer config management.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync-machine",   help="Sync machine settings from one profile to all others.")
    p_sync.add_argument("--nozzle", required=True, help="Nozzle size to use as source e.g. 0.4")

    p_sync_proc = sub.add_parser("sync-process", help="Sync process settings from one profile to all others.")
    p_sync_proc.add_argument("--source", required=True, help="Source process profile filename (without .json)")

    sub.add_parser("pull-machine",  help="Copy Voron machine profiles from OrcaSlicer into repo.")
    sub.add_parser("push-machine",  help="Copy Voron machine profiles from repo into OrcaSlicer.")
    sub.add_parser("pull-process",  help="Copy process profiles from OrcaSlicer into repo.")
    sub.add_parser("push-process",  help="Copy process profiles from repo into OrcaSlicer.")
    p_sync_fil = sub.add_parser("sync-filament", help="Sync filament settings across nozzle variants.")
    p_sync_fil.add_argument("--filament", required=True, help="Base filament name e.g. 'SUNLU PLA+ 2.0'")
    p_sync_fil.add_argument("--nozzle",   required=True, help="Source nozzle size e.g. 0.4")

    sub.add_parser("pull-filament", help="Copy filament profiles from OrcaSlicer into repo.")
    sub.add_parser("push-filament", help="Copy filament profiles from repo into OrcaSlicer.")

    args = parser.parse_args()

    if args.command == "sync-machine":
        cmd_sync_machine(args.nozzle, args.dry_run)
    elif args.command == "sync-process":
        cmd_sync_process(args.source, args.dry_run)
    elif args.command == "pull-machine":
        cmd_pull_machine(args.dry_run)
    elif args.command == "push-machine":
        cmd_push_machine(args.dry_run)
    elif args.command == "pull-process":
        cmd_pull_process(args.dry_run)
    elif args.command == "push-process":
        cmd_push_process(args.dry_run)
    elif args.command == "sync-filament":
        cmd_sync_filament(args.filament, args.nozzle, args.dry_run)
    elif args.command == "pull-filament":
        cmd_pull_filament(args.dry_run)
    elif args.command == "push-filament":
        cmd_push_filament(args.dry_run)

if __name__ == "__main__":
    main()