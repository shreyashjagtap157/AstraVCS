import json, tempfile, unittest
from pathlib import Path
from astra_model import RepositoryView, Operation
from astra_repository import AstraRepository, StateCorruptionError

OID_A='11'*32; OID_B='22'*32; OID_C='33'*32

class OperationReconcileTests(unittest.TestCase):
    def _diverge(self, repo, left_view, right_view):
        base_view=RepositoryView.create({b'main':OID_A},{b'default':OID_A}); repo.put(base_view)
        base=Operation((),base_view.view_id,b'base'); repo.put(base)
        repo._mkdir_durable(repo.metadata_root/'state')
        from astra_repository import _atomic_replace
        _atomic_replace(repo, repo.metadata_root/'state'/'operation-head', (base.operation_id+'\n').encode())
        repo.put(left_view); lop=Operation((base.operation_id,),left_view.view_id,b'left'); repo.put(lop)
        repo.put(right_view); rop=Operation((base.operation_id,),right_view.view_id,b'right'); repo.put(rop)
        _atomic_replace(repo, repo.metadata_root/'state'/'operation-head', (lop.operation_id+'\n').encode())
        return base,lop,rop
    def test_disjoint_ref_workspace_changes_merge(self):
        with tempfile.TemporaryDirectory() as td:
            r=AstraRepository.init(td)
            _,l,o=self._diverge(r, RepositoryView.create({b'main':OID_B},{b'default':OID_A}), RepositoryView.create({b'main':OID_A,b'release':OID_C},{b'default':OID_C}))
            res=r.reconcile_operation_heads(); self.assertTrue(res.merged)
            v=r.current_view(); self.assertEqual(dict(v.refs),{b'main':OID_B,b'release':OID_C}); self.assertEqual(dict(v.workspace_heads),{b'default':OID_C})
            op=r.get(__import__('astra_codec').ObjectType.OPERATION,res.operation_id); self.assertEqual(op.parents,tuple(sorted((l.operation_id,o.operation_id))))
    def test_conflicting_ref_is_persisted_and_head_not_moved(self):
        with tempfile.TemporaryDirectory() as td:
            r=AstraRepository.init(td)
            _,l,_=self._diverge(r, RepositoryView.create({b'main':OID_B},{b'default':OID_A}), RepositoryView.create({b'main':OID_C},{b'default':OID_A}))
            before=r.operation_head(); res=r.reconcile_operation_heads(); self.assertFalse(res.merged); self.assertEqual(r.operation_head(),before)
            doc=json.loads(Path(res.conflict_path).read_text()); self.assertEqual(doc['conflicts'][0]['kind'],'ref'); self.assertEqual(doc['conflicts'][0]['name_hex'],b'main'.hex())
    def test_three_tips_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            r=AstraRepository.init(td); base=RepositoryView.create({b'main':OID_A}); r.put(base); b=Operation((),base.view_id,b'base'); r.put(b)
            from astra_repository import _atomic_replace
            _atomic_replace(r,r.metadata_root/'state'/'operation-head',(b.operation_id+'\n').encode())
            for i,oid in enumerate((OID_A,OID_B,OID_C)):
                v=RepositoryView.create({b'main':oid,b'x'+bytes([48+i]):oid}); r.put(v); r.put(Operation((b.operation_id,),v.view_id,b'x'+bytes([48+i])))
            with self.assertRaises(StateCorruptionError): r.reconcile_operation_heads()
if __name__=='__main__': unittest.main()

class OperationReconcileResolutionTests(OperationReconcileTests):
    def test_manual_resolution_publishes_two_parent_operation(self):
        with tempfile.TemporaryDirectory() as td:
            r=AstraRepository.init(td)
            _,l,o=self._diverge(r, RepositoryView.create({b'main':OID_B},{b'default':OID_A}), RepositoryView.create({b'main':OID_C},{b'default':OID_A}))
            pending=r.reconcile_operation_heads(); self.assertIsNotNone(pending.conflict_path)
            result=r.resolve_operation_reconcile({('ref',b'main'):OID_C}); self.assertTrue(result.merged)
            self.assertEqual(dict(r.current_view().refs)[b'main'],OID_C)
            op=r.get(__import__('astra_codec').ObjectType.OPERATION,result.operation_id)
            self.assertEqual(set(op.parents),{l.operation_id,o.operation_id})
            self.assertFalse(Path(pending.conflict_path).exists())
    def test_resolution_requires_exact_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            r=AstraRepository.init(td)
            self._diverge(r, RepositoryView.create({b'main':OID_B},{b'default':OID_A}), RepositoryView.create({b'main':OID_C},{b'default':OID_A}))
            r.reconcile_operation_heads()
            with self.assertRaises(StateCorruptionError): r.resolve_operation_reconcile({})
    def test_resolution_rejects_stale_head(self):
        with tempfile.TemporaryDirectory() as td:
            r=AstraRepository.init(td)
            self._diverge(r, RepositoryView.create({b'main':OID_B},{b'default':OID_A}), RepositoryView.create({b'main':OID_C},{b'default':OID_A}))
            r.reconcile_operation_heads()
            # Publish unrelated state to move the head away from both recorded tips.
            current=r.operation_head(); view=r.current_view(); r.publish_view(view,b'unrelated',expected_head=current)
            with self.assertRaises(Exception): r.resolve_operation_reconcile({('ref',b'main'):OID_B})
