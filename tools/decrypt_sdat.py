#!/usr/bin/env python3
# Faithful pure-Python port of the SDAT decryption path of make_npdata (Hykem, GPLv3).
# Handles the non-DRM SDAT case (no RAP/klicensee needed). Verified field-for-field
# against make_npdata.c decrypt_data() for flags with SDAT_FLAG set.
import struct, sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SDAT_KEY   = bytes([0x0D,0x65,0x5E,0xF8,0xE6,0x74,0xA9,0x8A,0xB8,0x50,0x5C,0xFA,0x7D,0x01,0x29,0x33])
EDAT_KEY_0 = bytes([0xBE,0x95,0x9C,0xA8,0x30,0x8D,0xEF,0xA2,0xE5,0xE1,0x80,0xC6,0x37,0x12,0xA9,0xAE])
EDAT_KEY_1 = bytes([0x4C,0xA9,0xC1,0x4B,0x01,0xC9,0x53,0x09,0x96,0x9B,0xEC,0x68,0xAA,0x0B,0xC0,0x81])

SDAT_FLAG            = 0x01000000
EDAT_COMPRESSED_FLAG = 0x00000001
EDAT_FLAG_0x02       = 0x00000002
EDAT_ENCRYPTED_KEY   = 0x00000008
EDAT_FLAG_0x10       = 0x00000010
EDAT_FLAG_0x20       = 0x00000020
EDAT_DEBUG_DATA_FLAG = 0x80000000

def aes_ecb_enc(key, data):  # one or more 16-byte blocks
    return Cipher(algorithms.AES(key), modes.ECB()).encryptor().update(data)
def aes_ecb_dec(key, data):
    return Cipher(algorithms.AES(key), modes.ECB()).decryptor().update(data)
def aes_cbc_dec(key, iv, data):
    return Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor().update(data)

def xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))

def decrypt_sdat(path_in, path_out, verbose=True):
    raw = open(path_in, "rb").read()
    if raw[:4] != b"NPD\x00":
        raise SystemExit("not an NPD/SDAT file: %r" % raw[:4])

    version = struct.unpack(">i", raw[0x04:0x08])[0]
    digest    = raw[0x40:0x50]
    dev_hash  = raw[0x60:0x70]

    flags      = struct.unpack(">i", raw[0x80:0x84])[0]
    block_size = struct.unpack(">i", raw[0x84:0x88])[0]
    file_size  = struct.unpack(">Q", raw[0x88:0x90])[0]

    if verbose:
        print(f"version={version} flags=0x{flags & 0xffffffff:08X} "
              f"block_size=0x{block_size:X} file_size=0x{file_size:X}")
    if not (flags & SDAT_FLAG):
        raise SystemExit("not SDAT (EDAT needs a key/RAP) — aborting")

    # SDAT key:  key = dev_hash XOR SDAT_KEY
    crypt_key = xor(dev_hash, SDAT_KEY)

    ver_param = 1 if version == 4 else (1 if version >= 2 else 0)  # selects EDAT_KEY_1 vs _0
    edat_key  = EDAT_KEY_1 if ver_param else EDAT_KEY_0

    compressed   = bool(flags & EDAT_COMPRESSED_FLAG)
    meta_sz      = 0x20 if (compressed or (flags & EDAT_FLAG_0x20)) else 0x10
    block_num    = (file_size + block_size - 1) // block_size
    metadata_off = 0x100
    out = bytearray()

    for i in range(block_num):
        if flags & EDAT_FLAG_0x20:
            offset = metadata_off + i * block_size + (i + 1) * meta_sz
        elif compressed:
            raise SystemExit("compressed SDAT not handled (this file is not compressed)")
        else:
            offset = metadata_off + i * block_size + block_num * meta_sz

        length = block_size
        if i == block_num - 1 and (file_size % block_size):
            length = file_size % block_size
        pad_length = length
        read_len = (length + 0xF) & ~0xF
        enc = raw[offset:offset + read_len]

        # per-block key
        b_key = dev_hash[:0xC] + struct.pack(">I", i) if version > 1 else (b"\x00"*0xC + struct.pack(">I", i))
        key_result = aes_ecb_enc(crypt_key, b_key)

        # crypto_mode high nibble = 0x10000000 (ENCRYPTED_KEY): key_final = AESCBC-dec(EDAT_KEY, IV=0, key_result)
        if flags & EDAT_ENCRYPTED_KEY:
            key_final = aes_cbc_dec(edat_key, b"\x00"*0x10, key_result)
        else:
            key_final = key_result

        iv_final = digest if version > 1 else b"\x00"*0x10

        if flags & EDAT_DEBUG_DATA_FLAG:
            dec = enc
        elif (flags & EDAT_FLAG_0x02) == 0:   # crypto_mode low byte 0x02 -> AES128-CBC
            dec = aes_cbc_dec(key_final, iv_final, enc)
        else:                                  # 0x01 -> no algorithm
            dec = enc

        out += dec[:pad_length]

    open(path_out, "wb").write(out)
    print(f"wrote {len(out)} bytes -> {path_out}  (expected 0x{file_size:X} = {file_size})")
    print("OK" if len(out) == file_size else "SIZE MISMATCH")

if __name__ == "__main__":
    decrypt_sdat(sys.argv[1], sys.argv[2])
