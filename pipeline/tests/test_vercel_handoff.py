"""Offline vercel handoff contracts. No network; fixture-only provider shapes."""
from __future__ import annotations
import pytest
from validation import vercel_handoff as vh

SHA = 'a' * 40
OTHER_SHA = 'b' * 40


def response(status=200, payload=None):
    class R:
        status_code = status
        text = ''
        def json(self):
            if payload is None:
                raise ValueError('no json')
            return payload
    return R()


def env_item(key, targets=('production', 'preview'), typ='plain'):
    # Provider responses include values; fixtures verify they are dropped.
    return {'key': key, 'value': 'SUPER-SECRET-VALUE', 'target': list(targets), 'type': typ, 'id': 'x1'}


def raw_dep(uid, sha, state='READY', created=1):
    # Raw API shape: the commit lives under meta.githubCommitSha.
    return {'uid': uid, 'url': uid + '.vercel.app', 'state': state, 'created': created,
            'meta': {'githubCommitSha': sha, 'githubCommitMessage': 'internal'}}


def test_origin_requires_bare_https():
    assert vh.https_origin('https://dealscan-omega.vercel.app') == 'https://dealscan-omega.vercel.app'
    for bad in ('http://example.com', 'https://user:pw@x.vercel.app', 'https://x.vercel.app/path',
                'https://x.vercel.app/?q=1', 'javascript:alert(1)', '', None):
        with pytest.raises(vh.HandoffFailure):
            vh.https_origin(bad)


def test_sanitize_env_never_keeps_values():
    rows = vh.sanitize_env([env_item('NEXT_PUBLIC_SUPABASE_URL'), env_item('SUPABASE_SERVICE_ROLE_KEY')])
    assert all('value' not in row and set(row) <= {'key', 'target', 'type'} for row in rows)
    assert sorted(row['key'] for row in rows) == ['NEXT_PUBLIC_SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY']
    assert vh.sanitize_env('not-a-list') == []


def test_required_env_status_scopes_to_production_and_names_only():
    rows = vh.sanitize_env([env_item('NEXT_PUBLIC_SUPABASE_URL', ('production',)),
                            env_item('SUPABASE_URL', ('preview',))])
    status = vh.required_env_status(rows)
    assert status['status'] == 'failed'
    assert 'NEXT_PUBLIC_SUPABASE_URL' in status['present']
    assert 'SUPABASE_URL' in status['missing']  # preview-only does not count
    assert 'SUPER-SECRET-VALUE' not in str(status)


def test_required_env_status_passes_when_complete():
    keys = (*vh.REQUIRED_PUBLIC_ENV, *vh.REQUIRED_SERVER_ENV, *vh.REQUIRED_OPERATOR_ENV)
    rows = vh.sanitize_env([env_item(key, ('production',)) for key in keys])
    assert vh.required_env_status(rows)['status'] == 'passed'


def test_promotion_decision_paths():
    current = {'uid': 'd1', 'state': 'READY', 'commit': SHA}
    assert vh.promotion_decision(SHA, current, [current])['action'] == 'none'
    stale = {'uid': 'd0', 'state': 'READY', 'commit': OTHER_SHA}
    decision = vh.promotion_decision(SHA, stale, [current, stale])
    assert decision['action'] == 'promote' and decision['deployment'] == 'd1'
    assert vh.promotion_decision(SHA, stale, [stale])['reason'] == 'no_ready_deployment_for_reviewed_main'
    for bad in ('', None, 'zzzz', SHA.upper() + '0'):
        assert vh.promotion_decision(bad, current, [current])['reason'] == 'undetermined_main_commit'
    # A non-READY deployment of main must never be promoted.
    pending = {'uid': 'd2', 'state': 'BUILDING', 'commit': SHA}
    assert vh.promotion_decision(SHA, stale, [pending])['reason'] == 'no_ready_deployment_for_reviewed_main'


def test_health_and_page_verdicts():
    assert vh.health_verdict(200, {'status': 'ok', 'database': 'ok'})['status'] == 'passed'
    degraded = vh.health_verdict(503, {'database': 'not-configured'})
    assert degraded['status'] == 'failed' and degraded['database'] == 'not-configured'
    assert vh.health_verdict(200, {'database': 'unavailable'})['status'] == 'failed'
    html = '<a href="mailto:' + vh.EXPECTED_CONTACT + '">contact</a>'
    assert vh.page_verdict(200, html, require_contact=True)['status'] == 'passed'
    assert vh.page_verdict(200, 'no contact here', require_contact=True)['status'] == 'failed'
    assert vh.page_verdict(500, '')['status'] == 'failed'


def test_sanitize_project_and_deployment_allowlists():
    project = vh.sanitize_project({'id': 'p1', 'name': 'dealscan', 'rootDirectory': 'landing',
                                   'secretThing': 'x', 'link': {'type': 'github', 'repo': 'o/r', 'productionBranch': 'main'}})
    assert 'secretThing' not in project and project['git']['productionBranch'] == 'main'
    dep = vh.sanitize_deployment({'uid': 'd1', 'state': 'READY', 'meta': {'githubCommitSha': SHA, 'other': 1}})
    assert dep['commit'] == SHA and 'meta' not in dep


def test_client_requires_token_and_hides_denial_bodies(monkeypatch):
    with pytest.raises(vh.HandoffFailure):
        vh.VercelClient('  ')
    monkeypatch.setattr(vh.requests, 'request', lambda *a, **k: response(401, {'secret': 'leak'}))
    with pytest.raises(vh.HandoffFailure) as exc:
        vh.VercelClient('token').json('GET', '/v2/teams')
    assert 'leak' not in str(exc.value)


class FakeClient:
    def __init__(self, *, env_keys, prod, recent, promote_status=200, node='22.x', patch_status=200):
        self._env = env_keys; self._prod = prod; self._recent = recent
        self.promotions = []; self._promote_status = promote_status
        self._patch_status = patch_status
        self.patches = []
        self._project = {'id': 'p1', 'name': 'dealscan', 'rootDirectory': 'landing',
                         'framework': 'nextjs', 'nodeVersion': node}

    def resolve_project(self, name):
        return self._project, 'team-slug'

    def json(self, method, path, **kwargs):
        if '/env' in path:
            return {'envs': [env_item(key) for key in self._env]}
        if '/deployments' in path and (kwargs.get('params') or {}).get('target') == 'production':
            current = self._prod
            if self.promotions:
                current = next(d for d in self._recent if d['uid'] == self.promotions[-1])
            return {'deployments': [current]}
        if '/deployments' in path:
            return {'deployments': self._recent}
        raise AssertionError(path)

    def _call(self, method, path, **kwargs):
        if method == 'PATCH':
            self.patches.append((path, kwargs.get('json')))
            if self._patch_status in (200, 201):
                self._project.update(kwargs.get('json') or {})
            return response(self._patch_status, {'ok': True})
        self.promotions.append(path.rsplit('/', 1)[-1])
        return response(self._promote_status, {'ok': True})


def vercel_json(tmp_path, contact=vh.EXPECTED_CONTACT, with_build=True):
    import json as _json
    config = {'env': {'WAITLIST_CONTACT_EMAIL': contact}}
    if with_build:
        config['build'] = {'env': {'WAITLIST_CONTACT_EMAIL': contact}}
    path = tmp_path / 'vercel.json'
    path.write_text(_json.dumps(config))
    return path


def live_response(mapping):
    def get(url):
        status, payload, text = mapping[url]
        r = response(status, payload)
        r.text = text
        return r
    return get


def full_env():
    return [*vh.REQUIRED_PUBLIC_ENV, *vh.REQUIRED_SERVER_ENV, *vh.REQUIRED_OPERATOR_ENV]


def test_handoff_verified_when_everything_current(monkeypatch):
    dep = raw_dep('d1', SHA)
    client = FakeClient(env_keys=full_env(), prod=dict(dep), recent=[dict(dep)])
    origin = 'https://dealscan-omega.vercel.app'
    contact = 'mailto:' + vh.EXPECTED_CONTACT
    monkeypatch.setattr(vh, '_public_get', live_response({
        origin + '/': (200, None, '<html></html>'),
        origin + '/privacy': (200, None, contact),
        origin + '/api/health': (200, {'status': 'ok', 'database': 'ok'}, '')}))
    report = vh.run_handoff(client, 'dealscan', origin, SHA, promote=True)
    assert report['status'] == 'handoff_verified'
    assert report['checks']['promotion']['reason'] == 'already_current'
    assert client.promotions == []  # never promotes a current deployment


def test_handoff_promotes_stale_production(monkeypatch):
    stale = raw_dep('d0', OTHER_SHA, created=0)
    reviewed = raw_dep('d1', SHA)
    client = FakeClient(env_keys=full_env(), prod=dict(stale), recent=[dict(reviewed), dict(stale)])
    origin = 'https://dealscan-omega.vercel.app'
    monkeypatch.setattr(vh.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(vh, '_public_get', live_response({
        origin + '/': (200, None, 'ok'),
        origin + '/privacy': (200, None, 'mailto:' + vh.EXPECTED_CONTACT),
        origin + '/api/health': (200, {'database': 'ok'}, '')}))
    report = vh.run_handoff(client, 'dealscan', origin, SHA, promote=True)
    assert client.promotions == ['d1'] and report['status'] == 'handoff_verified'
    assert report['checks']['production']['commit'] == SHA


def test_handoff_reports_not_promotes_without_enablement(monkeypatch):
    stale = raw_dep('d0', OTHER_SHA, created=0)
    reviewed = raw_dep('d1', SHA)
    client = FakeClient(env_keys=full_env(), prod=dict(stale), recent=[dict(reviewed)])
    origin = 'https://dealscan-omega.vercel.app'
    monkeypatch.setattr(vh, '_public_get', live_response({
        origin + '/': (200, None, 'ok'),
        origin + '/privacy': (200, None, 'mailto:' + vh.EXPECTED_CONTACT),
        origin + '/api/health': (200, {'database': 'ok'}, '')}))
    report = vh.run_handoff(client, 'dealscan', origin, SHA, promote=False)
    assert client.promotions == []
    assert report['checks']['promotion']['action'] == 'skipped'
    assert report['status'] == 'blocked'  # production is not the reviewed commit


def test_handoff_blocked_on_missing_env_and_health(monkeypatch):
    dep = raw_dep('d1', SHA)
    client = FakeClient(env_keys=['NEXT_PUBLIC_SUPABASE_URL'], prod=dict(dep), recent=[dict(dep)])
    origin = 'https://dealscan-omega.vercel.app'
    monkeypatch.setattr(vh, '_public_get', live_response({
        origin + '/': (200, None, 'ok'),
        origin + '/privacy': (200, None, 'mailto:' + vh.EXPECTED_CONTACT),
        origin + '/api/health': (503, {'database': 'not-configured'}, '')}))
    report = vh.run_handoff(client, 'dealscan', origin, SHA, promote=True)
    assert report['status'] == 'blocked'
    assert report['checks']['environment']['status'] == 'failed'
    assert 'SUPABASE_SERVICE_ROLE_KEY' in report['checks']['environment']['missing']
    assert report['checks']['live']['/api/health']['database'] == 'not-configured'


def test_handoff_refuses_wrong_root_and_promotion_failure(monkeypatch):
    stale = raw_dep('d0', OTHER_SHA, created=0)
    reviewed = raw_dep('d1', SHA)
    client = FakeClient(env_keys=full_env(), prod=dict(stale), recent=[dict(reviewed)], promote_status=500)
    origin = 'https://dealscan-omega.vercel.app'
    monkeypatch.setattr(vh, '_public_get', live_response({origin + '/': (200, None, '')}))
    with pytest.raises(vh.HandoffFailure, match='vercel_promotion_failed'):
        vh.run_handoff(client, 'dealscan', origin, SHA, promote=True)


def live_ok(monkeypatch, origin, health=(200, {'database': 'ok'})):
    monkeypatch.setattr(vh, '_public_get', live_response({
        origin + '/': (200, None, '<html></html>'),
        origin + '/privacy': (200, None, 'mailto:' + vh.EXPECTED_CONTACT),
        origin + '/api/health': (health[0], health[1], '')}))


def test_config_provided_env_contract(tmp_path):
    provided = vh.config_provided_env(vercel_json(tmp_path))
    assert set(provided) == {'WAITLIST_CONTACT_EMAIL'}
    assert provided['WAITLIST_CONTACT_EMAIL'].endswith('vercel.json')
    assert vh.config_provided_env(vercel_json(tmp_path, contact='someone-else@example.com')) == {}
    assert vh.config_provided_env(vercel_json(tmp_path, with_build=False)) == {}
    assert vh.config_provided_env(tmp_path / 'does-not-exist.json') == {}
    assert vh.config_provided_env(None) == {}


def test_config_provided_contact_satisfies_only_the_operator_key():
    rows = vh.sanitize_env([env_item(key) for key in (*vh.REQUIRED_PUBLIC_ENV, *vh.REQUIRED_SERVER_ENV)])
    status = vh.required_env_status(rows, config_provided={'WAITLIST_CONTACT_EMAIL': 'vercel.json',
                                                           'SUPABASE_SERVICE_ROLE_KEY': 'must-not-count'})
    assert status['status'] == 'passed'
    assert status['satisfied_via_config'] == {'WAITLIST_CONTACT_EMAIL': 'vercel.json'}
    assert 'SUPABASE_SERVICE_ROLE_KEY' in status['present']


def test_config_fix_actions_only_flags_documented_settings():
    assert vh.config_fix_actions({'nodeVersion': '24.x'}) == {'nodeVersion': {'from': '24.x', 'to': '22.x'}}
    assert vh.config_fix_actions({'nodeVersion': '22.x'}) == {}
    assert vh.config_fix_actions({'nodeVersion': None}) == {}
    assert vh.config_fix_actions({'rootDirectory': 'wrong', 'nodeVersion': '22.x'}) == {}


def test_handoff_applies_documented_node_fix(monkeypatch, tmp_path):
    dep = raw_dep('d1', SHA)
    client = FakeClient(env_keys=[*vh.REQUIRED_PUBLIC_ENV, *vh.REQUIRED_SERVER_ENV],
                        prod=dict(dep), recent=[dict(dep)], node='24.x')
    origin = 'https://dealscan-omega.vercel.app'
    live_ok(monkeypatch, origin)
    report = vh.run_handoff(client, 'dealscan', origin, SHA, promote=False, fix_config=True,
                            config_env=vercel_json(tmp_path))
    assert client.patches == [('/v9/projects/p1', {'nodeVersion': '22.x'})]
    assert report['checks']['config_fix']['status'] == 'applied'
    assert report['checks']['config_fix']['verified'] is True
    assert report['checks']['project']['node_version'] == '22.x'
    assert report['checks']['environment']['satisfied_via_config']['WAITLIST_CONTACT_EMAIL']
    assert report['status'] == 'handoff_verified'


def test_handoff_reports_rejected_config_fix(monkeypatch, tmp_path):
    dep = raw_dep('d1', SHA)
    client = FakeClient(env_keys=[*vh.REQUIRED_PUBLIC_ENV, *vh.REQUIRED_SERVER_ENV],
                        prod=dict(dep), recent=[dict(dep)], node='24.x', patch_status=400)
    origin = 'https://dealscan-omega.vercel.app'
    live_ok(monkeypatch, origin)
    report = vh.run_handoff(client, 'dealscan', origin, SHA, promote=False, fix_config=True,
                            config_env=vercel_json(tmp_path))
    assert report['checks']['config_fix']['status'] == 'failed'
    assert report['checks']['project']['node_version'] == '24.x'
    assert report['status'] == 'blocked'


def test_handoff_flags_fix_without_enablement(monkeypatch, tmp_path):
    dep = raw_dep('d1', SHA)
    client = FakeClient(env_keys=[*vh.REQUIRED_PUBLIC_ENV, *vh.REQUIRED_SERVER_ENV],
                        prod=dict(dep), recent=[dict(dep)], node='24.x')
    origin = 'https://dealscan-omega.vercel.app'
    live_ok(monkeypatch, origin)
    report = vh.run_handoff(client, 'dealscan', origin, SHA, promote=False, fix_config=False,
                            config_env=vercel_json(tmp_path))
    assert client.patches == []
    assert report['checks']['config_fix']['status'] == 'needed'
    assert report['status'] == 'blocked'
