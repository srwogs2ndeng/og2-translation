#!/usr/bin/env python3
"""repack_override.py - fast PSARC repack that changes only a few files.

pack_psarc.pack() recompresses every block and needs the whole archive extracted
to disk. For a huge archive (General2d = 638 MB, 5961 files) where we override a
single file (windowdataMain.wtd), that is wasteful and slow.

This repacker keeps EVERY original compressed block verbatim and only:
  * compresses the overridden file's new bytes into fresh blocks appended at the
    end of the data region,
  * repoints that file's TOC entry (bidx/unc/off) to the appended blocks,
  * shifts every entry's absolute offset by the TOC-growth delta (adding block-
    table rows grows toc_length, which moves the whole data region).
The overridden file's old blocks become orphaned slack (tiny) - harmless.

Result is byte-for-byte identical to the original for every unchanged file, so
there is no recompression risk and no need to extract the archive.

API: repack_override(orig_psarc_path, {manifest_name: new_bytes}) -> bytes
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack_psarc as PK


def _file_block_span(entries, btab, bs, i):
    """(nblocks, stored_byte_len) for file i from its block-table run."""
    unc = entries[i]["unc"]
    nblk = (unc + bs - 1) // bs if unc else 0
    bidx = entries[i]["bidx"]
    stored = 0
    for k in range(nblk):
        sz = btab[bidx + k]
        stored += sz if sz != 0 else bs
    return nblk, stored


def repack_override(orig_psarc, overrides):
    d = open(orig_psarc, "rb").read()
    h, entries, btab, bnum = PK.parse(d)
    bs, n = h["block_size"], h["num_files"]
    names = PK.manifest_names(d, entries, btab, bs)          # names for files 1..n-1
    name_to_idx = {nm: i + 1 for i, nm in enumerate(names)}

    old_toc = h["toc_length"]
    new_btab = list(btab)
    appended = bytearray()                                    # new blocks, after old data
    old_data_len = len(d) - old_toc

    # plan overrides: append their new blocks, remember (i, new_bidx, new_unc, new_off_in_appended)
    plan = {}
    for name, raw in overrides.items():
        if name not in name_to_idx:
            raise KeyError(f"{name} not in archive manifest")
        i = name_to_idx[name]
        new_bidx = len(new_btab)
        off_in_app = len(appended)
        force_raw = i in PK._orig_force_raw(h, entries, btab, bs)
        if raw:
            for p in range(0, len(raw), bs):
                stored, tval = PK.compress_block(raw[p:p+bs], bs, force_raw=force_raw)
                new_btab.append(tval); appended += stored
        plan[i] = (new_bidx, len(raw), off_in_app)

    # new TOC length (grew by the appended block-table rows), hence offset delta
    new_toc = 0x20 + n * 30 + len(new_btab) * bnum
    delta = new_toc - old_toc
    new_data_len = old_data_len + len(appended)

    out = bytearray()
    out += b"PSAR" + struct.pack(">HH", *h["ver"]) + h["comp"]
    out += struct.pack(">IIIII", new_toc, 30, n, bs, h["flags"])
    for i in range(n):
        e = entries[i]
        if i in plan:
            nb, unc, off_app = plan[i]
            bidx, off_abs = nb, new_toc + old_data_len + off_app
        else:
            bidx, unc = e["bidx"], e["unc"]
            off_abs = e["off"] + delta                       # data region shifted by delta
        out += e["md5"] + struct.pack(">I", bidx) + PK.u40(unc) + PK.u40(off_abs)
    for v in new_btab:
        out += v.to_bytes(bnum, "big")
    assert len(out) == new_toc, (len(out), new_toc)
    out += d[old_toc:]                                        # all original blocks verbatim
    out += appended                                          # then the overridden file's blocks
    assert len(out) == new_toc + new_data_len
    return bytes(out)


if __name__ == "__main__":
    orig, name, newfile, outp = sys.argv[1:5]
    ov = {name: open(newfile, "rb").read()}
    open(outp, "wb").write(repack_override(orig, ov))
    print(f"wrote {outp}")
