"""Cryptographic release assurance, provenance, backup and anti-rollback."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import json,os,tempfile,time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from astra_model import Attestation,ReleaseManifest
from astra_bundle import create_bundle,apply_bundle
from astra_repository import AstraRepository,_atomic_replace

class AssuranceError(RuntimeError):pass

def key_id(public_key:Ed25519PublicKey)->str:
 raw=public_key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);return sha256(raw).hexdigest()
def generate_keypair():
 private=Ed25519PrivateKey.generate();return private,private.public_key()
def sign_attestation(private,subject_id,predicate_type:bytes,payload:bytes)->Attestation:
 kid=key_id(private.public_key());unsigned=Attestation(subject_id,predicate_type,payload,kid,b'\0'*64);sig=private.sign(unsigned.signing_bytes());return Attestation(subject_id,predicate_type,payload,kid,sig)
def verify_attestation(att:Attestation,public:Ed25519PublicKey)->bool:
 if key_id(public)!=att.signer_key_id:return False
 try:public.verify(att.signature,att.signing_bytes());return True
 except Exception:return False

def verify_threshold(attestations,keys:dict[str,Ed25519PublicKey],subject_id:str,predicate:bytes,threshold:int):
 good=set()
 for a in attestations:
  if a.subject_id==subject_id and a.predicate_type==predicate and a.signer_key_id in keys and verify_attestation(a,keys[a.signer_key_id]):good.add(a.signer_key_id)
 return len(good)>=threshold

class AntiRollbackStore:
 def __init__(self,repo,name='default'):
  self.repo=repo;self.path=repo.meta/'trust'/f'{name}.sequence';repo._mkdir_durable(self.path.parent)
 def observed(self):
  try:return int(self.path.read_text().strip())
  except FileNotFoundError:return -1
  except Exception as exc:raise AssuranceError('corrupt anti-rollback state') from exc
 def accept(self,sequence:int):
  old=self.observed()
  if sequence<old:raise AssuranceError(f'rollback detected: {sequence} < {old}')
  if sequence>old:_atomic_replace(self.repo,self.path,(str(sequence)+'\n').encode())

def canonical_json(value)->bytes:return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def build_provenance(*,revision_id,builder,command,materials=(),outputs=()):
 return canonical_json({'_type':'https://in-toto.io/Statement/v1','subject':[{'name':n,'digest':{'sha256':d}} for n,d in outputs],'predicateType':'https://slsa.dev/provenance/v1','predicate':{'buildDefinition':{'buildType':'dev.astravcs/build/v1','externalParameters':{'revision':revision_id,'command':command},'resolvedDependencies':[{'uri':u,'digest':{'sha256':d}} for u,d in materials]},'runDetails':{'builder':{'id':builder}}}})
def build_sbom(components):
 return canonical_json({'spdxVersion':'SPDX-2.3','dataLicense':'CC0-1.0','SPDXID':'SPDXRef-DOCUMENT','name':'AstraVCS release SBOM','documentNamespace':'https://astravcs.dev/spdx/'+sha256(repr(components).encode()).hexdigest(),'packages':[{'name':n,'SPDXID':'SPDXRef-'+str(i),'versionInfo':v,'downloadLocation':'NOASSERTION','filesAnalyzed':False} for i,(n,v) in enumerate(components)]})

def artifact_digest(path):
 h=sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

class BackupManager:
 def __init__(self,repo):self.repo=repo
 def create(self,path):
  create_bundle(self.repo,path);digest=artifact_digest(path);meta=Path(str(path)+'.sha256');meta.write_text(digest+'  '+Path(path).name+'\n');return digest
 @staticmethod
 def restore(bundle_path,destination):
  expected_path=Path(str(bundle_path)+'.sha256')
  if expected_path.exists():
   expected=expected_path.read_text().split()[0]
   if artifact_digest(bundle_path)!=expected:raise AssuranceError('backup checksum mismatch')
  repo=AstraRepository.init(destination);apply_bundle(repo,bundle_path,publish_state=True)
  if not repo.fsck().ok:raise AssuranceError('restored repository failed fsck')
  return repo


def create_release(repo:AstraRepository,name:bytes,revisions:tuple[str,...],artifacts:tuple[tuple[bytes,str],...],provenance_ids:tuple[str,...]=(),sequence:int=0)->ReleaseManifest:
    manifest=ReleaseManifest(name,revisions,tuple(sorted(artifacts,key=lambda x:x[0])),provenance_ids,sequence);repo.put(manifest);return manifest

class SignedUpdateMetadata:
 def __init__(self,private):self.private=private
 def create(self,version:str,sequence:int,artifact_sha256:str,url:str)->tuple[bytes,bytes,str]:
  payload=canonical_json({'version':version,'sequence':sequence,'artifact_sha256':artifact_sha256,'url':url});sig=self.private.sign(payload);return payload,sig,key_id(self.private.public_key())
 @staticmethod
 def verify(payload:bytes,signature:bytes,public:Ed25519PublicKey,rollback:AntiRollbackStore):
  try:public.verify(signature,payload);data=json.loads(payload)
  except Exception as exc:raise AssuranceError('invalid update metadata signature or payload') from exc
  rollback.accept(int(data['sequence']));return data

class UpdateChannelManifest:
 def __init__(self,private):self.private=private
 def create(self,channel,version,sequence,artifacts,*,minimum_version=None):
  if channel not in ('stable','beta','nightly'):raise AssuranceError('invalid update channel')
  rows=[]
  for platform,digest,url in sorted(artifacts):rows.append({'platform':platform,'sha256':digest,'url':url})
  payload=canonical_json({'schema':1,'channel':channel,'version':version,'sequence':sequence,'minimum_version':minimum_version,'artifacts':rows});return payload,self.private.sign(payload),key_id(self.private.public_key())
 @staticmethod
 def verify(payload,signature,public,rollback:AntiRollbackStore,*,channel):
  try:public.verify(signature,payload);data=json.loads(payload)
  except Exception as exc:raise AssuranceError('invalid update channel signature/payload') from exc
  if data.get('schema')!=1 or data.get('channel')!=channel:raise AssuranceError('update channel mismatch')
  seen=set()
  for a in data.get('artifacts',[]):
   if a.get('platform') in seen or len(a.get('sha256',''))!=64:raise AssuranceError('invalid/duplicate update artifact')
   seen.add(a['platform'])
  rollback.accept(int(data['sequence']));return data
