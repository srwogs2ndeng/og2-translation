#!/usr/bin/env python3
"""worksheet.py - translation worksheet layer over reinsert_utf8.

Turns any text container into an editable JSON worksheet and back, with the
ASCII-punctuation rule enforced automatically on every reinsert (see
memory/ascii-punctuation-rule).

  dump   <container> <work.json>          # {hexoff:{jp,en:"",slot}} for CJK strings
  apply  <container> <work.json> <out>    # reinsert normalized `en` (grow if needed)
  norm   "text"                           # print normalized text (debug)

The worksheet is the unit of translation work: agents/humans fill the "en"
fields; apply() writes them back into the container (in-place slot where it
fits, append+repoint growth otherwise) and self-verifies the round-trip.
"""
import sys, os, json, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reinsert_utf8 as R

# --- ASCII punctuation normalizer (memory/ascii-punctuation-rule) ---
# The font renders CJK-range typographic punctuation full-width/misaligned; English
# must use half-width ASCII. Keep the game's own brackets 「」 and U+3000 indents.
PUNCT = {
    "’": "'", "‘": "'", "ʼ": "'",         # curly/modifier apostrophes
    "“": '"', "”": '"', "„": '"',         # curly double quotes
    "—": "-", "–": "-", "―": "-",          # em/en/horizontal dash
    "…": "...",                                       # ellipsis
    " ": " ",                                          # nbsp
    "！": "!", "？": "?", "，": ",", "．": ".",  # fullwidth ! ? , .
    "：": ":", "；": ";", "（": "(", "）": ")",
    "　": " ",                                # ideographic fullwidth space -> normal (EN quotes)
}
_TR = {ord(k): v for k, v in PUNCT.items()}

def normalize(text):
    return text.translate(_TR)

def rewrap(text, width=48):
    """Re-flow dialogue so each line fills the text box. The game breaks lines only at
    literal '@' markers (no auto-wrap). The Japanese '@' breaks were sized for ~28
    fullwidth JP chars, so preserving them leaves short, early-broken English lines.
    Instead we JOIN the whole message into continuous prose (dropping the JP breaks) and
    re-wrap it to `width` half-width columns, inserting fresh '@' breaks — so each line
    uses as much of the box as possible."""
    joined = " ".join(s.strip() for s in text.split("@") if s.strip())
    if len(joined) <= width:
        return joined
    out, line = [], ""
    for word in joined.split(" "):
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line += " " + word
        else:
            out.append(line); line = word
    if line:
        out.append(line)
    return "@".join(out)


def cmd_dump(container, outp):
    d = open(container, "rb").read()
    ws = {}
    for off, t in R.scan(d, cjk_only=True):
        ws[f"0x{off:06X}"] = {"jp": t, "en": "", "slot": R.slot_len(d, off)}
    json.dump(ws, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"dumped {len(ws)} strings -> {outp}")


def cmd_apply(container, workp, outp):
    d = open(container, "rb").read()
    ws = json.load(open(workp, encoding="utf-8"))
    edits = {}
    skipped = 0
    for k, v in ws.items():
        raw = v.get("en") or ""
        if raw == "":                  # untranslated -> leave the JP in place
            skipped += 1
            continue
        # whitespace-only en is an INTENTIONAL blank (e.g. a JP line-wrap remnant
        # whose sentence the previous English line already absorbed): apply it as an
        # empty string so that continuation line renders blank instead of leaking JP.
        en = normalize(raw).strip()
        if d[:4] == b"LDBI":           # dialogue: re-wrap to the text box width
            # Strip <keyword-term> brackets so they flow as plain inline text.
            # In JP these were a fullwidth inline highlight; in EN the term
            # renderer draws them full-width/out-of-flow and shatters the line
            # into a jumbled two-column layout (ls002 "<Shura Rebellion>"...).
            # Only <name> tags (no '='); <C=..>/<W=..> control tags are kept.
            # Gated by OG2_PLAINTEXT_TERMS (default on) like the library fixers.
            _dlg = os.environ.get("OG2_PLAINTEXT_TERMS_DLG",
                                  os.environ.get("OG2_PLAINTEXT_TERMS", "1"))
            if _dlg == "1":
                en = re.sub(r"<([^<>=@]{1,40})>", r"\1", en)
            en = rewrap(en)
        edits[int(k, 16)] = en
    if d[:4] == b"FIXH" and os.environ.get("FIXH_GROW") != "0":
        # FIXH: splice-grow handles BOTH SOFS-referenced strings and adjacency-read
        # descriptions (which no offset field points at) in one pass - it rewrites
        # each edited string in place and fixes up every SOFS offset. It is hard-gated
        # (fails closed to the original bytes on any structural check), so if it trips
        # we fall back to the proven in-place + append+repoint path.
        import fixh_grow as FX          # deterministic 32-bit SOFS/STRI parse
        out, refused = FX.splice_grow(d, edits)
        if out == d and edits:          # gate tripped -> safe fallback
            out, refused = R.reinsert_grow(d, edits)
            out, refused = FX.grow_files(out, {o: edits[o] for o in refused})
    else:
        out, refused = R.reinsert_grow(d, edits)
    open(outp, "wb").write(out)
    # verify: re-scan output, every applied slot must read back the normalized en
    chk = dict(R.scan(out, cjk_only=False))
    ok = sum(1 for o, t in edits.items() if o not in refused)
    tag = "same size" if len(out) == len(d) else f"grew +{len(out)-len(d)}"
    print(f"applied {len(edits)-len(refused)}/{len(edits)} (skipped {skipped} untranslated), {tag} -> {outp}")
    if refused:
        print(f"  REFUSED (left original, safe): {len(refused)} offsets -> {[hex(o) for o in list(refused)[:8]]}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if   cmd == "dump":  cmd_dump(sys.argv[2], sys.argv[3])
    elif cmd == "apply": cmd_apply(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "norm":  print(normalize(sys.argv[2]))
    else: print(__doc__); sys.exit(1)
