#!/usr/bin/env python3
"""fix_landinfo.py - write the map terrain names into General3d's landinfo.mti.

WHY THIS EXISTS. landinfo.mti is a table of 84-byte records whose first 64 bytes are the
terrain name. The generic reinserter sizes every slot as "bytes up to the next NUL",
which for a 13-byte Japanese name means 13 bytes of room even though 64 are reserved and
the remaining 51 are already zero. English names are longer than their Japanese
originals, so 96 of the 300 were refused and left in Japanese.

The name FIELD is the real capacity. Writing name + NUL padding to exactly 64 bytes is
offset-preserving, keeps the 84-byte stride intact, and lets every name through.

    python tools/fix_landinfo.py            # build/en/... <- work/... + worksheet
    python tools/fix_landinfo.py --check    # report only, write nothing
"""
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = os.path.join("Dat", "Map", "MapLandInfo", "landinfo.mti")
JP = os.path.join(REPO, "work", "General3d", REL)
WS = os.path.join(REPO, "build", "worksheets", "General3d", REL + ".json")
EN = os.path.join(REPO, "build", "en", "General3d", REL)
NAME_FIELD = 64          # bytes reserved for the name at the start of each record
STRIDE = 84              # record size


def main():
    check = "--check" in sys.argv
    jp = bytearray(open(JP, "rb").read())
    ws = json.load(open(WS, encoding="utf-8"))

    offs = sorted(int(k, 16) for k in ws)
    # every name must sit on the record grid, or the field assumption is wrong
    base = offs[0]
    bad_grid = [o for o in offs if (o - base) % STRIDE]
    if bad_grid:
        sys.exit("offsets are not on the %d-byte record grid (%d bad): %s"
                 % (STRIDE, len(bad_grid), [hex(o) for o in bad_grid[:5]]))

    written = over = skipped = 0
    for k in ws:
        off = int(k, 16)
        en = (ws[k].get("en") or "").strip()
        if not en:
            skipped += 1
            continue
        nb = en.encode("utf-8")
        if len(nb) > NAME_FIELD - 1:
            print("  TOO LONG (%d > %d), left in Japanese: %s" % (len(nb), NAME_FIELD - 1, en))
            over += 1
            continue
        # the field must really be free: everything after the JP name up to the field end
        # is expected to be padding already
        end = jp.find(b"\x00", off)
        tail = jp[end:off + NAME_FIELD]
        if any(tail):
            print("  NOT PADDING after %s, refusing to overwrite: %r" % (k, bytes(tail[:16])))
            over += 1
            continue
        jp[off:off + NAME_FIELD] = nb + b"\x00" * (NAME_FIELD - len(nb))
        written += 1

    print("landinfo: wrote %d name(s), %d too long/unsafe, %d untranslated" % (written, over, skipped))
    if check:
        return 0
    os.makedirs(os.path.dirname(EN), exist_ok=True)
    assert len(jp) == os.path.getsize(JP), "size changed; this must be offset-preserving"
    open(EN, "wb").write(bytes(jp))
    print("  -> %s (%d bytes, unchanged)" % (os.path.relpath(EN, REPO), len(jp)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
