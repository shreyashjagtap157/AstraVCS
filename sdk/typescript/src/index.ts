export interface RefRecord { refs: [string,string][]; operation_head: string|null }
export interface RepositoryList { repositories: string[] }
export interface Proposal { id:string; repo:string; target_ref:string; source_revision:string; status:string; created_by:string; created_at:number }
export interface Issue { id:number; repo:string; title:string; body:string; state:string; created_by:string; created_at:number; updated_at:number }
export interface IssueComment { id:number; issue_id:number; author:string; body:string; created_at:number }
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

  issues(repo:string,state='open'):Promise<{issues:Issue[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues?state=${encodeURIComponent(state)}`)}
  createIssue(repo:string,title:string,body=''):Promise<{id:number}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues`,{method:'POST',body:JSON.stringify({title,body})})}
  issue(repo:string,id:number):Promise<{issue:Issue;comments:IssueComment[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}`)}
  commentIssue(repo:string,id:number,body:string):Promise<{id:number}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}/comments`,{method:'POST',body:JSON.stringify({body})})}
  closeIssue(repo:string,id:number):Promise<{ok:boolean}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}/close`,{method:'POST',body:'{}'})}
}
