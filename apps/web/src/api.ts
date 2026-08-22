export interface RefRecord { refs: [string,string][]; operation_head: string|null }
export interface RepositoryList { repositories: string[] }
export interface Proposal { id:string; repo:string; target_ref:string; source_revision:string; status:string; created_by:string; created_at:number }
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
}
