import ast, sys, os, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SDK_PATH = os.path.join(ROOT, 'sdk', 'python')
REF_PATH = os.path.join(ROOT, 'reference')

def syntax_check():
    src = open(os.path.join(SDK_PATH, 'astravcs_sdk', 'client.py'), encoding='utf-8').read()
    ast.parse(src)
    print('SDK syntax OK')

def smoke_test():
    sys.path.insert(0, SDK_PATH)
    sys.path.insert(0, REF_PATH)
    from astravcs_sdk import AstraClient, AstraSDKError
    from astra_server import AstraServer
    from astra_local import LocalWorkspace
    from astra_security import Principal, Grant

    root = tempfile.mkdtemp(prefix='astra-sdk-smoke-')
    srv = AstraServer(root)
    tok = srv.tokens.issue(Principal('admin', 'human'), [Grant('*', '*')], None)
    addr = srv.serve()
    base = 'http://127.0.0.1:%d' % addr[1]
    c = AstraClient(base, tok)
    results = []

    def check(name, fn):
        try:
            out = fn()
            results.append((name, 'OK', str(out)[:90]))
            return out
        except AstraSDKError as e:
            results.append((name, 'FAIL', str(e)[:140]))
            return None
        except Exception as e:
            results.append((name, 'ERR', repr(e)[:140]))
            return None

    # health & capabilities
    check('health', lambda: c.health())
    check('capabilities', lambda: c.capabilities())

    # repository lifecycle
    check('create_repository', lambda: c.create_repository('smoke'))
    check('repositories', lambda: c.repositories())
    check('refs(empty)', lambda: c.refs('smoke'))

    # build a real commit using LocalWorkspace
    repo = srv.registry.open('smoke')
    w = LocalWorkspace(repo)
    (repo.worktree / 'README.md').write_text('hello from sdk smoke test')
    commit = w.commit(b'initial commit')
    rev = getattr(commit, 'revision_id', None) or commit['revision_id']

    check('refs(after commit)', lambda: c.refs('smoke'))
    check('repo_revision', lambda: c.repo_revision('smoke', rev))
    check('repo_search', lambda: c.repo_search('smoke', 'hello'))
    check('repo_sync_capabilities', lambda: c.repo_sync_capabilities('smoke'))
    check('repo_sync_plan', lambda: c.repo_sync_plan('smoke'))
    from astra_codec import ObjectType
    rev_obj = repo.get(ObjectType.REVISION, rev)
    tree_obj = repo.get(ObjectType.TREE, rev_obj.tree_id)
    content_oid = tree_obj.as_dict()[b'README.md'].content_id
    check('repo_content', lambda: len(c.repo_content('smoke', content_oid)) > 0 and 'bytes')

    # issues
    check('create_issue', lambda: c.create_issue('smoke', 'Bug title', 'some body'))
    issues = check('issues', lambda: c.issues('smoke'))
    issue_id = issues[0]['id'] if issues else None
    check('issue get', lambda: c.issue('smoke', issue_id))
    check('issue comments', lambda: c.repo_issue_comments('smoke', issue_id))
    check('comment_issue', lambda: c.comment_issue('smoke', issue_id, 'a comment'))
    check('close_issue', lambda: c.close_issue('smoke', issue_id))

    # proposals + review flow
    check('create_proposal', lambda: c.repo_create_proposal('smoke', 'refs/heads/main', rev, 'tester'))
    page = c.repo_list_proposals('smoke')
    pid = page['proposals'][0]['id'] if page.get('proposals') else None
    check('get_proposal', lambda: c.repo_get_proposal('smoke', pid))
    check('set_draft', lambda: c.repo_set_proposal_draft('smoke', pid, 'tester', True))
    check('set_ready', lambda: c.repo_set_proposal_draft('smoke', pid, 'tester', False))
    check('refresh source', lambda: c.repo_update_proposal_source('smoke', pid, rev, 'tester', expected_old=rev))
    check('request_reviewers', lambda: c.repo_request_reviewers('smoke', pid, 'tester', principals=['bob']))
    check('list_requested_reviewers', lambda: c.repo_list_requested_reviewers('smoke', pid))
    check('remove_reviewers', lambda: c.repo_remove_requested_reviewers('smoke', pid, 'tester', principals=['bob']))
    check('add_review', lambda: c.repo_add_review('smoke', pid, 'tester', 'approved'))
    check('set_check', lambda: c.repo_set_check('smoke', pid, 'tests', 'completed', 'success'))
    check('mergeability', lambda: c.repo_list_proposals_mergeability('smoke', pid))
    check('recommended_reviewers', lambda: c.repo_list_proposals_recommended_reviewers('smoke', pid))
    check('evidence', lambda: c.repo_policy_evidence('smoke', pid))
    check('evidence history', lambda: c.repo_evidence_history('smoke', pid))
    check('threads list', lambda: c.repo_list_review_threads('smoke', pid))
    check('enqueue', lambda: c.repo_enqueue_merge('smoke', pid))
    check('merge_queue list', lambda: c.merge_queue('smoke'))
    check('dequeue', lambda: c.repo_dequeue_merge('smoke', pid))
    check('merge proposal', lambda: c.repo_merge_proposal('smoke', pid))

    # owners / orgs / roles
    check('upsert_owner', lambda: c.repo_upsert_path_owner('smoke', '*.md', 'principal', 'bob'))
    check('list_owners', lambda: c.repo_list_path_owners('smoke'))
    check('remove_owner', lambda: c.repo_remove_path_owner('smoke', '*.md', 'principal', 'bob'))
    org = check('create_org', lambda: c.create_org('acme', 'tester', 'admin'))
    org_id = org['id'] if org else 'acme'
    check('list_orgs', lambda: c.list_orgs())
    check('org members', lambda: c.list_org_members(org_id))
    check('org teams', lambda: c.list_org_teams(org_id))
    check('add_team', lambda: c.add_org_team(org_id, 'devs'))
    check('bind_org', lambda: c.repo_bind_org('smoke', org_id))
    check('list_org_binding', lambda: c.repo_list_org_binding('smoke'))
    check('set_repo_role', lambda: c.repo_set_repo_role('smoke', 'principal', 'bob', 'write'))

    # events
    check('events', lambda: c.events_page())

    # workspaces
    entry = [{'name': 'main', 'repository': 'smoke', 'revision': rev, 'mount': '.'}]
    ws = check('create_workspace', lambda: c.create_workspace('ws', entry))
    check('get_workspace', lambda: c.get_workspace(ws['id']) if ws else None)

    # plugins & policies
    check('list_plugins', lambda: c.list_plugins())
    check('list_policies', lambda: c.list_policies())
    check('upsert_policy', lambda: c.upsert_policy('refs/heads/main', required_reviews=1))
    check('delete_policy', lambda: c.delete_policy('refs/heads/main'))

    # ref update
    check('update_ref', lambda: c.repo_update_ref('smoke', 'refs/heads/feature', rev))

    srv.close()

    failed = [r for r in results if r[1] != 'OK']
    for name, status, detail in results:
        line = '%-32s %s' % (name, status)
        if status != 'OK':
            line += '  ' + detail
        print(line)
    print('---')
    print('%d passed, %d failed of %d' % (len(results) - len(failed), len(failed), len(results)))
    return 1 if failed else 0

if __name__ == '__main__':
    syntax_check()
    sys.exit(smoke_test())
