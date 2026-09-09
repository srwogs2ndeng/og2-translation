#!/usr/bin/env python3
"""wtd_positions.py - per-ELEMENT X/Y nudges for windowdataMain.wtd (General2d menu chrome).

Sibling of wtd_sizes.py, for the labels that wtd_sizes CANNOT help. A WTD text record
carries a few big-endian f32s just before its length byte, but not every record uses those
slots the same way. Two layouts matter here:

  size-bearing   [sizeX f32][sizeY f32][8c a0 00 xx][00 00 00][len][text]
  position-only  [0.0][X f32][Y f32]   [00 00 00][len][text]      (and a 4-byte-shifted
                 [X f32][Y f32][-0.0]  [00 00 00][len][text]       variant of the same)

wtd_sizes refuses the second kind - correctly, since there is no font size in it - which
left the Pilot Training tabs with no remedy but shortening the English. They do not need
shortening: they are positioned, not oversized. 'Stat Boost' sits at X=453 and
'Learn Skill' at X=634, 181 apart, and both sat too far left in their frames.

WHY THE FIELD IS FOUND BY VALUE, not at a fixed offset. Of the six records for those two
labels, four hold X at off-15 and two hold it at off-11 - the same record shape shifted
along by one slot. Hardcoding off-15 would have written the X of four records and
corrupted an unrelated float in the other two. So each entry states the value it EXPECTS
to find, the tool searches the candidate slots for it, and refuses the record if no slot
matches. It fails closed: a record it cannot identify is left exactly as it was.

Moves live in build/wtd_positions.json:
    {"0x0EEA8B": {"from_x": 453.0, "to_x": 493.0}, ...}
Applied AFTER wtd_tool apply and wtd_sizes, offset-preserving (4 bytes rewritten in place).

    python tools/wtd_positions.py <in.wtd> <out.wtd> [positions.json]
"""
import json, os, struct, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOTS = (15, 11, 7)          # the three f32 slots that precede a record's length byte
TOL = 0.5                    # matching an exact stored float, so this is generous


def x_field(w, off, expect_x, tol=TOL):
    """(pos, value) of the float slot before `off` holding `expect_x`, else None."""
    if off < 16:
        return None
    for d in SLOTS:
        p = off - d
        try:
            v = struct.unpack(">f", w[p:p + 4])[0]
        except struct.error:
            continue
        if abs(v - float(expect_x)) <= tol:
            return p, v
    return None


def apply(w, moves):
    """Rewrite each named record's X. Returns (bytes, applied, refused)."""
    d = bytearray(w)
    ok = 0
    refused = []
    for k, m in moves.items():
        off = int(k, 16)
        r = x_field(d, off, m["from_x"])
        if r is None:
            refused.append(k)
            continue
        struct.pack_into(">f", d, r[0], float(m["to_x"]))
        ok += 1
    return bytes(d), ok, refused


def main():
    inp, outp = sys.argv[1], sys.argv[2]
    mp = sys.argv[3] if len(sys.argv) > 3 else os.path.join(REPO, "build", "wtd_positions.json")
    moves = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    w = open(inp, "rb").read()
    out, ok, refused = apply(w, moves)
    assert len(out) == len(w), "wtd_positions must be offset-preserving"
    open(outp, "wb").write(out)
    print("wtd_positions: applied %d/%d position moves -> %s%s"
          % (ok, len(moves), outp, ("  REFUSED %s" % refused) if refused else ""))
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
