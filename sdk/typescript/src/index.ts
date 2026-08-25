export interface RefRecord { refs: [string,string][]; operation_head: string|null }
export interface RepositoryList { repositories: string[] }
export interface CompatibilityDescriptor { product_version:string; api_versions:number[]; repository_formats:number[]; bundle_formats:number[]; semantic_schemas:number[]; sync_protocol_versions:number[] }
export interface ReviewEvidence { id:number; proposal_id:string; reviewer:string; state:'approved'|'changes_requested'|'commented'; body:string; created_at:number; source_revision:string }
export interface CheckEvidence { id:number; proposal_id:string; name:string; status:string; conclusion:string|null; details:string; updated_at:number; source_revision:string }
export interface MergeQueueEntry { id:number; repo:string; target_ref:string; proposal_id:string; source_revision:string; state:'queued'|'processing'|'merged'|'cancelled'|'stale'; enqueued_by:string; enqueued_at:number; updated_at:number }
export interface Proposal { id:string; repo:string; target_ref:string; source_revision:string; status:string; created_by:string; created_at:number }
export interface Issue { id:number; repo:string; title:string; body:string; state:string; created_by:string; created_at:number; updated_at:number }
export interface IssueComment { id:number; issue_id:number; author:string; body:string; created_at:number }
export interface Organization { id:string; name:string }
export interface OrganizationMember { principal:string; role:string }
export interface Team { id:string; name:string }
export interface AgentJob { id:string; repo:string; input_revision:string; task:string; capabilities:string; network_policy:string; target_ref:string; status:string; result:string|null; created:number; updated:number }
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
  capabilities():Promise<CompatibilityDescriptor>{return this.request('/v1/capabilities')}
  organizations():Promise<{organizations:Organization[]}>{return this.request('/v1/orgs')}
  createOrganization(name:string):Promise<Organization>{return this.request('/v1/orgs',{method:'POST',body:JSON.stringify({name})})}
  organizationMembers(id:string):Promise<{members:OrganizationMember[]}>{return this.request(`/v1/orgs/${encodeURIComponent(id)}/members`)}
  addOrganizationMember(id:string,principal:string,role='read'):Promise<{ok:boolean}>{return this.request(`/v1/orgs/${encodeURIComponent(id)}/members`,{method:'POST',body:JSON.stringify({principal,role})})}
  createTeam(org:string,name:string):Promise<{id:string}>{return this.request(`/v1/orgs/${encodeURIComponent(org)}/teams`,{method:'POST',body:JSON.stringify({name})})}
  addTeamMember(team:string,principal:string):Promise<{ok:boolean}>{return this.request(`/v1/teams/${encodeURIComponent(team)}/members`,{method:'POST',body:JSON.stringify({principal})})}
  bindRepositoryOrganization(repo:string,org:string,visibility='private'):Promise<{ok:boolean}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/organization`,{method:'POST',body:JSON.stringify({org,visibility})})}
  setRepositoryRole(repo:string,subjectKind:'principal'|'team',subject:string,role:string):Promise<{ok:boolean}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/roles`,{method:'POST',body:JSON.stringify({subject_kind:subjectKind,subject,role})})}
  repositories():Promise<RepositoryList>{return this.request('/v1/repos')}
  refs(repo:string):Promise<RefRecord>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/refs`)}
  proposals(repo:string,limit=100,cursor?:string,status='open'):Promise<{proposals:Proposal[];next_cursor:string|null}>{const q=new URLSearchParams({limit:String(limit),status});if(cursor)q.set('cursor',cursor);return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals?${q}`)}
  proposalEvidence(repo:string,proposalId:string,scope:'current'|'all'='current'):Promise<{proposal_id:string;source_revision:string;scope:string;reviews:ReviewEvidence[];checks:CheckEvidence[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/evidence?scope=${scope}`)}
  mergeQueue(repo:string,targetRef?:string,state='queued'):Promise<{entries:MergeQueueEntry[]}>{const q=new URLSearchParams({state});if(targetRef)q.set('target_ref',targetRef);return this.request(`/v1/repos/${encodeURIComponent(repo)}/merge-queue?${q}`)}
  enqueueProposal(repo:string,proposalId:string):Promise<{entry:MergeQueueEntry}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/enqueue`,{method:'POST',body:'{}'})}
  dequeueProposal(repo:string,proposalId:string):Promise<{entry:MergeQueueEntry}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/dequeue`,{method:'POST',body:'{}'})}
  processMergeQueue(repo:string,targetRef:string):Promise<{processed:boolean;proposal_id?:string;revision?:string}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/merge-queue/process`,{method:'POST',body:JSON.stringify({target_ref:targetRef})})}
  createRepository(name:string):Promise<{name:string}>{return this.request('/v1/repos',{method:'POST',body:JSON.stringify({name})})}
  createAgentJob(repo:string,inputRevision:string,task:string,capabilities:string[]=['changes.create','proposals.create'],networkPolicy='deny',maxSeconds=900,targetRef='refs/heads/main'):Promise<{id:string}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/agents`,{method:'POST',body:JSON.stringify({input_revision:inputRevision,task,capabilities,network_policy:networkPolicy,max_seconds:maxSeconds,target_ref:targetRef})})}
  agentJob(id:string):Promise<{job:AgentJob}>{return this.request(`/v1/agents/${encodeURIComponent(id)}`)}
  cancelAgentJob(id:string,reason='cancelled by user'):Promise<{job:AgentJob}>{return this.request(`/v1/agents/${encodeURIComponent(id)}/cancel`,{method:'POST',body:JSON.stringify({reason})})}

  issues(repo:string,state='open',limit=100,after=0):Promise<{issues:Issue[];next_after:number|null}>{const q=new URLSearchParams({state,limit:String(limit),after:String(after)});return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues?${q}`)}
  createIssue(repo:string,title:string,body=''):Promise<{id:number}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues`,{method:'POST',body:JSON.stringify({title,body})})}
  issue(repo:string,id:number):Promise<{issue:Issue;comments:IssueComment[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}`)}
  commentIssue(repo:string,id:number,body:string):Promise<{id:number}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}/comments`,{method:'POST',body:JSON.stringify({body})})}
  closeIssue(repo:string,id:number):Promise<{ok:boolean}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/issues/${id}/close`,{method:'POST',body:'{}'})}
  events(limit=100,after=0):Promise<{events:Record<string,unknown>[];next_after:number|null}>{return this.request(`/v1/events?limit=${limit}&after=${after}`)}
}
