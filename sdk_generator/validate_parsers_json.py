#!/usr/bin/env python3
"""Guard against the doubled-parsers.json corruption.

Background: the parser index (sdk_generator/outputs/github_parser.json, symlinked
to src/genie/libs/parser/parsers.json) is written by an append-style generator.
Running generation twice without first removing the output concatenates two full
JSON documents -> "Extra data: line ... (char ...)" on every device.parse().
This shipped once already; a corrupt copy can be packaged and uploaded to pypi.

Usage:
    # verify (exit 0 clean / non-zero corrupt) -- run AFTER build, BEFORE pypi upload
    python sdk_generator/validate_parsers_json.py

    # clean-slate regenerate from the datafile (the safe, truncating path)
    python sdk_generator/validate_parsers_json.py --regen
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs", "github_parser.json")
DATAFILE = os.path.join(HERE, "github", "parser_datafile.yaml")
MIN_PARSERS = 6400          # clean index is ~6477 (upstream + arcos)
SENTINEL = "show version"   # a parser that must carry an arcos folder


def validate(path=OUT):
    raw = open(path).read()
    try:
        d = json.loads(raw)          # rejects trailing/extra data (the doubling)
    except json.JSONDecodeError as e:
        return False, f"CORRUPT: {e} — file is {len(raw)/1e6:.1f} MB (doubled?)"
    if len(d) < MIN_PARSERS:
        return False, f"only {len(d)} parsers (< {MIN_PARSERS}); index looks truncated"
    if "arcos" not in d.get(SENTINEL, {}).get("folders", {}):
        return False, f"arcos folder missing from '{SENTINEL}' — upstream-only index"
    return True, f"OK: {len(d)} parsers, {len(raw)/1e6:.1f} MB, arcos present"


def regen(path=OUT, datafile=DATAFILE):
    import genie.json.make_json as mj
    m = mj.MakeParsers(datafile)
    m.make()
    if os.path.exists(path):
        os.remove(path)              # pre-clean: append-mode can never double
    with open(path, "w") as fh:      # truncating write
        json.dump(m.output, fh, indent=1)
    return len(m.output)


if __name__ == "__main__":
    if "--regen" in sys.argv:
        n = regen()
        print(f"regenerated cleanly: {n} parsers")
    ok, msg = validate()
    print(msg)
    sys.exit(0 if ok else 1)
