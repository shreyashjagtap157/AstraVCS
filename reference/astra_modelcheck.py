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
