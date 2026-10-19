import {AstraApi} from './dist/api.js';

const base = process.env.ASTRA_BASE;
const token = process.env.ASTRA_TOKEN;
const rev = process.env.ASTRA_REV;
if (!base || !token || !rev) {
  console.error('missing ASTRA_BASE/ASTRA_TOKEN/ASTRA_REV');
  process.exit(2);
}
const api = new AstraApi(base, token);
const repo = 'websmoke';
let pass = 0;
let fail = 0;

async function check(name, fn) {
  try {
    const out = await fn();
    pass++;
    let detail = '';
    try { detail = JSON.stringify(out) ?? ''; } catch { detail = String(out); }
    console.log(name.padEnd(32), 'OK  ', detail.slice(0, 90));
    return out;
  } catch (e) {
    fail++;
    console.log(name.padEnd(32), 'FAIL', String(e && e.message || e).slice(0, 140));
    return null;
  }
}

await check('repositories', () => api.repositories());
await check('createRepository', () => api.createRepository('websmoke2'));
await check('createRepository(dup)', () => api.createRepository('websmoke2').then(
  () => { throw new Error('expected duplicate error'); },
  e => `rejected: ${e.message}`));
await check('refs', async () => {
  const r = await api.refs(repo);
  if (!Array.isArray(r.refs) || r.refs.length === 0) throw new Error('no refs');
  return r;
});
await check('updateRef(feature)', () => api.updateRef(repo, 'refs/heads/feature', rev));
await check('refs(after update)', async () => {
  const r = await api.refs(repo);
  const feature = r.refs.find(([name]) => name === 'refs/heads/feature');
  if (!feature || feature[1] !== rev) throw new Error('feature ref missing');
  return r;
});
await check('revision', () => api.revision(repo, rev));
await check('search', () => api.search(repo, 'hello', rev));
await check('issues list(empty)', () => api.issues(repo));
const issue = await check('createIssue', () => api.createIssue(repo, 'Web smoke bug', 'filed from node'));
if (issue) {
  await check('issue get', () => api.issue(repo, issue.id));
  await check('addIssueComment', () => api.addIssueComment(repo, issue.id, 'looking into it'));
  await check('closeIssue', () => api.closeIssue(repo, issue.id));
}
const proposal = await check('createProposal(draft)', () => api.createProposal(repo, 'refs/heads/main', rev, true));
let pid = proposal && proposal.id;
await check('proposal get', () => api.proposal(repo, pid));
await check('setProposalDraft(ready)', () => api.setProposalDraft(repo, pid, false));
await check('requestReviewers', () => api.requestReviewers(repo, pid, ['bob'], []));
await check('requestedReviewers', () => api.requestedReviewers(repo, pid));
await check('removeRequestedReviewers', () => api.removeRequestedReviewers(repo, pid, ['bob'], []));
await check('addReview', () => api.addReview(repo, pid, 'approved', 'lgtm'));
await check('setCheck', () => api.setCheck(repo, pid, 'web-check', 'completed', 'success', 'set by node smoke'));
await check('refreshProposal', () => api.refreshProposal(repo, pid, rev));
await check('mergeability', () => api.mergeability(repo, pid));
await check('proposalEvidence', () => api.proposalEvidence(repo, pid));
await check('reviewThreads', () => api.reviewThreads(repo, pid));
await check('createReviewThread(missing anchor)', () => api.createReviewThread(repo, pid, {
  revision_id: rev, node_id: 'nope', path_hex: '00', body: 'hi'
}).then(() => { throw new Error('expected rejection'); }, e => `rejected: ${e.message}`));
await check('enqueueProposal', () => api.enqueueProposal(repo, pid));
await check('mergeQueue', () => api.mergeQueue(repo));
await check('dequeueProposal', () => api.dequeueProposal(repo, pid));
await check('processMergeQueue(empty)', () => api.processMergeQueue(repo, 'refs/heads/main'));
await check('mergeProposal', async () => {
  const merged = await api.mergeProposal(repo, pid);
  if (!merged.revision) throw new Error('no revision returned');
  return merged;
});
await check('proposal status after merge', async () => {
  const p = await api.proposal(repo, pid);
  if (p.proposal.status === 'open') throw new Error('proposal still open');
  return p.proposal.status;
});
await check('refs after merge', async () => {
  const r = await api.refs(repo);
  const main = r.refs.find(([name]) => name === 'refs/heads/main');
  if (!main) throw new Error('main missing');
  return r;
});
await check('owners list', () => api.ownershipRules(repo));
await check('owners upsert', () => api.setOwnershipRule(repo, {pattern: '*.md', subject_kind: 'principal', subject: 'bob'}));
await check('owners delete', () => api.setOwnershipRule(repo, {pattern: '*.md', subject_kind: 'principal', subject: 'bob'}, 'delete'));
await check('policies list', () => api.policies());
await check('policies upsert', () => api.upsertPolicy({pattern: 'refs/heads/main', required_reviews: 1}));
await check('policies delete', () => api.deletePolicy('refs/heads/main'));
await check('plugins list', () => api.plugins());
await check('events', () => api.events(0));
await check('agent create+get+cancel', async () => {
  const r = await api.refs(repo);
  const main = r.refs.find(([name]) => name === 'refs/heads/main');
  if (!main) throw new Error('main missing');
  const created = await api.createAgentJob(repo, main[1], 'run the test suite');
  const job = await api.agentJob(created.id);
  if (job.job.id !== created.id) throw new Error('job id mismatch');
  const cancelled = await api.cancelAgentJob(created.id, 'smoke done');
  return {id: created.id, status: cancelled.job.status};
});

console.log('---');
console.log(`${pass} passed, ${fail} failed of ${pass + fail}`);
process.exit(fail ? 1 : 0);
