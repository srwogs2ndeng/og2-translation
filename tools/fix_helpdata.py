#!/usr/bin/env python3
"""fix_helpdata.py - OFFSET-PRESERVING rebuild of HelpData.dat (help / tooltip popups).

WHY (found in-game 2026-07-27): the help renderer draws an entry as N lines whose starts are
FIXED BYTE OFFSETS from the entry start = the ORIGINAL JP segment boundaries (a tiny binary
record before each entry holds N and the JP line width W=0x2c=44 fullwidth chars; line k
starts at hdr + k*(W*3+1)). The worksheet apply's splice_grow shrank/grew segments in place
and shifted everything after them, so line 2 started mid-word ('ts the terrain best.') and
line 3 ran into the NEXT entry ('mbat, and'). Same class as the dictionaries.

MODEL: the STRI block is a sequence of NUL-terminated strings. TEXT segments run in groups
separated by tiny binary separators; each group = one help entry, its segments = its lines.
Segment 0 may carry a 1-3 byte control HEADER (0x85 / 0x88 / `1a 01 0a` / `2f 01 86` ...)
before the JP text; it is preserved byte-for-byte (see [[library-text-rules]] rule 7).

WRITE: English for the entry = worksheet EN (keyed by seg0 file offset) or, for the
segments the extractor skipped, helpdesc_inline_en.json (matched by JP body). The joined
text is wrapped across the entry's line slots (byte cap = JP segment length, display cap
~84 cells = the 44-fullwidth box at our K=0.57 advance) with the slot-aware DP (sentence
ends in tiny tail slots, no orphans), then each slot is written [hdr][line][NUL fill] to
EXACTLY its JP length. Nothing moves; every original NUL terminator stays.

Inputs:  work/Logic/Dat/FixedData/HelpData.dat
         build/worksheets/Logic/Dat/FixedData/HelpData.dat.json
         build/helpdesc_inline_en.json
Output:  build/en/Logic/Dat/FixedData/HelpData.dat   (overwrites the apply result)
Run from deploy.py apply Logic (replaces fix_helpdesc.py).
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from fix_keyworddata import wrap_slots, wrap_into, SPAN, disp_cost

WRAP = 92   # display cells per line (see cells= below)


def hdrlen(s):
    if len(s) >= 3 and s[1] == 0x01:          # [X][01][Y] 3-byte control code
        return 3
    for p in range(min(len(s), 6)):
        if s[p] >= 0xE0 or s[p] == 0x3C:       # first JP lead byte or '<' tag
            return p
    return 0

def is_text(s):
    return len(s) > 1 and (any(b >= 0xE0 for b in s) or
                           (len(s) > 4 and sum(0x20 <= b < 0x7f for b in s) >= len(s) - 3))

def body_key(t):
    # canonical JP body: drop any leading control / punct+\x01 prefix the extractor kept
    return re.sub(r"^[^\u3000-\u9fff\uff00-\uffef<]{0,4}", "", t)

_HDRCH = re.compile(r"^[^　-鿿＀-￯<A-Za-z0-9\"'(]{0,4}")

def strip_hdr(en, jp_ws):
    """The worksheet extractor decoded a segment's 1-3 byte control HEADER as text and it
    survived into the EN ('ESShows...', ';Shown...'). Strip exactly the header
    chars the JP worksheet text starts with (or any leading control-char run)."""
    m = len(jp_ws) - len(jp_ws.lstrip()) if False else 0
    mm = re.match(r"^[^　-鿿＀-￯<]{0,4}", jp_ws or "")
    h = mm.group(0) if mm else ""
    if h and any(ord(c) < 0x20 for c in h) and en.startswith(h):
        return en[len(h):]
    # fallback: leading run containing a control char -> drop through the last control char
    if any(ord(c) < 0x20 for c in en[:3]):
        last = max(i for i, c in enumerate(en[:3]) if ord(c) < 0x20)
        return en[last + 1:].lstrip(" ;:")
    return en

def clean_join(parts):
    t = " ".join(p.strip() for p in parts if p and p.strip())
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)          # 'damage .' -> 'damage.'
    t = re.sub(r"(?<!\.)\.\.(?!\.)", ".", t)          # 'best..' -> 'best.'
    return t.strip()

def main():
    jp = open(os.path.join(REPO, "work", "Logic", "Dat", "FixedData", "HelpData.dat"), "rb").read()
    ws = json.load(open(os.path.join(REPO, "build", "worksheets", "Logic", "Dat", "FixedData", "HelpData.dat.json"), encoding="utf-8"))
    inl = json.load(open(os.path.join(REPO, "build", "helpdesc_inline_en.json"), encoding="utf-8"))
    inl_by_body = {}
    for x in inl:
        inl_by_body.setdefault(body_key(x["jp"]), x["en"])

    ovp = os.path.join(REPO, "build", "helpdata_en_override.json")
    override = json.load(open(ovp, encoding="utf-8")) if os.path.exists(ovp) else {}
    stri = jp.find(b"STRI"); blk0 = stri + 0x12
    segs = []; o = blk0
    while o < len(jp):
        e = jp.find(b"\x00", o)
        if e < 0: break
        segs.append((o, jp[o:e])); o = e + 1
    entries = []; cur = []
    for off, s in segs:
        if is_text(s): cur.append((off, s))
        elif cur: entries.append(cur); cur = []
    if cur: entries.append(cur)

    d = bytearray(jp)
    lossy = []; jp_of = {}; text_of = {}; caps_of = {}
    stats = {"entries": len(entries), "multi": 0, "shortened": 0, "truncated": 0, "missing_en": 0, "tiny_gap": 0}
    for e in entries:
        pieces = []; miss = False
        for off, s in e:
            h = hdrlen(s); k = "0x%06X" % off
            en = (ws.get(k) or {}).get("en") if k in ws else None
            if en: en = strip_hdr(en, (ws.get(k) or {}).get("jp") or "")
            if not en or not en.strip():
                en = inl_by_body.get(body_key(s[h:].decode("utf-8", "replace")))
            if en is None:
                miss = True; break
            pieces.append(en)
        if miss:
            stats["missing_en"] += 1
            continue                                   # leave this entry Japanese
        text = clean_join(pieces)
        k0 = "0x%06X" % e[0][0]
        if k0 in override and override[k0].strip():      # hand-tightened full text wins
            text = clean_join([strip_hdr(override[k0], (ws.get(k0) or {}).get("jp") or "")])
        caps = [len(s) - hdrlen(s) for _, s in e]
        # display budget scales with the entry's box: the widest JP segment is W fullwidth
        # chars = W*3 bytes; measured in-game 86 EN chars fill a 44-char (132-byte) box at
        # our K=0.57 advance -> ~0.64 EN cells per JP byte. Narrow tail slots are byte-bound.
        # measured in-game: 86 EN chars fill the standard 44-fullwidth help box at our K=0.57
        # advance. Allow 92: a >86 line trips the (K-aware) fit-mode and is condensed <=7%,
        # invisible on a tooltip and far better than dropping text. Short slots are byte-bound.
        cells = [min(c, WRAP) for c in caps]
        jp_of[k0] = " ".join(x[hdrlen(x):].decode("utf-8", "replace") for _, x in e); text_of[k0] = text; caps_of[k0] = cells
        if len(e) > 1: stats["multi"] += 1
        lines = wrap_slots(text, caps, cells)
        if lines is None:
            lines = wrap_into(text, caps, cells)
        if lines is None:                              # drop trailing sentences until it fits
            parts = re.split(r"(?<=[.!?])\s+", text)
            while len(parts) > 1 and lines is None:
                parts = parts[:-1]; lines = wrap_into(" ".join(parts), caps, cells)
            if lines is not None: stats["shortened"] += 1; lossy.append(k0)
        if lines is None:                              # last resort: hard cut with '...'
            toks = SPAN.findall(text); out = []; ti = 0
            for c in caps:
                line = ""
                while ti < len(toks):
                    cand = toks[ti] if not line else line + " " + toks[ti]
                    if len(cand.encode()) > c: break
                    line = cand; ti += 1
                out.append(line)
            if ti < len(toks):
                for j in range(len(out) - 1, -1, -1):
                    if out[j]:
                        base = out[j].rstrip(".") + "..."
                        if len(base.encode()) <= caps[j]: out[j] = base
                        break
            lines = out; stats["truncated"] += 1; lossy.append(k0)
        for (off, s), line in zip(e, lines):
            h = hdrlen(s); room = len(s) - h
            lb = line.encode("utf-8")
            if not lb: lb = b" "; stats["tiny_gap"] += 1
            assert len(lb) <= room, (hex(off), len(lb), room)
            d[off + h: off + len(s)] = lb + b"\x00" * (room - len(lb))
            assert d[off + len(s)] == 0
    assert len(d) == len(jp)
    out = os.path.join(REPO, "build", "en", "Logic", "Dat", "FixedData", "HelpData.dat")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(bytes(d))
    if os.environ.get("OG2_HELP_EXPORT"):
        exp = [{"key": k, "jp": jp_of[k], "en_current": text_of[k], "line_cells": caps_of[k],
                "total_cells": sum(caps_of[k])} for k in lossy]
        json.dump(exp, open(os.environ["OG2_HELP_EXPORT"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  exported %d lossy entries -> %s" % (len(exp), os.environ["OG2_HELP_EXPORT"]))
    print("fix_helpdata: %(entries)d entries (%(multi)d multi-line) -> HelpData.dat | shortened=%(shortened)d truncated=%(truncated)d missing_en=%(missing_en)d" % stats)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
