#!/usr/bin/env python3
"""Repair a *specific, known* Aurora Minecraft TU75 metadata bug.

This tool deliberately refuses unfamiliar layouts and never edits the source.
Only uses Python's standard library. SPDX-License-Identifier: MIT.
"""

import argparse
from pathlib import Path
import sqlite3
import sys

TITLE_ID = 0x584111F7
MEDIA_ID = 0x7CD33B56
VERSION = 80                  # Final Minecraft Xbox 360 TU75 = internal version 80
TU_HASH = "134378DAA5728AEC36BC0A8777857D0E9CA6D17B"
TU_FILE = "tu00000001_00000000"
LIVE_PATH = "\\Content\\0000000000000000\\584111F7\\000B0000\\"
OLD_CACHE_PATH = "\\Cache\\"
EXPECTED_COLUMNS = {
    "Id", "TitleId", "MediaId", "Version", "Hash", "FileName",
    "LivePath", "LiveDeviceId", "BackupPath",
}


def die(message):
    raise ValueError(message)


def valid_db(db):
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        die("SQLite integrity check failed; do not edit this database.")
    columns = {row[1] for row in db.execute("PRAGMA table_info(TitleUpdates)")}
    if not EXPECTED_COLUMNS.issubset(columns):
        die("This does not appear to be a compatible Aurora content.db database.")


def examine(db):
    """Return a safe repair plan based on record content, NOT record IDs."""
    valid_db(db)
    db.row_factory = sqlite3.Row
    records = list(db.execute(
        "SELECT Id, TitleId, MediaId, Version, Hash, FileName, LivePath, "
        "LiveDeviceId, BackupPath FROM TitleUpdates "
        "WHERE TitleId=? AND Version=? ORDER BY Id",
        (TITLE_ID, VERSION),
    ))
    if not records:
        die("No Minecraft Version 80 (TU75) entries found. "
            "Install/register TU75 in Aurora first; this tool does not download updates.")
    for row in records:
        if (row["MediaId"] != MEDIA_ID
                or (row["Hash"] or "").upper() != TU_HASH
                or (row["FileName"] or "").lower() != TU_FILE):
            die("Found an unfamiliar Minecraft Version 80 record. "
                "No changes made; review the Title ID, Media ID, and update hash.")

    active = [r for r in records if (r["LivePath"] or "").lower() == LIVE_PATH.lower()]
    if len(active) != 1:
        die(f"Expected one Minecraft TU75 record for 000B0000; found {len(active)}. "
            "No changes made.")
    chosen = active[0]
    serial = chosen["LiveDeviceId"]
    if not serial or not isinstance(serial, str) or "\\" in serial or "/" in serial:
        die("Missing/unexpected storage-device identifier. No changes made.")

    desired = (f"Game:\\Data\\TitleUpdates\\{serial}\\584111F7\\"
               f"{TU_HASH}\\{TU_FILE}")
    old_path = chosen["BackupPath"] or ""
    if old_path and old_path.lower() != desired.lower():
        die("The TU75 backup path is not blank and differs from the expected path. "
            "Refusing to overwrite an unfamiliar value.")
    duplicates = []
    for row in records:
        if row["Id"] == chosen["Id"]:
            continue
        if ((row["LivePath"] or "").lower() == OLD_CACHE_PATH.lower()
                and (row["BackupPath"] or "") == ""
                and row["LiveDeviceId"] == serial):
            duplicates.append(row["Id"])
        else:
            die("An unexpected TU75 entry exists. No changes made; inspect manually.")

    return chosen["Id"], desired, old_path, duplicates


def main():
    parser = argparse.ArgumentParser(
        description="Safely repair Minecraft Xbox 360 TU75 (Aurora Version 80) metadata."
    )
    parser.add_argument("database", type=Path,
                        help="A copy of Aurora/Data/Databases/content.db (NOT live FTP path)")
    parser.add_argument("--fix", action="store_true",
                        help="Produce a repaired database copy; without this, preview only")
    parser.add_argument("--output", type=Path,
                        help="Optional new database filename (default: content_tu75_fixed.db)")
    args = parser.parse_args()
    src_path = args.database.expanduser().resolve()
    if not src_path.is_file():
        parser.error(f"Can't find input database: {src_path}")
    with src_path.open("rb") as handle:
        signature = handle.read(16)
    if signature != b"SQLite format 3\x00":
        parser.error("Input is not a binary SQLite database. Don't use the Base64 text file.")

    source = sqlite3.connect(src_path.as_uri() + "?mode=ro", uri=True)
    try:
        row_id, desired, old, duplicates = examine(source)
        print("Minecraft: Xbox 360 Edition / TU75 (internal version 80)")
        print(f"Title ID: 584111F7 | update SHA-1: {TU_HASH}")
        print(f"Relevant database record: {row_id}")
        print(f"BackupPath: {old or '[EMPTY]'}")
        print(f"Expected:   {desired}")
        print(f"Erroneous empty Cache duplicates: {len(duplicates)} (IDs {duplicates})")
        if old.lower() == desired.lower() and not duplicates:
            print("\nNo repair needed: the records already match the known-good structure.")
            return 0
        print("\nPlanned edits: fill empty BackupPath and/or remove ONLY listed duplicates.")
        if not args.fix:
            print("DRY RUN ONLY. Re-run with --fix to create a separate repaired DB file.")
            return 0

        dest_path = (args.output or (src_path.parent / "content_tu75_fixed.db")).expanduser().resolve()
        if dest_path == src_path:
            die("Output may not overwrite the original database.")
        if dest_path.exists():
            die(f"Output already exists: {dest_path}. Move/delete it or use --output.")

        try:
            dest = sqlite3.connect(dest_path)
            try:
                source.backup(dest)  # database-consistent copy; original is read-only
                dest.execute("BEGIN IMMEDIATE")
                if not old:
                    dest.execute(
                        "UPDATE TitleUpdates SET BackupPath=? WHERE Id=? "
                        "AND TitleId=? AND Version=? AND (BackupPath='' OR BackupPath IS NULL)",
                        (desired, row_id, TITLE_ID, VERSION),
                    )
                    if dest.execute("SELECT changes()").fetchone()[0] != 1:
                        die("Unexpected UPDATE count. Aborting.")
                for duplicate_id in duplicates:
                    dest.execute(
                        "DELETE FROM TitleUpdates WHERE Id=? AND TitleId=? AND Version=? "
                        "AND (BackupPath='' OR BackupPath IS NULL) AND LivePath=?",
                        (duplicate_id, TITLE_ID, VERSION, OLD_CACHE_PATH),
                    )
                    if dest.execute("SELECT changes()").fetchone()[0] != 1:
                        die("Unexpected DELETE count. Aborting.")
                dest.commit()
                valid_db(dest)
                # Check the repair has no further proposed edits.
                repaired_id, check_path, current_path, remaining = examine(dest)
                if repaired_id != row_id or current_path.lower() != desired.lower() or remaining:
                    die("Post-repair validation failed; aborting output.")
            finally:
                dest.close()
        except Exception:
            dest_path.unlink(missing_ok=True)
            raise
        print(f"\nSUCCESS: {dest_path}")
        print("Original database was NOT changed.")
        print("The TU75 file must already exist at the expected cache location.")
        print("Close Aurora (launch XeXMenu) before replacing content.db on Xbox.")
        return 0
    finally:
        source.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, sqlite3.Error, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
