export interface RefRecord { refs: [string,string][]; operation_head: string|null }
export interface RepositoryList { repositories: string[] }
export interface Proposal { id:string; repo:string; target_ref:string; source_revision:string; status:string; created_by:string; created_at:number }

export interface RevisionRecord { revision:string; parents:string[]; tree:string; change_version:string|null }
export interface SearchHit { revision:string; path_hex:string; content_id:string; snippet:string }
export interface Issue { id:number; repo:string; title:string; body:string; state:string; created_by:string; created_at:number }
export interface IssueComment { id:number; issue_id:number; author:string; body:string; created_at:number }
export interface PackageVersion { namespace:string; name:string; version:string; filename:string; digest:string; size:number; created_at:number }
export interface PlatformEvent { id:number; type:string; repo:string|null; actor:string; payload:string|Record<string,unknown>; created_at:number }

export interface PluginRecord { id:string; version:string; model:string; entrypoint:string; requested:string[]; granted:string[]; enabled:number; updated:number }
export interface PluginCatalogEntry { plugin_id:string; version:string; execution_model:string; requested_capabilities:string[]; entrypoint:string; digest?:string }
export interface AgentJob { id:string; repo:string; input_revision:string; task:string; capabilities:string; network_policy:string; status:string; result:string|null; created:number; updated:number }
export class AstraApi {
  constructor(private readonly base:string, private token:string) {}
  setToken(token:string):void { this.token=token }
  private async request<T>(path:string, init:RequestInit={}):Promise<T> {
    const headers=new Headers(init.headers); if(this.token) headers.set('Authorization',`Bearer ${this.token}`); headers.set('Accept','application/json');
    if(init.body && !headers.has('Content-Type')) headers.set('Content-Type','application/json');
    const response=await fetch(`${this.base}${path}`,{...init,headers});
    const body=await response.json().catch(()=>({error:`HTTP ${response.status}`})) as Record<string,unknown>;
    if(!response.ok) throw new Error(String(body.error ?? `HTTP ${response.status}`)); return body as T;
  }
  repositories():Promise<RepositoryList>{return this.request('/v1/repos')}
  refs(repo:string):Promise<RefRecord>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/refs`)}
  proposals(repo:string):Promise<{proposals:Proposal[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals`)}
  createRepository(name:string):Promise<{name:string}>{return this.request('/v1/repos',{method:'POST',body:JSON.stringify({name})})}
  createAgentJob(repo:string,inputRevision:string,task:string,capabilities:string[]=['changes.create','proposals.create'],networkPolicy='deny',maxSeconds=900):Promise<{id:string}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/agents`,{method:'POST',body:JSON.stringify({input_revision:inputRevision,task,capabilities,network_policy:networkPolicy,max_seconds:maxSeconds})})}
  agentJob(id:string):Promise<{job:AgentJob}>{return this.request(`/v1/agents/${encodeURIComponent(id)}`)}
  revision(repo:string,oid:string):Promise<RevisionRecord>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/revisions/${encodeURIComponent(oid)}`)}
  search(repo:string,query:string,revision?:string):Promise<{hits:SearchHit[]}>{const q=new URLSearchParams({q:query});if(revision)q.set('revision',revision);return this.request(`/v1/repos/${encodeURIComponent(repo)}/search?${q}`)}
  issues(repo:string,state='open'):Promise<{issues:Issue[]}>{const q=new URLSearchParams({state});return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues?${q}`)}
  issue(repo:string,id:number):Promise<{issue:Issue;comments:IssueComment[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}`)}
  createIssue(repo:string,title:string,body=''):Promise<{id:number}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues`,{method:'POST',body:JSON.stringify({title,body})})}
  addIssueComment(repo:string,id:number,body:string):Promise<{id:number}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}/comments`,{method:'POST',body:JSON.stringify({body})})}
  closeIssue(repo:string,id:number):Promise<{ok:boolean}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}/close`,{method:'POST',body:'{}'})}
  packages(namespace:string,name:string):Promise<{packages:PackageVersion[]}>{return this.request(`/v1/packages/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`)}
  events(after=0):Promise<{events:PlatformEvent[]}>{return this.request(`/v1/events?after=${after}`)}
  plugins():Promise<{plugins:PluginRecord[]}>{return this.request('/v1/plugins')}
  pluginCatalog():Promise<{entries:PluginCatalogEntry[]}>{return this.request('/v1/plugin-catalog')}
  installCatalogPlugin(pluginId:string,version:string,grantedCapabilities:string[]):Promise<{plugin:PluginRecord;secret:string;catalog_digest?:string}>{return this.request('/v1/plugin-catalog/install',{method:'POST',body:JSON.stringify({plugin_id:pluginId,version,granted_capabilities:grantedCapabilities})})}
  setPluginEnabled(pluginId:string,enabled:boolean):Promise<{ok:boolean}>{return this.request(`/v1/plugins/${encodeURIComponent(pluginId)}/${enabled?'enable':'disable'}`,{method:'POST',body:'{}'})}
  rotatePluginSecret(pluginId:string):Promise<{secret:string}>{return this.request(`/v1/plugins/${encodeURIComponent(pluginId)}/rotate-secret`,{method:'POST',body:'{}'})}
  uninstallPlugin(pluginId:string):Promise<{ok:boolean}>{return this.request(`/v1/plugins/${encodeURIComponent(pluginId)}/uninstall`,{method:'POST',body:'{}'})}
}
