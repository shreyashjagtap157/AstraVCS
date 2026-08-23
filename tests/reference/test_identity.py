import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_identity import OrganizationStore
from astra_security import TokenStore,Principal
class IdentityTests(unittest.TestCase):
 def test_org_team_repo_roles_generate_least_privilege_grants(self):
  with tempfile.TemporaryDirectory() as td:
   store=OrganizationStore(Path(td)/'org.db');tokens=TokenStore(Path(td)/'tok.db')
   try:
    org=store.create_org('Acme');store.add_member(org.org_id,'alice','read');store.bind_repo('repo',org.org_id);team=store.create_team(org.org_id,'dev');store.add_team_member(team,'alice');store.set_repo_role('repo','team',team,'write')
    grants=store.grants_for('alice','repo');self.assertTrue(any(g.capability=='repo.write' for g in grants));self.assertFalse(any(g.capability=='*' for g in grants))
    tok=tokens.issue(Principal('alice','human'),list(grants),ttl_seconds=None);self.assertEqual(tokens.require(tok,'repo.write','repo').principal_id,'alice')
   finally:tokens.close();store.close()
 def test_admin_role_is_explicit_and_public_repo_gets_read_only(self):
  with tempfile.TemporaryDirectory() as td:
   s=OrganizationStore(Path(td)/'org.db')
   try:
    o=s.create_org('O');s.bind_repo('public',o.org_id,'public');self.assertEqual(s.effective_role('outsider','public'),'read');s.add_member(o.org_id,'root','admin');self.assertEqual(s.effective_role('root','public'),'admin')
   finally:s.close()
if __name__=='__main__':unittest.main()
