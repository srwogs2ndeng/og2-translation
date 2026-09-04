#!/usr/bin/env python3
# Minimal Sony PSARC (v1.4, zlib) extractor. Reads the manifest (file 0) for names.
import struct, sys, os, zlib

def u40(b):  # 40-bit big-endian
    return int.from_bytes(b, "big")

def extract(psarc_path, out_dir, list_only=False):
    f = open(psarc_path, "rb")
    hdr = f.read(32)
    assert hdr[:4] == b"PSAR", "not a PSARC"
    comp = hdr[8:12]
    toc_length    = struct.unpack(">I", hdr[0x0C:0x10])[0]
    entry_size    = struct.unpack(">I", hdr[0x10:0x14])[0]
    num_files     = struct.unpack(">I", hdr[0x14:0x18])[0]
    block_size    = struct.unpack(">I", hdr[0x18:0x1C])[0]
    print(f"compression={comp} files={num_files} entry_size={entry_size} "
          f"block_size=0x{block_size:X} toc_len=0x{toc_length:X}")
    assert comp == b"zlib" and entry_size == 30

    entries = []
    for _ in range(num_files):
        e = f.read(30)
        md5 = e[0:16]
        block_index = struct.unpack(">I", e[16:20])[0]
        unc_size = u40(e[20:25])
        offset   = u40(e[25:30])
        entries.append((md5, block_index, unc_size, offset))

    # block-size table fills the rest of the TOC; 2 bytes/entry for block_size 0x10000
    bnum = 1
    n = block_size
    while n > 0x100:
        n >>= 8; bnum += 1
    btable_bytes = toc_length - f.tell()
    nblocks = btable_bytes // bnum
    bt_raw = f.read(btable_bytes)
    block_table = [int.from_bytes(bt_raw[i*bnum:(i+1)*bnum], "big") for i in range(nblocks)]

    archive = open(psarc_path, "rb").read()

    def read_file(idx):
        _, bidx, unc, off = entries[idx]
        out = bytearray(); cur = off; bi = bidx
        while len(out) < unc:
            bs = block_table[bi]; bi += 1
            if bs == 0:
                chunk = archive[cur:cur+block_size]; cur += block_size
                out += chunk
            else:
                chunk = archive[cur:cur+bs]; cur += bs
                if chunk[:1] == b"\x78":
                    try: out += zlib.decompress(chunk)
                    except zlib.error: out += chunk
                else:
                    out += chunk
        return bytes(out[:unc])

    # file 0 = manifest (newline-separated paths for files 1..n)
    manifest = read_file(0).decode("ascii", "replace")
    names = [ln.strip() for ln in manifest.splitlines() if ln.strip()]
    print(f"manifest lists {len(names)} names for {num_files-1} data files")

    if list_only:
        from collections import Counter
        exts = Counter(os.path.splitext(n)[1].lower() for n in names)
        print("=== extension histogram ===")
        for ext, c in exts.most_common():
            print(f"  {ext or '(none)':12} {c}")
        print("=== first 40 names ===")
        for n in names[:40]:
            print("  ", n)
        return

    os.makedirs(out_dir, exist_ok=True)
    for i in range(1, num_files):
        name = names[i-1] if i-1 < len(names) else f"_unknown/{i:04d}.bin"
        dest = os.path.join(out_dir, name.lstrip("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as o:
            o.write(read_file(i))
    print(f"extracted {num_files-1} files -> {out_dir}")

if __name__ == "__main__":
    args = sys.argv[1:]
    list_only = "--list" in args
    args = [a for a in args if a != "--list"]
    extract(args[0], args[1] if len(args) > 1 else "out", list_only=list_only)
