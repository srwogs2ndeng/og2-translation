#!/usr/bin/env python3
"""fix_fixh_text.py - OFFSET-PRESERVING rebuild of the FixedData files whose description
text is MULTI-LINE (HelpData, SpiritData, PartsData, ACEBonusData).

WHY (in-game 2026-07-27): these renderers locate line 2+ of an entry by a FIXED byte stride
from the entry start, so the worksheet apply's splice_grow (which resizes each string in
place and shifts what follows) made later lines start mid-word and run into the next entry:
    HelpData   'ts the terrain best.' / 'mbat, and'   (record before entry: N lines, W=44 chars
                                                       -> line k at hdr + k*(W*3+1))
    SpiritData 'l, Valor, Alert,'                     (seg0's 1-byte header IS its length ->
                                                       line 2 at start + len + 1)
Keeping every segment at its exact JP byte length keeps every stride (and length byte) valid.

MODEL: STRI block = NUL-terminated strings; runs of TEXT segments between tiny binary
separators = one entry; segment 0 may carry a 1-3 byte control HEADER (length byte, 0x85,
1a-01-0a, 2f-01-86 ...) which is preserved byte-for-byte. English per segment comes from
the worksheet (keyed by segment file offset; a header char the extractor decoded into the EN
is stripped) or, for HelpData's extractor-skipped segments, helpdesc_inline_en.json.

WRITE: joined EN wrapped over the entry's slots (byte cap = JP seg len; display cap WRAP for
the wide help box, byte-bound otherwise) with the slot-aware DP; each slot = [hdr][line][NUL
fill] at EXACTLY its JP length; never empty. Single-segment strings that are SOFS-referenced
and too long (spirit names 'Intuition' > 6B) are appended + SOFS-repointed via fixh_grow
(append-only: nothing moves). Anything else that does not fit is shortened (reported).

    python tools/fix_fixh_text.py            # all four files
    OG2_TEXT_EXPORT=<json> ...               # also export lossy entries for a rewrite pass
Overrides: build/<stem>_en_override.json {"0x<seg0 off>": "full English"} win over sources.
"""
import json, os, re, struct, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import fixh_grow
from fix_keyworddata import wrap_slots, wrap_into, SPAN, disp_cost

FILES = {
    # name: (display cells per line or None=byte-bound, inline-EN json or None, mode)
    #   mode "flow"  = the entry's segments are ONE flowing text -> join + re-wrap over the slots
    #   mode "lines" = each segment is an INDEPENDENT item (ACE bonuses) -> 1:1 segment->slot
    "HelpData.dat":     (84,   "helpdesc_inline_en.json", "flow"),  # 44-fullwidth box = 86 EN chars measured; NEVER exceed (fit-mode shrinks hard)
    "SpiritData.dat":   (48,   None, "flow"),                       # effect box ~ 25 fullwidth (JP L1 <= 25 chars)
    "PartsData.dat":    (46,   None, "flow"),                       # parts box  ~ 24 fullwidth
    "ACEBonusData.dat": (None, None, "lines"),                      # byte-bound, one bonus per line
}


def hdrlen(s):
    if len(s) >= 2 and s[0] == len(s) and s[0] < 0xE0:   # 1-byte LENGTH header (Spirit/Parts/ACE)
        return 1
    if len(s) >= 3 and s[1] == 0x01:                     # [X][01][Y] 3-byte control code
        return 3
    for p in range(min(len(s), 6)):
        if s[p] >= 0xE0 or s[p] == 0x3C:                 # first JP lead byte or '<' tag
            return p
    return 0


def is_text(s):
    return len(s) > 1 and (any(b >= 0xE0 for b in s) or
                           (len(s) > 4 and sum(0x20 <= b < 0x7f for b in s) >= len(s) - 3))


def body_key(t):
    return re.sub(r"^[^　-鿿＀-￯<]{0,4}", "", t or "")


def strip_hdr(en, jp_ws):
    """Drop a header the extractor decoded into the EN ('FHit rate', 'E<02>SShows', '<01>;Shown')."""
    mm = re.match(r"^[^　-鿿＀-￯<]{0,4}", jp_ws or "")
    h = mm.group(0) if mm else ""
    if h and en.startswith(h):
        rest = en[len(h):]
        ctrl = any(ord(c) < 0x20 for c in h)
        # a 1-char letter header ('F','L') is only stripped when the EN clearly continues with a
        # new word start ('FHit', 'LHalves'); '@' '.' '1' and control chars are always stripped
        if ctrl or not h[0].isalpha() or (rest[:1].isupper() or rest[:1] in "\"'(+-<0123456789"):
            return rest
    if any(ord(c) < 0x20 for c in en[:3]):
        last = max(i for i, c in enumerate(en[:3]) if ord(c) < 0x20)
        return en[last + 1:].lstrip(" ;:")
    return en


def clean_join(parts):
    t = " ".join(p.strip() for p in parts if p and p.strip())
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"(?<!\.)\.\.(?!\.)", ".", t)
    return t.strip()


def build(name, wrap, inline_name, export, mode="flow"):
    jp = open(os.path.join(REPO, "work", "Logic", "Dat", "FixedData", name), "rb").read()
    ws = json.load(open(os.path.join(REPO, "build", "worksheets", "Logic", "Dat", "FixedData", name + ".json"), encoding="utf-8"))
    inl_by_body = {}
    ip = os.path.join(REPO, "build", inline_name) if inline_name else None
    if ip and os.path.exists(ip):
        for x in json.load(open(ip, encoding="utf-8")):
            inl_by_body.setdefault(body_key(x["jp"]), x["en"])
    stem = name.split(".")[0].lower()
    ovp = os.path.join(REPO, "build", stem + "_en_override.json")
    override = json.load(open(ovp, encoding="utf-8")) if os.path.exists(ovp) else {}
    det = fixh_grow.detect(jp)
    sofs = set()
    if det:
        base, fields = det
        sofs = {struct.unpack_from(">I", jp, p)[0] + base for p in fields}

    stri = jp.find(b"STRI"); o = stri + 0x12; segs = []
    while o < len(jp):
        e = jp.find(b"\x00", o)
        if e < 0:
            break
        segs.append((o, jp[o:e])); o = e + 1
    entries = []; cur = []
    for off, s in segs:
        if is_text(s):
            cur.append((off, s))
        elif cur:
            entries.append(cur); cur = []
    if cur:
        entries.append(cur)

    d = bytearray(jp); grow_edits = {}; lossy = []
    st = {"entries": len(entries), "multi": 0, "grown": 0, "shortened": 0, "truncated": 0, "missing": 0}
    for e in entries:
        pieces = []; miss = False
        for off, s in e:
            h = hdrlen(s); k = "0x%06X" % off
            en = (ws.get(k) or {}).get("en") if k in ws else None
            if en:
                en = strip_hdr(en, (ws.get(k) or {}).get("jp") or "")
            if not en or not en.strip():
                en = inl_by_body.get(body_key(s[h:].decode("utf-8", "replace")))
            if en is None:
                miss = True; break
            pieces.append(en)
        if miss:
            st["missing"] += 1; continue
        k0 = "0x%06X" % e[0][0]
        if override.get(k0, "").strip():
            text = clean_join([strip_hdr(override[k0], (ws.get(k0) or {}).get("jp") or "")])
        else:
            text = clean_join(pieces)
        caps = [len(s) - hdrlen(s) for _, s in e]
        # single SOFS-referenced string that does not fit -> append + repoint (names etc.)
        if len(e) == 1 and e[0][0] in sofs and len(text.encode("utf-8")) > caps[0]:
            grow_edits[e[0][0]] = text; st["grown"] += 1; continue
        cells = [min(c, wrap) if wrap else c for c in caps]
        if len(e) > 1:
            st["multi"] += 1
        if mode == "lines" and len(e) > 1 and not override.get(k0, "").strip():
            # independent items: keep segment->slot 1:1; a too-long item is trimmed to its slot
            lines = []
            for piece, c in zip(pieces, caps):
                pb = clean_join([piece])
                if len(pb.encode("utf-8")) > c:
                    toks = SPAN.findall(pb); cut = ""
                    for tk in toks:
                        cand = tk if not cut else cut + " " + tk
                        if len(cand.encode("utf-8")) > c: break
                        cut = cand
                    pb = cut; st["truncated"] += 1; lossy.append(k0)
                lines.append(pb)
        else:
            lines = wrap_slots(text, caps, cells) or wrap_into(text, caps, cells)
        if lines is None:
            parts = re.split(r"(?<=[.!?])\s+", text)
            while len(parts) > 1 and lines is None:
                parts = parts[:-1]; lines = wrap_into(" ".join(parts), caps, cells)
            if lines is not None:
                st["shortened"] += 1; lossy.append(k0)
        if lines is None:
            toks = SPAN.findall(text); out = []; ti = 0
            for c in caps:
                line = ""
                while ti < len(toks):
                    cand = toks[ti] if not line else line + " " + toks[ti]
                    if len(cand.encode()) > c:
                        break
                    line = cand; ti += 1
                out.append(line)
            if ti < len(toks):
                for j in range(len(out) - 1, -1, -1):
                    if out[j]:
                        b2 = out[j].rstrip(".") + "..."
                        if len(b2.encode()) <= caps[j]:
                            out[j] = b2
                        break
            lines = out; st["truncated"] += 1; lossy.append(k0)
        for (off, s), line in zip(e, lines):
            h = hdrlen(s); room = len(s) - h
            lb = line.encode("utf-8") or b" "
            assert len(lb) <= room, (name, hex(off), len(lb), room)
            d[off + h: off + len(s)] = lb + b"\x00" * (room - len(lb))
            assert d[off + len(s)] == 0
        if export is not None:
            export.append({"file": name, "key": k0,
                           "jp": " ".join(x[hdrlen(x):].decode("utf-8", "replace") for _, x in e),
                           "en_current": text, "line_cells": cells, "total_cells": sum(cells),
                           "lossy": k0 in lossy})
    assert len(d) == len(jp)
    out = bytes(d); refused = set()
    if grow_edits:
        # SPLICE the over-long names in place (shifting what follows + fixing every SOFS
        # offset) rather than append+repoint: the spirit menu reads names from their
        # ORIGINAL slot region and an appended copy rendered BLANK in-game (2026-07-27).
        # Multi-line effect segments move as intact blocks, so their strides stay valid.
        out, refused = fixh_grow.splice_grow(out, grow_edits)
        if refused == set(grow_edits) and grow_edits:      # gate tripped -> fallback
            out, refused = fixh_grow.grow_files(bytes(d), grow_edits)
            print("  (splice gate tripped for %s; used append+repoint)" % name)
    outp = os.path.join(REPO, "build", "en", "Logic", "Dat", "FixedData", name)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    open(outp, "wb").write(out)
    print("fix_fixh_text: %-18s entries=%d multi=%d grown=%d refused=%d shortened=%d truncated=%d missing=%d" %
          (name, st["entries"], st["multi"], st["grown"], len(refused), st["shortened"], st["truncated"], st["missing"]))
    return refused


def main():
    exp_path = os.environ.get("OG2_TEXT_EXPORT"); export = [] if exp_path else None
    for name, (wrap, inline, mode) in FILES.items():
        build(name, wrap, inline, export, mode)
    if exp_path:
        lossy = [x for x in export if x["lossy"]]
        json.dump(lossy, open(exp_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  exported %d lossy entries -> %s" % (len(lossy), exp_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
