export interface DaemonStatusEntry { path_hex:string; state:string }
export interface DaemonStatus { entries:DaemonStatusEntry[]; head:string|null }
export interface DaemonHistoryEntry { revision:string; parents:string[]; tree:string }
export class AstraDaemonApi {
  constructor(private readonly base:string, private readonly token:string) {}
  private async request<T>(path:string,init:RequestInit={}):Promise<T>{
    const headers=new Headers(init.headers);headers.set('Authorization',`Bearer ${this.token}`);headers.set('Accept','application/json');if(init.body)headers.set('Content-Type','application/json');
    const response=await fetch(`${this.base}${path}`,{...init,headers});const body=await response.json().catch(()=>({error:`HTTP ${response.status}`})) as Record<string,unknown>;
    if(!response.ok)throw new Error(String(body.error??`HTTP ${response.status}`));return body as T;
  }
  status():Promise<DaemonStatus>{return this.request('/v1/status')}
  history():Promise<{history:DaemonHistoryEntry[]}>{return this.request('/v1/log')}
  commit(message:string):Promise<{revision:string}>{return this.request('/v1/commit',{method:'POST',body:JSON.stringify({message})})}
}
