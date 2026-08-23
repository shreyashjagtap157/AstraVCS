#!/usr/bin/env python3
"""One-command qualification gate for available local toolchains."""
from pathlib import Path
import json,shutil,subprocess,sys,tomllib
ROOT=Path(__file__).resolve().parents[1]
def run(cmd,cwd=ROOT):print('+',' '.join(cmd));subprocess.run(cmd,cwd=cwd,check=True)
def main():
 run([sys.executable,'-W','error::ResourceWarning','-m','unittest','discover','-s','tests/reference','-q'])
 run([sys.executable,'-m','compileall','-q','reference','conformance','tests/reference'])
 run(['git','diff','--check'])
 run([sys.executable,'tools/check_versions.py'])
 for d in ['apps/web','apps/desktop','sdk/typescript']:run(['npx','--yes','tsc','--noEmit'],ROOT/d)
 if shutil.which('go'):run(['go','test','./...'],ROOT/'sdk/go')
 if shutil.which('javac'):
  out=ROOT/'.validation-java';out.mkdir(exist_ok=True);run(['javac','-d',str(out),'sdk/java/src/main/java/dev/astravcs/AstraClient.java'])
 if shutil.which('cargo'):run(['cargo','test','--workspace','--all-targets'])
 else:print('DEFERRED: Rust toolchain unavailable; cargo qualification not executed',file=sys.stderr)
 run([sys.executable,'benches/bench_reference.py'])
 return 0
if __name__=='__main__':raise SystemExit(main())
