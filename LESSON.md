# Photo renamer: how it works, and how to build your own

`photo_renamer.py` is a **reference demo written by Claude** for you to learn from. Don't put it on GitHub as your
project. Build your own version (part 3), and put *that* on GitHub and in your README.

## Try it (safe: it only previews unless you add --apply)

```
cd ~/learning/photo-renamer
mkdir ~/Desktop/test-photos && cp -p ~/Desktop/*.jpeg ~/Desktop/test-photos/
python3 photo_renamer.py ~/Desktop/test-photos            # preview
python3 photo_renamer.py ~/Desktop/test-photos --apply    # rename + undo log
python3 photo_renamer.py --undo ~/Desktop/test-photos/renames-....csv
python3 -m unittest -v                                    # the tests
```

Always try it on **copies** first. `cp -p` keeps the original file dates.

## 1. The big idea, in three steps

1. **Find out when each photo was taken.** (`when_taken`)
2. **Plan every new name first, without touching anything.** (`make_plan`)
3. **Only then rename, and write down what you did so it can be undone.** (`apply_plan`, `undo`)

Splitting "decide" from "do" is the most useful thing in this program. It's why the preview is free, why the
tests are easy, and why a mistake never destroys a photo.

## 2. The parts worth understanding

**Where does "date taken" come from?** A camera hides a tiny database called **EXIF** inside every JPEG. It's
not magic, just bytes, and `exif_date` reads them by hand:

- Every JPEG starts with the bytes `FF D8`. After that it's a list of *segments*: `FF`, a type byte, a 2-byte
  length, then the contents. The program hops from segment to segment using the length.
- The segment of type `E1` that starts with `Exif` holds the camera data. Inside is a mini **TIFF** file: a
  header saying which byte order is used (`II` = Intel, little-endian; `MM` = Motorola, big-endian), then
  *tables* of 12-byte entries: tag number, type, count, value.
- Tag `0x8769` points to a second table. In that table, tag `0x9003` (**DateTimeOriginal**) is the moment the
  shutter was pressed, stored as text like `2019:07:14 15:32:08`.
- `struct.unpack` is what turns raw bytes into numbers. `"<H"` means "2-byte number, little-endian".

If a photo has no EXIF (screenshots, downloads, WhatsApp images), it falls back to the file's modified date and
says `(file date)` so you know it's a guess.

**Never overwriting anything.** `make_plan` keeps a set of every name already in the folder (`in_use`). If two
photos were taken in the same second, the second one gets `_2`, then `_3`. It compares names in lowercase because
macOS treats `A.jpg` and `a.jpg` as the same file. `apply_plan` also checks `new.exists()` right before renaming.

**Running it twice does nothing.** Photos already named like `2019-07-14_15-32-08.jpg` are skipped (the
`ALREADY_DONE` pattern). The tests caught a bug here: without that check, a file already named by date but with
no EXIF inside was renamed *again* to today's date.

**The undo log.** Each rename is written to a CSV file the moment it happens (`f.flush()`), so even if the program
crashes halfway, the log lists exactly what was done. `--undo` reads it backwards and renames everything back.

**The tests** (`test_photo_renamer.py`) build fake JPEGs byte by byte with real EXIF inside. Reading
`fake_jpeg` is the fastest way to understand the format: it's `exif_date` in reverse.

## 3. Build your own (do this in a new, empty folder, without looking at the demo first)

Each step should work before you start the next. Get stuck, try for 20 minutes, then peek at the demo or ask.

1. Print the name of every `.jpg` in a folder. (`pathlib.Path(folder).iterdir()`)
2. Print each file's modified date as `2019-07-14_15-32-08`. (`stat().st_mtime`, `datetime.fromtimestamp`, `strftime`)
3. Print a preview: `old name -> new name`. Don't rename anything yet.
4. Handle two photos with the same date (`_2`, `_3`). Test it: copy one photo twice.
5. Add `--apply` with `argparse`, and only rename when it's given.
6. Write the undo log, then `--undo`.
7. Hard part: read the real date from EXIF. Open a photo in binary (`open(p, "rb")`), print the first 40 bytes
   with `print(data[:40])`, and find `FF D8`, `FF E1` and `Exif` yourself before writing any parsing code.
8. Write one test that would have caught a bug you actually hit.

Then commit it to your own GitHub repo, with your own README saying what you learned and what broke.
That's a project you can talk about in an interview, because you'll remember getting stuck.
