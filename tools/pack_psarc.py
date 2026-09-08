#!/usr/bin/env python3
"""
Sony PSARC (v1.4, zlib) repacker -- inverse of tools/extract_psarc.py.

Rebuilds an archive from a directory of loose files plus the ORIGINAL archive
(used for the exact file order / manifest bytes / header params). Sony's PSARC used
zlib level 9, which Python's zlib reproduces byte-for-byte, so repacking an unmodified
tree yields a BYTE-IDENTICAL archive -- the correctness gate (`verify`). When files
change, only their blocks differ; the structure is rebuilt faithfully.

PSARC layout (big-endian):
  0x00 "PSAR" ; 0x04 ver(1,4) ; 0x08 "zlib" ; 0x0C toc_length ; 0x10 entry_size(30)
  0x14 num_files ; 0x18 block_size(0x10000) ; 0x1C archive_flags
  TOC: num_files * 30  = md5[16] · block_index(u32) · uncompressed_size(40b) · offset(40b)
  block-size table: ceil(log256(block_size)) bytes/entry (2 here); 0 => full block
  data: each file's blocks back-to-back, file 0 = manifest (newline-separated names)

Per block: zlib level-9 compress; if the compressed size < the raw chunk size, store
compressed, else store the raw chunk. Block-table entry = stored length, except a
full-size raw block (== block_size) is recorded as 0.

CLI:
  python tools/pack_psarc.py verify <orig.psarc> <extracted_dir>
  python tools/pack_psarc.py pack   <orig.psarc> <dir> <out.psarc>
"""
import struct, sys, os, zlib

def u32(d, o): return struct.unpack(">I", d[o:o+4])[0]
def u40(v):    return v.to_bytes(5, "big")

def read_header(d):
    assert d[:4] == b"PSAR", "not PSARC"
    return dict(ver=(u32(d,4)>>16, u32(d,4)&0xFFFF), comp=d[8:12],
               toc_length=u32(d,0x0C), entry_size=u32(d,0x10),
               num_files=u32(d,0x14), block_size=u32(d,0x18), flags=u32(d,0x1C))

def parse(d):
    h = read_header(d)
    n, esz, bs = h["num_files"], h["entry_size"], h["block_size"]
    entries = []
    for i in range(n):
        o = 0x20 + i*esz
        entries.append(dict(md5=d[o:o+16], bidx=u32(d,o+16),
                            unc=int.from_bytes(d[o+20:o+25],"big"),
                            off=int.from_bytes(d[o+25:o+30],"big")))
    bnum = 1; nn = bs
    while nn > 0x100: nn >>= 8; bnum += 1
    bt_off = 0x20 + n*esz
    bt_raw = d[bt_off:h["toc_length"]]
    btab = [int.from_bytes(bt_raw[i*bnum:(i+1)*bnum],"big")
            for i in range(len(bt_raw)//bnum)]
    return h, entries, btab, bnum

def read_file(d, entries, btab, bs, idx):
    e = entries[idx]; out = bytearray(); cur = e["off"]; bi = e["bidx"]
    while len(out) < e["unc"]:
        sz = btab[bi]; bi += 1
        if sz == 0:
            out += d[cur:cur+bs]; cur += bs
        else:
            chunk = d[cur:cur+sz]; cur += sz
            if chunk[:1] == b"\x78":
                try: out += zlib.decompress(chunk)
                except zlib.error: out += chunk
            else:
                out += chunk
    return bytes(out[:e["unc"]])

def manifest_names(d, entries, btab, bs):
    return [ln.strip() for ln in
            read_file(d, entries, btab, bs, 0).decode("ascii","replace").splitlines()
            if ln.strip()]

def compress_block(raw, bs, force_raw=False):
    """Return (stored_bytes, table_value) for one block. force_raw stores it
    uncompressed even if zlib could shrink it (some files were packed that way)."""
    if len(raw) == 0:
        return b"", 0
    if not force_raw:
        c = zlib.compress(raw, 9)
        if len(c) < len(raw):
            return c, len(c)
    # store raw; full block -> table 0, else its length
    return raw, (0 if len(raw) == bs else len(raw))

def _orig_force_raw(h, entries, btab, bs):
    """Return a set of file indices the original stored fully uncompressed
    (stored size == uncompressed size <=> every block raw)."""
    import math
    force = set()
    for i, e in enumerate(entries):
        if e["unc"] == 0:
            continue
        nblk = math.ceil(e["unc"] / bs)
        stored = sum(bs if btab[e["bidx"]+j] == 0 else btab[e["bidx"]+j]
                     for j in range(nblk))
        if stored == e["unc"]:
            force.add(i)
    return force

def pack(orig_psarc, src_dir, file_bytes=None):
    """Rebuild the archive. file_bytes: optional {name: bytes} overrides for files
    read from disk (names as in the manifest). Returns the new archive bytes."""
    d = open(orig_psarc, "rb").read()
    h, entries, btab, bnum = parse(d)
    bs, n = h["block_size"], h["num_files"]
    names = manifest_names(d, entries, btab, bs)
    assert len(names) == n-1, f"manifest {len(names)} != files {n-1}"

    # gather each data file's bytes (file 0 = manifest, reproduced exactly)
    contents = [read_file(d, entries, btab, bs, 0)]            # file 0 manifest, verbatim
    for i, name in enumerate(names, start=1):
        if file_bytes and name in file_bytes:
            contents.append(file_bytes[name])
        else:
            with open(os.path.join(src_dir, name.lstrip("/")), "rb") as f:
                contents.append(f.read())

    # build block stream + per-file (block_index, uncompressed_size, offset_rel).
    # PSARC deduplicates identical files: a repeated content reuses the first
    # occurrence's blocks (its block_index + offset), emitting no new blocks.
    force_raw = _orig_force_raw(h, entries, btab, bs)
    new_btab = []; data = bytearray(); meta = []
    seen = {}                                   # content bytes -> (bidx, off_rel)
    for fi, raw in enumerate(contents):
        if raw in seen and len(raw) > 0:
            bidx, off_rel = seen[raw]
            meta.append((bidx, len(raw), off_rel))
            continue
        bidx = len(new_btab); off_rel = len(data)
        fr = (fi in force_raw)
        for p in range(0, len(raw), bs):
            stored, tval = compress_block(raw[p:p+bs], bs, force_raw=fr)
            new_btab.append(tval); data += stored
        if len(raw) > 0:
            seen[raw] = (bidx, off_rel)
        meta.append((bidx, len(raw), off_rel))

    # assemble header + TOC + block table
    toc_length = 0x20 + n*30 + len(new_btab)*bnum
    out = bytearray()
    out += b"PSAR" + struct.pack(">HH", *h["ver"]) + h["comp"]
    out += struct.pack(">IIIII", toc_length, 30, n, bs, h["flags"])
    for i in range(n):
        bidx, unc, off_rel = meta[i]
        out += entries[i]["md5"]
        out += struct.pack(">I", bidx) + u40(unc) + u40(toc_length + off_rel)
    for v in new_btab:
        out += v.to_bytes(bnum, "big")
    assert len(out) == toc_length, (len(out), toc_length)
    out += data
    return bytes(out)

def functional_check(orig_bytes, out_bytes):
    """Extract every file from both archives and confirm they are identical.
    This is the correctness gate: the repack must contain exactly the same files."""
    ho, eo, bo, _ = parse(orig_bytes)
    hn, en, bn, _ = parse(out_bytes)
    if ho["num_files"] != hn["num_files"]:
        return False, f"file count {ho['num_files']} != {hn['num_files']}"
    for i in range(ho["num_files"]):
        a = read_file(orig_bytes, eo, bo, ho["block_size"], i)
        b = read_file(out_bytes, en, bn, hn["block_size"], i)
        if a != b:
            return False, f"file {i} differs ({len(a)} vs {len(b)} bytes)"
    return True, f"{ho['num_files']} files all identical"

def cmd_verify(orig, src_dir):
    orig_bytes = open(orig, "rb").read()
    out = pack(orig, src_dir)
    exact = (out == orig_bytes)
    ok, msg = functional_check(orig_bytes, out)
    tag = "BYTE-IDENTICAL" if exact else f"size {len(out)} vs {len(orig_bytes)} (Δ{len(out)-len(orig_bytes)})"
    print(f"repack({src_dir}): {tag}")
    print(f"functional (extract(repack) == extract(orig)): {'PASS' if ok else 'FAIL'} - {msg}")
    if not exact and not ok:
        n = min(len(out), len(orig_bytes))
        k = next((i for i in range(n) if out[i] != orig_bytes[i]), n)
        print(f"  first byte diff at 0x{k:X}: out {out[k:k+12].hex()} / orig {orig_bytes[k:k+12].hex()}")
    return 0 if ok else 1

def cmd_pack(orig, src_dir, outp):
    out = pack(orig, src_dir)
    open(outp, "wb").write(out)
    print(f"wrote {outp} ({len(out)} bytes)")

if __name__ == "__main__":
    if len(sys.argv) < 4: print(__doc__); sys.exit(1)
    if   sys.argv[1] == "verify": sys.exit(cmd_verify(sys.argv[2], sys.argv[3]))
    elif sys.argv[1] == "pack":   cmd_pack(sys.argv[2], sys.argv[3], sys.argv[4])
    else: print("unknown cmd"); sys.exit(1)
