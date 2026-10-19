export interface DaemonStatusEntry { path_hex:string; state:string }
export interface DaemonStatus { entries:DaemonStatusEntry[]; head:string|null }
export interface DaemonHistoryEntry { revision:string; parents:string[]; tree:string }
export class AstraDaemonApi {
  constructor(private readonly base:string, private readonly token:string) {}
  protected async request<T>(path:string,init:RequestInit={}):Promise<T>{
    const headers=new Headers(init.headers);headers.set('Authorization',`Bearer ${this.token}`);headers.set('Accept','application/json');if(init.body)headers.set('Content-Type','application/json');
    const response=await fetch(`${this.base}${path}`,{...init,headers});const body=await response.json().catch(()=>({error:`HTTP ${response.status}`})) as Record<string,unknown>;
    if(!response.ok)throw new Error(String(body.error??`HTTP ${response.status}`));return body as T;
  }
  status():Promise<DaemonStatus>{return this.request('/v1/status')}
  history():Promise<{history:DaemonHistoryEntry[]}>{return this.request('/v1/log')}
  commit(message:string):Promise<{revision:string}>{return this.request('/v1/commit',{method:'POST',body:JSON.stringify({message})})}
}

export interface DaemonBranch { name:string; revision:string }
export interface DaemonBranches { current:string|null; branches:DaemonBranch[] }
export interface DaemonRevision { revision:string; parents:string[]; tree:string; change_version:string|null }
export interface DaemonSearchHit { revision:string; path_hex:string; content_id:string; snippet:string }
export interface DaemonSearch { hits:DaemonSearchHit[] }

export class AstraDaemonWorkspaceApi extends AstraDaemonApi {
  branches():Promise<DaemonBranches>{return this.request('/v1/branches')}
  revision(oid:string):Promise<DaemonRevision>{return this.request(`/v1/revisions/${encodeURIComponent(oid)}`)}
  search(query:string,revision?:string):Promise<DaemonSearch>{const q=new URLSearchParams({q:query});if(revision)q.set('revision',revision);return this.request(`/v1/search?${q}`)}
  createBranch(name:string,revision?:string):Promise<{ok:boolean}>{return this.request('/v1/branches',{method:'POST',body:JSON.stringify({name,revision})})}
  deleteBranch(name:string):Promise<{ok:boolean}>{return this.request('/v1/branches/delete',{method:'POST',body:JSON.stringify({name})})}
  switchBranch(name:string,force=false):Promise<{revision:string}>{return this.request('/v1/switch',{method:'POST',body:JSON.stringify({name,force})})}
  checkout(revision:string,force=false):Promise<{revision:string}>{return this.request('/v1/checkout',{method:'POST',body:JSON.stringify({revision,force})})}
}
