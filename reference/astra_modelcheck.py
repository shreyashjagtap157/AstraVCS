"""Small executable state-model checks for high-risk AstraVCS transitions."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import permutations
@dataclass(frozen=True)
class CasWrite:writer:str;expected:str|None;new:str

def enumerate_head_cas(initial:str|None,writes:tuple[CasWrite,...]):
 outcomes=[]
 for order in permutations(writes):
  head=initial;success=[]
  for w in order:
   if head==w.expected:head=w.new;success.append(w.writer)
  outcomes.append((tuple(w.writer for w in order),head,tuple(success)))
 return tuple(outcomes)

def verify_same_expected_single_winner():
 writes=(CasWrite('a','old','A'),CasWrite('b','old','B'),CasWrite('c','old','C'))
 for _,head,winners in enumerate_head_cas('old',writes):
  if len(winners)!=1 or head not in ('A','B','C'):return False
 return True

def verify_retry_requires_new_observation():
 first=CasWrite('a','old','A');stale=CasWrite('b','old','B');retry=CasWrite('b','A','B')
 # First succeeds, stale cannot, refreshed retry can.
 head='old';wins=[]
 for w in (first,stale,retry):
  if head==w.expected:head=w.new;wins.append(w.writer)
 return head=='B' and wins==['a','b']

@dataclass(frozen=True)
class LeaseState:
 owner:str|None=None; expired:bool=False; terminal:str|None=None; attempts:int=0; completions:tuple[str,...]=()

def lease_step(state:LeaseState,action:tuple[str,str|None])->LeaseState:
 kind,worker=action
 if state.terminal is not None:return state
 if kind=='claim':
  if state.owner is None or state.expired:return LeaseState(worker,False,None,state.attempts+1,state.completions)
  return state
 if kind=='heartbeat':
  if state.owner==worker and not state.expired:return LeaseState(state.owner,False,None,state.attempts,state.completions)
  return state
 if kind=='expire':
  if state.owner is not None:return LeaseState(state.owner,True,None,state.attempts,state.completions)
  return state
 if kind=='finish':
  if state.owner==worker and not state.expired:return LeaseState(None,False,worker,state.attempts,state.completions+(worker,))
  return state
 raise ValueError('unknown lease action')

def verify_agent_lease_single_completion(max_steps=6):
 from itertools import product
 actions=(('claim','a'),('claim','b'),('heartbeat','a'),('heartbeat','b'),('expire',None),('finish','a'),('finish','b'))
 for length in range(1,max_steps+1):
  for seq in product(actions,repeat=length):
   state=LeaseState()
   for action in seq:state=lease_step(state,action)
   if len(state.completions)>1:return False
 return True

def verify_reclaimed_lease_rejects_old_finish():
 state=LeaseState();state=lease_step(state,('claim','a'));state=lease_step(state,('expire',None));state=lease_step(state,('claim','b'));before=state;state=lease_step(state,('finish','a'))
 if state!=before:return False
 state=lease_step(state,('finish','b'));return state.terminal=='b' and state.completions==('b',) and state.attempts==2
