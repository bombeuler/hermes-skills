---
name: pdf-bookmark-and-metadata
description: "Rebuild bookmarks and metadata for book PDFs and DjVu files."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, DjVu, Bookmarks, TOC, Metadata, OCR, Calibre]
    related_skills: [ocr-and-documents, zotero-integration]
---

# Book PDF / DjVu: Bookmarks and Metadata

## When to Use

- The user says "fix the contents / bookmarks / metadata of this book", "this PDF has no table of contents", "add bookmarks for me".
- The typical object is a DuXiu / Anna's Archive scan: pure images, no text layer, empty `get_toc()`, empty metadata.
- It also covers **a single article pulled out of a handbook or series** (Elsevier ScienceDirect chapter PDFs: Title is `PII: Sxxxx-xxxx(05)xxxxxx-x`, full text layer, no bookmarks). Write the metadata as "series + volume + editors + page range + DOI"; do not treat it as a standalone book — see §2.
- **DjVu files (`.djvu`) work the same way**: same offset method, same per-entry verification, same delivery wording; only the writer changes (`djvused set-outline`). See "## DjVu books".
- Not applicable: extracting body text only (use `ocr-and-documents`), or editing text that already exists inside a PDF (use `nano-pdf`).

Output: full multi-level bookmarks (part / chapter / section / subsection) + metadata (PDF: title, author, publisher, year, ISBN, language, plus XMP; DjVu: an outline tree).

Helper script: `scripts/pdf_toc_toolkit.py` (inventory / locate / digits / sheet / apply — one per workflow step below).

## Hard rules

1. **Never read page by page.** Look up metadata and contents online first; inside the file read only the **TOC pages** and a few **anchor pages** (chapter openers, tail pages). The user has asked for this explicitly: page-by-page vision browsing is a waste and the wrong method.
2. **Read characters and digits separately.** tesseract `chi_sim` is unreliable on characters (plenty of substitutions) but reliable on **pure digit columns**. So: titles through careful vision, page numbers through digit-column OCR, and cross-check by **aligning the row counts**.
3. **Verify the offset at many points.** Printed page → file page is usually a constant offset, but it must be confirmed with ≥10 anchors (every chapter opener + references + tail index). Never extrapolate the whole book from one page.
4. **Never rewrite what the book prints.** Renumbered entries, typos, repeated page numbers, missing entries: report them exactly as printed and let the user decide; bookmark titles keep the book's own wording.
5. **Back up before writing, reopen and verify after saving.** Copy the file before overwriting it; after saving, reopen and check the page count, the bookmark count, and that several pages still render (so the image streams were not damaged).
6. **PDF metadata ≠ Calibre's `metadata.opf`.** Touching the PDF only is this skill's default scope; whether to sync the opf (publisher / ISBN / year) has to be asked.
7. **Metadata describes the book only.** Organiser names and AI tool names never go into PDF fields; `/Creator` and `/Producer` are tool facts — do not fake them. A credit, if wanted, goes in the upload notes, not in the file. Scan-source markers (`DuXiu/SuperStar`, Anna) are cleared on request; the publisher stays as a bibliographic fact (citations need it), not as a claim of ownership.

## Workflow

### 1. Inventory

```bash
PYTHONPATH=~/.local/lib/python3.14/site-packages python -c "
import fitz
d=fitz.open('book.pdf'); print(d.page_count, d.metadata); print(len(d.get_toc()))
print([len(d[i].get_text().strip()) for i in range(10)])"
```

Text length 0 on every page with one image per page → a scan; everything downstream is OCR and vision. Use `inventory()` from `scripts/pdf_toc_toolkit.py`.

### 2. Metadata (title from the web, the copyright page is authoritative)

Search "title author", "title ISBN published" to find the record; Baidu Baike, library catalogues and Douban give publisher / year / ISBN. But **do not copy their page count** — encyclopaedia page counts often disagree with the physical book, and copyright pages usually print no page count at all.

The copyright page (the page right after the title page in a scan; for Chinese books the "图书在版编目（CIP）数据" block) yields everything in one careful read: title / author, ISBN, **CLC class number** (it decides the upload category), CIP verification number, format (开本), **printed sheets (印张)**, word count, print run, price, edition and printing, responsible editor. When no page count is printed, estimate the leaf count as `sheets × 16`, or just take the file's `page_count` (if the two are close, the scan is not missing pages). Cross-check the ISBN against the barcode on the back cover.

**Single article (one chapter of a handbook)**: no copyright page needed; every bibliographic fact sits on the article's first page — series name (`HANDBOOK OF NUMERICAL ANALYSIS, VOL. II`), series volume title (`Finite Element Methods (Part 1)`), editors, copyright line (`© 1991. Elsevier Science Publishers B.V. (North-Holland)`). Convert the PII in the Title into a DOI and check it on ScienceDirect (`S1570-8659(05)80040-7` → `10.1016/S1570-8659(05)80040-7`; the same page gives the page range). Never take page numbers from secondary citations. The page range must agree with the printed pages you computed: first page of the article = startingPage, last index page = endingPage; a mismatch means missing pages or a wrong offset. Write `prism:publicationName/volume/isbn/publicationDate/startingPage/endingPage/doi` in the XMP, and put series volume, page range and DOI in Subject as well (citations need them).

### 3. Where the TOC comes from

Online TOC > the book's own TOC pages > OCR output. Chinese monographs often publish only a four-line part-level list online (that is what an encyclopaedia's contents box is); **that is not enough for bookmarks** — use the book's TOC pages instead, and never pad a coarse list into a full one.

### 4. Locate the TOC pages (spends no vision)

OCR the first 25 pages in full, run `re.sub(r'\s+','',text)` and look for `目录` / `目次`. The TOC usually follows the preface and its running heads are roman numerals (ix…xvii). Then render only those pages for careful reading:

```bash
python scripts/pdf_toc_toolkit.py locate book.pdf --pages 1-26
```

### 5. Read the TOC pages

Render the TOC pages at 250 dpi and ask the vision model, page by page, to "transcribe every entry and its page number, preserving levels". Levels follow the number of dots: `x.y` is a section, `x.y.z` a subsection; `第X篇` / `第X章` / `附录` / `参考文献` each have a fixed level.

In parallel run digit-column OCR (right 16% of the width, 400 dpi, `--psm 6` with a digit whitelist):

```bash
python scripts/pdf_toc_toolkit.py digits book.pdf --pages 13-21
```

**Align by row count**: pair row by row only when the number of digits equals the number of title rows. When they differ, find where: single-digit numbers `3` / `4` / `5` are often dropped whole by OCR (vision's single digit is trustworthy), while vision tends to read a two-digit 9 as 5 (OCR is more trustworthy). Zoom in on doubtful rows individually.

### 6. Compute the offset

`file page = printed page + offset`. Method: render the **top strip** of every candidate anchor page (printed page + assumed offset) into a single contact sheet and check all of them at once, instead of paging through:

```bash
python scripts/pdf_toc_toolkit.py sheet book.pdf --anchors 3:24,22:43,71:92 --out /tmp/sheet.png
```

If all 12 chapter openers + references + tail index hit, the offset is linear (a missing or duplicated page in the middle shifts every later anchor, so covering many points rules that class of error out).

Small running-head page numbers are **not worth OCRing**: they are tiny and the scan is skewed, so both the digit column and the full-page strip fail. Do not burn time there.

### 6.5 Strip Anna / DuXiu baggage (after the bookmarks, before delivery)

DuXiu scans distributed through Anna's Archive hang attachment name trees in the PDF: usually `annas_archive_metadata.json.zst` and `original_files.tar.zst` (often a few tens of bytes of empty shell). Users normally want them gone.

```python
print(d.embfile_count(), d.embfile_names())
for n in d.embfile_names(): d.embfile_del(n)
d.save('/tmp/x.pdf', garbage=4, deflate=True)
```

Verify three things: `embfile_count() == 0`; `grep -c -a -i annas file.pdf` returns 0; `qpdf --check` reports no syntax errors. After deletion the `/EmbeddedFiles` name tree keeps an empty `<</Names[]>>`; harmless, do not dig it out.

**The "Document generated by Anna's Archive…" stamp on the last page is a page, not an attachment** — deleting it changes the page count; when the user only says "delete the files", do not delete pages as well, ask first. When the user says "delete the Anna and DuXiu stuff", three places are meant: the embedded attachments (`embfile_del`), the stamp page (`d.delete_page(d.page_count-1)`), and `DuXiu/SuperStar` inside `/Creator` (`set_metadata(..., creator='')`, confirmed with `pdfinfo` showing an empty Creator). Verify each of the three separately; never assume the whole batch is done because the first step succeeded. After deleting a page, re-verify the page labels (see Pitfalls).

Names like `000252.pdg` inside DuXiu's `/PieceInfo` are page piece names, not files; if they must be cleaned, rebuild `/PageLabels` at the same time (§6.6).

### 6.6 Rebuild the page labels (the DuXiu piece-name trap)

A DuXiu scan's `/PageLabels` is not real page numbering but a **piece-name table**: every leaf of the number tree holds only `/P(cov001.pdg)`, `/P(000253.pdg)`, so Okular and Adobe show `cov001.pdg` in the page box, which users hate. The whole tree has to be replaced.

That table is also **independent evidence for the global offset**: the real file names `000001…000401` correspond page by page to `pdf page - 21` (only the final stamp page is the exception among 402 entries). Extract it at the end and recompute the offset — that verifies the bookmark offset down to every single page.

```python
obj = '<</Nums[0<</P()>>4<</S/r>>21<</S/D>>]>>'   # 0-3 no label; preface starts at i; part title page starts at 1
x = d.get_new_xref(); d.update_object(x, obj)
d.xref_set_key(d.pdf_catalog(), 'PageLabels', f'{x} 0 R')
```

Traps:

- `set_page_labels()` writes non-ASCII prefixes as **UTF-8 hex strings** (`<E5B081E99DA2>`), which are not legal PDF text strings, so CJK prefixes break. A CJK prefix needs a hand-written `<FEFF` + `s.encode('utf-16-be').hex()`; but `get_label()` cannot read any non-ASCII back (even `Ä` comes back as `<C384>`), so if you cannot verify it yourself, do not use it — give unnumbered cover/title pages an **empty prefix** `<</P()>>`, or use a pure-ASCII prefix: `/P(C)/S/D/St 1` yields C1, C2, C3… (the user prefers this).
- Also set the emptied `/Names` name tree to `null` and switch `/PageMode` from `/UseAttachments` to `/UseOutlines`; otherwise the reader pops open the (now empty) attachment panel on open.
- **Non-DuXiu books have the same page-box problem: `/PageLabels` does not exist at all, the page box shows 1..N, while scholarly citations use the printed page numbers.** Do not use the range prefixes of `set_page_labels()` (one offset segment cannot express a jump); write `/Nums` explicitly, page by page:
  ```python
  nums = ''.join('%d<</P(%d)>>' % (i, printed_of(i)) for i in range(d.page_count))  # /P holds digits only
  x = d.get_new_xref(); d.update_object(x, '<</Nums[%s]>>' % nums)
  d.xref_set_key(d.pdf_catalog(), 'PageLabels', '%d 0 R' % x)
  ```
  `printed_of()` is a three-line function you write yourself from the offset segments of §6 (it is not in the toolkit). After writing it, spot-check `d[pg-1].get_label()` on the first page, a front-matter page, and the first and last body pages: the number must equal the printed page number in that page's running head.

### 7. Write the bookmarks + metadata

```python
entries = [[level, title, pdf_page], ...]   # level 1..4, pdf_page starting at 1
doc.set_toc(entries)
doc.set_metadata({'title':..., 'author':..., 'subject':..., 'keywords':..., 'creator':..., 'producer':...})
doc.set_xml_metadata(xmp)   # dc:publisher / prism:isbn / prism:publicationDate
```

- Strip markdown math markers such as `$` and `\,` from bookmark titles, but keep plain-text formulas (`V_k^ω(Ω)` and the like stay as they are).
- PyMuPDF writes non-ASCII strings into the outline as UTF-16 automatically; nothing else to do.
- Back up first, save to `/tmp`, then `shutil.move` over the original, and **reopen to verify**.

`apply` in `scripts/pdf_toc_toolkit.py` does these three steps (with backup and verification).

### 8. Verify tail pages separately

Printed contents pages often omit tail entries, or the last entry's wording disagrees with the heading on the page. Render thumbnails of the last 4 pages once and read them all: for this class of book it has happened that the contents said "检索 401" while the heading on that page was "符号索引", and the page before it carried a **second, unlisted general index**.

### 9. Delivery

Report back: metadata table, bookmark structure with per-level counts, page offset and how it was verified, **the list of anomalies in the book's own contents**, and the backup path; end by asking whether to sync Calibre's `metadata.opf`. Do not touch the opf on your own.

Final tally before delivery (four items, all with numbers — never just "done"): `d.page_count` / `len(d.get_toc())` / `d.embfile_count()`; page-label spot checks (first page, front matter, first and last body page); `qpdf --check` with no syntax errors; `grep -a -i` for `duxiu` / `annas` / `superstar` all zero.

For DjVu the tally is three items: `djvused -e n` unchanged, `djvused -e print-outline` count equal to what was written, and `djvutxt | wc -c` character count unchanged (`-s` rewrites the whole file).

## DjVu books (outlines via djvused)

Applies to `.djvu` book scans (the classics — Lions, Grisvard, Adams, Pazy). One command tells you whether a TOC exists; empty output means none:

```bash
djvused book.djvu -e print-outline     # empty → no outline
djvused book.djvu -e n                 # page count
djvutxt book.djvu | wc -c              # text-layer size; 0 = pure images, use the OCR/vision route of §4–§6
```

Most DjVu scans carry hidden text (a `TXTz` chunk), on the order of hundreds of thousands of characters — locating TOC pages, computing offsets and verifying headings all rely on it, so no OCR is needed.

### D1. Per-page text

`djvutxt` separates pages with `\f`: `txt.split("\f")` gives the text page by page, and the trailing empty string has to be dropped. Locate the TOC pages by `Contents` / `CONTENTS` at the top of the page (both Grisvard and Adams have them on DjVu pages 3–5).

### D2. Offset, same method as for PDFs

Take a standalone integer from the first and last two lines of each page as the folio, then build the `djvu page - folio` map. Both books measured here had a constant offset: Grisvard **+12** (printed 1–410 → DjVu 13–422), Adams **+11** (printed 1–259 → DjVu 12–270). **The tail drops by one**: where the scan is missing a page the offset becomes +10 for that stretch (the Index of Adams), so locate Index / References by the heading on the page and never extrapolate from the middle stretch.

### D3. Verify every entry against its target page

Pull up the page each bookmark points to and confirm the section number (`1.4.5`) or the title's key words appear in the body. This step also catches misprinted page numbers in the book's own contents: Grisvard's contents say `2.1 Foreword 84` while 2.1 actually starts on 81 (that page carries both the chapter title "2 Regular second-order…" and "2.1 Foreword") — the bookmark points to 81, and the discrepancy is reported to the user as §9 requires.

### D4. Outline syntax

The top form must be named `bookmarks`, otherwise it fails outright with `*** Syntax error in outline data: expecting '(bookmarks'`. Children are listed side by side inside the parent's parentheses; no key is needed:

```
(bookmarks
  ("Preface" "#7")
  ("1  Sobolev spaces" "#13"
    ("1.1  Motivation" "#13")
    ("1.2  Boundaries" "#16"
      ("1.2.1  Graphs and manifolds" "#17")))
  ("Bibliography" "#412")
  ("Index" "#421"))
```

`#N` is the **1-based page index** (not the printed page number). Nesting depth is unlimited; part / chapter / section / subsection map to levels 1 / 2 / 3 / 4 exactly as in the PDF variant.

### D5. Writing and verifying

```bash
cp book.djvu ~/pdf-backups/
djvused book.djvu -e "set-outline /tmp/outline.txt" -s    # without -s it only changes memory, nothing is written
djvused book.djvu -e print-outline                        # read back
```

Careful when comparing the read-back: **non-ASCII comes back as octal escapes of the UTF-8 bytes** (`Ω` → `\316\251`), so a plain string comparison wrongly reports a mismatch. Decode first, then compare:

```python
dec = lambda s: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), s).encode('latin-1').decode('utf-8')
```

All three checks are mandatory: `n` unchanged, `djvutxt | wc -c` character count unchanged (the text layer must not be lost), and `ddjvu -format=pgm -subsample=4 -page=N` renders with a dark-pixel ratio > 0.

### D6. Rendering and tooling traps

- `ddjvu` **cannot output png**, only `pbm/pgm/ppm/pnm/rle/tiff/pdf`; to look at a page, render pgm/ppm and convert with Pillow.
- `-scale=N` means **shrink**: `-scale=3` yields a 15×23 thumbnail that makes the file look corrupt. To subsample use `-subsample=N`; with no argument you get the original resolution (scans are often 600 dpi, 3029×4832).
- To decide whether an outline exists, trust only whether `print-outline` is empty. Do not use heuristics such as "the output contains quotes" — measured: that misclassifies whole batches of unbookmarked books as having a TOC.
- Reader support varies: Okular and DjView show an outline pane, some readers support DjVu outlines poorly — not seeing it does not mean it was not written.

## Auditing a directory: which files have no TOC

A format-agnostic step whose only job is to narrow the scope: walk a directory of books once, decide file by file whether a TOC exists, and write the result out as a list (path / format / page count / text layer or not), then pick the books and work through them with the workflow above one at a time. **Read-only scan first; never start rewriting in bulk.**

- PDF: empty `fitz.open(p).get_toc()` means no bookmarks; also record `page_count` and the text length of the first 6 pages, which splits the list into "digital (titles can be harvested automatically)" and "scanned (needs OCR)".
- EPUB: parse the zip, find a nav document marked `epub:type="toc"` or the `toc.ncx`, and count `a` elements / `navPoint` elements.
- DjVu: empty `djvused -e print-outline` output means no outline. **Do not** count quotes in the output — measured: that misclassifies batch after batch of unbookmarked books as having a TOC.
- Kindle formats (azw3 / mobi) have no dependable standard-library parser; convert to epub first and count nav/ncx entries. If the converter will not start because the `python3` on `PATH` lacks `msgpack`, work around it with
  `PYTHONPATH=/usr/lib/calibre /usr/bin/python3 /usr/sbin/ebook-convert --version` (the system python's msgpack plus the tool's own library path).

## Pitfalls

- **An Elsevier / ScienceDirect single chapter with a text layer: no OCR, read the running heads to get the page numbers.** Blocks from `get_text("blocks")` with `y1 < 0.12*height` are the running head (`SECTION 12 Local estimates 421` / `436 L.B. Wahlbin CHAPTER III`); a regex for integers in 350–525 gives the printed page number, and one command yields the whole `printed page → pdf page` map — far more reliable than OCRing a digit column. Then look up the printed page numbers from the TOC page, and confirm that the first body line of that page really is that section heading before calling it verified.
- **The offset can be piecewise — do not assume one constant.** Scans drop blank even pages (chapter versos), and every dropped page adds 1 to the offset after it. Measured in one book: offset 353 (pdf 1–40), 354 (pdf 41–135), 355 (pdf 136–167); the three breakpoints sat exactly on two discarded blank versos. Compute the offset page by page from the running heads and find the breakpoints; never extrapolate linearly from the first and last page.
- **The number of blank pages around a part title page is not fixed.** Do not apply a "part title page + blank + chapter opener" template: measured, the first part was title page / blank, while the second was blank / title page / blank. Decide by **ink coverage** first (dark-pixel ratio at 60 dpi: blank 0.000, part title page 0.007–0.009, body text > 0.02), then paste one image to confirm the four headings — more reliable than guessing from thumbnail order.
- **`--psm 6` in Chinese OCR swallows single-character digits whole.** When the row counts differ, do not conclude the contents are incomplete; add the single digits by hand first.
- **Never transcribe titles with a full-page chi_sim OCR.** The substitution rate is unusable in practice ("插值" → "撒值", "空间" → "窒闻"); it is only good for coarse decisions such as finding the word "目录".
- **Save large files with `garbage=4, deflate=True`; image streams are not recompressed.** After overwriting, verify: `page_count` unchanged, `len(get_toc())` equal to the expected count, and the dark-pixel ratio of a few low-dpi renders > 0.
- **Two consecutive entries with the same page number can be correct** (the book prints it that way); do not "fix" it into an increasing sequence.
- **Anna's baggage is not in one place**: only the `.zst` entries in the attachment name tree are embedded files; the tail stamp page and the `.pdg` names in DuXiu's `/PieceInfo` are not — do not mix them up.
- **Page labels and bookmarks are two different things.** The bookmarks may jump to the right page while the page box still shows `cov001.pdg`; `/PageLabels` has to be rebuilt separately.
- **xref numbers change after saving**, so reading back through an old xref raises `bad xref`; reopen and spot-check with `d[pg].get_label()`.
- **Page labels must be re-verified after deleting a page**: the last label follows the page count, so the extra entry disappears when the stamp page goes; afterwards `d[-1].get_label()` must equal the last printed page number.
- **Searching for source strings hits coincidental bytes in compressed streams**: `grep -a pdg` matches random bytes inside image streams (`cQpdg~`, `#pdgS"<`); treat a hit as a lead only and read the context to tell a piece name from noise. `annas` / `duxiu` / `superstar` must be 0 after cleaning.
- **`prism:numberOfPages` in XMP goes stale.** Deleting a page (say the stamp page) does not update it and `pdfinfo` will not complain; read it back with a regex and set it to the current `page_count`. The same holds for `dc:date` / `prism:publicationDate` — once written they stay.

## Environment notes

- PyMuPDF may live in the user site; when `import fitz` fails, add `PYTHONPATH=~/.local/lib/python3.14/site-packages`.
- `tesseract` with `chi_sim` is required: check with `tesseract --list-langs`, install with `pacman -S tesseract tesseract-data-chi_sim` if missing.
- Contact sheets need Pillow.
- DjVu tooling is DjVuLibre: `djvused` (outline, page count), `djvutxt` (text layer), `ddjvu` (rendering).
