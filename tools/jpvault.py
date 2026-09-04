#!/usr/bin/env python3
"""jpvault.py - keep the game's original Japanese out of the public repository.

WHAT THIS IS FOR. The worksheets pair every Japanese string with its English. The English
is ours to publish; the Japanese is the game's script, about 1.9 million characters of it,
and publishing that is redistributing the work itself. This splits the two: the English,
the offsets and the slot sizes stay in the open where the patch can be read and improved,
and the Japanese goes into a vault that only someone who already owns the game can open.

WHAT THIS IS NOT. It is not secrecy, and nothing here would stop a determined person who
owns the game. The key is derived from the user's own disc files, so the repository alone
cannot open the vault, and someone without the game gets nothing from cloning it. That is
the whole claim. Encrypting with a key shipped alongside the ciphertext would achieve
nothing at all, since every clone would carry both halves.

KEY DERIVATION uses two files the patch never writes to, so the key is stable no matter
how many times the game is patched or rolled back:
  * PsarcList.bin, in full (180 bytes)
  * Movie.psarc: its size, and a hash of its first and last 4 MiB
Reading 8 MiB rather than 3 GB keeps `unlock` instant while still requiring the real file.

    python tools/jpvault.py lock                    # strip jp -> build/jp_vault.enc
    python tools/jpvault.py unlock <PSARC dir>      # restore jp from the vault
    python tools/jpvault.py check  <PSARC dir>      # can this dump open the vault?

`lock` is a publishing step: it rewrites the worksheets in place without their `jp`
fields. Run it on a snapshot, never on the working tree you are translating in.
"""
import glob, hashlib, json, os, sys, zlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.join(REPO, "build", "jp_vault.enc")
MAGIC = b"OG2JPV01"
SEP = "	"          # path separator that cannot occur inside a JSON key we use


def is_jp_field(name):
    """Field names that hold the game's own Japanese rather than our English.

    Not just "jp": keyword_entries.json carries the original library descriptions in
    "jp_desc" and the original names in "name_jp", which a jp-only rule left sitting in
    the open. Anything named jp, jp_*, or *_jp is treated as the game's text."""
    return name == "jp" or name.startswith("jp_") or name.endswith("_jp")


# Files whose Japanese the BUILD needs. Everything else that carries Japanese is a build
# intermediate (agent batches, QA reports) and is simply left out of a public snapshot
# rather than encrypted; see tools/make_anon_snapshot.py.
PATTERNS = [
    os.path.join("build", "worksheets", "**", "*.json"),
    os.path.join("build", "*_inline_en.json"),
    os.path.join("build", "dict_entries.json"),
    os.path.join("build", "keyword_entries.json"),
    os.path.join("build", "spirit_desc_in.json"),
]


def targets():
    out = []
    for pat in PATTERNS:
        for f in glob.glob(os.path.join(REPO, pat), recursive=True):
            if os.path.isfile(f):
                out.append(f)
    return sorted(set(out))


# ---------------------------------------------------------------- generic jp walk

def _split(node, path, found):
    """Collect every Japanese field as (path -> text) and delete it from the tree."""
    if isinstance(node, dict):
        for k in [k for k in node if is_jp_field(k) and isinstance(node[k], str)]:
            found[SEP.join(path + [k])] = node.pop(k)
        for k, v in list(node.items()):
            _split(v, path + [k], found)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _split(v, path + [str(i)], found)


def _merge(root, table):
    """Put every Japanese field back exactly where _split took it from."""
    for path, text in table.items():
        parts = path.split(SEP)
        node = root
        for p in parts[:-1]:
            node = node[int(p)] if isinstance(node, list) else node[p]
        node[parts[-1]] = text


# ---------------------------------------------------------------- key + crypto

def _digest_file(path, head=4 << 20):
    h = hashlib.sha256()
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        h.update(f.read(head))
        if size > head:
            f.seek(max(head, size - head))
            h.update(f.read(head))
    return size, h.digest()


def key_material(psarc_dir):
    """Bytes only an owner of the game can produce, from files the patch never writes."""
    lst = os.path.join(psarc_dir, "PsarcList.bin")
    mov = os.path.join(psarc_dir, "Movie.psarc")
    missing = [os.path.basename(p) for p in (lst, mov) if not os.path.isfile(p)]
    if missing:
        raise SystemExit(
            "cannot derive the key: %s not found in\n  %s\n"
            "Point this at your game's USRDIR/PSARC directory, from your own dump."
            % (" and ".join(missing), psarc_dir))
    h = hashlib.sha256()
    h.update(MAGIC)
    h.update(open(lst, "rb").read())
    size, dig = _digest_file(mov)
    h.update(size.to_bytes(8, "little"))
    h.update(dig)
    return h.digest()


def _aesgcm(key):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise SystemExit("this needs the cryptography package:  pip install cryptography")
    return AESGCM(key)


def encrypt(key, plaintext):
    nonce = hashlib.sha256(MAGIC + key).digest()[:12]     # deterministic: same input,
    return nonce + _aesgcm(key).encrypt(nonce, plaintext, MAGIC)  # same vault bytes


def decrypt(key, blob):
    return _aesgcm(key).decrypt(blob[:12], blob[12:], MAGIC)


# ---------------------------------------------------------------- commands

def cmd_lock(psarc_dir):
    key = key_material(psarc_dir)
    payload, stripped = {}, 0
    for f in targets():
        rel = os.path.relpath(f, REPO).replace("\\", "/")
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        found = {}
        _split(data, [], found)
        if not found:
            continue
        payload[rel] = found
        stripped += len(found)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    raw = zlib.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"), 9)
    os.makedirs(os.path.dirname(VAULT), exist_ok=True)
    with open(VAULT, "wb") as fh:
        fh.write(MAGIC + encrypt(key, raw))
    print("locked %d Japanese strings from %d files -> %s (%.1f MB)"
          % (stripped, len(payload), os.path.relpath(VAULT, REPO),
             os.path.getsize(VAULT) / 1e6))
    return 0


def cmd_unlock(psarc_dir):
    if not os.path.exists(VAULT):
        sys.exit("no vault at %s" % VAULT)
    key = key_material(psarc_dir)
    blob = open(VAULT, "rb").read()
    if not blob.startswith(MAGIC):
        sys.exit("%s is not a jp vault" % VAULT)
    try:
        payload = json.loads(zlib.decompress(decrypt(key, blob[len(MAGIC):])))
    except Exception:
        sys.exit("this dump cannot open the vault.\n"
                 "  The key comes from PsarcList.bin and Movie.psarc in your USRDIR/PSARC.\n"
                 "  A different region or revision of the game will not match.")
    restored = 0
    for rel, table in payload.items():
        f = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(f):
            print("  skipped (not present): %s" % rel)
            continue
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        _merge(data, table)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        restored += len(table)
    print("restored %d Japanese strings into %d files" % (restored, len(payload)))
    return 0


def cmd_check(psarc_dir):
    if not os.path.exists(VAULT):
        print("no vault present; the worksheets already carry their Japanese")
        return 0
    key = key_material(psarc_dir)
    blob = open(VAULT, "rb").read()
    try:
        decrypt(key, blob[len(MAGIC):])
    except Exception:
        print("NO: this dump does not open the vault")
        return 1
    print("OK: this dump opens the vault")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "lock" and len(argv) == 3:
        return cmd_lock(argv[2])
    if cmd == "unlock" and len(argv) == 3:
        return cmd_unlock(argv[2])
    if cmd == "check" and len(argv) == 3:
        return cmd_check(argv[2])
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
