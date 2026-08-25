export interface RefRecord { refs: [string,string][]; operation_head: string|null }
export interface RepositoryList { repositories: string[] }
export interface ReviewEvidence { id:number; proposal_id:string; reviewer:string; state:'approved'|'changes_requested'|'commented'; body:string; created_at:number; source_revision:string }
export interface CheckEvidence { id:number; proposal_id:string; name:string; status:string; conclusion:string|null; details:string; updated_at:number; source_revision:string }
export interface MergeQueueEntry { id:number; repo:string; target_ref:string; proposal_id:string; source_revision:string; state:'queued'|'processing'|'merged'|'cancelled'|'stale'; enqueued_by:string; enqueued_at:number; updated_at:number }
export interface Proposal { id:string; repo:string; target_ref:string; source_revision:string; status:string; created_by:string; created_at:number; draft:number|boolean }
export interface Mergeability { mergeable:boolean; blockers:Array<{type:string;message:string;[key:string]:unknown}>; proposal_id?:string; source_revision?:string; current_target?:string|null; expected_target?:string|null }
export interface ReviewThread { id:string; proposal_id:string; revision_id:string; node_id:string; path_hex:string; line_start:number|null; line_end:number|null; state:'open'|'resolved'; author:string; created_at:number; resolved_by:string|null; resolved_at:number|null; comments?:ReviewThreadComment[]; outdated?:boolean }
export interface ReviewThreadComment { id:number; thread_id:string; author:string; body:string; created_at:number }

export interface RevisionRecord { revision:string; parents:string[]; tree:string; change_version:string|null }
export interface SearchHit { revision:string; path_hex:string; content_id:string; snippet:string }
export interface Issue { id:number; repo:string; title:string; body:string; state:string; created_by:string; created_at:number }
export interface IssueComment { id:number; issue_id:number; author:string; body:string; created_at:number }
export interface PackageVersion { namespace:string; name:string; version:string; filename:string; digest:string; size:number; created_at:number }
export interface PlatformEvent { id:number; type:string; repo:string|null; actor:string; payload:string|Record<string,unknown>; created_at:number }


export interface RefPolicyRecord { pattern:string; required_capability:string; required_reviews:number; required_checks:string[]; require_resolved_threads:boolean; require_requested_reviewers:boolean; require_code_owner_reviews:boolean; block_changes_requested:boolean; priority:number; updated:number }
export interface PluginRecord { id:string; version:string; model:string; entrypoint:string; requested:string[]; granted:string[]; enabled:number; updated:number }
export interface PluginCatalogEntry { plugin_id:string; version:string; execution_model:string; requested_capabilities:string[]; entrypoint:string; digest?:string }
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
  repositories():Promise<RepositoryList>{return this.request('/v1/repos')}
  refs(repo:string):Promise<RefRecord>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/refs`)}
  proposals(repo:string):Promise<{proposals:Proposal[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals`)}
  mergeability(repo:string,proposalId:string):Promise<Mergeability>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/mergeability`)}
  ownershipRules(repo:string):Promise<{owners:Array<{repo:string;pattern:string;subject_kind:'principal'|'team';subject:string;priority:number}>}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/owners`)}
  setOwnershipRule(repo:string,rule:{pattern:string;subject_kind:'principal'|'team';subject:string;priority?:number},action:'upsert'|'delete'='upsert'):Promise<{owners:unknown[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/owners`,{method:'POST',body:JSON.stringify({...rule,action})})}
  recommendedReviewers(repo:string,proposalId:string):Promise<{paths_hex:string[];reviewers:string[];teams:string[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/recommended-reviewers`)}
  requestedReviewers(repo:string,proposalId:string,state?:'requested'|'fulfilled'|'removed'):Promise<{reviewers:Array<{proposal_id:string;subject_kind:'principal'|'team';subject:string;state:string;requested_by:string;requested_at:number;updated_at:number}>}>{const q=state?`?state=${state}`:'';return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/reviewers${q}`)}
  requestReviewers(repo:string,proposalId:string,reviewers:string[]=[],teams:string[]=[]):Promise<{reviewers:unknown[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/request-reviewers`,{method:'POST',body:JSON.stringify({reviewers,teams})})}
  syncCodeOwnerReviewers(repo:string,proposalId:string):Promise<{reviewers:unknown[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/sync-code-owner-reviewers`,{method:'POST',body:'{}'})}
  removeRequestedReviewers(repo:string,proposalId:string,reviewers:string[]=[],teams:string[]=[]):Promise<{reviewers:unknown[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/remove-reviewers`,{method:'POST',body:JSON.stringify({reviewers,teams})})}
  refreshProposal(repo:string,proposalId:string,sourceRevision:string,expectedOld?:string):Promise<{proposal:Proposal}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/refresh`,{method:'POST',body:JSON.stringify({source_revision:sourceRevision,...(expectedOld?{expected_old:expectedOld}:{})})})}
  reviewThreads(repo:string,proposalId:string,state?:'open'|'resolved'):Promise<{threads:ReviewThread[]}>{const q=state?`?state=${state}`:'';return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/threads${q}`)}
  createReviewThread(repo:string,proposalId:string,input:{revision_id:string;node_id:string;path_hex:string;body:string;line_start?:number;line_end?:number}):Promise<{id:string}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/threads`,{method:'POST',body:JSON.stringify(input)})}
  reviewThread(repo:string,threadId:string):Promise<{thread:ReviewThread;comments:ReviewThreadComment[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/review-threads/${encodeURIComponent(threadId)}`)}
  addReviewThreadComment(repo:string,threadId:string,body:string):Promise<{id:number}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/review-threads/${encodeURIComponent(threadId)}/comments`,{method:'POST',body:JSON.stringify({body})})}
  setReviewThreadResolved(repo:string,threadId:string,resolved:boolean):Promise<{thread:ReviewThread}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/review-threads/${encodeURIComponent(threadId)}/${resolved?'resolve':'reopen'}`,{method:'POST',body:'{}'})}
  proposalEvidence(repo:string,proposalId:string,scope:'current'|'all'='current'):Promise<{proposal_id:string;source_revision:string;scope:string;reviews:ReviewEvidence[];checks:CheckEvidence[]}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/evidence?scope=${scope}`)}
  mergeQueue(repo:string,targetRef?:string,state='queued'):Promise<{entries:MergeQueueEntry[]}>{const q=new URLSearchParams({state});if(targetRef)q.set('target_ref',targetRef);return this.request(`/v1/repos/${encodeURIComponent(repo)}/merge-queue?${q}`)}
  enqueueProposal(repo:string,proposalId:string):Promise<{entry:MergeQueueEntry}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/enqueue`,{method:'POST',body:'{}'})}
  dequeueProposal(repo:string,proposalId:string):Promise<{entry:MergeQueueEntry}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/dequeue`,{method:'POST',body:'{}'})}
  processMergeQueue(repo:string,targetRef:string):Promise<{processed:boolean;proposal_id?:string;revision?:string}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/merge-queue/process`,{method:'POST',body:JSON.stringify({target_ref:targetRef})})}
  createRepository(name:string):Promise<{name:string}>{return this.request('/v1/repos',{method:'POST',body:JSON.stringify({name})})}
  createProposal(repo:string,targetRef:string,sourceRevision:string,draft=false):Promise<{id:string;target_revision:string|null;draft:boolean}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals`,{method:'POST',body:JSON.stringify({target_ref:targetRef,source_revision:sourceRevision,draft})})}
  setProposalDraft(repo:string,proposalId:string,draft:boolean):Promise<{proposal:Proposal}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/proposals/${encodeURIComponent(proposalId)}/${draft?'draft':'ready'}`,{method:'POST',body:'{}'})}
  createAgentJob(repo:string,inputRevision:string,task:string,capabilities:string[]=['changes.create','proposals.create'],networkPolicy='deny',maxSeconds=900,targetRef='refs/heads/main'):Promise<{id:string}>{return this.request(`/v1/repos/${encodeURIComponent(repo)}/agents`,{method:'POST',body:JSON.stringify({input_revision:inputRevision,task,capabilities,network_policy:networkPolicy,max_seconds:maxSeconds,target_ref:targetRef})})}
  agentJob(id:string):Promise<{job:AgentJob}>{return this.request(`/v1/agents/${encodeURIComponent(id)}`)}
  cancelAgentJob(id:string,reason='cancelled by user'):Promise<{job:AgentJob}>{return this.request(`/v1/agents/${encodeURIComponent(id)}/cancel`,{method:'POST',body:JSON.stringify({reason})})}
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
  policies():Promise<{policies:RefPolicyRecord[]}>{return this.request('/v1/policies')}
  upsertPolicy(policy:{pattern:string;required_capability?:string;required_reviews?:number;required_checks?:string[];require_resolved_threads?:boolean;require_requested_reviewers?:boolean;require_code_owner_reviews?:boolean;block_changes_requested?:boolean;priority?:number}):Promise<{policy:RefPolicyRecord}>{return this.request('/v1/policies/upsert',{method:'POST',body:JSON.stringify(policy)})}
  deletePolicy(pattern:string):Promise<{ok:boolean}>{return this.request('/v1/policies/delete',{method:'POST',body:JSON.stringify({pattern})})}
}
