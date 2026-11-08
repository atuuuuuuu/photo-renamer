"""Tests for photo_renamer.py. Run:  python3 -m unittest -v"""
import os
import struct
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import photo_renamer as r


def fake_jpeg(taken=None, changed=None, order="<"):
    """Build the smallest JPEG with an EXIF block, byte by byte, like a camera would."""
    if taken is None and changed is None:
        return b"\xff\xd8\xff\xd9"                          # a JPEG with no EXIF at all
    mark = b"II" if order == "<" else b"MM"
    s_changed = (changed or "").encode() + b"\x00"
    s_taken = (taken or "").encode() + b"\x00"
    # Layout: header(8) | IFD0: 2 entries (2+24+4=30) | EXIF IFD: 1 entry (2+12+4=18) | strings
    ifd0, exif_ifd = 8, 38
    p_changed, p_taken = 56, 56 + len(s_changed)
    t = mark + struct.pack(order + "HI", 42, ifd0)
    t += struct.pack(order + "H", 2)
    t += struct.pack(order + "HHII", 0x0132, 2, len(s_changed), p_changed)   # DateTime
    t += struct.pack(order + "HHII", 0x8769, 4, 1, exif_ifd)                  # pointer to the EXIF table
    t += struct.pack(order + "I", 0)
    t += struct.pack(order + "H", 1)
    t += struct.pack(order + "HHII", 0x9003, 2, len(s_taken), p_taken)       # DateTimeOriginal
    t += struct.pack(order + "I", 0)
    t += s_changed + s_taken
    app1 = b"Exif\x00\x00" + t
    return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


class ReadDate(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_reads_date_taken_both_byte_orders(self):
        for order in "<>":
            p = self.write(f"a{order == '<'}.jpg", fake_jpeg("2019:07:14 15:32:08", "2020:01:01 00:00:00", order))
            self.assertEqual(r.exif_date(p), datetime(2019, 7, 14, 15, 32, 8))

    def test_no_exif_falls_back_to_file_date(self):
        p = self.write("plain.jpg", fake_jpeg())
        os.utime(p, (0, datetime(2018, 3, 1, 9, 0, 0).timestamp()))
        self.assertEqual(r.when_taken(p), (datetime(2018, 3, 1, 9, 0, 0), "file date"))

    def test_not_a_jpeg(self):
        self.assertIsNone(r.exif_date(self.write("x.png", b"\x89PNG....")))
        self.assertIsNone(r.exif_date(self.write("broken.jpg", b"\xff\xd8\xff\xe1\x00")))


class PlanAndApply(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "IMG_0001.JPG").write_bytes(fake_jpeg("2019:07:14 15:32:08"))
        (self.dir / "photo (3).jpeg").write_bytes(fake_jpeg("2019:07:14 15:32:08"))   # same second
        (self.dir / "2019-07-14_15-32-08.jpg").write_bytes(b"already here, never overwrite me")
        (self.dir / "notes.txt").write_text("not a photo")

    def test_plan_never_overwrites_and_skips_non_photos(self):
        plan = r.make_plan(self.dir)
        names = sorted(new.name for _, new, _ in plan)
        self.assertEqual(names, ["2019-07-14_15-32-08_2.jpg", "2019-07-14_15-32-08_3.jpg"])

    def test_preview_changes_nothing_apply_and_undo_round_trip(self):
        before = sorted(p.name for p in self.dir.iterdir())
        plan = r.make_plan(self.dir)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before)    # planning touched nothing
        log = r.apply_plan(self.dir, plan)
        self.assertEqual((self.dir / "2019-07-14_15-32-08.jpg").read_bytes(), b"already here, never overwrite me")
        self.assertEqual(r.make_plan(self.dir), [])                             # running again: nothing to do
        r.undo(log)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir() if p != log), before)


if __name__ == "__main__":
    unittest.main()
