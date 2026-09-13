# Format notes (reverse-engineered 2026-06-30)

All confirmed against the actual dump unless marked (theory).

## 1. ISO
- `Dai-2-Ji Super Robot Taisen OG (Japan).iso`, 8,588,886,016 bytes, **decrypted**.
- ISO9660/UDF readable: `\x01CD001` at 0x8000, VolumeId `PS3VOLUME`. 7-Zip opens it directly.
- The "Headers Error / data after end of archive" 7-Zip warning is just the 64 KiB UDF
  tail; extraction is fine.

## 2. PSARC archives (`PS3_GAME/USRDIR/PSARC/`)
| file | size | wrapper | holds |
|------|------|---------|-------|
| Logic.psarc.sdat | 26 MB | SDAT | scenario scripts + databases (TEXT) |
| Common.psarc.sdat | 292 MB | SDAT | UI text, fonts, shared (TEXT + FONT, theory) |
| General2d.psarc.sdat | 654 MB | SDAT | 2D UI, title cards (FONT/graphics, theory) |
| Battle.psarc.sdat | 1.6 GB | SDAT | battle assets + battle text (theory) |
| General3d.psarc.sdat | 1.0 GB | SDAT | 3D models |
| Sound.psarc | 1.4 GB | none | audio |
| Movie.psarc | 3.1 GB | none | FMV |

`PsarcList.bin` (magic `PSAL`) is just the index of these paths.

## 3. SDAT layer (NPD/EDAT)
- Header: NPD (0x00–0x7F) + EDAT (0x80–0x8F).
  - 0x00 magic `NPD\0`; 0x04 version (BE int) = **4**; 0x40 digest[16]; 0x60 dev_hash[16].
  - 0x80 flags (BE) = **0x0100003C**; 0x84 block_size = 0x4000; 0x88 file_size (BE u64).
- flags 0x0100003C = SDAT | ENCRYPTED_KEY(0x08) | FLAG_0x10 | FLAG_0x20 | 0x04. **Not compressed.**
- SDAT key (no RAP needed): `key = dev_hash XOR SDAT_KEY`.
- metadata_section_size = 0x20 (FLAG_0x20 set); metadata precedes-block layout.
- Per block i: `offset = 0x100 + i*block_size + (i+1)*0x20`, len = block_size
  (last = file_size % block_size).
  - b_key = dev_hash[0:12] + uint32_be(i)
  - key_result = AES-128-ECB-enc(key, b_key)
  - key_final  = AES-128-ECB-dec(EDAT_KEY_1, key_result)   (ENCRYPTED_KEY flag)
  - data       = AES-128-CBC-dec(key_final, iv=digest, block)
  - hash check skipped (decryption only). version==4 ⇒ EDAT_KEY_1, iv=digest.
- See `tools/decrypt_sdat.py`. Verified: Logic decrypts to exact `file_size` 0x1937C6C.

## 4. PSARC (Sony, v1.4, zlib)
- Header 32 bytes: `PSAR`, ver 1.4, comp `zlib`, toc_length, entry_size=30, num_files,
  block_size=0x10000, flags.
- TOC entry (30 B): md5_name[16] · block_index(u32) · uncompressed_size(40-bit BE) ·
  file_offset(40-bit BE).
- Block-size table after TOC: 2 bytes/entry here; value 0 ⇒ full block_size.
- File 0 = manifest (newline-separated paths for files 1..n; names are MD5-hashed otherwise).
- See `tools/extract_psarc.py`. Logic = 825 files (824 + manifest).

## 5. Text format — the important part
- Encoding is **UTF-8**, null-terminated strings, gathered in **string pools** addressed by
  **32-bit big-endian pointer tables**.
- Scenario scripts begin with magic **`LOGO`**; 0x04 = file size; then a section table of
  (count, offset) pairs → bytecode/data sections → pointer table → UTF-8 string pool.
  Unused space is filled with `0xDEAD` (0xAD 0xDE little-endian) — ignore it.
- Confirmed string kinds:
  - char/portrait tags: `[ＤＭ]-アイビス`, `[ＡＤ]-アクセル` (fullwidth Latin prefix codes)
  - mission text: `１．　ハガネの撃墜。`, `ゲームオーバー`
  - encyclopedia (FixedData/PilotDictionaryData.dat): full pilot bios, `<魔装機神>`
    angle-bracket inline tags for special terms.
- Implication: **fullwidth Latin glyphs exist** in the font already. Open question is
  **half-width / proportional Latin** for clean English — that's the font lane.

## 6. Reinsertion (TODO — design)
Round-trip first. Before any translation goes in, prove: parse → re-serialize →
byte-identical original. Only then start swapping strings. The pointer table must be
rewritten when string lengths change; pools can grow (fix the section-table offsets and
the file-size field at 0x04). Then re-zip into PSARC, re-wrap SDAT (port make_npdata's
encrypt path, or run the real tool), OR skip repacking and drop loose decrypted files into
the RPCS3 game dir.
