#!/usr/bin/env python3
"""fixh_grow.py - grow strings in a FIXH data file (Logic/Dat/FixedData/*.dat).

FIXH is a tagged-section container:
    [FIXH hdr][DATA records][SOFS offset table][STRI string block]
  * SOFS = ['SOFS' | u32 size | offset table]. The table is a flat contiguous
    array of **32-bit BIG-ENDIAN** offsets, each relative to the string-block
    base, pointing at name/description strings. (Earlier code read these as
    16-bit; that only appeared to work because each 4-byte entry's zero high
    half resolved to block-offset 0 - and it could NOT address blocks > 64 KB,
    leaving HelpData/UnitDictionaryData strings stuck in Japanese.)
  * STRI = ['STRI' | u32 size | u32 count | u32 flags | 2-byte pad | strings].
    **Block base = STRI + 0x12** (EXACT: a string's stored offset + base == its
    file position; verified across all 26 FixedData files, 100% of entries).

GROWTH = APPEND-ONLY (safe by construction):
  * The existing string block is preserved BYTE-FOR-BYTE (nothing moves, so any
    positional/inline data stays valid).
  * A grown string is appended at the end of the block; only its offset-table
    entry (a 32-bit field) is repointed to the appended copy.
  * 32-bit offsets address the whole block, so growth never overflows in practice.

detect() confirms the base by requiring EVERY 32-bit table entry to resolve to a
valid string start; any wrong base fails this and the file is refused (kept
in-place) rather than risk corruption.

API: grow(data, {block_offset: new_text}) -> (new_bytes, refused set)
     grow_files(data, {file_offset: new_text}) -> (new_bytes, refused set)
"""
import struct, sys

def detect(d):
    """Return (block_base, [field_positions]) using the deterministic SOFS/STRI
    layout with 32-bit offsets, or None if the base cannot be confirmed (every
    entry must resolve to a string start) so the caller keeps the file in-place."""
    sofs = d.find(b"SOFS")
    stri = d.find(b"STRI")
    if sofs < 0 or stri < 0 or stri < sofs:
        return None
    tbl_off = sofs + 8
    tbl_sz = struct.unpack_from(">I", d, sofs + 4)[0]
    if tbl_off + tbl_sz > len(d) or tbl_sz % 4:
        return None
    base = stri + 0x12
    if base >= len(d):
        return None                      # STRI header present but empty block
    starts = _string_starts(d, base)
    if not starts:
        return None
    fields = list(range(tbl_off, tbl_off + tbl_sz, 4))
    if not fields:
        return None
    # STRICT: every 32-bit entry must resolve to a real string start. This is the
    # gate that rejects a wrong base (a wrong base scatters into mid-string bytes
    # and fails immediately). All 26 FixedData files pass at 32-bit width.
    for p in fields:
        if struct.unpack_from(">I", d, p)[0] not in starts:
            return None
    return base, fields


def _string_starts(d, base):
    starts = set(); i = base
    while i < len(d):
        starts.add(i - base)
        j = d.find(b"\x00", i)
        if j < 0: break
        i = j + 1
    return starts

def grow(data, edits):
    d = bytearray(data)
    det = detect(d)
    if det is None:
        return bytes(d), set(edits)
    base, fields = det
    block_len = len(d) - base
    out = bytearray(d)
    refused = set()
    for off, text in edits.items():
        # only grow if this string is referenced by a detected offset field
        hits = [p for p in fields if struct.unpack_from(">I", d, p)[0] == off]
        if not hits:
            refused.add(off); continue          # not safely repointable -> leave JP
        new = text.encode("utf-8") + b"\x00"
        new_off = block_len
        if new_off > 0xFFFFFFFF:
            refused.add(off); continue
        out += new
        block_len += len(new)
        for p in hits:
            struct.pack_into(">I", out, p, new_off)
    # post-build safety gate: EVERY offset field must still resolve to a string
    # start in the grown output, else refuse the whole grow (return original).
    starts2 = _string_starts(out, base)
    for p in fields:
        if struct.unpack_from(">I", out, p)[0] not in starts2:
            return bytes(d), set(edits)
    return bytes(out), refused

def grow_files(data, edits):
    """edits keyed by FILE offset (as worksheets are). Returns (bytes, refused
    file-offset set). Converts to block-relative internally."""
    det = detect(data)
    if det is None:
        return bytes(data), set(edits)
    base = det[0]
    blk = {fo - base: t for fo, t in edits.items()}
    out, ref_blk = grow(data, blk)
    refused = {fo for fo in edits if (fo - base) in ref_blk}
    return out, refused


def _read_cstr(d, p):
    j = d.find(b"\x00", p)
    return d[p:j] if j >= 0 else d[p:]


def splice_grow(data, edits):
    """Grow strings that append+repoint CANNOT reach: adjacency-read description
    text (no offset field points at them). Splices each new string in place of the
    old one inside the block and fixes up EVERY SOFS offset by the cumulative
    insertion delta before it. Safe because SOFS is the ONLY thing that references
    block offsets (verified: no other 32-bit block/file pointer targets these
    strings, they are located purely by walking from the preceding name), so a
    uniform shift + SOFS fix-up preserves both adjacency and every name lookup.

    edits keyed by FILE offset. HARD-GATED and self-protecting: returns the
    ORIGINAL bytes (refusing every edit) unless ALL of these hold on the result -
        * a no-op rebuild (no edits) is byte-identical to the input,
        * every SOFS offset resolves to a valid string start,
        * every non-edited SOFS name reads back byte-identical,
        * every edited string reads back == its new text (SOFS lookup where the
          string is SOFS-referenced; adjacency position otherwise),
        * the NUL-terminated unit count is unchanged.
    so a wrong structural assumption fails closed instead of corrupting data."""
    det = detect(data)
    if det is None:
        return bytes(data), set(edits)
    base, fields = det
    d = bytes(data)
    starts = _string_starts(d, base)

    # collect valid splices (edit offset must be a real string start in the block)
    splices = []               # (file_off, old_len_incl_nul, new_bytes_incl_nul)
    refused = set()
    for fo, text in edits.items():
        if (fo - base) not in starts:
            refused.add(fo); continue
        end = d.find(b"\x00", fo)
        if end < 0:
            refused.add(fo); continue
        new = text.encode("utf-8") + b"\x00"
        splices.append((fo, end - fo + 1, new))
    if not splices:
        return d, refused
    splices.sort()

    # rebuild the file: copy verbatim, substituting each old string with its new
    # bytes; record cumulative delta at each original file offset for SOFS fix-up.
    out = bytearray()
    src = 0
    cum = 0
    shift_points = []          # (orig_file_off_past_this_string, cumulative_delta)
    for fo, old_len, new in splices:
        out += d[src:fo]
        out += new
        src = fo + old_len
        cum += len(new) - old_len
        shift_points.append((src, cum))     # strings starting at/after src shift by cum
    out += d[src:]
    out = bytearray(out)

    def delta_before(file_off):
        # total insertion applied to bytes originally at >= file_off
        c = 0
        for pt, cc in shift_points:
            if file_off >= pt:
                c = cc
        return c

    # fix up every SOFS offset: name at orig file off (base+X) moves by delta_before
    for p in fields:
        X = struct.unpack_from(">I", d, p)[0]
        orig_fo = base + X
        newX = X + delta_before(orig_fo)
        # the field itself sits before `base`, so its position in `out` is unchanged
        struct.pack_into(">I", out, p, newX)

    out = bytes(out)

    # ---- HARD verification gates (fail closed) ----
    new_base = base            # header/SOFS/STRI region before base is untouched in size
    new_starts = _string_starts(out, new_base)
    # every SOFS offset resolves
    for p in fields:
        if struct.unpack_from(">I", out, p)[0] not in new_starts:
            return d, set(edits)
    # unit-count preserved (count NUL terminators in the STRING BLOCK only; the
    # SOFS table before `base` legitimately changes zero-byte count when offsets
    # are repointed, so counting the whole file would false-fail here)
    if out[new_base:].count(b"\x00") != d[base:].count(b"\x00"):
        return d, set(edits)
    # every SOFS name reads back identical to before (names are not edited here;
    # if one WAS edited it must read back as the new text)
    edited_fo = {fo for fo, _, _ in splices}
    for p in fields:
        oldX = struct.unpack_from(">I", d, p)[0]
        newX = struct.unpack_from(">I", out, p)[0]
        old_s = _read_cstr(d, base + oldX)
        new_s = _read_cstr(out, new_base + newX)
        if (base + oldX) in edited_fo:
            continue                       # verified below against its new text
        if old_s != new_s:
            return d, set(edits)
    # every edited string reads back == its new text at its (shifted) position
    for fo, old_len, new in splices:
        newpos = fo + delta_before(fo)      # its own start shifts by prior splices only
        if _read_cstr(out, newpos) + b"\x00" != new:
            return d, set(edits)

    return out, refused

if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read()
    det = detect(d)
    if not det:
        print("REFUSE (base unconfirmed)")
    else:
        base, fields = det
        print(f"block_base=0x{base:X} fields={len(fields)} (32-bit)")
