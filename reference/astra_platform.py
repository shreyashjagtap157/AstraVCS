"""Durable non-canonical collaboration metadata for AstraVCS."""
from __future__ import annotations
from pathlib import Path
import json,sqlite3,time,uuid
from astra_model import validate_object_id,validate_node_id,validate_path

class PlatformError(RuntimeError):pass
class CollaborationStore:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path,check_same_thread=False);self.db.row_factory=sqlite3.Row
  self.db.executescript('''
  PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
  CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, repo TEXT,target_ref TEXT,target_revision TEXT,source_revision TEXT,status TEXT,created_by TEXT,created_at INTEGER);
  CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT,reviewer TEXT,state TEXT,body TEXT,created_at INTEGER);
  CREATE TABLE IF NOT EXISTS checks(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT,name TEXT,status TEXT,conclusion TEXT,details TEXT,updated_at INTEGER,UNIQUE(proposal_id,name));
  CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,type TEXT,repo TEXT,actor TEXT,payload TEXT,created_at INTEGER);
  CREATE TABLE IF NOT EXISTS issues(id INTEGER PRIMARY KEY AUTOINCREMENT,repo TEXT,title TEXT,body TEXT,state TEXT,created_by TEXT,created_at INTEGER,updated_at INTEGER);
  CREATE TABLE IF NOT EXISTS issue_comments(id INTEGER PRIMARY KEY AUTOINCREMENT,issue_id INTEGER,author TEXT,body TEXT,created_at INTEGER);
  CREATE TABLE IF NOT EXISTS review_threads(id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL,revision_id TEXT NOT NULL,node_id TEXT NOT NULL,path_hex TEXT NOT NULL,line_start INTEGER,line_end INTEGER,state TEXT NOT NULL,author TEXT NOT NULL,created_at INTEGER NOT NULL,resolved_by TEXT,resolved_at INTEGER);
  CREATE TABLE IF NOT EXISTS review_thread_comments(id INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,author TEXT NOT NULL,body TEXT NOT NULL,created_at INTEGER NOT NULL);
  ''');self.db.commit()
 def close(self): self.db.close()
 def emit(self,event_type,repo,actor,payload):
  cur=self.db.execute('INSERT INTO events(type,repo,actor,payload,created_at) VALUES(?,?,?,?,?)',(event_type,repo,actor,json.dumps(payload,sort_keys=True,separators=(',',':')),int(time.time())));self.db.commit();return cur.lastrowid
 def open_proposal(self,repo,target_ref,source_revision,actor,target_revision=None):
  pid=str(uuid.uuid4());now=int(time.time());self.db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)',(pid,repo,target_ref,target_revision,source_revision,'open',actor,now));self.db.commit();self.emit('proposal.opened',repo,actor,{'proposal_id':pid,'target_ref':target_ref,'target_revision':target_revision,'source_revision':source_revision});return pid
 def get_proposal(self,pid):
  r=self.db.execute('SELECT * FROM proposals WHERE id=?',(pid,)).fetchone();return None if r is None else dict(r)
 def list_proposals(self,repo,status='open'):
  return [dict(x) for x in self.db.execute('SELECT * FROM proposals WHERE repo=? AND status=? ORDER BY created_at,id',(repo,status))]
 def add_review(self,pid,reviewer,state,body=''):
  if state not in ('approved','changes_requested','commented'):raise PlatformError('invalid review state')
  p=self.db.execute('SELECT repo FROM proposals WHERE id=?',(pid,)).fetchone()
  if not p:raise PlatformError('proposal not found')
  self.db.execute('INSERT INTO reviews(proposal_id,reviewer,state,body,created_at) VALUES(?,?,?,?,?)',(pid,reviewer,state,body,int(time.time())));self.db.commit();self.emit('review.submitted',p['repo'],reviewer,{'proposal_id':pid,'state':state})
 def create_review_thread(self,pid,revision_id,node_id,path,author,body,line_start=None,line_end=None):
  proposal=self.get_proposal(pid)
  if not proposal:raise PlatformError('proposal not found')
  validate_object_id(revision_id,'RevisionID');validate_node_id(node_id);validate_path(path)
  if not body:raise PlatformError('review thread body must not be empty')
  if line_start is not None and line_start<1:raise PlatformError('line_start must be positive')
  if line_end is not None and (line_start is None or line_end<line_start):raise PlatformError('line_end must be >= line_start')
  tid=str(uuid.uuid4());now=int(time.time())
  self.db.execute('INSERT INTO review_threads VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,pid,revision_id,node_id,path.hex(),line_start,line_end,'open',author,now,None,None));self.db.commit()
  cid=self.add_review_thread_comment(tid,author,body,emit=False);self.emit('review.thread.opened',proposal['repo'],author,{'proposal_id':pid,'thread_id':tid,'comment_id':cid,'revision_id':revision_id,'node_id':node_id,'path_hex':path.hex()});return tid
 def get_review_thread(self,tid):
  r=self.db.execute('SELECT * FROM review_threads WHERE id=?',(tid,)).fetchone();return None if r is None else dict(r)
 def list_review_threads(self,pid,state=None):
  if not self.get_proposal(pid):raise PlatformError('proposal not found')
  if state is None:rows=self.db.execute('SELECT * FROM review_threads WHERE proposal_id=? ORDER BY created_at,id',(pid,))
  else:
   if state not in ('open','resolved'):raise PlatformError('invalid thread state')
   rows=self.db.execute('SELECT * FROM review_threads WHERE proposal_id=? AND state=? ORDER BY created_at,id',(pid,state))
  return [dict(x) for x in rows]
 def add_review_thread_comment(self,tid,author,body,emit=True):
  if not body:raise PlatformError('review thread comment must not be empty')
  thread=self.get_review_thread(tid)
  if not thread:raise PlatformError('review thread not found')
  proposal=self.get_proposal(thread['proposal_id']);now=int(time.time());cur=self.db.execute('INSERT INTO review_thread_comments(thread_id,author,body,created_at) VALUES(?,?,?,?)',(tid,author,body,now));self.db.commit();cid=cur.lastrowid
  if emit:self.emit('review.thread.comment',proposal['repo'],author,{'proposal_id':thread['proposal_id'],'thread_id':tid,'comment_id':cid})
  return cid
 def review_thread_comments(self,tid):
  if not self.get_review_thread(tid):raise PlatformError('review thread not found')
  return [dict(x) for x in self.db.execute('SELECT * FROM review_thread_comments WHERE thread_id=? ORDER BY created_at,id',(tid,))]
 def resolve_review_thread(self,tid,actor,resolved=True):
  thread=self.get_review_thread(tid)
  if not thread:raise PlatformError('review thread not found')
  proposal=self.get_proposal(thread['proposal_id']);state='resolved' if resolved else 'open';now=int(time.time())
  self.db.execute('UPDATE review_threads SET state=?,resolved_by=?,resolved_at=? WHERE id=?',(state,actor if resolved else None,now if resolved else None,tid));self.db.commit()
  self.emit('review.thread.'+('resolved' if resolved else 'reopened'),proposal['repo'],actor,{'proposal_id':thread['proposal_id'],'thread_id':tid});return self.get_review_thread(tid)
 def set_check(self,pid,name,status,conclusion=None,details=''):
  p=self.db.execute('SELECT repo FROM proposals WHERE id=?',(pid,)).fetchone()
  if not p:raise PlatformError('proposal not found')
  self.db.execute('INSERT INTO checks(proposal_id,name,status,conclusion,details,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(proposal_id,name) DO UPDATE SET status=excluded.status,conclusion=excluded.conclusion,details=excluded.details,updated_at=excluded.updated_at',(pid,name,status,conclusion,details,int(time.time())));self.db.commit();self.emit('check.updated',p['repo'],'check:'+name,{'proposal_id':pid,'status':status,'conclusion':conclusion})
 def policy_evidence(self,pid):
  reviews=[dict(x) for x in self.db.execute('SELECT * FROM reviews WHERE proposal_id=?',(pid,))]
  checks={x['name']:dict(x) for x in self.db.execute('SELECT * FROM checks WHERE proposal_id=?',(pid,))}
  return {'reviews':reviews,'checks':checks}
 def require_policy(self,pid,policy):
  evidence=self.policy_evidence(pid);latest={}
  for r in evidence['reviews']:latest[r['reviewer']]=r['state']
  approvals=sum(1 for state in latest.values() if state=='approved')
  if approvals<policy.required_reviews:raise PlatformError(f'proposal requires {policy.required_reviews} approvals; has {approvals}')
  for name in policy.required_checks:
   c=evidence['checks'].get(name)
   if not c or c.get('status')!='completed' or c.get('conclusion')!='success':raise PlatformError(f'required check {name} has not succeeded')
  return True
 def close_proposal(self,pid,actor,state='merged'):
  p=self.db.execute('SELECT repo FROM proposals WHERE id=?',(pid,)).fetchone()
  if not p:raise PlatformError('proposal not found')
  self.db.execute('UPDATE proposals SET status=? WHERE id=?',(state,pid));self.db.commit();self.emit('proposal.'+state,p['repo'],actor,{'proposal_id':pid})

 def create_issue(self,repo,title,body,actor):
  if not title or len(title)>4096:raise PlatformError('invalid issue title')
  now=int(time.time());cur=self.db.execute('INSERT INTO issues(repo,title,body,state,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(repo,title,body,'open',actor,now,now));self.db.commit();iid=cur.lastrowid;self.emit('issue.opened',repo,actor,{'issue_id':iid,'title':title});return iid
 def get_issue(self,iid):
  r=self.db.execute('SELECT * FROM issues WHERE id=?',(iid,)).fetchone();return None if r is None else dict(r)
 def list_issues(self,repo,state='open'):
  return [dict(x) for x in self.db.execute('SELECT * FROM issues WHERE repo=? AND state=? ORDER BY created_at,id',(repo,state))]
 def add_issue_comment(self,iid,author,body):
  if not body:raise PlatformError('issue comment must not be empty')
  issue=self.get_issue(iid)
  if not issue:raise PlatformError('issue not found')
  now=int(time.time());cur=self.db.execute('INSERT INTO issue_comments(issue_id,author,body,created_at) VALUES(?,?,?,?)',(iid,author,body,now));self.db.execute('UPDATE issues SET updated_at=? WHERE id=?',(now,iid));self.db.commit();cid=cur.lastrowid;self.emit('issue.comment',issue['repo'],author,{'issue_id':iid,'comment_id':cid});return cid
 def issue_comments(self,iid):
  if not self.get_issue(iid):raise PlatformError('issue not found')
  return [dict(x) for x in self.db.execute('SELECT * FROM issue_comments WHERE issue_id=? ORDER BY created_at,id',(iid,))]
 def close_issue(self,iid,actor):
  issue=self.get_issue(iid)
  if not issue:raise PlatformError('issue not found')
  if issue['state']=='closed':return
  now=int(time.time());self.db.execute('UPDATE issues SET state=?,updated_at=? WHERE id=?',('closed',now,iid));self.db.commit();self.emit('issue.closed',issue['repo'],actor,{'issue_id':iid})
 def events(self,after=0,limit=100):
  return [dict(x) for x in self.db.execute('SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?',(after,limit))]
