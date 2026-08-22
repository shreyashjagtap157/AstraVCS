#!/usr/bin/env python3
from pathlib import Path
import argparse,signal,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer
from astra_security import Principal,Grant
p=argparse.ArgumentParser();p.add_argument('--root',default='/var/lib/astravcs');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8080);p.add_argument('--bootstrap-token-file');a=p.parse_args();s=AstraServer(a.root)
if a.bootstrap_token_file:
 token=s.tokens.issue(Principal('bootstrap-admin','human'),[Grant('*','*')],3600);Path(a.bootstrap_token_file).write_text(token+'\n');Path(a.bootstrap_token_file).chmod(0o600)
addr=s.serve(a.host,a.port);print(f'AstraVCS reference server listening on {addr[0]}:{addr[1]}',flush=True)
stop=False
signal.signal(signal.SIGTERM,lambda *_:globals().__setitem__('stop',True));signal.signal(signal.SIGINT,lambda *_:globals().__setitem__('stop',True))
try:
 while not stop:time.sleep(.2)
finally:s.close()
