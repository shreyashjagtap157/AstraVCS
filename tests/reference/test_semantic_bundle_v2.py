import json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_portable_bundle import create_portable_bundle,apply_portable_bundle,PortableBundleError,FORMAT_V1,FORMAT_V2

class SemanticBundleV2Tests(unittest.TestCase):
 def _repo(self,td):
  repo=AstraRepository.init(td);Path(td,'x').write_bytes(b'semantic-v2');c=LocalWorkspace(repo).commit(b'x');return repo,c.revision_id
 def test_v2_roundtrip(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src,rev=self._repo(a);f=Path(a)/'x.astra';create_portable_bundle(src,f);m=json.loads(zipfile.ZipFile(f).read('manifest.json'));self.assertEqual(m['format'],FORMAT_V2);self.assertEqual(m['repository_format'],1)
   dst=AstraRepository.init(b);apply_portable_bundle(dst,f,publish_refs=True);self.assertEqual(LocalWorkspace(dst).head(),rev);self.assertTrue(dst.fsck().ok)
 def test_v2_detects_semantic_tampering(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src,_=self._repo(a);good=Path(a)/'g.astra';bad=Path(a)/'b.astra';create_portable_bundle(src,good)
   with zipfile.ZipFile(good) as zin,zipfile.ZipFile(bad,'w',zipfile.ZIP_STORED) as zout:
    changed=False
    for info in zin.infolist():
     raw=zin.read(info.filename)
     if not changed and info.filename.startswith('semantic/'):
      raw=raw[:-1]+bytes([raw[-1]^1]);changed=True
     zout.writestr(info,raw)
   with self.assertRaises(PortableBundleError):apply_portable_bundle(AstraRepository.init(b),bad)
 def test_v2_creation_fails_when_tree_content_is_missing(self):
  with tempfile.TemporaryDirectory() as td:
   repo,_=self._repo(td);typ,oid,p=next((t,o,p) for t,o,p in repo.iter_mappings() if int(t)==1);p.unlink()
   with self.assertRaises(PortableBundleError):create_portable_bundle(repo,Path(td)/'missing.astra')
 def test_legacy_v1_reader(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src,rev=self._repo(a);f=Path(a)/'legacy.astra';sem=[];contents={}
   from astra_codec import ObjectType
   from astra_semantic_codec import encode_semantic
   for typ,oid,_ in src.iter_mappings():
    typ=ObjectType(int(typ));value=src.get(typ,oid)
    if typ==ObjectType.CONTENT:continue
    sem.append((typ,oid,encode_semantic(value).encode()))
    if typ==ObjectType.TREE:
     for _,e in value.entries:
      if e.content_id:contents[e.content_id]=src.get_content(e.content_id)
   v=src.current_view();m={'format':FORMAT_V1,'head':src.operation_head(),'refs':[[n.hex(),o] for n,o in v.refs],'workspaces':[[n.hex(),o] for n,o in v.workspace_heads],'semantic':[[int(t),o] for t,o,_ in sem],'contents':sorted(contents)}
   with zipfile.ZipFile(f,'w',zipfile.ZIP_STORED) as z:
    z.writestr('manifest.json',json.dumps(m,sort_keys=True,separators=(',',':'))+'\n')
    for t,o,raw in sem:z.writestr(f'semantic/{int(t)}/{o}',raw)
    for cid,data in contents.items():z.writestr(f'content/{cid}',data)
   dst=AstraRepository.init(b);apply_portable_bundle(dst,f,publish_refs=True);self.assertEqual(LocalWorkspace(dst).head(),rev)
if __name__=='__main__':unittest.main()
