"""Disposable content/symbol search index for AstraVCS repositories."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re,sqlite3
from astra_codec import ObjectType
from astra_repository import AstraRepository,SemanticObjectNotFoundError

class SearchError(RuntimeError):pass
@dataclass(frozen=True)
class SearchHit:revision:str;path:bytes;content_id:str;snippet:str
@dataclass(frozen=True)
class SymbolHit:revision:str;path:bytes;name:str;kind:str;line:int

_SYMBOL_PATTERNS=(
 ('function',re.compile(r'^\s*(?:def|fn|function)\s+([A-Za-z_][A-Za-z0-9_]*)',re.M)),
 ('class',re.compile(r'^\s*(?:class|struct|enum|trait|interface)\s+([A-Za-z_][A-Za-z0-9_]*)',re.M)),
)
class SearchIndex:
 def __init__(self,repo:AstraRepository,path=None):
  self.repo=repo;self.path=Path(path or repo.meta/'indexes'/'search.sqlite');self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row
  self.db.executescript('''PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;
  CREATE TABLE IF NOT EXISTS contents(content_id TEXT PRIMARY KEY,text TEXT NOT NULL);
  CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(content_id UNINDEXED,text,tokenize='unicode61');
  CREATE TABLE IF NOT EXISTS paths(revision TEXT NOT NULL,path BLOB NOT NULL,content_id TEXT NOT NULL,PRIMARY KEY(revision,path));
  CREATE INDEX IF NOT EXISTS paths_content ON paths(content_id,revision);
  CREATE TABLE IF NOT EXISTS symbols(revision TEXT,path BLOB,name TEXT,kind TEXT,line INTEGER,PRIMARY KEY(revision,path,name,kind,line));
  CREATE INDEX IF NOT EXISTS symbol_name ON symbols(name,revision);
  ''');self.db.commit()
 def close(self):self.db.close()
 def clear(self):self.db.executescript('DELETE FROM contents;DELETE FROM content_fts;DELETE FROM paths;DELETE FROM symbols;');self.db.commit()
 def rebuild(self,max_text_bytes=2*1024*1024):
  self.clear();revisions=0;indexed_content=set()
  for typ,oid,_ in self.repo.iter_mappings():
   if typ!=ObjectType.REVISION:continue
   rev=self.repo.get(ObjectType.REVISION,oid);tree=self.repo.get(ObjectType.TREE,rev.tree_id);revisions+=1
   for path,entry in tree.entries:
    if entry.kind!='file' or not entry.content_id:continue
    self.db.execute('INSERT OR REPLACE INTO paths VALUES(?,?,?)',(oid,path,entry.content_id))
    if entry.content_id in indexed_content:continue
    try:data=self.repo.get_content(entry.content_id)
    except SemanticObjectNotFoundError:continue
    if len(data)>max_text_bytes or b'\0' in data:continue
    try:text=data.decode('utf-8')
    except UnicodeDecodeError:continue
    self.db.execute('INSERT OR REPLACE INTO contents VALUES(?,?)',(entry.content_id,text));self.db.execute('INSERT INTO content_fts(content_id,text) VALUES(?,?)',(entry.content_id,text));indexed_content.add(entry.content_id)
   # symbols are revision/path-specific, derived from indexed text.
   for path,entry in tree.entries:
    if entry.content_id not in indexed_content:continue
    row=self.db.execute('SELECT text FROM contents WHERE content_id=?',(entry.content_id,)).fetchone();text=row['text'] if row else ''
    for kind,pat in _SYMBOL_PATTERNS:
     for m in pat.finditer(text):
      line=text.count('\n',0,m.start())+1;self.db.execute('INSERT OR IGNORE INTO symbols VALUES(?,?,?,?,?)',(oid,path,m.group(1),kind,line))
  self.db.commit();return {'revisions':revisions,'contents':len(indexed_content)}
 def search(self,query,*,revision=None,limit=50):
  if not query or len(query)>512 or limit<1 or limit>500:raise SearchError('invalid search query/limit')
  sql='''SELECT p.revision,p.path,p.content_id,snippet(content_fts,1,'[',']','…',12) AS snippet FROM content_fts JOIN paths p ON p.content_id=content_fts.content_id WHERE content_fts MATCH ?''';args=[query]
  if revision is not None:sql+=' AND p.revision=?';args.append(revision)
  sql+=' ORDER BY p.revision,p.path LIMIT ?';args.append(limit)
  return tuple(SearchHit(r['revision'],r['path'],r['content_id'],r['snippet']) for r in self.db.execute(sql,args))
 def symbols(self,name,*,revision=None,limit=50):
  if not name or len(name)>256:raise SearchError('invalid symbol query')
  sql='SELECT * FROM symbols WHERE name=?';args=[name]
  if revision is not None:sql+=' AND revision=?';args.append(revision)
  sql+=' ORDER BY revision,path,line LIMIT ?';args.append(limit)
  return tuple(SymbolHit(r['revision'],r['path'],r['name'],r['kind'],r['line']) for r in self.db.execute(sql,args))
