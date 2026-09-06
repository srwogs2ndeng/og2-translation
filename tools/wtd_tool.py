#!/usr/bin/env python3
"""wtd_tool.py - dump/apply for windowdataMain.wtd (General2d menu chrome).

The .wtd is a `_DTW` UI-layout binary. Menu text is stored as records embedded in
the layout as:  [1-byte length][UTF-8 content][NUL]  where the length byte equals
1 + content_bytes (i.e. the offset from the length byte to the terminating NUL).
Records sit among binary layout data (position floats, texture refs) and ~214
absolute offset references point at string starts, so the ONLY safe edit is
OFFSET-PRESERVING in place: rewrite a record's content within its existing span,
update its length byte, and NUL-pad any freed slack. Nothing shifts, so every
layout float and offset reference stays valid. English that would need more than
the original length byte is refused (kept Japanese).

  dump  <wtd> <work.json>        # {hexoff:{jp,en,slot}} - jp is clean content
  apply <wtd> <work.json> <out>  # rebuild in place, verify, report

`hexoff` points at the LENGTH byte. `slot` = original length byte value = the max
(1 + content_bytes) an English string may occupy.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reinsert_utf8 as R
from worksheet import normalize

# The .wtd text renderer parses ASCII '<...>' as CONTROL TAGS (e.g. <I=61> icon,
# like the CSB's <C=..>/<W=..>). The menus use FULLWIDTH ＜＞【】 as literal display
# brackets, which the menu font renders fine. So we must NOT convert those to ASCII
# (doing so makes "<Robot Library>" look like a malformed tag and crashes the menu).
# Keep fullwidth brackets; apply only the safe half-width punctuation normalization.
def _norm(t):
    return normalize(t)


def records(d):
    """Yield (len_off, content_str, lenval) for every length-prefixed text record:
    a NUL-delimited chunk whose first byte equals the chunk's byte length."""
    for off, chunk in R.scan(d, cjk_only=False):
        b = chunk.encode("utf-8")
        # length-prefix record: first byte == total chunk byte length (= 1 + content)
        if len(b) >= 2 and b[0] == len(b):
            try:
                content = b[1:].decode("utf-8")
            except UnicodeDecodeError:
                continue
            if R.has_cjk(content):
                yield off, content, b[0]


def cmd_dump(wtd, outp):
    d = open(wtd, "rb").read()
    ws = {}
    for off, content, lenval in records(d):
        ws[f"0x{off:06X}"] = {"jp": content, "en": "", "slot": lenval}
    json.dump(ws, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"dumped {len(ws)} length-prefixed text records -> {outp}")


def apply(d, ws):
    """Return (out_bytes, refused_offsets, applied_count). Offset-preserving."""
    out = bytearray(d)
    refused = set(); applied = 0
    for k, v in ws.items():
        en = (v.get("en") or "")
        if en.strip() == "":
            continue
        off = int(k, 16)
        orig_len = out[off]                       # length byte value L (= content+1)
        new_content = _norm(en).encode("utf-8")
        # The records are VARIABLE-LENGTH and the game walks to the next field using
        # this length byte, so we must NOT change it (offset-preserving means the next
        # field stays at its physical position off+L+1; a smaller length would make the
        # game read the next field from inside our padding -> crash). Instead keep L,
        # write the English content, then NUL-fill the rest of the L-byte field (the
        # terminator + slack). English must be <= L-1 bytes to leave room for the NUL.
        if len(new_content) > orig_len - 1:       # no room for content + terminator
            refused.add(off); continue
        out[off + 1: off + 1 + len(new_content)] = new_content
        for p in range(off + 1 + len(new_content), off + orig_len + 1):
            out[p] = 0                            # terminator + NUL slack, through off+L
        # out[off] (the length byte) is deliberately left unchanged
        applied += 1
    return bytes(out), refused, applied


def cmd_apply(wtd, workp, outp):
    d = open(wtd, "rb").read()
    ws = json.load(open(workp, encoding="utf-8"))
    out, refused, applied = apply(d, ws)
    assert len(out) == len(d), "wtd apply must be offset-preserving"
    # verify: re-read each applied record, content must equal normalized en
    ok = 0
    for k, v in ws.items():
        en = (v.get("en") or "").strip()
        if not en or int(k, 16) in refused:
            continue
        off = int(k, 16)
        nul = out.find(b"\x00", off + 1)
        got = out[off + 1:nul].decode("utf-8", "replace")
        if got == _norm(en):
            ok += 1
    open(outp, "wb").write(out)
    print(f"applied {applied} (verified {ok}), refused {len(refused)} (too long), "
          f"size {len(out)} (unchanged) -> {outp}")
    if refused:
        ex = [hex(o) for o in list(refused)[:8]]
        print(f"  refused (kept JP): {len(refused)} {ex}")


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    cmd = sys.argv[1]
    if cmd == "dump":  cmd_dump(sys.argv[2], sys.argv[3])
    elif cmd == "apply": cmd_apply(sys.argv[2], sys.argv[3], sys.argv[4])
    else: print(__doc__)
