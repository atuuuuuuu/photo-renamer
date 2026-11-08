# photo-renamer

Rename badly named photos (`IMG_0042.JPG`, `photo (3).jpeg`) by the date they were taken:
`2019-07-14_15-32-08.jpg`. Plain Python 3, no packages to install.

> **A learning project.** This version was written with [Claude](https://claude.ai) as a reference while I learn
> how image files work inside. I'm studying it and rewriting it myself; see [LESSON.md](LESSON.md).

## Use it

```bash
python3 photo_renamer.py ~/Pictures/old-laptop            # preview only, changes nothing
python3 photo_renamer.py ~/Pictures/old-laptop --apply    # rename, and save an undo log
python3 photo_renamer.py --undo ~/Pictures/old-laptop/renames-20261109-101500.csv
```

Try it on a copy of your photos first (`cp -p` keeps the file dates).

## What it does

- Reads the **date taken** from each JPEG's EXIF data, by hand, byte by byte, with no imaging library.
  Photos without EXIF fall back to the file's modified date, marked `(file date)` in the preview.
- **Previews by default.** Nothing changes until you add `--apply`.
- **Never overwrites.** Two photos from the same second become `..._2.jpg`, `..._3.jpg`.
- **Undo log.** Every rename is written to a CSV as it happens; `--undo` puts the old names back.
- **Safe to run twice.** Photos already named by date are left alone.

## Tests

```bash
python3 -m unittest -v
```

The tests build fake camera JPEGs byte by byte (both byte orders) and check reading, collisions,
preview-changes-nothing, apply and undo.
