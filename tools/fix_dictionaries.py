#!/usr/bin/env python3
"""fix_dictionaries.py - offset-preserving rebuild of the library dictionaries.

UnitDictionaryData.dat / PilotDictionaryData.dat are position-addressed like
KeyWordData (the library UI reads description LINES by position), so splice
compaction scrambles them. Same treatment as fix_keyworddata.py, minus names
(these files hold descriptions only):

  * every text segment overwritten in place: [prefix][english][space pad][NUL@orig]
  * wrap: byte capacity AND ~50 display cells per line, <tags> charged x1.7

Inputs:  work/Logic/Dat/FixedData/<file>            (pristine JP)
         build/dict_entries.json                    (runs: offsets/caps/prefixes)
         build/dict_desc_en.json                    (merged EN, key=U_/P_0x<first seg off>)
Output:  build/en/Logic/Dat/FixedData/<file>

Run AFTER `deploy.py apply Logic` (deploy.py calls it). Worksheets for these
files are intentionally blank - this script is their only writer.
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from fix_keyworddata import wrap_into, wrap_slots, NAMEFIX, SPAN, disp_cost, strip_terms  # shared wrappers

# Box width: maxWidth for the library desc object is 672 px (live-captured 2026-07-27),
# drawn at fontsize 21.6 x advance K 0.57 = 12.3 px/char flat -> 54.6 chars fill the box.
# The engine's fit-test measures FLAT MONOSPACE (n*fontsize) but the draw is proportional,
# so a 52-54 char line with a few wide glyphs (W/M/m) draws past 672 and CLIPS at the box
# edge (seen in-game at WRAP=54: "nearly every entry has cut-off text"). WRAP=50 keeps
# every line <= ~660 px even at +7% wide glyphs -> no clipping, no fit-mode. Measured
# cost: 6/363 entries lose a trailing sentence (was 0 at 54; 51->4, 49->11, 48->19).
# HISTORY: the old comment here blamed an unavoidable "engine crush" and set 54 to keep
# 100% of text. That crush was OUR bug (space-padding measured as glyphs) -- fixed by
# NUL-filling below -- so 54 is no longer needed to fight it; 50 is the right target now.
WRAP = 50
FILES = {"UnitDictionaryData.dat": "U", "PilotDictionaryData.dat": "P"}


def wrap_truncate(text, caps, cells):
    """Last-resort packer: greedily fill lines to capacity, DROP whatever doesn't
    fit (ending the last used line with '...'). Guarantees English renders even
    if the text is a touch too long for the box - never leaves scrambled JP."""
    text = text.replace("\n", " ")
    lines = [""] * len(caps)
    cost = [0.0] * len(caps)
    li = 0
    toks = SPAN.findall(text)
    ti = 0
    while ti < len(toks) and li < len(caps):
        tok = toks[ti]
        c = disp_cost(tok)
        cur = lines[li]
        cand = tok if not cur else cur + " " + tok
        add = c if not cur else c + 1
        if len(cand.encode("utf-8")) <= caps[li] and cost[li] + add <= cells[li]:
            lines[li] = cand
            cost[li] += add
            ti += 1
        else:
            li += 1  # move to next line, retry same token
    if ti < len(toks):  # ran out of room: mark truncation on the last filled line
        for j in range(len(lines) - 1, -1, -1):
            if lines[j]:
                base = lines[j].rstrip(".") + "..."
                if len(base.encode("utf-8")) <= caps[j]:
                    lines[j] = base
                break
    return lines


# wrap_slots (the slot-aware DP wrapper) now lives in fix_keyworddata.py so the KEY WORD
# boxes use the same tiny-slot / sentence-end rules. Imported above.

def main():
    ents = json.load(open(os.path.join(REPO, "build", "dict_entries.json"), encoding="utf-8"))
    desc = json.load(open(os.path.join(REPO, "build", "dict_desc_en.json"), encoding="utf-8"))
    problems = []
    for fn, tag in FILES.items():
        src = open(os.path.join(REPO, "work", "Logic", "Dat", "FixedData", fn), "rb").read()
        d = bytearray(src)
        for e in ents[fn]:
            key = f"{tag}_0x{e['segs'][0]['off']:06X}"
            en = (desc.get(key) or "").strip()
            for full, abbr in NAMEFIX.items():
                en = en.replace(f"<{full}>", f"<{abbr}>")
            en = strip_terms(en)  # PLAINTEXT_TERMS: <Name> -> Name (see flag docstring)
            en = re.sub(r"\s+", " ", en).strip()  # flow continuously (no hard breaks)
            if not en:
                problems.append((fn, key, "NO TRANSLATION"))
                continue
            caps = [s["cap"] - s["prefix"] for s in e["segs"]]
            cells = [min(c, WRAP) for c in caps]
            lines = wrap_slots(en, caps, cells)          # DP slot-aware: no blank lines
            if lines is None:
                lines = wrap_into(en, caps, cells)       # fallback: old byte-greedy
            if lines is None:
                lines = wrap_into(en.replace("\n", " "), caps, cells)
            if lines is None:  # drop whole trailing sentences until it fits (keeps prose clean)
                flat = en.replace("\n", " ")
                parts = re.split(r"(?<=[.!?])\s+", flat)
                while len(parts) > 1 and lines is None:
                    parts = parts[:-1]
                    lines = wrap_into(" ".join(parts), caps, cells)
                if lines is not None:
                    problems.append((fn, key, f"SHORTENED (dropped tail) len={len(en)}"))
            if lines is None:  # last resort: fill + truncate rather than leave JP
                lines = wrap_truncate(en, caps, cells)
                problems.append((fn, key, f"TRUNCATED cells={sum(cells)} len={len(en)}"))
            for s, line in zip(e["segs"], lines):
                start = s["off"] + s["prefix"]
                room = s["cap"] - s["prefix"]
                lb = line.encode("utf-8")
                # A slot must NEVER be fully empty. (2026-07-27) The line walker COLLAPSES runs
                # of NUL, so an all-NUL slot (trailing unused slot, or a tiny slot the DP left as
                # a paragraph gap) makes it read straight on into the NEXT entry - a foreign line
                # ('riz Raven adds a Tesla Drive booster pod') showed up at the end of the Lion
                # transport's entry in-game. One space = a 1-glyph string = renders as a blank
                # line, keeps the slot count in step with the JP structure. (The old space-PAD
                # never had this problem because no slot was ever empty; the fix below only
                # stops padding to the CAP.)
                if not lb:
                    lb = b" "
                assert len(lb) <= room
                # NUL-fill the tail, do NOT space-pad. (2026-07-27) The renderer MEASURES the
                # whole NUL-terminated string, so space padding was counted as real glyphs: a
                # cap-81 slot always measured 81 glyphs no matter how short its text, and the
                # auto-fit then condensed it to 672/1749.6 = 0.384 -> unreadable. A cap-21 slot
                # measured 21, fit fine, and rendered full size. That is why the "font size"
                # tracked the SLOT CAP rather than the text, and why the old note claiming the
                # renderer trims trailing spaces was wrong (verified live: 10/10 slots padded,
                # strlen == cap). Terminating right after the text makes the measured width the
                # ACTUAL text width. d[off+cap] is outside this slice, so it stays NUL.
                d[start:start + room] = lb + b"\x00" * (room - len(lb))
        assert len(d) == len(src)
        for e in ents[fn]:
            for s in e["segs"]:
                assert d[s["off"] + s["cap"]] == 0
        out = os.path.join(REPO, "build", "en", "Logic", "Dat", "FixedData", fn)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(bytes(d))
        print(f"fix_dictionaries: {fn}: {len(ents[fn])} entries -> {out}")
    # SHORTENED/TRUNCATED are graceful fit adjustments (still English) - not failures;
    # only a genuinely missing translation is a hard error.
    hard = [p for p in problems if p[2] == "NO TRANSLATION"]
    soft = len(problems) - len(hard)
    if soft:
        print(f"  ({soft} entries auto-fitted: trailing sentence dropped or truncated to box)")
    for p in hard:
        print("  !!", p)
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
