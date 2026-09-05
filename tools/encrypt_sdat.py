#!/usr/bin/env python3
"""
SDAT re-encryptor -- inverse of tools/decrypt_sdat.py. Wraps a (modified) .psarc
back into a .psarc.sdat that RPCS3 loads.

Why this works without Sony's private keys (verified against RPCS3 unedat.cpp):
  * RPCS3 FATALLY enforces only the per-block hash (returns -1 -> refuses to load).
    For these files (NPD v4, flags 0x0100003C: SDAT | ENCRYPTED_KEY | 0x10 | 0x20 |
    0x04, not compressed) that hash is an HMAC-SHA1 over the *encrypted* block. We
    recompute it correctly (validated byte-for-byte against the real file).
  * The ECDSA metadata/header signatures and the metadata-section hash only emit
    warnings (non-fatal), so the stale originals are fine.
  * NPD header hashes: title_hash signs content_id+filename only (unchanged);
    dev_hash is skipped for SDAT (no klicensee). file_size/block_size are not signed.
  => Copy the 0x100-byte header verbatim, patch file_size, re-encrypt the blocks.

Per block i (flags 0x0100003C):
  b_key      = dev_hash[:0xC] + be32(i)
  key_result = AES-ECB-enc(crypt_key, b_key)            crypt_key = dev_hash ^ SDAT_KEY
  key_final  = AES-ECB-dec(EDAT_KEY_1, key_result)      (ENCRYPTED_KEY, EDAT_IV = 0)
  enc        = AES-CBC-enc(key_final, iv=digest, plaintext_padded_to_0x10)
  hash       = AES-ECB-enc(crypt_key, key_result)       (FLAG_0x10)
  hmac_key   = AES-ECB-dec(EDAT_KEY_1, hash) + 00*4     (0x14 bytes)
  test_hash  = HMAC-SHA1(hmac_key, enc)[:0x14]
  metadata   = (test_hash[:0x10]^mask) || mask , with mask[:4]=test_hash[0x10:0x14]
Layout: 0x100 header, then per block [0x20 metadata][block_size data].

To minimise the disc diff, blocks whose plaintext is unchanged from the original
.sdat are copied verbatim (byte-identical); only changed blocks are re-encrypted.

CLI:
  python tools/encrypt_sdat.py wrap   <orig.sdat> <new.psarc> <out.sdat>
  python tools/encrypt_sdat.py verify <orig.sdat>          # round-trip + HMAC validity
"""
import struct, sys, hmac, hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SDAT_KEY   = bytes([0x0D,0x65,0x5E,0xF8,0xE6,0x74,0xA9,0x8A,0xB8,0x50,0x5C,0xFA,0x7D,0x01,0x29,0x33])
EDAT_KEY_1 = bytes([0x4C,0xA9,0xC1,0x4B,0x01,0xC9,0x53,0x09,0x96,0x9B,0xEC,0x68,0xAA,0x0B,0xC0,0x81])

SDAT_FOOTER_V4 = b"SDATA 4.0.0.W\x00\x00\x00"   # plaintext trailer make_npdata appends

def ecb_enc(k,d): return Cipher(algorithms.AES(k),modes.ECB()).encryptor().update(d)
def ecb_dec(k,d): return Cipher(algorithms.AES(k),modes.ECB()).decryptor().update(d)
def cbc_enc(k,iv,d): return Cipher(algorithms.AES(k),modes.CBC(iv)).encryptor().update(d)
def cbc_dec(k,iv,d): return Cipher(algorithms.AES(k),modes.CBC(iv)).decryptor().update(d)
def xor(a,b): return bytes(x^y for x,y in zip(a,b))

class Sdat:
    def __init__(self, header_bytes):
        d = header_bytes
        assert d[:4] == b"NPD\x00", "not NPD/SDAT"
        self.version    = struct.unpack(">i", d[0x04:0x08])[0]
        self.digest     = d[0x40:0x50]
        self.dev_hash   = d[0x60:0x70]
        self.flags      = struct.unpack(">i", d[0x80:0x84])[0] & 0xFFFFFFFF
        self.block_size = struct.unpack(">i", d[0x84:0x88])[0]
        self.file_size  = struct.unpack(">Q", d[0x88:0x90])[0]
        self.header     = bytearray(d[:0x100])
        assert self.version == 4, "only NPD v4 handled"
        assert self.flags == 0x0100003C, f"unexpected flags 0x{self.flags:08X}"
        self.crypt_key  = xor(self.dev_hash, SDAT_KEY)

    # block region in the file for block i (metadata precedes data, FLAG_0x20)
    def _meta_off(self, i): return 0x100 + i*(0x20 + self.block_size)
    def _data_off(self, i): return self._meta_off(i) + 0x20

    def _keys(self, i):
        b_key = self.dev_hash[:0xC] + struct.pack(">I", i)
        key_result = ecb_enc(self.crypt_key, b_key)
        key_final  = ecb_dec(EDAT_KEY_1, key_result)            # ENCRYPTED_KEY, IV=0
        hsh        = ecb_enc(self.crypt_key, key_result)        # FLAG_0x10
        hmac_key   = ecb_dec(EDAT_KEY_1, hsh) + b"\x00"*4       # generate_hash, IV=0 -> 0x14
        return key_final, hmac_key

    def encrypt_block(self, i, plaintext):
        """Return (metadata[0x20], enc_data[aligned]) for one block."""
        key_final, hmac_key = self._keys(i)
        pad_len = len(plaintext)
        alen = (pad_len + 0xF) & ~0xF
        pt = plaintext + b"\x00"*(alen - pad_len)
        enc = cbc_enc(key_final, self.digest, pt)
        th = hmac.new(hmac_key, enc, hashlib.sha1).digest()     # 0x14
        mask = bytearray(0x10)
        mask[0:4] = th[0x10:0x14]                               # so decrypt recovers th[0x10:0x14]
        meta = bytes(xor(th[:0x10], mask)) + bytes(mask)        # decrypt: th0x10 = meta0^meta1
        return meta, enc

    def decrypt_block(self, raw, i):
        key_final, _ = self._keys(i)
        bs = self.block_size
        length = bs
        nblocks = (self.file_size + bs - 1)//bs
        if i == nblocks-1 and self.file_size % bs:
            length = self.file_size % bs
        alen = (length + 0xF) & ~0xF
        enc = raw[self._data_off(i):self._data_off(i)+alen]
        return cbc_dec(key_final, self.digest, enc)[:length]

def wrap(orig_sdat_path, new_psarc, out_path=None):
    """Re-wrap new_psarc bytes into an SDAT using orig_sdat's header/keys.
    Unchanged blocks are copied from the original verbatim."""
    raw = open(orig_sdat_path, "rb").read()
    s = Sdat(raw[:0x100])
    bs = s.block_size
    if isinstance(new_psarc, (str,)):
        new_psarc = open(new_psarc, "rb").read()
    new_size = len(new_psarc)
    nblocks = (new_size + bs - 1)//bs
    out = bytearray(s.header)
    struct.pack_into(">Q", out, 0x88, new_size)                 # patch file_size
    orig_nblocks = (s.file_size + bs - 1)//bs
    for i in range(nblocks):
        pt = new_psarc[i*bs:(i+1)*bs]
        unchanged = (i < orig_nblocks and pt == s.decrypt_block(raw, i))
        if unchanged:
            beg = s._meta_off(i)
            length = bs if not (i==orig_nblocks-1 and s.file_size%bs) else s.file_size%bs
            alen = (length + 0xF) & ~0xF
            out += raw[beg:beg+0x20+alen]                       # verbatim metadata+data
        else:
            meta, enc = s.encrypt_block(i, pt)
            out += meta + enc
    out += SDAT_FOOTER_V4                                       # plaintext trailer
    data = bytes(out)
    if out_path:
        open(out_path, "wb").write(data)
        print(f"wrote {out_path} ({len(data)} bytes, {nblocks} blocks, file_size=0x{new_size:X})")
    return data

def _rpcs3_block_hash_ok(s, sdat_bytes, i):
    """Replicate RPCS3's fatal per-block check: reconstruct test_hash from metadata
    and compare to HMAC-SHA1 over the encrypted block."""
    bs = s.block_size
    nblocks = (s.file_size + bs - 1)//bs
    length = bs if not (i==nblocks-1 and s.file_size%bs) else s.file_size%bs
    alen = (length + 0xF) & ~0xF
    meta = sdat_bytes[s._meta_off(i):s._meta_off(i)+0x20]
    enc  = sdat_bytes[s._data_off(i):s._data_off(i)+alen]
    th = bytearray(meta[:0x14])
    for j in range(0x10): th[j] = meta[j] ^ meta[j+0x10]
    _, hmac_key = s._keys(i)
    return hmac.new(hmac_key, enc, hashlib.sha1).digest() == bytes(th)

def cmd_verify(orig):
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
    import decrypt_sdat
    import tempfile, os
    raw = open(orig, "rb").read()
    s = Sdat(raw[:0x100])
    # decrypt original -> plaintext psarc
    tmp = tempfile.mktemp(suffix=".psarc")
    decrypt_sdat.decrypt_sdat(orig, tmp, verbose=False)
    psarc = open(tmp, "rb").read(); os.remove(tmp)
    # 1) re-wrap unchanged -> must be byte-identical to original sdat
    rewrapped = wrap(orig, psarc)
    exact = rewrapped == raw
    print(f"re-wrap unchanged == original .sdat : {'BYTE-IDENTICAL' if exact else f'DIFFERS (len {len(rewrapped)} vs {len(raw)})'}")
    # 2) modify the psarc (flip bytes in a middle block), re-wrap, decrypt back, hashes valid
    bs = s.block_size
    mod = bytearray(psarc)
    tgt = (len(mod)//2) // bs * bs
    mod[tgt:tgt+8] = b"TESTEDIT"
    mod_sdat = wrap(orig, bytes(mod))
    s2 = Sdat(mod_sdat[:0x100])
    redec = bytearray()
    nb = (s2.file_size + bs - 1)//bs
    for i in range(nb):
        redec += s2.decrypt_block(mod_sdat, i)
    redec = bytes(redec[:s2.file_size])
    rt_ok = redec == bytes(mod)
    hashes_ok = all(_rpcs3_block_hash_ok(s2, mod_sdat, i) for i in range(nb))
    print(f"modified round-trip decrypt(wrap(mod)) == mod : {'PASS' if rt_ok else 'FAIL'}")
    print(f"every block passes RPCS3 fatal HMAC check     : {'PASS' if hashes_ok else 'FAIL'} ({nb} blocks)")
    return 0 if (exact and rt_ok and hashes_ok) else 1

if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    if   sys.argv[1] == "wrap":   wrap(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "verify": sys.exit(cmd_verify(sys.argv[2]))
    else: print("unknown cmd"); sys.exit(1)
