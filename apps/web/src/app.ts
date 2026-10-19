import {AstraApi, Proposal, Issue} from './api.js';
import {isTauri, platformInfo, discoverDaemonSession, revealPath, daemonClient} from './tauri.js';
import type {AstraDaemonWorkspaceApi} from './daemon.js';

const q = <T extends Element>(selector: string): T => {
  const v = document.querySelector(selector);
  if (!v) throw new Error(`missing ${selector}`);
  return v as T;
};

const api = new AstraApi(localStorage.getItem('astra-api-base') || location.origin, '');

const server = q<HTMLInputElement>('#server');
const token = q<HTMLInputElement>('#token');
const connectBtn = q<HTMLButtonElement>('#connect');
const statusEl = q<HTMLElement>('#status');
const repos = q<HTMLUListElement>('#repos');
const repoForm = q<HTMLFormElement>('#repo-form');
const repoName = q<HTMLInputElement>('#repo-name');
const selected = q<HTMLElement>('#selected');
const refs = q<HTMLPreElement>('#refs');
const refForm = q<HTMLFormElement>('#ref-form');
const refName = q<HTMLInputElement>('#ref-name');
const refRevision = q<HTMLInputElement>('#ref-revision');
const proposalList = q<HTMLUListElement>('#proposal-list');
const proposalForm = q<HTMLFormElement>('#proposal-form');
const proposalRef = q<HTMLInputElement>('#proposal-ref');
const proposalRevision = q<HTMLInputElement>('#proposal-revision');
const proposalDraft = q<HTMLInputElement>('#proposal-draft');
const reviewThreads = q<HTMLPreElement>('#review-threads');
const issueList = q<HTMLUListElement>('#issue-list');
const issueForm = q<HTMLFormElement>('#issue-form');
const issueTitle = q<HTMLInputElement>('#issue-title');
const issueBody = q<HTMLTextAreaElement>('#issue-body');
const searchQuery = q<HTMLInputElement>('#search-query');
const searchRun = q<HTMLButtonElement>('#search-run');
const searchResults = q<HTMLPreElement>('#search-results');
const agentTask = q<HTMLInputElement>('#agent-task');
const agentStart = q<HTMLButtonElement>('#agent-start');
const agentStatus = q<HTMLPreElement>('#agent-status');
const daemonPanel = q<HTMLElement>('#daemon-panel');
const daemonRoot = q<HTMLInputElement>('#daemon-root');
const daemonConnect = q<HTMLButtonElement>('#daemon-connect');
const daemonReveal = q<HTMLButtonElement>('#daemon-reveal');
const daemonRefresh = q<HTMLButtonElement>('#daemon-refresh');
const daemonLog = q<HTMLButtonElement>('#daemon-log');
const daemonStatus = q<HTMLPreElement>('#daemon-status');
const daemonHistory = q<HTMLPreElement>('#daemon-history');
const daemonCommitMsg = q<HTMLInputElement>('#daemon-commit-msg');
const daemonCommit = q<HTMLButtonElement>('#daemon-commit');
const daemonBranch = q<HTMLInputElement>('#daemon-branch');
const daemonBranchCreate = q<HTMLButtonElement>('#daemon-branch-create');
const daemonBranches = q<HTMLSelectElement>('#daemon-branches');
const daemonSwitch = q<HTMLButtonElement>('#daemon-switch');
const daemonOut = q<HTMLPreElement>('#daemon-out');

let selectedRepo: string | undefined;
let selectedHead: string | undefined;

server.value = localStorage.getItem('astra-api-base') || location.origin;
token.value = localStorage.getItem('astra-token') || '';

function message(text: string, error = false): void {
  statusEl.textContent = text;
  statusEl.setAttribute('role', error ? 'alert' : 'status');
}

function currentRepo(): string {
  if (!selectedRepo) throw new Error('select a repository first');
  return selectedRepo;
}

async function act(work: () => Promise<unknown>, done = 'Done'): Promise<void> {
  try {
    await work();
    message(done);
  } catch (e) {
    message(String(e), true);
  }
}

function button(label: string, onClick: () => void): HTMLButtonElement {
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = label;
  b.onclick = onClick;
  return b;
}

async function loadRepos(): Promise<void> {
  try {
    const base = server.value.trim() || location.origin;
    api.setBase(base);
    api.setToken(token.value);
    localStorage.setItem('astra-api-base', base);
    localStorage.setItem('astra-token', token.value);
    const data = await api.repositories();
    repos.replaceChildren(...data.repositories.map(name => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = name;
      b.onclick = () => void selectRepo(name);
      const li = document.createElement('li');
      li.append(b);
      return li;
    }));
    const hash = decodeURIComponent(window.location.hash.replace(/^#\//, ''));
    const target = data.repositories.includes(hash) ? hash : data.repositories[0];
    if (target) {
      await selectRepo(target);
      message(`${data.repositories.length} repositories \u00b7 ${target}`);
    } else {
      resetSelection();
      message('0 repositories');
    }
  } catch (e) {
    message(String(e), true);
  }
}

function resetSelection(): void {
  selectedRepo = undefined;
  selectedHead = undefined;
  selected.textContent = 'Select a repository';
  refs.textContent = '';
  proposalList.replaceChildren();
  issueList.replaceChildren();
  reviewThreads.textContent = '';
  searchResults.textContent = '';
  agentStatus.textContent = '';
  searchRun.disabled = true;
  agentStart.disabled = true;
}

async function selectRepo(name: string): Promise<void> {
  try {
    selectedRepo = name;
    selected.textContent = name;
    const [r, p, i] = await Promise.all([api.refs(name), api.proposals(name), api.issues(name)]);
    refs.textContent = r.refs.map(([ref, oid]) => `${ref}  ${oid}`).join('\n') || 'no refs yet';
    selectedHead = r.refs.find(([ref]) => ref === 'refs/heads/main')?.[1];
    refName.value = 'refs/heads/main';
    refRevision.value = selectedHead || '';
    proposalRef.value = 'refs/heads/main';
    proposalRevision.value = selectedHead || '';
    searchRun.disabled = false;
    agentStart.disabled = !selectedHead;
    renderProposals(p.proposals);
    renderIssues(i.issues);
    const first = p.proposals[0];
    if (first) {
      const t = await api.reviewThreads(name, first.id);
      reviewThreads.textContent = JSON.stringify(t.threads, null, 2);
    } else {
      reviewThreads.textContent = '[]';
    }
    history.replaceState(null, '', `#/${encodeURIComponent(name)}`);
  } catch (e) {
    message(String(e), true);
  }
}

function renderProposals(items: Proposal[]): void {
  proposalList.replaceChildren(...items.map(p => {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.textContent = `${p.id.slice(0, 8)} \u2192 ${p.target_ref} \u00b7 ${p.status}${p.draft ? ' \u00b7 draft' : ''} \u00b7 ${p.source_revision.slice(0, 8)} `;
    li.append(label);
    if (p.status !== 'open') return li;
    li.append(button('Approve', () => void act(async () => {
      await api.addReview(currentRepo(), p.id, 'approved');
      await selectRepo(currentRepo());
    }, 'Approval recorded')));
    if (p.draft) {
      li.append(button('Mark ready', () => void act(async () => {
        await api.setProposalDraft(currentRepo(), p.id, false);
        await selectRepo(currentRepo());
      }, 'Proposal ready')));
      return li;
    }
    li.append(button('Set check', () => void act(async () => {
      await api.setCheck(currentRepo(), p.id, 'web-check', 'completed', 'success', 'manually set from web client');
      await selectRepo(currentRepo());
    }, 'Check set')));
    li.append(button('Queue', () => void act(async () => {
      await api.enqueueProposal(currentRepo(), p.id);
      await selectRepo(currentRepo());
    }, 'Queued for merge')));
    li.append(button('Merge', () => void (async () => {
      try {
        const repo = currentRepo();
        const result = await api.mergeProposal(repo, p.id);
        message(`Merged into ${p.target_ref} as ${result.revision.slice(0, 8)}`);
        await selectRepo(repo);
      } catch (e) {
        message(String(e), true);
      }
    })()));
    return li;
  }));
}

function renderIssues(items: Issue[]): void {
  issueList.replaceChildren(...items.map(issue => {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.textContent = `#${issue.id} ${issue.title} \u00b7 ${issue.state} \u00b7 by ${issue.created_by} `;
    li.append(label);
    if (issue.state !== 'open') return li;
    li.append(button('Close', () => void act(async () => {
      await api.closeIssue(currentRepo(), issue.id);
      await selectRepo(currentRepo());
    }, `Issue #${issue.id} closed`)));
    const comment = document.createElement('input');
    comment.type = 'text';
    comment.placeholder = 'comment';
    comment.maxLength = 4000;
    comment.setAttribute('aria-label', `comment on issue ${issue.id}`);
    const reply = button('Reply', () => void act(async () => {
      const body = comment.value.trim();
      if (!body) throw new Error('comment is empty');
      await api.addIssueComment(currentRepo(), issue.id, body);
      comment.value = '';
      await selectRepo(currentRepo());
    }, `Comment added to #${issue.id}`));
    li.append(comment, reply);
    return li;
  }));
}

async function runSearch(): Promise<void> {
  if (!selectedRepo) return;
  try {
    const data = await api.search(selectedRepo, searchQuery.value, selectedHead);
    searchResults.textContent = JSON.stringify(data.hits, null, 2);
    message(`${data.hits.length} search hits`);
  } catch (e) {
    message(String(e), true);
  }
}

connectBtn.onclick = () => void loadRepos();
token.addEventListener('keydown', e => { if (e.key === 'Enter') void loadRepos(); });

repoForm.onsubmit = e => {
  e.preventDefault();
  void act(async () => {
    const name = repoName.value.trim();
    await api.createRepository(name);
    repoName.value = '';
    history.replaceState(null, '', `#/${encodeURIComponent(name)}`);
    await loadRepos();
  }, 'Repository created');
};

refForm.onsubmit = e => {
  e.preventDefault();
  void act(async () => {
    await api.updateRef(currentRepo(), refName.value.trim(), refRevision.value.trim());
    await selectRepo(currentRepo());
  }, 'Ref updated');
};

proposalForm.onsubmit = e => {
  e.preventDefault();
  void act(async () => {
    const source = proposalRevision.value.trim() || selectedHead;
    if (!source) throw new Error('enter a source revision');
    await api.createProposal(currentRepo(), proposalRef.value.trim(), source, proposalDraft.checked);
    proposalDraft.checked = false;
    await selectRepo(currentRepo());
  }, 'Proposal opened');
};

issueForm.onsubmit = e => {
  e.preventDefault();
  void act(async () => {
    await api.createIssue(currentRepo(), issueTitle.value.trim(), issueBody.value.trim());
    issueTitle.value = '';
    issueBody.value = '';
    await selectRepo(currentRepo());
  }, 'Issue opened');
};

searchRun.onclick = () => void runSearch();
searchQuery.addEventListener('keydown', e => { if (e.key === 'Enter') void runSearch(); });

agentStart.onclick = () => void act(async () => {
  const repo = currentRepo();
  if (!selectedHead) throw new Error('main branch does not exist yet');
  const created = await api.createAgentJob(repo, selectedHead, agentTask.value);
  const job = await api.agentJob(created.id);
  agentStatus.textContent = JSON.stringify(job, null, 2);
}, 'Agent job queued');

let daemon: AstraDaemonWorkspaceApi | null = null;
let daemonFolder = '';

function daemonEnabled(on: boolean): void {
  for (const el of [daemonReveal, daemonRefresh, daemonLog, daemonCommit, daemonBranchCreate, daemonBranches, daemonSwitch]) el.disabled = !on;
}

async function daemonRefreshStatus(): Promise<void> {
  if (!daemon) return;
  try {
    const s = await daemon.status();
    const b = await daemon.branches();
    const shown = s.entries.slice(0, 20).map(e => `${e.path_hex.slice(0, 12)}  ${e.state}`).join('\n');
    daemonStatus.textContent = `head: ${s.head ?? '(no commits)'}\n${s.entries.length} entries${shown ? '\n' + shown : ''}`;
    daemonBranches.replaceChildren(...b.branches.map(x => {
      const opt = document.createElement('option');
      opt.value = x.name;
      opt.textContent = `${x.name} @ ${x.revision.slice(0, 8)}`;
      if (x.name === b.current) opt.selected = true;
      return opt;
    }));
  } catch (e) {
    daemonOut.textContent = String(e);
  }
}

daemonConnect.onclick = () => void act(async () => {
  const root = daemonRoot.value.trim();
  if (!root) throw new Error('enter the repository root');
  const session = await discoverDaemonSession(root);
  daemon = daemonClient(session);
  daemonFolder = root;
  localStorage.setItem('astra-repo-root', root);
  daemonEnabled(true);
  await daemonRefreshStatus();
}, 'Daemon connected');

daemonReveal.onclick = () => void act(async () => {
  if (!daemonFolder) throw new Error('connect the daemon first');
  await revealPath(daemonFolder);
}, 'Revealed in file manager');

daemonRefresh.onclick = () => void act(async () => {
  await daemonRefreshStatus();
}, 'Status refreshed');

daemonLog.onclick = () => void act(async () => {
  if (!daemon) throw new Error('connect the daemon first');
  const h = await daemon.history();
  daemonHistory.textContent = h.history.map(r => `${r.revision.slice(0, 12)}  parents=${r.parents.length}  tree=${r.tree.slice(0, 12)}`).join('\n') || 'empty history';
  message(`${h.history.length} revisions`);
});

daemonCommit.onclick = () => void act(async () => {
  if (!daemon) throw new Error('connect the daemon first');
  const msg = daemonCommitMsg.value.trim();
  if (!msg) throw new Error('commit message is empty');
  const r = await daemon.commit(msg);
  daemonCommitMsg.value = '';
  daemonOut.textContent = `committed ${r.revision}`;
  await daemonRefreshStatus();
}, 'Committed');

daemonBranchCreate.onclick = () => void act(async () => {
  if (!daemon) throw new Error('connect the daemon first');
  const name = daemonBranch.value.trim();
  if (!name) throw new Error('branch name is empty');
  await daemon.createBranch(name);
  daemonBranch.value = '';
  await daemonRefreshStatus();
}, 'Branch created');

daemonSwitch.onclick = () => void act(async () => {
  if (!daemon) throw new Error('connect the daemon first');
  const name = daemonBranches.value;
  if (!name) throw new Error('no branch selected');
  const r = await daemon.switchBranch(name);
  daemonOut.textContent = `switched to ${name} @ ${r.revision.slice(0, 12)}`;
  await daemonRefreshStatus();
}, 'Branch switched');

if (isTauri()) {
  daemonPanel.hidden = false;
  daemonRoot.value = localStorage.getItem('astra-repo-root') || '';
  void platformInfo().then(info => {
    daemonStatus.textContent = `${info.os}/${info.arch}  v${info.appVersion}${info.debug ? '  (debug)' : ''}`;
  });
  if (localStorage.getItem('astra-api-base')) {
    void loadRepos();
  } else {
    server.value = 'http://127.0.0.1:8080';
    message('Set the server URL or connect the local daemon');
  }
} else {
  void loadRepos();
}
