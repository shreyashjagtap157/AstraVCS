import io,json,os,random,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_codec import ObjectEnvelope,ObjectType,CodecError
from astra_semantic_codec import decode_semantic,SemanticCodecError
from astra_repository import AstraRepository
from astra_bundle import apply_bundle,BundleError,BUNDLE_FORMAT
from astra_local import LocalWorkspace

class AdversarialTests(unittest.TestCase):
 def test_random_envelope_bytes_fail_cleanly_or_decode(self):
  rng=random.Random(0xA57A)
  for _ in range(5000):
   raw=rng.randbytes(rng.randrange(0,256))
   try:ObjectEnvelope.decode(raw)
   except CodecError:pass
 def test_random_semantic_payloads_fail_without_unexpected_exceptions(self):
  rng=random.Random(12345)
  for typ in ObjectType:
   for _ in range(100):
    env=ObjectEnvelope(typ,rng.randbytes(rng.randrange(0,128)))
    try:decode_semantic(env)
    except (SemanticCodecError,ValueError):pass
 def test_bundle_path_traversal_is_rejected(self):
  with tempfile.TemporaryDirectory() as td,tempfile.NamedTemporaryFile(suffix='.astra') as f:
   repo=AstraRepository.init(td)
   with zipfile.ZipFile(f.name,'w') as z:
    z.writestr('manifest.json',json.dumps({'format':BUNDLE_FORMAT,'objects':[],'mappings':[],'operation_head':None}))
    z.writestr('large/../../escape',b'x')
   with self.assertRaises(BundleError):apply_bundle(repo,f.name)
   self.assertFalse((Path(td).parent/'escape').exists())
 def test_random_commit_checkout_cycles_preserve_fsck(self):
  rng=random.Random(9876)
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);w=LocalWorkspace(repo);root=Path(td);history=[]
   for i in range(60):
    p=root/f'f{rng.randrange(5)}';p.write_text(str(rng.randrange(100000)))
    try:c=w.commit(f'c{i}'.encode());history.append(c.revision_id)
    except Exception as exc:
     self.fail(f'unexpected commit failure: {exc}')
    if history and rng.random()<.25:w.checkout(rng.choice(history),ref=None,force=True)
    self.assertTrue(repo.fsck().ok)
