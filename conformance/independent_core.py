"""Independent AstraVCS bootstrap conformance verifier.

This module intentionally imports no AstraVCS implementation modules. It is a
second executable interpretation of the documented envelope and semantic
identity formats for core objects.
"""
from __future__ import annotations
from hashlib import sha256

MAGIC=b'ASTRA\x00';HEADER=len(MAGIC)+1+2+8
CONTENT,TREE,CHANGE,REVISION=1,2,3,4

def blob(x:bytes)->bytes:return len(x).to_bytes(8,'big')+x

def digest(domain:bytes,*parts:bytes)->str:
 h=sha256();h.update(blob(domain))
 for p in parts:h.update(blob(p))
 return h.hexdigest()

def envelope(raw:bytes):
 if len(raw)<HEADER or raw[:6]!=MAGIC:raise ValueError('bad envelope')
 typ=raw[6];version=int.from_bytes(raw[7:9],'big');n=int.from_bytes(raw[9:17],'big')
 if version!=0 or len(raw)!=HEADER+n:raise ValueError('bad envelope framing')
 return typ,raw[HEADER:]

class R:
 def __init__(self,b):self.b=b;self.i=0
 def take(self,n):
  if n<0 or self.i+n>len(self.b):raise ValueError('truncated')
  out=self.b[self.i:self.i+n];self.i+=n;return out
 def u8(self):return self.take(1)[0]
 def u32(self):return int.from_bytes(self.take(4),'big')
 def u64(self):return int.from_bytes(self.take(8),'big')
 def varblob(self):return self.take(self.u64())
 def done(self):
  if self.i!=len(self.b):raise ValueError('trailing bytes')

def verify_content(raw:bytes)->str:
 typ,p=envelope(raw)
 if typ!=CONTENT:raise ValueError('not content')
 return digest(b'ASTRA:CONTENT:V0',p)

def verify_tree(raw:bytes)->str:
 typ,p=envelope(raw)
 if typ!=TREE:raise ValueError('not tree')
 schema=1 if p[:1]==b'\x01' else 0;r=R(p)
 if schema:r.take(1)
 count=r.u32();identity=bytearray();previous=None
 for _ in range(count):
  path=r.varblob()
  if previous is not None and path<=previous:raise ValueError('noncanonical path order')
  previous=path;node=r.take(16);kind=r.u8()
  if kind not in (1,2,3):raise ValueError('bad node kind')
  identity+=blob(path)+node+bytes((kind,))
  if schema:identity+=r.take(4)
  marker=r.u8()
  if marker not in (0,1):raise ValueError('bad content marker')
  identity+=bytes((marker,))
  if marker:identity+=r.take(32)
  marker=r.u8()
  if marker not in (0,1):raise ValueError('bad provenance marker')
  identity+=bytes((marker,))
  if marker:identity+=r.take(16)
 r.done();return digest(b'ASTRA:TREE:V1' if schema else b'ASTRA:TREE:V0',bytes(identity))

def verify_change(raw:bytes)->str:
 typ,p=envelope(raw)
 if typ!=CHANGE:raise ValueError('not change')
 r=R(p);change=r.take(16);message=r.varblob();before=r.take(32);after=r.take(32);r.done()
 return digest(b'ASTRA:CHANGE-VERSION:V0',change,message,before,after)

def _attr(r:R)->bytes:
 name=r.varblob();email=r.varblob();ts=r.take(8);tz=r.take(2)
 return blob(name)+blob(email)+ts+tz

def verify_revision(raw:bytes)->str:
 typ,p=envelope(raw)
 if typ!=REVISION:raise ValueError('not revision')
 schema=1 if p[:1]==b'\x01' else 0;r=R(p)
 if schema:r.take(1)
 parents=b''.join(r.take(32) for _ in range(r.u32()));tree=r.take(32);marker=r.u8()
 if marker not in (0,1):raise ValueError('bad change marker')
 cv=r.take(32) if marker else bytes(32)
 if schema:
  author=_attr(r);committer=_attr(r);r.done();return digest(b'ASTRA:REVISION:V1',parents,tree,cv,author,committer)
 r.done();return digest(b'ASTRA:REVISION:V0',parents,tree,cv)

def verify(raw:bytes)->str:
 typ,_=envelope(raw)
 return {CONTENT:verify_content,TREE:verify_tree,CHANGE:verify_change,REVISION:verify_revision}[typ](raw)
