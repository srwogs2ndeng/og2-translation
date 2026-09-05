#!/usr/bin/env python3
"""wtd_sizes.py - per-ELEMENT font size overrides for windowdataMain.wtd (General2d menu chrome).

Every WTD text record carries its own font size as two big-endian f32s right before the
text: layout ... [sizeX f32][sizeY f32][8c a0 00 xx][00 00 00][len byte][text][NUL]. Found
2026-07-27: 1007 text records have it; stock values are 24x24 (labels), 19x19 (spirit status
badges), 20x24 / 15x28 / 16x18 (the game already uses X-only condensing). The window-family
renderer applies these as fontsize X/Y (SetFontSize), so shrinking sizeX on ONE record
condenses ONLY that element - a surgical fix for English labels that overrun a JP-sized cell
(2-letter spirit badges jamming, 'Stats' overlapping 'Mel', terrain 'Sk/Ln/Se/Sp' crowding).

Overrides live in build/wtd_sizes.json:  {"0x<text len-byte offset>": [sizeX, sizeY], ...}
(the same hex offsets the worksheet uses). Applied AFTER wtd_tool apply, offset-preserving
(8 bytes overwritten in place). Refuses any record without the marker pattern or with an
implausible original size (guards against false matches on non-text records).

    python tools/wtd_sizes.py <in.wtd> <out.wtd> [sizes.json]
"""
import json, os, struct, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def size_fields(w, off, expect_len=None):
    """(pos, sizeX, sizeY) for the text record whose length byte is at `off`, else None.

    The size floats always sit at off-15 and off-11. What lies between them and the text
    does NOT: most records carry the marker 8c a0 00 xx / 00 00 00, but others carry
    00 00 60 00 02, or plain zeroes. Demanding the marker silently refused those, which
    is how 5 of the 11 "Stats" labels kept overrunning after being "fixed".

    So the marker is now one of two ways to be sure. The other, stronger, is the LENGTH
    BYTE: `expect_len` is what the worksheet says this string measures, and the byte at
    `off` must equal it. That identifies the record without assuming any layout. A caller
    that cannot supply it still gets the old strict marker behaviour."""
    if off < 16:
        return None
    marker_ok = (w[off - 7:off - 4] == b"\x8c\xa0\x00" and w[off - 3:off] == b"\x00\x00\x00")
    if not (marker_ok or (expect_len is not None and w[off] == expect_len)):
        return None
    sx = struct.unpack(">f", w[off - 15:off - 11])[0]
    sy = struct.unpack(">f", w[off - 11:off - 7])[0]
    if not (6.0 <= sx <= 60.0 and 6.0 <= sy <= 60.0):
        return None
    return off - 15, sx, sy


def apply(w, sizes, lengths=None):
    """`lengths` maps the same hex keys to each string's byte length, from the worksheet,
    so a record can be identified by its length byte when its marker bytes differ."""
    d = bytearray(w); ok = 0; refused = []
    for k, (sx, sy) in sizes.items():
        off = int(k, 16)
        r = size_fields(d, off, (lengths or {}).get(k))
        if r is None:
            refused.append(k); continue
        pos = r[0]
        struct.pack_into(">f", d, pos, float(sx))
        struct.pack_into(">f", d, pos + 4, float(sy))
        ok += 1
    return bytes(d), ok, refused


def main():
    inp, outp = sys.argv[1], sys.argv[2]
    sp = sys.argv[3] if len(sys.argv) > 3 else os.path.join(REPO, "build", "wtd_sizes.json")
    sizes = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    w = open(inp, "rb").read()
    # the worksheet gives each record's JP length, which anchors records whose marker
    # bytes differ from the common layout
    lengths = {}
    wsp = os.path.join(REPO, "build", "worksheets", "General2d", "Dat", "Window",
                       "WindowToolData", "windowdataMain.wtd.json")
    if os.path.exists(wsp):
        for k, v in json.load(open(wsp, encoding="utf-8")).items():
            jp = v.get("jp") if isinstance(v, dict) else None
            if jp:
                lengths[k] = len(jp.encode("utf-8")) + 1
    out, ok, refused = apply(w, sizes, lengths)
    assert len(out) == len(w)
    open(outp, "wb").write(out)
    print(f"wtd_sizes: applied {ok}/{len(sizes)} size overrides -> {outp}"
          + (f"  REFUSED {refused}" if refused else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
