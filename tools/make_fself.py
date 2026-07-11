#!/usr/bin/env python3
"""make_fself.py - pure-Python fake-signed SELF (fSELF) wrapper for a PS3 EBOOT.

Ports PSL1GHT's make_fself.py (phiren) to Python 3, self-contained (no external
Struct dependency). Wraps a plaintext PPC64 ELF into an unsigned / "fake" SELF
(key_revision 0x8000) that RPCS3 boots directly - no real Sony keys involved.

The layout it produces places the appended ELF at file offset 0x90, identical to
the way a retail EBOOT.BIN is laid out, and points each segment's section-info
entry at (elfOffset + phdr.offset) so RPCS3's SELFDecrypter copies the plaintext
segment bytes straight out.

Usage:
    make_fself.py input.elf [output]      # default output EBOOT.BIN
"""
import sys, struct

# --- struct sizes (all big-endian) ---
SELFHDR_LEN  = 0x68   # sce_hdr(0x20) + ext_hdr(0x48)
APPINFO_LEN  = 0x18
EHDR_LEN     = 0x40   # Elf64_Ehdr
PHDR_LEN     = 0x38   # Elf64_Phdr
SECINFO_LEN  = 0x20   # per-segment section/phdr-offset entry
DIGEST_LEN   = 0xC0   # control info blob


def align_up(v, a):
    r = v % a
    return v if r == 0 else v + (a - r)


def pad_to(v, a):
    r = v % a
    return b"" if r == 0 else b"\x00" * (a - r)


def read_elf(fn):
    with open(fn, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF":
        raise SystemExit("not an ELF: %s" % fn)
    if data[4] != 2 or data[5] != 2:
        raise SystemExit("expected 64-bit big-endian ELF (PS3 PPC64)")
    (_e_type, _e_machine, _e_version, _e_entry, e_phoff, e_shoff,
     _e_flags, _e_ehsize, _e_phentsize, e_phnum, _e_shentsize, _e_shnum,
     _e_shstrndx) = struct.unpack_from(">HHIQQQIHHHHHH", data, 16)
    phdrs = []
    off = e_phoff
    for _ in range(e_phnum):
        ph = struct.unpack_from(">IIQQQQQQ", data, off)  # type,flags,off,vaddr,paddr,filesz,memsz,align
        phdrs.append(ph)
        off += PHDR_LEN
    return data, e_shoff, e_phoff, e_phnum


def build_appinfo():
    return struct.pack(">QIIQ",
                       0x1010000001000003,  # authid
                       0x1000002,           # vendor_id
                       0x4,                 # self_type (APP)
                       0x0001000000000000)  # version


def build_digest():
    magic_bits = bytes([0x62, 0x7c, 0xb1, 0x80, 0x8a, 0xb9, 0x38, 0xe3, 0x2c, 0x8c,
                        0x09, 0x17, 0x08, 0x72, 0x6a, 0x57, 0x9e, 0x25, 0x86, 0xe4])
    file_sha1 = bytes([0x42, 0x69, 0x74, 0x65, 0x20, 0x4d, 0x65, 0x2c, 0x20, 0x53,
                       0x6f, 0x6e, 0x79, 0x00, 0xde, 0x07])
    # control info entry 1: ELF digest (type 2)
    blob  = struct.pack(">IIQ", 2, 0x40, 1)
    blob += magic_bits + b"\x00" * 0x14 + b"\x00" * 0x08
    # control info entry 2: NPDRM (type 3)
    blob += struct.pack(">IIQ", 3, 0x90, 0)
    blob += struct.pack(">IIII", 0x4e504400, 1, 2, 1)  # 'NPD\0', ver, drmType, unk
    blob += bytes([0x30] * 0x2f + [0x00])              # contentID
    blob += file_sha1
    blob += b"\xaa" * 0x10                             # notSHA1
    blob += bytes([0x00] * 0x0f + [0x01])             # notXORKLSHA1
    assert len(blob) == DIGEST_LEN, len(blob)
    return blob


def create_fself(elf_fn, out_fn="EBOOT.BIN"):
    data, shoff, phoff, phnum = read_elf(elf_fn)

    appinfo_off   = align_up(SELFHDR_LEN, 0x10)                 # 0x70
    elf_off_hdr   = align_up(appinfo_off + APPINFO_LEN, 0x10)   # 0x90 (ehdr copy)
    phdr_off_hdr  = elf_off_hdr + EHDR_LEN                      # 0xD0
    secinfo_start = phdr_off_hdr + PHDR_LEN * phnum
    secinfo_off   = align_up(secinfo_start, 0x10)
    digest_start  = secinfo_off + SECINFO_LEN * phnum
    digest_off    = align_up(digest_start, 0x10)
    end_of_header = digest_off + DIGEST_LEN
    elf_offset    = align_up(end_of_header, 0x80)               # where full ELF is appended

    # --- SELF header (sce_hdr + ext_hdr) ---
    header = struct.pack(">IIHHI" + "Q" * 11,
                         0x53434500,          # magic 'SCE\0'
                         2,                   # header version
                         0x8000,              # key_revision -> FAKE
                         1,                   # header type = SELF
                         end_of_header - 0x10,  # metadata offset
                         elf_offset,          # header size
                         len(data),           # encrypted (== plaintext) size
                         3,                   # unknown
                         appinfo_off,
                         elf_off_hdr,
                         phdr_off_hdr,
                         elf_offset + shoff,  # shdr (inside appended elf)
                         secinfo_off,
                         0,                   # sce version
                         digest_off,
                         DIGEST_LEN)

    # --- per-segment section info (points into appended elf) ---
    secinfo = b""
    off = phoff
    for _ in range(phnum):
        ptype, _flags, poff, _va, _pa, filesz, _memsz, _align = \
            struct.unpack_from(">IIQQQQQQ", data, off)
        off += PHDR_LEN
        unk4 = 2 if ptype == 1 else 0   # PT_LOAD
        secinfo += struct.pack(">QQIIII", elf_offset + poff, filesz, 1, 0, 0, unk4)

    out = bytearray()
    out += header;                       out += pad_to(len(out), 0x10)
    out += build_appinfo();              out += pad_to(len(out), 0x10)
    out += data[0:EHDR_LEN]              # exact ehdr copy
    out += data[phoff:phoff + PHDR_LEN * phnum]  # exact phdr copies
    out += pad_to(len(out), 0x10)
    out += secinfo
    out += pad_to(len(out), 0x10)
    out += build_digest()
    out += pad_to(len(out), 0x80)
    assert len(out) == elf_offset, (len(out), elf_offset)
    out += data                          # full plaintext ELF

    with open(out_fn, "wb") as f:
        f.write(out)
    print("wrote %s (%d bytes); elf at 0x%X, %d phdrs, entry inside appended elf" %
          (out_fn, len(out), elf_offset, phnum))
    return bytes(out)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        create_fself(sys.argv[1])
    elif len(sys.argv) == 3:
        create_fself(sys.argv[1], sys.argv[2])
    else:
        print("usage: make_fself.py input.elf [output=EBOOT.BIN]")
        sys.exit(1)
