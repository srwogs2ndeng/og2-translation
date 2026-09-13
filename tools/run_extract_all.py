#!/usr/bin/env python3
"""
End-to-end driver: ISO -> decrypted PSARC -> extracted game files.

Pipeline (all reproducible, pure-Python except 7-Zip for the UDF read):
  1. 7-Zip pulls PS3_GAME/USRDIR/PSARC/*.psarc(.sdat) out of the decrypted ISO
  2. decrypt_sdat.py  removes the SDAT layer  (.psarc.sdat -> .psarc)
  3. extract_psarc.py unpacks the PSARC       (.psarc -> loose files)

Run from anywhere; paths are resolved relative to this stub.
By default it processes only the text-bearing archives (Logic/Common/Battle).
Use --all to also do General2d/General3d/Sound/Movie (large; mostly non-text).
"""
import os, sys, subprocess, glob, shutil

HERE   = os.path.dirname(os.path.abspath(__file__))
STUB   = os.path.dirname(HERE)                      # og2-translation/
RPCS3  = os.path.dirname(STUB)                      # rpcs3 install root
GAMES  = os.path.join(RPCS3, "games")
WORK   = os.path.join(STUB, "work")                 # all output lands here

# Archives most relevant to translation. Logic = scenario+databases (UTF-8 text),
# Common/Battle = likely the bulk dialogue + fonts. Others are textures/audio/video.
TEXT_ARCHIVES = ["Logic", "Common", "Battle"]
BIG_ARCHIVES  = ["General2d", "General3d", "Sound", "Movie"]

sys.path.insert(0, HERE)
import decrypt_sdat, extract_psarc

def find_7z():
    for p in (r"C:\Program Files\7-Zip\7z.exe",
              r"C:\Program Files (x86)\7-Zip\7z.exe",
              shutil.which("7z") or ""):
        if p and os.path.exists(p):
            return p
    sys.exit("7-Zip not found; install it or edit find_7z().")

def find_iso():
    hits = glob.glob(os.path.join(GAMES, "*.iso"))
    if not hits:
        sys.exit(f"No .iso in {GAMES}")
    return hits[0]

def main():
    do_all = "--all" in sys.argv
    archives = TEXT_ARCHIVES + (BIG_ARCHIVES if do_all else [])
    sevenzip, iso = find_7z(), find_iso()
    os.makedirs(WORK, exist_ok=True)
    print(f"ISO : {iso}\n7z  : {sevenzip}\nwork: {WORK}\narchives: {archives}\n")

    for name in archives:
        # The on-disc name is either <name>.psarc.sdat (encrypted) or <name>.psarc.
        for cand in (f"{name}.psarc.sdat", f"{name}.psarc"):
            inner = f"PS3_GAME/USRDIR/PSARC/{cand}"
            local = os.path.join(WORK, cand)
            if not os.path.exists(local):
                print(f"[7z ] extracting {cand} from ISO ...")
                r = subprocess.run([sevenzip, "e", f"-o{WORK}", iso, inner, "-y"],
                                   capture_output=True, text=True)
                if not os.path.exists(local):
                    continue  # this candidate name not present; try the other
            # decrypt if it's an sdat
            psarc = local
            if local.endswith(".sdat"):
                psarc = local[:-5]  # strip .sdat
                if not os.path.exists(psarc):
                    print(f"[dec] {cand} -> {os.path.basename(psarc)}")
                    decrypt_sdat.decrypt_sdat(local, psarc, verbose=True)
            # extract the psarc
            outdir = os.path.join(WORK, name)
            if not os.path.isdir(outdir):
                print(f"[psarc] unpack -> {name}/")
                extract_psarc.extract(psarc, outdir)
            print()
            break

    print("Done. Extracted trees under:", WORK)

if __name__ == "__main__":
    main()
