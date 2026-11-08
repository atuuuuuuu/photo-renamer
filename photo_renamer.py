#!/usr/bin/env python3
"""
Photo renamer: give badly named photos (IMG_0042.JPG, "photo (3).jpg") names
from the date they were taken, like 2023-07-14_15-32-08.jpg.

Reference demo for learning. Safe by default: it only SHOWS the plan.

    python3 photo_renamer.py ~/Pictures/old-laptop            # preview, changes nothing
    python3 photo_renamer.py ~/Pictures/old-laptop --apply    # rename, and save an undo log
    python3 photo_renamer.py --undo ~/Pictures/old-laptop/renames-20261109-101500.csv
"""
import argparse
import csv
import re
import struct
import sys
from datetime import datetime
from pathlib import Path

PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".heic", ".gif", ".tif", ".tiff"}
NAME_FORMAT = "%Y-%m-%d_%H-%M-%S"
ALREADY_DONE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(_\d+)?$")   # 2019-07-14_15-32-08 or ..._2


# ---------------------------------------------------------------------------
# 1. When was this photo taken?
# ---------------------------------------------------------------------------
# A camera hides a little database called EXIF inside every JPEG. One of its
# entries, DateTimeOriginal, is the moment the shutter was pressed. We read it
# by hand, so you can see that a photo file is not a black box either.

def exif_date(path):
    """Return the date stored inside a JPEG, or None if there isn't one."""
    try:
        with open(path, "rb") as f:
            data = f.read(256 * 1024)          # EXIF lives near the start of the file
        if data[:2] != b"\xff\xd8":            # every JPEG starts with these two bytes
            return None
        # A JPEG is a list of segments: FF <type> <2-byte length> <contents>.
        i = 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if marker in (0xD9, 0xDA):         # end of image / start of the pixels: stop looking
                break
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker == 0xE1 and data[i + 4:i + 10] == b"Exif\x00\x00":   # APP1 = the EXIF segment
                return read_tiff_date(data[i + 10:i + 2 + length])
            i += 2 + length
    except (OSError, struct.error, ValueError, IndexError):
        pass                                    # unreadable or odd file: fall back to the file date
    return None


def read_tiff_date(t):
    """EXIF inside is a tiny TIFF file: a header, then tables ("IFDs") of 12-byte entries."""
    order = {b"II": "<", b"MM": ">"}.get(t[:2])  # Intel (little-endian) or Motorola (big-endian)
    if order is None:
        return None

    def entries(offset):
        count = struct.unpack(order + "H", t[offset:offset + 2])[0]
        for k in range(count):
            e = offset + 2 + 12 * k
            tag, kind, n, value = struct.unpack(order + "HHI4s", t[e:e + 12])
            yield tag, n, value

    def text(n, value):                         # text longer than 4 bytes is stored elsewhere; value says where
        start = struct.unpack(order + "I", value)[0]
        return t[start:start + n].rstrip(b"\x00").decode("ascii", "ignore")

    first_table = struct.unpack(order + "I", t[4:8])[0]
    found, exif_table = None, None
    for tag, n, value in entries(first_table):
        if tag == 0x0132:                       # DateTime: when the file was last changed (backup answer)
            found = text(n, value)
        elif tag == 0x8769:                     # pointer to the EXIF table, which has the real date take n
            exif_table = struct.unpack(order + "I", value)[0]
    if exif_table:
        for tag, n, value in entries(exif_table):
            if tag == 0x9003:                   # DateTimeOriginal: the moment the photo was taken
                found = text(n, value)
    try:
        return datetime.strptime(found, "%Y:%m:%d %H:%M:%S") if found else None
    except ValueError:
        return None


def when_taken(path):
    """Best guess at when a photo was taken, and where that guess came from."""
    date = exif_date(path)
    if date:
        return date, "date taken"
    return datetime.fromtimestamp(path.stat().st_mtime), "file date"


# ---------------------------------------------------------------------------
# 2. Plan every rename first, without touching anything
# ---------------------------------------------------------------------------

def make_plan(folder):
    """List of (old path, new path, source). Never targets a name that already exists."""
    photos = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in PHOTO_TYPES)
    in_use = {p.name.lower() for p in folder.iterdir()}   # lower(): macOS treats A.jpg and a.jpg as the same file
    plan = []
    for photo in photos:
        if ALREADY_DONE.match(photo.stem):
            continue                            # already named by date (by us, or by a phone): leave it alone
        date, source = when_taken(photo)
        ext = photo.suffix.lower().replace(".jpeg", ".jpg")
        base = date.strftime(NAME_FORMAT)
        new_name, n = base + ext, 2
        while new_name.lower() in in_use:       # two photos in the same second: add _2, _3, ...
            new_name, n = f"{base}_{n}{ext}", n + 1
        in_use.add(new_name.lower())
        plan.append((photo, folder / new_name, source))
    return plan


# ---------------------------------------------------------------------------
# 3. Do it (only with --apply), and keep an undo log
# ---------------------------------------------------------------------------

def apply_plan(folder, plan):
    log = folder / f"renames-{datetime.now():%Y%m%d-%H%M%S}.csv"
    with open(log, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["old", "new"])
        for old, new, _ in plan:
            if new.exists():                    # belt and braces: never overwrite a photo
                print(f"  skipped {old.name}: {new.name} already exists")
                continue
            old.rename(new)
            writer.writerow([old.name, new.name])
            f.flush()                           # if we crash halfway, the log still lists what was done
    return log


def undo(log):
    with open(log, newline="") as f:
        rows = list(csv.DictReader(f))
    folder = log.parent
    for row in reversed(rows):
        new, old = folder / row["new"], folder / row["old"]
        if new.exists() and not old.exists():
            new.rename(old)
            print(f"  {row['new']}  ->  {row['old']}")
    print(f"Undid {len(rows)} renames.")


def main():
    ap = argparse.ArgumentParser(description="Rename photos by the date they were taken.")
    ap.add_argument("folder", nargs="?", type=Path, help="folder of photos")
    ap.add_argument("--apply", action="store_true", help="actually rename (default: just preview)")
    ap.add_argument("--undo", type=Path, metavar="LOG", help="undo the renames listed in this log file")
    args = ap.parse_args()

    if args.undo:
        return undo(args.undo)
    if not args.folder or not args.folder.is_dir():
        ap.error("give a folder of photos")

    plan = make_plan(args.folder)
    if not plan:
        print("Nothing to rename.")
        return
    width = max(len(old.name) for old, _, _ in plan)
    for old, new, source in plan:
        print(f"  {old.name:<{width}}  ->  {new.name}   ({source})")

    if not args.apply:
        print(f"\n{len(plan)} photos would be renamed. Nothing changed yet: add --apply to do it.")
        return
    log = apply_plan(args.folder, plan)
    print(f"\nRenamed {len(plan)} photos. To undo:  python3 {sys.argv[0]} --undo {log}")


if __name__ == "__main__":
    main()
