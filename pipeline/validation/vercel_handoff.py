"""Vercel production runtime inspection with strict evidence boundaries.

Uses only VERCEL_TOKEN from the Actions secret store (never printed, never
echoed in headers/diagnostics). The only mutating call is an idempotent
promotion of an already-built READY deployment whose commit equals the
reviewed main HEAD, and only when the workflow passes --promote. Everything
else is read-only HTTP. Environment listings report variable names and targets
only: values from any provider are never fetched or printed.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests

REQUIRED_PUBLIC_ENV = ('NEXT_PUBLIC_SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_ANON_KEY')
REQUIRED_SERVER_ENV = ('SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY')
REQUIRED_OPERATOR_ENV = ('WAITLIST_CONTACT_EMAIL',)
EXPECTED_ROOT = 'landing'
EXPECTED_NODE = '22.x'
# Mirrors production_preflight: the operator-provided public contact, not a credential.
EXPECTED_CONTACT = 'doriaphiri82@gmail.com'
_ENV_ALLOWLIST = ('key', 'target', 'type')
_PROJECT_ALLOWLIST = ('id', 'name', 'framework', 'rootDirectory', 'buildCommand',
                      'installCommand', 'outputDirectory', 'nodeVersion')
_TIMEOUT = (5, 20)


class HandoffFailure(RuntimeError):
    pass


def https_origin(value: str, *, name: str = 'URL') -> str:
    """Only a canonical HTTPS origin; no credentials, query, fragment or path."""
    try:
        url = urlsplit(str(value or ''))
        host = url.hostname.lower() if url.hostname else ''
        if url.scheme == 'https' and host and ':' not in host and not (
                url.username or url.password or url.query or url.fragment or url.path.strip('/')):
            return 'https://' + host
    except ValueError:
        pass
    raise HandoffFailure(f'{name} must be a bare HTTPS origin')


def sanitize_env(items: object) -> list[dict]:
    """Name/target/type only. Values from the provider are dropped here."""
    out = []
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict) and isinstance(item.get('key'), str):
            targets = item.get('target')
            out.append({'key': item['key'],
                        'target': [t for t in targets if isinstance(t, str)] if isinstance(targets, list) else [],
                        'type': item.get('type') if isinstance(item.get('type'), str) else None})
    return out


def required_env_status(items: list[dict], *, target: str = 'production') -> dict:
    """Which required variables exist for the target, by name only."""
    present = {}
    for item in items:
        key = item.get('key')
        if isinstance(key, str) and target in (item.get('target') or []):
            present[key] = item.get('type')
    required = [*REQUIRED_PUBLIC_ENV, *REQUIRED_SERVER_ENV, *REQUIRED_OPERATOR_ENV]
    missing = [key for key in required if key not in present]
    return {'target': target, 'present': sorted(present), 'missing': missing,
            'status': 'passed' if not missing else 'failed'}


def sanitize_project(info: object) -> dict:
    if not isinstance(info, dict):
        return {}
    project = {key: info.get(key) for key in _PROJECT_ALLOWLIST if info.get(key) is not None}
    link = info.get('link')
    if isinstance(link, dict):
        project['git'] = {key: link.get(key) for key in ('type', 'repo', 'productionBranch')
                          if isinstance(link.get(key), str)}
    return project


def sanitize_deployment(item: object) -> dict:
    if not isinstance(item, dict):
        return {}
    meta = item.get('meta') if isinstance(item.get('meta'), dict) else {}
    sha = meta.get('githubCommitSha') if isinstance(meta.get('githubCommitSha'), str) else None
    return {'uid': item.get('uid'), 'url': item.get('url'), 'state': item.get('state'),
            'commit': sha, 'created': item.get('created')}


def promotion_decision(main_sha: str | None, production: dict, ready: list[dict]) -> dict:
    """Promote only a READY deployment of the exact reviewed main commit."""
    valid = isinstance(main_sha, str) and re.fullmatch(r'[0-9a-f]{40}', main_sha or '') is not None
    if not valid:
        return {'action': 'blocked', 'reason': 'undetermined_main_commit'}
    prod_sha = production.get('commit') if production else None
    if production.get('state') == 'READY' and prod_sha == main_sha:
        return {'action': 'none', 'reason': 'already_current', 'commit': main_sha}
    for item in ready:
        if item.get('commit') == main_sha and item.get('state') == 'READY' and item.get('uid'):
            return {'action': 'promote', 'deployment': item['uid'], 'commit': main_sha,
                    'current_production_commit': prod_sha if isinstance(prod_sha, str) else None}
    return {'action': 'blocked', 'reason': 'no_ready_deployment_for_reviewed_main',
            'commit': main_sha, 'current_production_commit': prod_sha if isinstance(prod_sha, str) else None}


def health_verdict(status_code: int, body: object) -> dict:
    row = body if isinstance(body, dict) else {}
    ok = status_code == 200 and row.get('database') == 'ok'
    return {'status': 'passed' if ok else 'failed', 'http_status': status_code,
            'database': row.get('database') if isinstance(row.get('database'), str) else None}


def page_verdict(status_code: int, body: str, *, contact: str = EXPECTED_CONTACT,
                 require_contact: bool = False) -> dict:
    ok = status_code == 200 and (not require_contact or ('mailto:' + contact) in body)
    return {'status': 'passed' if ok else 'failed', 'http_status': status_code,
            'operator_contact_matches': ('mailto:' + contact) in body}


class VercelClient:
    def __init__(self, token: str) -> None:
        if not token or not token.strip():
            raise HandoffFailure('VERCEL_TOKEN is missing')
        self.token = token.strip()

    def _call(self, method: str, path: str, **kwargs) -> requests.Response:
        try:
            response = requests.request(method, 'https://api.vercel.com' + path,
                headers={'Authorization': 'Bearer ' + self.token},
                timeout=_TIMEOUT, allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise HandoffFailure('vercel_api_unavailable') from None
        if response.status_code in (401, 403):
            raise HandoffFailure(f'vercel_token_denied (HTTP {response.status_code})')
        return response

    def json(self, method: str, path: str, **kwargs):
        response = self._call(method, path, **kwargs)
        if response.status_code != 200:
            raise HandoffFailure(f'vercel_api_error (HTTP {response.status_code}) for {path.split("?")[0]}')
        try:
            return response.json()
        except ValueError:
            raise HandoffFailure('vercel_api_returned_non_json') from None

    def resolve_project(self, name: str) -> tuple[dict, str | None]:
        """Find the project by name across accessible teams, then personal account."""
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', name):
            raise HandoffFailure('Project name must be a DNS-safe slug')
        teams = []
        try:
            teams = [t.get('slug') for t in self.json('GET', '/v2/teams').get('teams', [])
                     if isinstance(t, dict) and isinstance(t.get('slug'), str)]
        except HandoffFailure:
            teams = []
        for slug in [*teams, None]:
            params = {'slug': slug} if slug else {}
            response = self._call('GET', f'/v9/projects/{name}', params=params)
            if response.status_code == 404:
                continue
            if response.status_code != 200:
                raise HandoffFailure(f'vercel_project_lookup_failed (HTTP {response.status_code})')
            return response.json(), slug
        raise HandoffFailure(f'project {name} is not accessible to this token')


def _public_get(url: str) -> requests.Response:
    try:
        response = requests.get(url, timeout=_TIMEOUT, allow_redirects=False,
                                headers={'User-Agent': 'dealscan-readiness/1'})
    except requests.RequestException:
        raise HandoffFailure('deployed_site_unavailable') from None
    return response


def run_handoff(client: VercelClient, project_name: str, alias: str, main_sha: str | None,
                *, promote: bool) -> dict:
    checks = {}
    origin = https_origin(alias, name='Production alias')
    info, team = client.resolve_project(project_name)
    project = sanitize_project(info)
    project_id = project.get('id') or info.get('id')
    if not isinstance(project_id, str):
        raise HandoffFailure('vercel_project_id_missing')
    params = {'slug': team} if team else {}
    checks['project'] = {'status': 'passed', 'team': team, **project}
    checks['project']['root_directory_matches'] = project.get('rootDirectory') == EXPECTED_ROOT
    node = project.get('nodeVersion')
    # Vercel's REST project payload does not always expose the dashboard Node
    # setting; when absent, builds are governed by package.json engines (22.x).
    checks['project']['node_version'] = node
    checks['project']['node_version_matches'] = node in (None, EXPECTED_NODE)

    env_rows = sanitize_env(client.json('GET', f'/v9/projects/{project_id}/env', params={**params, 'limit': '100'}).get('envs', []))
    checks['environment'] = required_env_status(env_rows)

    deployments = client.json('GET', '/v6/deployments',
        params={**params, 'projectId': project_id, 'target': 'production', 'limit': '5'}).get('deployments', [])
    production = sanitize_deployment(deployments[0]) if deployments else {}
    recent = client.json('GET', '/v6/deployments',
        params={**params, 'projectId': project_id, 'limit': '20'}).get('deployments', [])
    ready = [sanitize_deployment(d) for d in recent if isinstance(d, dict)]
    checks['production'] = {'status': 'passed' if production.get('state') == 'READY' else 'failed', **production}

    decision = promotion_decision(main_sha, production, ready)
    if decision['action'] == 'promote' and not promote:
        decision = {'action': 'skipped', 'reason': 'promotion_not_enabled_for_this_run', **{k: v for k, v in decision.items() if k != 'action' and k != 'reason'}}
    checks['promotion'] = decision
    if decision.get('action') == 'promote':
        response = client._call('POST', f"/v10/projects/{project_id}/promote/{decision['deployment']}", params=params)
        if response.status_code not in (200, 201):
            raise HandoffFailure(f'vercel_promotion_failed (HTTP {response.status_code})')
        # Poll until the alias serves the reviewed commit (bounded, read-only).
        settled = False
        for _ in range(12):
            time.sleep(5)
            deployments = client.json('GET', '/v6/deployments',
                params={**params, 'projectId': project_id, 'target': 'production', 'limit': '1'}).get('deployments', [])
            current = sanitize_deployment(deployments[0]) if deployments else {}
            if current.get('commit') == decision['commit'] and current.get('state') == 'READY':
                checks['production'] = {'status': 'passed', **current}
                settled = True
                break
        decision['settled'] = settled
        if not settled:
            raise HandoffFailure('vercel_promotion_did_not_settle')

    live = {}
    try:
        response = _public_get(origin + '/')
        live['/'] = page_verdict(response.status_code, response.text)
    except HandoffFailure as exc:
        live['/'] = {'status': 'failed', 'reason': str(exc)}
    try:
        response = _public_get(origin + '/privacy')
        live['/privacy'] = page_verdict(response.status_code, response.text, require_contact=True)
    except HandoffFailure as exc:
        live['/privacy'] = {'status': 'failed', 'reason': str(exc)}
    try:
        response = _public_get(origin + '/api/health')
        try:
            body = response.json()
        except ValueError:
            body = None
        live['/api/health'] = health_verdict(response.status_code, body)
    except HandoffFailure as exc:
        live['/api/health'] = {'status': 'failed', 'reason': str(exc)}
    checks['live'] = live

    node = checks['project'].get('node_version')
    passed = (checks['project']['root_directory_matches'] and node in (None, EXPECTED_NODE)
              and checks['environment']['status'] == 'passed'
              and checks['production'].get('status') == 'passed'
              and checks['production'].get('commit') == main_sha
              and all(checks['live'][path].get('status') == 'passed' for path in ('/', '/privacy', '/api/health')))
    return {'status': 'handoff_verified' if passed else 'blocked',
            'scope': 'vercel_runtime_inspection', 'promotion_permitted': promote,
            'checked_at': datetime.now(timezone.utc).isoformat(), 'commit': os.getenv('GITHUB_SHA'),
            'reviewed_main_commit': main_sha, 'checks': checks,
            'note': 'Supabase Auth site/callback URLs require Supabase management access (SUPABASE_ACCESS_TOKEN); '
                    'they are not readable through a Vercel token. Values of environment variables are never inspected.'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='dealscan')
    parser.add_argument('--alias', default='https://dealscan-omega.vercel.app')
    parser.add_argument('--main-sha', default=os.getenv('REVIEWED_MAIN_SHA', ''))
    parser.add_argument('--promote', action='store_true',
                        help='Allow the idempotent promote-to-reviewed-main step (operator authorized)')
    parser.add_argument('--report-file', required=True)
    args = parser.parse_args(argv)
    try:
        client = VercelClient(os.getenv('VERCEL_TOKEN', ''))
        report = run_handoff(client, args.project, args.alias, args.main_sha.strip().lower() or None,
                             promote=args.promote)
    except HandoffFailure as exc:
        report = {'status': 'blocked', 'scope': 'vercel_runtime_inspection',
                  'checked_at': datetime.now(timezone.utc).isoformat(),
                  'commit': os.getenv('GITHUB_SHA'), 'failure': str(exc), 'checks': {}}
    path = Path(args.report_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if os.getenv('GITHUB_ACTIONS') == 'true':
        message = json.dumps(report, separators=(',', ':')).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        level = 'notice' if report['status'] == 'handoff_verified' else 'error'
        print(f'::{level} title=Vercel production handoff::{message}')
    return 0 if report['status'] == 'handoff_verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
