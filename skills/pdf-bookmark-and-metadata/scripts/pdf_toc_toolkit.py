#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描书 PDF 目录书签/元信息工具箱（PyMuPDF + tesseract）。

子命令
  inventory <pdf>
      盘点页数 / 文字层 / 现有书签 / 元信息。
  locate <pdf> [--pages 1-26] [--dpi 250]
      整页 OCR 找“目录”起始页。汉字 OCR 只用于定位，不用于抄标题。
  digits <pdf> --pages 13-21 [--x0 0.84] [--dpi 400]
      目录页右侧数字列 -> 页码序列。与视觉读出的标题按行数对齐。
  sheet <pdf> --anchors 3:24,22:43,381:402 --out /tmp/sheet.png [--band 0 0.22]
      把各锚点页顶部条带拼成一张联系表，一次视觉得核对偏移量。
  apply <pdf> --entries toc.json [--meta meta.json] [--xmp xmp.xml] [--no-backup]
      备份 + 写书签/元信息 + 重开验证。

toc.json :  [[level, "标题", pdf_page], ...]      level 1..4，pdf_page 从 1 起
meta.json:  {"title":..., "author":..., "subject":..., "keywords":...}

PyMuPDF 装在 user site 时：
  PYTHONPATH=~/.local/lib/python3.14/site-packages python pdf_toc_toolkit.py ...
"""
import argparse, json, os, re, shutil, subprocess, sys

try:
    import fitz
except ImportError:  # pragma: no cover
    sys.exit('PyMuPDF 缺失：pip install pymupdf（或加 PYTHONPATH=~/.local/lib/python3.14/site-packages）')


def _ocr(img, lang='chi_sim', psm=6, digits_only=False, tmp='/tmp/_ocr_strip.png'):
    cmd = ['tesseract', img, '-', '-l', lang, '--psm', str(psm)]
    if digits_only:
        cmd += ['-c', 'tessedit_char_whitelist=0123456789']
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def _parse_pages(spec, total):
    out = []
    for part in str(spec).split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [p for p in out if 1 <= p <= total]


def inventory(pdf):
    d = fitz.open(pdf)
    probe = range(min(d.page_count, 40))
    chars = [len(d[i].get_text().strip()) for i in probe]
    info = {
        'pages': d.page_count,
        'metadata': d.metadata,
        'toc_entries': len(d.get_toc()),
        'text_layer_chars_first40': chars,
        'scanned': sum(chars) == 0,
    }
    d.close()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return info


def locate(pdf, pages='1-26', dpi=250):
    d = fitz.open(pdf)
    hits = []
    for pg in _parse_pages(pages, d.page_count):
        d[pg - 1].get_pixmap(dpi=dpi).save('/tmp/_pg.png')
        flat = re.sub(r'\s+', '', _ocr('/tmp/_pg.png'))
        if '目录' in flat or '目次' in flat:
            hits.append(pg)
    d.close()
    print('目录候选页:', hits)
    return hits


def digits(pdf, pages, x0=0.84, y0=0.10, y1=0.95, dpi=400):
    d = fitz.open(pdf)
    res = {}
    for pg in _parse_pages(pages, d.page_count):
        p = d[pg - 1]
        r = p.rect
        p.get_pixmap(dpi=dpi, clip=fitz.Rect(r.width * x0, r.height * y0,
                                             r.width, r.height * y1)).save('/tmp/_col.png')
        nums = re.findall(r'\d+', _ocr('/tmp/_col.png', psm=6, digits_only=True))
        res[pg] = nums
        print(pg, len(nums), nums)
    d.close()
    return res


def sheet(pdf, anchors, out, band=(0.0, 0.22), dpi=200, width=1100):
    """anchors: [(label, pdf_page), ...]；label 写成 'printed 71 -> pdf 92' 最方便对照。"""
    from PIL import Image, ImageDraw
    d = fitz.open(pdf)
    tiles = []
    for label, pg in anchors:
        p = d[pg - 1]
        r = p.rect
        pix = p.get_pixmap(dpi=dpi, clip=fitz.Rect(0, r.height * band[0],
                                                  r.width, r.height * band[1]))
        img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        img = img.resize((width, int(img.height * width / img.width)))
        tile = Image.new('RGB', (img.width, img.height + 26), 'white')
        tile.paste(img, (0, 26))
        ImageDraw.Draw(tile).text((6, 6), str(label), fill='red')
        tiles.append(tile)
    d.close()
    sh = Image.new('RGB', (width, sum(t.height for t in tiles)), 'white')
    y = 0
    for t in tiles:
        sh.paste(t, (0, y))
        y += t.height
    sh.save(out)
    print('sheet ->', out, sh.size)
    return out


def apply(pdf, entries, meta=None, xmp=None, backup=True, bakdir='~/pdf-backups'):
    d = fitz.open(pdf)
    n = d.page_count
    bad = [e for e in entries if not (1 <= int(e[2]) <= n)]
    if bad:
        raise SystemExit('页码越界: %r' % bad[:5])
    toc = [[int(e[0]), str(e[1]), int(e[2])] for e in entries]

    if backup:
        os.makedirs(os.path.expanduser(bakdir), exist_ok=True)
        bak = os.path.join(os.path.expanduser(bakdir),
                           os.path.splitext(os.path.basename(pdf))[0] + '.bak.pdf')
        if not os.path.exists(bak):
            shutil.copy2(pdf, bak)
        print('backup ->', bak)

    d.set_toc(toc)
    if meta:
        d.set_metadata({**d.metadata, **{k: str(v) for k, v in meta.items()}})
    if xmp:
        d.set_xml_metadata(xmp)
    tmp = '/tmp/_toc_out.pdf'
    d.save(tmp, garbage=4, deflate=True)
    d.close()
    shutil.move(tmp, pdf)

    # 重开验证
    v = fitz.open(pdf)
    got = v.get_toc()
    levels = {lv: sum(1 for t in got if t[0] == lv) for lv in sorted({t[0] for t in got})}
    ink = []
    for pg in {1, len(got) and got[-1][2] or 1, v.page_count}:
        pix = v[pg - 1].get_pixmap(dpi=50)
        s = pix.samples
        dark = sum(1 for i in range(0, len(s), pix.n) if s[i] < 128)
        ink.append((pg, round(dark / (pix.width * pix.height), 4)))
    print('pages', v.page_count, '| toc', len(got), '| by level', levels)
    print('ink ratio', ink)
    print('title', v.metadata.get('title'), '| author', v.metadata.get('author'))
    v.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('inventory'); p.add_argument('pdf')
    p = sub.add_parser('locate'); p.add_argument('pdf')
    p.add_argument('--pages', default='1-26'); p.add_argument('--dpi', type=int, default=250)
    p = sub.add_parser('digits'); p.add_argument('pdf'); p.add_argument('--pages', required=True)
    p.add_argument('--x0', type=float, default=0.84); p.add_argument('--dpi', type=int, default=400)
    p = sub.add_parser('sheet'); p.add_argument('pdf'); p.add_argument('--anchors', required=True,
                                                                   help='3:24,22:43 或 (若为纯页码列表) 3,22,71')
    p.add_argument('--out', required=True); p.add_argument('--band', nargs=2, type=float,
                                                           default=[0.0, 0.22]); p.add_argument('--width', type=int, default=1100)
    p = sub.add_parser('apply'); p.add_argument('pdf'); p.add_argument('--entries', required=True)
    p.add_argument('--meta'); p.add_argument('--xmp'); p.add_argument('--no-backup', action='store_true')

    a = ap.parse_args()
    if a.cmd == 'inventory':
        inventory(a.pdf)
    elif a.cmd == 'locate':
        locate(a.pdf, a.pages, a.dpi)
    elif a.cmd == 'digits':
        digits(a.pdf, a.pages, a.x0, dpi=a.dpi)
    elif a.cmd == 'sheet':
        anchors = []
        for tok in a.anchors.split(','):
            tok = tok.strip()
            if not tok:
                continue
            if ':' in tok:
                lab, pg = tok.split(':', 1)
                anchors.append((lab.strip(), int(pg)))
            else:
                anchors.append(('pdf %s' % tok, int(tok)))
        sheet(a.pdf, anchors, a.out, tuple(a.band), width=a.width)
    elif a.cmd == 'apply':
        entries = json.load(open(a.entries, encoding='utf-8'))
        meta = json.load(open(a.meta, encoding='utf-8')) if a.meta else None
        xmp = open(a.xmp, encoding='utf-8').read() if a.xmp else None
        apply(a.pdf, entries, meta, xmp, backup=not a.no_backup)


if __name__ == '__main__':
    main()
