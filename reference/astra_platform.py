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
  CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, repo TEXT,target_ref TEXT,target_revision TEXT,source_revision TEXT,status TEXT,created_by TEXT,created_at INTEGER,draft INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT,reviewer TEXT,state TEXT,body TEXT,created_at INTEGER);
  CREATE TABLE IF NOT EXISTS checks(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT,name TEXT,status TEXT,conclusion TEXT,details TEXT,updated_at INTEGER,UNIQUE(proposal_id,name));
  CREATE TABLE IF NOT EXISTS check_evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT NOT NULL,name TEXT NOT NULL,status TEXT,conclusion TEXT,details TEXT,updated_at INTEGER NOT NULL,source_revision TEXT NOT NULL,UNIQUE(proposal_id,name,source_revision));
  CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,type TEXT,repo TEXT,actor TEXT,payload TEXT,created_at INTEGER);
  CREATE TABLE IF NOT EXISTS issues(id INTEGER PRIMARY KEY AUTOINCREMENT,repo TEXT,title TEXT,body TEXT,state TEXT,created_by TEXT,created_at INTEGER,updated_at INTEGER);
  CREATE TABLE IF NOT EXISTS issue_comments(id INTEGER PRIMARY KEY AUTOINCREMENT,issue_id INTEGER,author TEXT,body TEXT,created_at INTEGER);
  CREATE TABLE IF NOT EXISTS review_threads(id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL,revision_id TEXT NOT NULL,node_id TEXT NOT NULL,path_hex TEXT NOT NULL,line_start INTEGER,line_end INTEGER,state TEXT NOT NULL,author TEXT NOT NULL,created_at INTEGER NOT NULL,resolved_by TEXT,resolved_at INTEGER);
  CREATE TABLE IF NOT EXISTS review_thread_comments(id INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,author TEXT NOT NULL,body TEXT NOT NULL,created_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS proposal_reviewers(proposal_id TEXT NOT NULL,subject_kind TEXT NOT NULL,subject TEXT NOT NULL,state TEXT NOT NULL,requested_by TEXT NOT NULL,requested_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,PRIMARY KEY(proposal_id,subject_kind,subject));
  CREATE TABLE IF NOT EXISTS merge_queue(id INTEGER PRIMARY KEY AUTOINCREMENT,repo TEXT NOT NULL,target_ref TEXT NOT NULL,proposal_id TEXT NOT NULL UNIQUE,source_revision TEXT NOT NULL,state TEXT NOT NULL,enqueued_by TEXT NOT NULL,enqueued_at INTEGER NOT NULL,updated_at INTEGER NOT NULL);
  CREATE INDEX IF NOT EXISTS merge_queue_order ON merge_queue(repo,target_ref,state,id);
  ''')
  proposal_cols={r['name'] for r in self.db.execute('PRAGMA table_info(proposals)')}
  if 'draft' not in proposal_cols:self.db.execute('ALTER TABLE proposals ADD COLUMN draft INTEGER NOT NULL DEFAULT 0')
  review_cols={r['name'] for r in self.db.execute('PRAGMA table_info(reviews)')}
  if 'source_revision' not in review_cols:self.db.execute('ALTER TABLE reviews ADD COLUMN source_revision TEXT')
  check_cols={r['name'] for r in self.db.execute('PRAGMA table_info(checks)')}
  if 'source_revision' not in check_cols:self.db.execute('ALTER TABLE checks ADD COLUMN source_revision TEXT')
  self.db.execute('UPDATE reviews SET source_revision=(SELECT source_revision FROM proposals WHERE proposals.id=reviews.proposal_id) WHERE source_revision IS NULL')
  self.db.execute('UPDATE checks SET source_revision=(SELECT source_revision FROM proposals WHERE proposals.id=checks.proposal_id) WHERE source_revision IS NULL')
  self.db.execute('INSERT OR IGNORE INTO check_evidence(proposal_id,name,status,conclusion,details,updated_at,source_revision) SELECT proposal_id,name,status,conclusion,details,updated_at,source_revision FROM checks WHERE source_revision IS NOT NULL')
  self.db.commit()
 def close(self): self.db.close()
 def emit(self,event_type,repo,actor,payload):
  cur=self.db.execute('INSERT INTO events(type,repo,actor,payload,created_at) VALUES(?,?,?,?,?)',(event_type,repo,actor,json.dumps(payload,sort_keys=True,separators=(',',':')),int(time.time())));self.db.commit();return cur.lastrowid
 def open_proposal(self,repo,target_ref,source_revision,actor,target_revision=None,draft=False):
  pid=str(uuid.uuid4());now=int(time.time());self.db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?)',(pid,repo,target_ref,target_revision,source_revision,'open',actor,now,1 if draft else 0));self.db.commit();self.emit('proposal.opened',repo,actor,{'proposal_id':pid,'target_ref':target_ref,'target_revision':target_revision,'source_revision':source_revision,'draft':bool(draft)});return pid
 def get_proposal(self,pid):
  r=self.db.execute('SELECT * FROM proposals WHERE id=?',(pid,)).fetchone();return None if r is None else dict(r)
 def list_proposals(self,repo,status='open'):
  return [dict(x) for x in self.db.execute('SELECT * FROM proposals WHERE repo=? AND status=? ORDER BY created_at,id',(repo,status))]
 def list_proposals_page(self,repo,status='open',after_created=-1,after_id='',limit=100):
  if limit<1 or limit>100:raise PlatformError('limit must be between 1 and 100')
  return [dict(x) for x in self.db.execute('SELECT * FROM proposals WHERE repo=? AND status=? AND (created_at>? OR (created_at=? AND id>?)) ORDER BY created_at,id LIMIT ?',(repo,status,after_created,after_created,after_id,limit))]
 def set_proposal_draft(self,pid,actor,draft):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  if p['status']!='open':raise PlatformError('proposal is not open')
  self.db.execute('UPDATE proposals SET draft=? WHERE id=?',(1 if draft else 0,pid));self.db.commit();self.emit('proposal.'+('drafted' if draft else 'ready'),p['repo'],actor,{'proposal_id':pid});return self.get_proposal(pid)
 def update_proposal_source(self,pid,source_revision,actor,expected_old=None):
  validate_object_id(source_revision,'RevisionID');p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  if p['status']!='open':raise PlatformError('proposal is not open')
  if expected_old is not None and p['source_revision']!=expected_old:raise PlatformError('proposal source advanced')
  now=int(time.time())
  if expected_old is None:updated=self.db.execute('UPDATE proposals SET source_revision=? WHERE id=? AND status=?',(source_revision,pid,'open'))
  else:updated=self.db.execute('UPDATE proposals SET source_revision=? WHERE id=? AND status=? AND source_revision=?',(source_revision,pid,'open',expected_old))
  if updated.rowcount!=1:
   self.db.rollback();raise PlatformError('proposal source advanced')
  cur=self.db.execute("UPDATE proposal_reviewers SET state='requested',updated_at=? WHERE proposal_id=? AND state='fulfilled'",(now,pid));self.db.commit();self.emit('proposal.source.updated',p['repo'],actor,{'proposal_id':pid,'old_source_revision':p['source_revision'],'source_revision':source_revision,'re_requested_reviewers':cur.rowcount});return self.get_proposal(pid)
 def request_reviewers(self,pid,actor,principals=(),teams=()):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  items=[('principal',x) for x in principals]+[('team',x) for x in teams]
  if not items:raise PlatformError('at least one reviewer is required')
  if any(not x or len(x)>256 for _,x in items):raise PlatformError('invalid reviewer subject')
  now=int(time.time())
  for kind,subject in items:self.db.execute("INSERT INTO proposal_reviewers(proposal_id,subject_kind,subject,state,requested_by,requested_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(proposal_id,subject_kind,subject) DO UPDATE SET state='requested',requested_by=excluded.requested_by,requested_at=excluded.requested_at,updated_at=excluded.updated_at",(pid,kind,subject,'requested',actor,now,now))
  self.db.commit();self.emit('review.requested',p['repo'],actor,{'proposal_id':pid,'reviewers':list(principals),'teams':list(teams)});return self.list_requested_reviewers(pid)
 def remove_requested_reviewers(self,pid,actor,principals=(),teams=()):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  items=[('principal',x) for x in principals]+[('team',x) for x in teams]
  if not items:raise PlatformError('at least one reviewer is required')
  now=int(time.time())
  for kind,subject in items:self.db.execute("UPDATE proposal_reviewers SET state='removed',updated_at=? WHERE proposal_id=? AND subject_kind=? AND subject=?",(now,pid,kind,subject))
  self.db.commit();self.emit('review.request.removed',p['repo'],actor,{'proposal_id':pid,'reviewers':list(principals),'teams':list(teams)});return self.list_requested_reviewers(pid)
 def list_requested_reviewers(self,pid,state=None):
  if not self.get_proposal(pid):raise PlatformError('proposal not found')
  if state is None:rows=self.db.execute('SELECT * FROM proposal_reviewers WHERE proposal_id=? ORDER BY subject_kind,subject',(pid,))
  else:
   if state not in ('requested','fulfilled','removed'):raise PlatformError('invalid reviewer request state')
   rows=self.db.execute('SELECT * FROM proposal_reviewers WHERE proposal_id=? AND state=? ORDER BY subject_kind,subject',(pid,state))
  return [dict(x) for x in rows]
 def add_review(self,pid,reviewer,state,body='',reviewer_teams=()):
  if state not in ('approved','changes_requested','commented'):raise PlatformError('invalid review state')
  p=self.db.execute('SELECT repo,source_revision FROM proposals WHERE id=?',(pid,)).fetchone()
  if not p:raise PlatformError('proposal not found')
  now=int(time.time());self.db.execute('INSERT INTO reviews(proposal_id,reviewer,state,body,created_at,source_revision) VALUES(?,?,?,?,?,?)',(pid,reviewer,state,body,now,p['source_revision']));cur=self.db.execute("UPDATE proposal_reviewers SET state='fulfilled',updated_at=? WHERE proposal_id=? AND subject_kind='principal' AND subject=? AND state='requested'",(now,pid,reviewer));team_count=0
  for team in reviewer_teams:team_count+=self.db.execute("UPDATE proposal_reviewers SET state='fulfilled',updated_at=? WHERE proposal_id=? AND subject_kind='team' AND subject=? AND state='requested'",(now,pid,team)).rowcount
  self.db.commit();self.emit('review.submitted',p['repo'],reviewer,{'proposal_id':pid,'state':state})
  if cur.rowcount or team_count:self.emit('review.request.fulfilled',p['repo'],reviewer,{'proposal_id':pid,'reviewer':reviewer,'teams':list(reviewer_teams)})
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
  p=self.db.execute('SELECT repo,source_revision FROM proposals WHERE id=?',(pid,)).fetchone()
  if not p:raise PlatformError('proposal not found')
  self.db.execute('INSERT INTO check_evidence(proposal_id,name,status,conclusion,details,updated_at,source_revision) VALUES(?,?,?,?,?,?,?) ON CONFLICT(proposal_id,name,source_revision) DO UPDATE SET status=excluded.status,conclusion=excluded.conclusion,details=excluded.details,updated_at=excluded.updated_at',(pid,name,status,conclusion,details,int(time.time()),p['source_revision']));self.db.commit();self.emit('check.updated',p['repo'],'check:'+name,{'proposal_id':pid,'status':status,'conclusion':conclusion,'source_revision':p['source_revision']})
 def policy_evidence(self,pid):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  reviews=[dict(x) for x in self.db.execute('SELECT * FROM reviews WHERE proposal_id=? AND source_revision=? ORDER BY created_at,id',(pid,p['source_revision']))]
  checks={x['name']:dict(x) for x in self.db.execute('SELECT * FROM check_evidence WHERE proposal_id=? AND source_revision=?',(pid,p['source_revision']))}
  return {'reviews':reviews,'checks':checks}
 def evidence_history(self,pid):
  if not self.get_proposal(pid):raise PlatformError('proposal not found')
  reviews=[dict(x) for x in self.db.execute('SELECT * FROM reviews WHERE proposal_id=? ORDER BY created_at,id',(pid,))]
  checks=[dict(x) for x in self.db.execute('SELECT * FROM check_evidence WHERE proposal_id=? ORDER BY updated_at,id',(pid,))]
  return {'reviews':reviews,'checks':checks}
 def require_policy(self,pid,policy):
  evidence=self.policy_evidence(pid);latest={}
  for r in evidence['reviews']:latest[r['reviewer']]=r['state']
  if getattr(policy,'block_changes_requested',False) and any(state=='changes_requested' for state in latest.values()):raise PlatformError('proposal has outstanding changes requested')
  approvals=sum(1 for state in latest.values() if state=='approved')
  if approvals<policy.required_reviews:raise PlatformError(f'proposal requires {policy.required_reviews} approvals; has {approvals}')
  for name in policy.required_checks:
   c=evidence['checks'].get(name)
   if not c or c.get('status')!='completed' or c.get('conclusion')!='success':raise PlatformError(f'required check {name} has not succeeded')
  if getattr(policy,'require_resolved_threads',False):
   p=self.get_proposal(pid);open_current=[t for t in self.list_review_threads(pid,'open') if t['revision_id']==p['source_revision']]
   if open_current:raise PlatformError(f'proposal has {len(open_current)} unresolved review threads')
  if getattr(policy,'require_requested_reviewers',False):
   outstanding=self.list_requested_reviewers(pid,'requested')
   if outstanding:raise PlatformError(f'proposal has {len(outstanding)} outstanding requested reviewers')
  return True
 def close_proposal(self,pid,actor,state='merged'):
  p=self.db.execute('SELECT repo FROM proposals WHERE id=?',(pid,)).fetchone()
  if not p:raise PlatformError('proposal not found')
  self.db.execute('UPDATE proposals SET status=? WHERE id=?',(state,pid));self.db.commit();self.emit('proposal.'+state,p['repo'],actor,{'proposal_id':pid})


 def enqueue_merge(self,pid,actor):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  if p['status']!='open':raise PlatformError('proposal is not open')
  if p.get('draft'):raise PlatformError('draft proposal cannot enter merge queue')
  now=int(time.time())
  try:self.db.execute("INSERT INTO merge_queue(repo,target_ref,proposal_id,source_revision,state,enqueued_by,enqueued_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(p['repo'],p['target_ref'],pid,p['source_revision'],'queued',actor,now,now));self.db.commit()
  except sqlite3.IntegrityError as exc:self.db.rollback();raise PlatformError('proposal is already queued') from exc
  self.emit('merge_queue.enqueued',p['repo'],actor,{'proposal_id':pid,'source_revision':p['source_revision'],'target_ref':p['target_ref']});return self.merge_queue_entry(pid)
 def merge_queue_entry(self,pid):
  r=self.db.execute('SELECT * FROM merge_queue WHERE proposal_id=?',(pid,)).fetchone();return None if r is None else dict(r)
 def list_merge_queue(self,repo,target_ref=None,state='queued'):
  if state not in ('queued','merged','cancelled','stale'):raise PlatformError('invalid merge queue state')
  if target_ref is None:rows=self.db.execute('SELECT * FROM merge_queue WHERE repo=? AND state=? ORDER BY id',(repo,state))
  else:rows=self.db.execute('SELECT * FROM merge_queue WHERE repo=? AND target_ref=? AND state=? ORDER BY id',(repo,target_ref,state))
  return [dict(x) for x in rows]
 def cancel_merge(self,pid,actor,state='cancelled'):
  if state not in ('cancelled','stale','merged'):raise PlatformError('invalid merge queue terminal state')
  row=self.merge_queue_entry(pid)
  if not row or row['state']!='queued':raise PlatformError('proposal is not queued')
  self.db.execute('UPDATE merge_queue SET state=?,updated_at=? WHERE proposal_id=? AND state=?',(state,int(time.time()),pid,'queued'));self.db.commit();self.emit('merge_queue.'+state,row['repo'],actor,{'proposal_id':pid,'target_ref':row['target_ref']});return self.merge_queue_entry(pid)
 def merge_queue_head(self,repo,target_ref):
  r=self.db.execute("SELECT * FROM merge_queue WHERE repo=? AND target_ref=? AND state='queued' ORDER BY id LIMIT 1",(repo,target_ref)).fetchone();return None if r is None else dict(r)

 def create_issue(self,repo,title,body,actor):
  if not title or len(title)>4096:raise PlatformError('invalid issue title')
  now=int(time.time());cur=self.db.execute('INSERT INTO issues(repo,title,body,state,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(repo,title,body,'open',actor,now,now));self.db.commit();iid=cur.lastrowid;self.emit('issue.opened',repo,actor,{'issue_id':iid,'title':title});return iid
 def get_issue(self,iid):
  r=self.db.execute('SELECT * FROM issues WHERE id=?',(iid,)).fetchone();return None if r is None else dict(r)
 def list_issues(self,repo,state='open'):
  return [dict(x) for x in self.db.execute('SELECT * FROM issues WHERE repo=? AND state=? ORDER BY created_at,id',(repo,state))]
 def list_issues_page(self,repo,state='open',after=0,limit=100):
  if limit<1 or limit>100:raise PlatformError('limit must be between 1 and 100')
  return [dict(x) for x in self.db.execute('SELECT * FROM issues WHERE repo=? AND state=? AND id>? ORDER BY id LIMIT ?',(repo,state,after,limit))]
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
