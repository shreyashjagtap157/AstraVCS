"""Minimal MCP/JSON-RPC adapter exposing permission-safe Astra context tools."""
from __future__ import annotations
from astra_ai import RepositoryContextService
class MCPError(RuntimeError):pass
class AstraMCP:
 def __init__(self,repo):self.context=RepositoryContextService(repo)
 def handle(self,request:dict):
  if request.get('jsonrpc')!='2.0':raise MCPError('invalid JSON-RPC version')
  ident=request.get('id');method=request.get('method');params=request.get('params') or {}
  try:
   if method=='tools/list':result={'tools':list(self.context.tools())}
   elif method=='tools/call':
    name=params.get('name');args=params.get('arguments') or {}
    if name=='get_revision':result=self.context.revision(args['revision_id'],include_content=bool(args.get('include_content',False)))
    elif name=='get_history':result=self.context.history(args['revision_id'],int(args.get('limit',20)))
    elif name=='get_change':result=self.context.change(args['change_version_id'])
    elif name=='get_conflict':result=self.context.conflict(args['conflict_id'])
    else:raise MCPError('unknown tool')
   else:raise MCPError('unknown method')
   return {'jsonrpc':'2.0','id':ident,'result':result}
  except Exception as exc:return {'jsonrpc':'2.0','id':ident,'error':{'code':-32000,'message':str(exc)}}
