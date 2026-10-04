#!/usr/bin/env python3
"""Prove all generated build outputs are byte-identical across a rebuild."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
manifest=json.loads((ROOT/'source/asset-manifest.json').read_text())
files=[ROOT/a['path'] for a in manifest['assets']]
files += [ROOT/'source/asset-manifest.json',ROOT/'source/README.md',ROOT/'review/coverage.json']
before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
subprocess.run([sys.executable,str(ROOT/'source/build.py')],check=True)
changed=[str(p.relative_to(ROOT)) for p in files if hashlib.sha256(p.read_bytes()).hexdigest()!=before[p]]
assert not changed,changed
result={'result':'PASS','byte_identical_files':len(files)}
(ROOT/'review/reproducibility.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
