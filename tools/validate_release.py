#!/usr/bin/env python3
"""Post-commit release qualification including dual-control self-hosting."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def run(*cmd):subprocess.run(cmd,cwd=ROOT,check=True)
def main():
 run(sys.executable,'tools/validate.py')
 run(sys.executable,'tools/self_host_check.py')
 return 0
if __name__=='__main__':raise SystemExit(main())
