import {AstraApi} from './api.js';
const q=<T extends Element>(selector:string):T=>{const v=document.querySelector(selector);if(!v)throw new Error(`missing ${selector}`);return v as T};
const api=new AstraApi(location.origin,'');
const token=q<HTMLInputElement>('#token'), status=q<HTMLElement>('#status'), repos=q<HTMLUListElement>('#repos'), refs=q<HTMLPreElement>('#refs'), proposals=q<HTMLPreElement>('#proposals'), issues=q<HTMLPreElement>('#issues'), searchQuery=q<HTMLInputElement>('#search-query'), searchRun=q<HTMLButtonElement>('#search-run'), searchResults=q<HTMLPreElement>('#search-results'), agentTask=q<HTMLInputElement>('#agent-task'), agentStart=q<HTMLButtonElement>('#agent-start'), agentStatus=q<HTMLPreElement>('#agent-status');
let selectedRepo:string|undefined;let selectedHead:string|undefined;
function message(text:string,error=false){status.textContent=text;status.setAttribute('role',error?'alert':'status')}
async function loadRepos(){try{api.setToken(token.value);const data=await api.repositories();repos.replaceChildren(...data.repositories.map(name=>{const b=document.createElement('button');b.textContent=name;b.onclick=()=>void selectRepo(name);const li=document.createElement('li');li.append(b);return li}));message(`${data.repositories.length} repositories`)}catch(e){message(String(e),true)}}
async function selectRepo(name:string){try{const [r,p,i]=await Promise.all([api.refs(name),api.proposals(name),api.issues(name)]);refs.textContent=JSON.stringify(r,null,2);proposals.textContent=JSON.stringify(p.proposals,null,2);issues.textContent=JSON.stringify(i.issues,null,2);q<HTMLElement>('#selected').textContent=name;selectedRepo=name;selectedHead=r.refs.find(([ref])=>ref==='refs/heads/main')?.[1];agentStart.disabled=!selectedHead;searchRun.disabled=false}catch(e){message(String(e),true)}}
async function runSearch(){if(!selectedRepo)return;try{const data=await api.search(selectedRepo,searchQuery.value,selectedHead);searchResults.textContent=JSON.stringify(data.hits,null,2);message(`${data.hits.length} search hits`)}catch(e){message(String(e),true)}}
async function queueAgent(){if(!selectedRepo||!selectedHead)return;try{const created=await api.createAgentJob(selectedRepo,selectedHead,agentTask.value);agentStatus.textContent=JSON.stringify(await api.agentJob(created.id),null,2);message(`Agent job ${created.id} queued`)}catch(e){message(String(e),true)}}
q<HTMLButtonElement>('#connect').onclick=()=>void loadRepos(); token.addEventListener('keydown',e=>{if(e.key==='Enter')void loadRepos()});

searchRun.onclick=()=>void runSearch(); searchQuery.addEventListener('keydown',e=>{if(e.key==='Enter')void runSearch()});
agentStart.onclick=()=>void queueAgent();
