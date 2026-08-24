"""Version/capability negotiation shared by AstraVCS clients and servers."""
from __future__ import annotations
from dataclasses import dataclass

class CompatibilityError(RuntimeError):pass

@dataclass(frozen=True)
class CompatibilityDescriptor:
 api_versions: tuple[int,...]=(1,)
 repository_formats: tuple[int,...]=(1,)
 bundle_formats: tuple[int,...]=(1,2)
 semantic_schemas: tuple[int,...]=(0,1)
 sync_protocol_versions: tuple[int,...]=(1,)

 def __post_init__(self):
  for name in ('api_versions','repository_formats','bundle_formats','semantic_schemas','sync_protocol_versions'):
   values=getattr(self,name)
   if not values or any(not isinstance(v,int) or v<0 for v in values) or tuple(sorted(set(values)))!=values:raise ValueError(f'{name} must be sorted unique non-negative versions')
 def canonical(self):
  return {name:list(getattr(self,name)) for name in ('api_versions','repository_formats','bundle_formats','semantic_schemas','sync_protocol_versions')}
 @classmethod
 def from_dict(cls,data):
  try:return cls(**{name:tuple(int(v) for v in data[name]) for name in ('api_versions','repository_formats','bundle_formats','semantic_schemas','sync_protocol_versions')})
  except Exception as exc:raise CompatibilityError('malformed compatibility descriptor') from exc
 def negotiate(self,peer:'CompatibilityDescriptor'):
  chosen={}
  for name in ('api_versions','repository_formats','bundle_formats','semantic_schemas','sync_protocol_versions'):
   common=sorted(set(getattr(self,name))&set(getattr(peer,name)))
   if not common:raise CompatibilityError(f'no common {name}')
   chosen[name]=common[-1]
  return NegotiatedCompatibility(**chosen)

@dataclass(frozen=True)
class NegotiatedCompatibility:
 api_versions:int
 repository_formats:int
 bundle_formats:int
 semantic_schemas:int
 sync_protocol_versions:int
 def canonical(self):return self.__dict__.copy()

CURRENT_COMPATIBILITY=CompatibilityDescriptor()
