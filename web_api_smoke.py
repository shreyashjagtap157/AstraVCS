"""Driver: boots the reference server, then runs apps/web/api-smoke.mjs (compiled web API client)."""
import os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'reference'))
from astra_server import AstraServer
from astra_local import LocalWorkspace
from astra_security import Principal, Grant


def main():
    static_dir = os.path.join(ROOT, 'apps', 'web')
    root = tempfile.mkdtemp(prefix='astra-web-smoke-')
    srv = AstraServer(root, static_dir=static_dir)
    tok = srv.tokens.issue(Principal('admin', 'human'), [Grant('*', '*')], None)
    addr = srv.serve()
    base = 'http://127.0.0.1:%d' % addr[1]

    srv.registry.create('websmoke')
    repo = srv.registry.open('websmoke')
    w = LocalWorkspace(repo)
    (repo.worktree / 'README.md').write_text('hello from web api smoke test')
    commit = w.commit(b'initial commit')
    rev = getattr(commit, 'revision_id', None) or commit['revision_id']

    import urllib.error, urllib.request
    failures = []

    def http_check(name, req, want_status, want_sub=None, want_headers=None):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body = resp.read()
                headers = dict(resp.headers)
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read()
            headers = dict(e.headers)
        ok = status == want_status
        if ok and want_sub is not None:
            ok = want_sub in body
        if ok and want_headers:
            ok = all(headers.get(h) == v for h, v in want_headers.items())
        print('%-32s %s' % (name, 'OK' if ok else 'FAIL status=%s' % status))
        if not ok:
            failures.append(name)

    # CORS preflight for the browser client
    pre = urllib.request.Request(base + '/v1/repos', method='OPTIONS')
    pre.add_header('Origin', 'http://localhost:5173')
    pre.add_header('Access-Control-Request-Method', 'POST')
    pre.add_header('Access-Control-Request-Headers', 'authorization,content-type')
    http_check('cors preflight', pre, 204, want_headers={'Access-Control-Allow-Origin': '*'})
    get = urllib.request.Request(base + '/v1/repos', method='GET')
    get.add_header('Origin', 'http://localhost:5173')
    get.add_header('Authorization', 'Bearer ' + tok)
    http_check('cors actual response', get, 200, want_headers={'Access-Control-Allow-Origin': '*'})

    # static web app hosting
    http_check('static index', urllib.request.Request(base + '/'), 200, b'doctype html')
    http_check('static app.js', urllib.request.Request(base + '/dist/app.js'), 200, b'loadRepos')
    http_check('static api.js', urllib.request.Request(base + '/dist/api.js'), 200, b'AstraApi')
    http_check('static styles', urllib.request.Request(base + '/styles.css'), 200, b'grid-template-columns')
    http_check('static traversal blocked', urllib.request.Request(base + '/..%2f..%2fsecret'), 404, None)

    env = dict(os.environ, ASTRA_BASE=base, ASTRA_TOKEN=tok, ASTRA_REV=rev)
    node = os.path.join(ROOT, 'apps', 'web', 'api-smoke.mjs')
    proc = subprocess.run(['node', node], env=env, capture_output=True, text=True, timeout=180)
    sys.stdout.write(proc.stdout)
    if proc.stderr.strip():
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        failures.append('api-smoke.mjs')

    # local daemon (desktop client path): CORS + workspace routes
    import json
    from astra_daemon import AstraDaemon
    (repo.worktree / 'README.md').write_text('hello from web api smoke test\nupdated for daemon')
    daemon = AstraDaemon(repo)
    daddr = daemon.serve()
    dbase = 'http://127.0.0.1:%d' % daddr[1]
    session_file = repo.metadata_root / 'state' / 'daemon-session.json'
    session_ok = session_file.is_file() and b'"token"' in session_file.read_bytes() and b'"url"' in session_file.read_bytes()
    print('%-32s %s' % ('daemon session file', 'OK' if session_ok else 'FAIL'))
    if not session_ok:
        failures.append('daemon session file')

    dpre = urllib.request.Request(dbase + '/v1/status', method='OPTIONS')
    dpre.add_header('Origin', 'http://tauri.localhost')
    dpre.add_header('Access-Control-Request-Method', 'GET')
    dpre.add_header('Access-Control-Request-Headers', 'authorization')
    http_check('daemon cors preflight', dpre, 204, want_headers={'Access-Control-Allow-Origin': '*'})

    def daemon_call(path, method='GET', body=None, token=None):
        headers = {'Origin': 'http://tauri.localhost'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            headers['Content-Type'] = 'application/json'
        return urllib.request.Request(dbase + path, method=method, data=data, headers=headers)

    http_check('daemon rejects bad token', daemon_call('/v1/status', token='wrong'), 403)
    http_check('daemon cors status', daemon_call('/v1/status', token=daemon.token), 200, b'"entries"',
               {'Access-Control-Allow-Origin': '*'})
    http_check('daemon branches list', daemon_call('/v1/branches', token=daemon.token), 200, b'"branches"')
    http_check('daemon log', daemon_call('/v1/log', token=daemon.token), 200, b'"history"')
    http_check('daemon commit', daemon_call('/v1/commit', 'POST', {'message': 'daemon smoke'}, daemon.token), 201, b'"revision"')
    http_check('daemon create branch', daemon_call('/v1/branches', 'POST', {'name': 'daemon-feature'}, daemon.token), 201, b'"ok"')
    http_check('daemon switch branch', daemon_call('/v1/switch', 'POST', {'name': 'daemon-feature'}, daemon.token), 200, b'"revision"')
    http_check('daemon checkout back', daemon_call('/v1/checkout', 'POST', {'revision': rev}, daemon.token), 200, b'"revision"')
    daemon.close()

    srv.close()
    print('---')
    if failures:
        print('FAILED: ' + ', '.join(failures))
        return 1
    print('web smoke: all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
