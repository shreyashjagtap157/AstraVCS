import json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'));sys.path.insert(0,str(ROOT/'conformance'))
from astra_repository import AstraRepository,BOOTSTRAP_REPOSITORY_FORMAT
from astra_local import LocalWorkspace
from astra_bundle import create_bundle,apply_bundle,BundleError,BUNDLE_FORMAT_V1,BUNDLE_FORMAT_V2
from independent_bundle_v2 import verify_bundle

class BundleV2ConformanceTests(unittest.TestCase):
 def _source(self,td):
  repo=AstraRepository.init(td);Path(td,'a.txt').write_bytes(b'bundle-v2\n');c=LocalWorkspace(repo).commit(b'fixture');return repo,c.revision_id
 def test_v2_roundtrip_and_independent_verification(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src,rev=self._source(a);bundle=Path(a)/'repo.astra';create_bundle(src,bundle);info=verify_bundle(bundle);self.assertGreater(info['objects'],0);dst=AstraRepository.init(b);m=apply_bundle(dst,bundle,publish_state=True);self.assertEqual(m['format'],BUNDLE_FORMAT_V2);self.assertEqual(LocalWorkspace(dst).head(),rev);self.assertTrue(dst.fsck().ok)
 def test_v2_creation_refuses_bootstrap_repository(self):
  with tempfile.TemporaryDirectory() as td:
   repo,_=self._source(td);repo.format_path.write_bytes(BOOTSTRAP_REPOSITORY_FORMAT);legacy=AstraRepository(td)
   with self.assertRaises(BundleError):create_bundle(legacy,Path(td)/'x.astra')
 def test_v2_rejects_wrong_repository_descriptor(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src,_=self._source(a);good=Path(a)/'good.astra';bad=Path(a)/'bad.astra';create_bundle(src,good)
   with zipfile.ZipFile(good,'r') as zin,zipfile.ZipFile(bad,'w',compression=zipfile.ZIP_STORED) as zout:
    for item in zin.infolist():
     data=zin.read(item.filename)
     if item.filename=='manifest.json':
      m=json.loads(data);m['repository_format']['format']=2;data=(json.dumps(m,sort_keys=True,separators=(',',':'))+'\n').encode()
     zout.writestr(item,data)
   with self.assertRaises(BundleError):apply_bundle(AstraRepository.init(b),bad)
   with self.assertRaises(ValueError):verify_bundle(bad)
 def test_legacy_v1_reader_remains_supported(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src,rev=self._source(a);legacy=Path(a)/'legacy.astra';objects=[]
   for k in sorted(src.store.iter_keys()):objects.append((k,src.store._object_path(k).read_bytes()))
   manifest={'format':BUNDLE_FORMAT_V1,'objects':[k for k,_ in objects],'mappings':[],'operation_head':src.operation_head()}
   with zipfile.ZipFile(legacy,'w',compression=zipfile.ZIP_STORED) as z:
    z.writestr('manifest.json',json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
    for k,raw in objects:z.writestr('objects/'+k,raw)
   dst=AstraRepository.init(b);m=apply_bundle(dst,legacy,publish_state=True);self.assertEqual(m['format'],BUNDLE_FORMAT_V1);self.assertEqual(LocalWorkspace(dst).head(),rev)
if __name__=='__main__':unittest.main()
