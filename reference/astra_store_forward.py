"""Signed store-forward transport envelopes for disconnected/high-delay links.

This is transport-neutral and intentionally not labelled BPv7 compliance. A
standards-grade BPv7 adapter can carry these verified Astra bundles later.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import base64,json,os,secrets,time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
class StoreForwardError(RuntimeError):pass
@dataclass(frozen=True)
class StoreForwardEnvelope:
 sender:str;destination:str;sequence:int;created:int;expires:int;bundle_sha256:str;signature:bytes
 def unsigned(self):
  return (json.dumps({'version':1,'sender':self.sender,'destination':self.destination,'sequence':self.sequence,'created':self.created,'expires':self.expires,'bundle_sha256':self.bundle_sha256},sort_keys=True,separators=(',',':'))+'\n').encode()
 def encode(self):return self.unsigned()+base64.b64encode(self.signature)+b'\n'
 @staticmethod
 def create(sender,destination,sequence,bundle:bytes,private:Ed25519PrivateKey,ttl_seconds=86400,now=None):
  now=int(time.time()) if now is None else int(now);digest=sha256(bundle).hexdigest();temp=StoreForwardEnvelope(sender,destination,sequence,now,now+ttl_seconds,digest,b'');return StoreForwardEnvelope(sender,destination,sequence,now,now+ttl_seconds,digest,private.sign(temp.unsigned()))
 @staticmethod
 def decode(raw):
  try:first,sig=raw.splitlines();d=json.loads(first);return StoreForwardEnvelope(d['sender'],d['destination'],int(d['sequence']),int(d['created']),int(d['expires']),d['bundle_sha256'],base64.b64decode(sig,validate=True))
  except Exception as exc:raise StoreForwardError('malformed store-forward envelope') from exc
 def verify(self,bundle,public:Ed25519PublicKey,*,destination=None,now=None,last_sequence=-1):
  now=int(time.time()) if now is None else int(now)
  if destination is not None and self.destination!=destination:raise StoreForwardError('store-forward destination mismatch')
  if self.expires<now or self.created>now+300:raise StoreForwardError('store-forward envelope expired/not yet valid')
  if self.sequence<=last_sequence:raise StoreForwardError('store-forward rollback/replay detected')
  if sha256(bundle).hexdigest()!=self.bundle_sha256:raise StoreForwardError('store-forward bundle checksum mismatch')
  try:public.verify(self.signature,self.unsigned())
  except Exception as exc:raise StoreForwardError('store-forward signature invalid') from exc
  return True
class StoreForwardSpool:
 def __init__(self,root):self.root=Path(root);self.incoming=self.root/'incoming';self.outgoing=self.root/'outgoing';self.incoming.mkdir(parents=True,exist_ok=True);self.outgoing.mkdir(parents=True,exist_ok=True)
 def queue(self,envelope,bundle,outgoing=True):
  dest=self.outgoing if outgoing else self.incoming;oid=sha256(envelope.encode()+bundle).hexdigest();d=dest/oid;d.mkdir(exist_ok=False);(d/'envelope').write_bytes(envelope.encode());(d/'bundle').write_bytes(bundle);return oid
 def load(self,oid,outgoing=True):
  d=(self.outgoing if outgoing else self.incoming)/oid
  try:return StoreForwardEnvelope.decode((d/'envelope').read_bytes()),(d/'bundle').read_bytes()
  except FileNotFoundError as exc:raise StoreForwardError('spooled transfer not found') from exc
