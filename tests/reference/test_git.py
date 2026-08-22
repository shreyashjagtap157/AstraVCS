import os,sys,tempfile,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_git import import_git,export_git,GitInteropError

def g(root,*args,env=None,input=None):
    e=os.environ.copy();e.update({'GIT_AUTHOR_NAME':'Alice','GIT_AUTHOR_EMAIL':'a@example.com','GIT_COMMITTER_NAME':'Alice','GIT_COMMITTER_EMAIL':'a@example.com','GIT_AUTHOR_DATE':'1700000000 +0530','GIT_COMMITTER_DATE':'1700000000 +0530'});e.update(env or {})
    return subprocess.run(['git','-C',str(root),*args],input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,env=e).stdout
class GitTests(unittest.TestCase):
    def make_repo(self,root):
        g(root,'init','-q');g(root,'config','user.name','Alice');g(root,'config','user.email','a@example.com')
        (root/'a.txt').write_bytes(b'one\n');g(root,'add','a.txt');g(root,'commit','-q','-m','initial')
        if os.name!='nt': os.chmod(root/'a.txt',0o755)
        (root/'b').write_bytes(b'two\n');g(root,'add','-A');g(root,'commit','-q','-m','second')
    def test_import_export_strict_roundtrip(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b,tempfile.TemporaryDirectory() as c:
            src=Path(a);self.make_repo(src); originals=g(src,'rev-list','--all').splitlines()
            ar=AstraRepository.init(b);r=import_git(src,ar);self.assertEqual(r.commits,2)
            e=export_git(ar,c,strict=True);self.assertEqual(e.commits,2)
            rebuilt=g(Path(c),'rev-list','--all').splitlines();self.assertEqual(set(rebuilt),set(originals))
    def test_import_merge_topology(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            src=Path(a);self.make_repo(src);g(src,'checkout','-q','-b','side','HEAD~1');(src/'side').write_text('s');g(src,'add','side');g(src,'commit','-q','-m','side');g(src,'checkout','-q','master');g(src,'merge','-q','--no-ff','side','-m','merge')
            ar=AstraRepository.init(b);r=import_git(src,ar);self.assertEqual(r.commits,4)
    def test_reject_gitlink(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            src=Path(a);g(src,'init','-q');blob='0'*40
            # Use update-index cacheinfo with commit-looking object requires valid OID; create nested repo commit object then insert.
            commit=g(src,'hash-object','-t','commit','-w','--stdin',input=b'tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904\nauthor A <a@x> 1 +0000\ncommitter A <a@x> 1 +0000\n\nx').strip().decode()
            g(src,'update-index','--add','--cacheinfo',f'160000,{commit},sub');g(src,'commit','-q','-m','sub')
            ar=AstraRepository.init(b)
            with self.assertRaisesRegex(GitInteropError,'gitlinks'):import_git(src,ar)
if __name__=='__main__':unittest.main()
