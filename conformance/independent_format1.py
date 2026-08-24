"""Independent Repository Format 1 verifier.

Imports no AstraVCS implementation modules.  It verifies the stable repository
layout/state descriptor and semantic-map/store-key relationships from disk.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path

FORMAT1 = b'{"format":1,"operation_state":1,"semantic_map":1,"storage":"loose-v1"}\n'
OBJECT_DIRS = {"content","tree","change-version","revision","view","operation","conflict","attestation","release-manifest"}
MAGIC=b"ASTRA\x00"
DOMAIN=b"ASTRA:LOOSE-OBJECT:V0"

def _blob(x:bytes)->bytes:return len(x).to_bytes(8,"big")+x

def store_key(raw:bytes)->str:
 h=sha256();h.update(_blob(DOMAIN));h.update(_blob(raw));return h.hexdigest()

def verify_format1(root)->dict:
 root=Path(root);meta=root/".astra"
 if (meta/"format").read_bytes()!=FORMAT1:raise ValueError("not Repository Format 1")
 if not (meta/"semantic-map").is_dir():raise ValueError("semantic-map missing")
 if not (meta/"store"/"objects").is_dir():raise ValueError("object store missing")
 checked=0
 for typedir in sorted((meta/"semantic-map").iterdir()):
  if not typedir.is_dir():raise ValueError("unexpected semantic-map entry")
  if typedir.name not in OBJECT_DIRS:raise ValueError("unknown semantic object directory")
  for mapping in sorted(typedir.rglob("*")):
   if not mapping.is_file():continue
   rel=mapping.relative_to(typedir);parts=rel.parts
   if len(parts)!=2 or len(parts[0])!=2:raise ValueError("invalid semantic mapping path")
   oid=parts[0]+parts[1]
   if len(oid)!=64 or any(c not in "0123456789abcdef" for c in oid):raise ValueError("invalid semantic id path")
   key=mapping.read_text("ascii").strip()
   if len(key)!=64 or any(c not in "0123456789abcdef" for c in key):raise ValueError("invalid store key mapping")
   obj=meta/"store"/"objects"/"sha256"/key[:2]/key[2:]
   raw=obj.read_bytes()
   if store_key(raw)!=key:raise ValueError("store key mismatch")
   if len(raw)<17 or raw[:6]!=MAGIC:raise ValueError("invalid object envelope")
   n=int.from_bytes(raw[9:17],"big")
   if len(raw)!=17+n:raise ValueError("invalid object envelope length")
   checked+=1
 head=meta/"state"/"operation-head"
 operation_head=None
 if head.exists():
  operation_head=head.read_text("ascii").strip()
  if len(operation_head)!=64 or any(c not in "0123456789abcdef" for c in operation_head):raise ValueError("invalid operation head")
 return {"format":1,"mappings_checked":checked,"operation_head":operation_head}
