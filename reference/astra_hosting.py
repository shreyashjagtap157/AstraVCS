"""Shared hosted-runtime composition for multi-node AstraVCS deployments."""
from __future__ import annotations
from dataclasses import dataclass
import os
from astra_backend import SQLAlchemyMetadataBackend,HostedRepositoryRegistry,S3BlobBackend
from astra_shared_control import SharedControlPlane
from astra_server import AstraServer

class HostingConfigError(RuntimeError):pass

@dataclass
class SharedHostingRuntime:
 db_url:str
 repo_blobs:object
 control_blobs:object|None=None
 def __post_init__(self):
  self.control_blobs=self.control_blobs or self.repo_blobs
  self.repo_metadata=SQLAlchemyMetadataBackend(self.db_url);self.registry=HostedRepositoryRegistry(self.repo_metadata,self.repo_blobs);self.control=SharedControlPlane(self.db_url,self.control_blobs)
 def server(self,root,*,worker_id=None,policies=None):
  return AstraServer(root,policies=policies,registry=self.registry,tokens=self.control.token_store,platform=self.control.platform_store,agent_jobs=self.control.agent_store,packages=self.control.package_store,workspaces=self.control.workspace_store,worker_id=worker_id)
 def close(self):self.control.close();self.repo_metadata.close()

def shared_runtime_from_env(env=None,*,production=True):
 env=os.environ if env is None else env
 db_url=env.get('ASTRA_DATABASE_URL','').strip()
 bucket=env.get('ASTRA_S3_BUCKET','').strip()
 if not db_url:raise HostingConfigError('ASTRA_DATABASE_URL is required for shared hosting')
 if production and not db_url.startswith(('postgresql://','postgresql+')):raise HostingConfigError('production shared hosting requires PostgreSQL')
 if not bucket:raise HostingConfigError('ASTRA_S3_BUCKET is required for shared hosting')
 try:import boto3
 except ImportError as exc:raise HostingConfigError('boto3 is required for S3 shared hosting') from exc
 kwargs={}
 if env.get('ASTRA_S3_ENDPOINT'):kwargs['endpoint_url']=env['ASTRA_S3_ENDPOINT']
 if env.get('ASTRA_S3_REGION'):kwargs['region_name']=env['ASTRA_S3_REGION']
 client=boto3.client('s3',**kwargs);prefix=env.get('ASTRA_S3_PREFIX','astravcs/').strip('/')+'/'
 return SharedHostingRuntime(db_url,S3BlobBackend(client,bucket,prefix+'repo/'),S3BlobBackend(client,bucket,prefix+'control/'))
