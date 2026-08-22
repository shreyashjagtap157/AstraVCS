import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_index import GraphIndex
from astra_sync import sync_filtered
from astra_promises import PromiseStore
from astra_incremental import IncrementalContentCache
class ScaleTests(unittest.TestCase):
 def test_graph_index_rebuild_path_history_and_disposable(self):
  with tempfile.TemporaryDirectory() as td:
   r=AstraRepository.init(td);w=LocalWorkspace(r);p=Path(td)/'a';p.write_text('0');ids=[]
   for i in range(8):p.write_text(str(i));ids.append(w.commit(str(i).encode()).revision_id)
   idx=GraphIndex(r);self.assertEqual(idx.rebuild(),8);self.assertEqual(idx.generation(ids[-1]),8);hist=idx.path_history(b'a');self.assertEqual(hist[0],ids[-1]);self.assertTrue(idx.maybe_changed(ids[-1],b'a'));self.assertIn(ids[0],idx.ancestors(ids[-1]));idx.close();(r.meta/'indexes'/'graph.sqlite').unlink();self.assertEqual(Path(td,'a').read_text(),'7')
 def test_metadata_only_sync_records_promises(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   ra=AstraRepository.init(a);w=LocalWorkspace(ra);(Path(a)/'x').write_text('content');c=w.commit(b'c');rb=AstraRepository.init(b);res=sync_filtered(ra,rb,include_content=False);self.assertEqual(res.contents,0);self.assertTrue(PromiseStore(rb).all())
 def test_incremental_cache_avoids_second_content_read(self):
  with tempfile.TemporaryDirectory() as td:
   r=AstraRepository.init(td);p=Path(td)/'x';p.write_text('x');c=IncrementalContentCache(r);a,read1=c.content_id(p);b,read2=c.content_id(p);self.assertTrue(read1);self.assertFalse(read2);self.assertEqual(a,b);c.save()
if __name__=='__main__':unittest.main()
