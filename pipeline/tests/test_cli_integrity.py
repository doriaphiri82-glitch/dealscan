import json
from pathlib import Path
import pytest
import main
from helpers import authorized_county
from config.counties import registry
import registry_sync


@pytest.mark.parametrize('status,expected',[('ok',0),('degraded',1),('error',1),('skipped',1)])
def test_cli_ingestion_exit_matches_actual_outcome(monkeypatch,status,expected):
    monkeypatch.setattr(main,'pull_registry',lambda:None)
    monkeypatch.setattr(main,'push_registry',lambda:None)
    monkeypatch.setattr(main,'run_all',lambda **kw:{'attempted':1,'ok':int(status=='ok'),'results':[{'status':status}]})
    assert main.main(['--run','--county','fixture','--etl-only'])==expected


def test_unattempted_requested_ingestion_is_not_a_green_run(monkeypatch):
    monkeypatch.setattr(main,'pull_registry',lambda:None)
    monkeypatch.setattr(main,'push_registry',lambda:None)
    monkeypatch.setattr(main,'run_all',lambda **kw:{'attempted':0,'ok':0,'results':[]})
    assert main.main(['--run','--county','fixture'])==1


def test_live_validation_targets_the_exact_requested_county(monkeypatch):
    calls=[]
    monkeypatch.setattr(main,'pull_registry',lambda:None)
    monkeypatch.setattr(main,'push_registry',lambda:None)
    monkeypatch.setattr(main,'validate_live_batch',lambda n,include,**kw:calls.append((n,kw)) or {'attempted':1,'valid':0,'unreachable':1})
    assert main.main(['--validate-live','1','--county','el_paso_tx'])==1
    assert calls==[(1,{'county_id':'el_paso_tx'})]


@pytest.mark.parametrize('operation',[['--verify-deal','1'],['--production-smoke','fixture'],['--authorize-county','fixture']])
def test_dry_run_cannot_accidentally_invoke_a_writing_operation(operation):
    with pytest.raises(SystemExit) as exc: main.main([*operation,'--dry-run'])
    assert exc.value.code==2


def test_failed_registry_read_does_not_push_a_stale_local_fallback(monkeypatch):
    monkeypatch.setattr(main,'pull_registry',lambda: (_ for _ in ()).throw(RuntimeError('unavailable')))
    monkeypatch.setattr(main,'push_registry',lambda: (_ for _ in ()).throw(AssertionError('must not overwrite authoritative state')))
    assert main.main(['--run','--county','fixture'])==1


def test_runtime_registry_uses_supabase_empty_as_authoritative(monkeypatch):
    county=authorized_county({'county_id':'fixture','county_name':'Fixture','persisted_count':1000,'verification_status':'verified'})
    registry._save_registry({'counties':{'fixture':county},'meta':{}})
    class Backend:
        def init_db(self): pass
        def get_counties(self): return []
    monkeypatch.setattr(registry_sync,'_USE_SUPABASE',True)
    monkeypatch.setattr(registry_sync,'get_backend',lambda:Backend())
    registry_sync.pull_registry()
    restored=registry.get_county('fixture')
    assert restored['ingestion_authorized'] is False and restored['validation_status']=='pending'
    assert restored.get('persisted_count') is None
    assert restored['arcgis_layer_url']==county['arcgis_layer_url']


def test_report_projection_excludes_raw_owner_credentials_and_registry_patches():
    report=main.safe_report({'results':[{'county_id':'fixture','raw_payload':{'OWNER':'PRIVATE'},
                                       'owner_name':'PRIVATE','registry_patch':{'secret':'PRIVATE'},
                                       'source_config':{'token':'PRIVATE'},'counts':{'stored':1}}]})
    assert report=={'results':[{'county_id':'fixture','counts':{'stored':1}}]}
    assert 'PRIVATE' not in json.dumps(report)


def test_workflows_use_reproducible_builds_and_never_commit_runtime_data():
    root=Path(__file__).parents[2]
    ci=(root/'.github/workflows/ci.yml').read_text()
    assert "node-version: '22'" in ci and 'npm ci' in ci and 'npm test' in ci and 'npm run typecheck' in ci
    assert "'supabase/**'" in ci and 'requirements.lock.txt' in ci
    scheduled=(root/'.github/workflows/scrape.yml').read_text()
    smoke=(root/'.github/workflows/production-smoke.yml').read_text()
    for content in (scheduled,smoke):
        assert 'DEALSCAN_DB_BACKEND: supabase' in content and 'DEALSCAN_ENV: production' in content
        assert 'group: dealscan-production-ingestion' in content and 'contents: read' in content
        assert 'git push' not in content and 'continue-on-error' not in content
        assert 'raw_payload' not in content and 'pipeline/data/**' not in content
    assert scheduled.index('--validate-live') < scheduled.index('--authorize-county') < scheduled.index('--run --etl-only')
    assert 'ENABLE_PRODUCTION_INGESTION' in scheduled
    assert '--production-smoke' in smoke and 'app_url:' in smoke


def test_read_only_coverage_hydrates_without_pushing(monkeypatch):
    calls=[]
    monkeypatch.setattr(main,'pull_registry',lambda:calls.append('read'))
    monkeypatch.setattr(main,'push_registry',lambda:calls.append('write'))
    assert main.main(['--coverage'])==0
    assert calls==['read']


def test_scheduler_delegates_to_bounded_cli_and_preserves_failure(monkeypatch):
    import scheduler
    calls=[]
    monkeypatch.setattr(scheduler,'pipeline_main',lambda argv:calls.append(argv) or 1)
    assert scheduler.main(['--run-once','--county','fixture','--max-records','25'])==1
    assert calls==[['--run','--max-records','25','--etl-only','--county','fixture']]


def test_production_watcher_cannot_bypass_workflow_controls(monkeypatch):
    import scheduler
    monkeypatch.setenv('DEALSCAN_ENV','production')
    with pytest.raises(SystemExit) as exc: scheduler.main(['--watch'])
    assert exc.value.code==2


def test_legacy_runner_preserves_disabled_operation_failure(monkeypatch,tmp_path):
    import os,subprocess,sys
    from pathlib import Path
    monkeypatch.setenv('DEALSCAN_SQLITE_PATH',str(tmp_path/'isolated.db'))
    script=Path(__file__).resolve().parents[1]/'runner.py'
    result=subprocess.run([sys.executable,str(script),'--deliver'],env=os.environ.copy(),capture_output=True,text=True,timeout=20)
    assert result.returncode==1
    assert not (tmp_path/'isolated.db').exists()


@pytest.mark.parametrize('flag',['--authorize-county','--authorize-ingestion'])
def test_runbook_authorization_flag_preserves_exact_county_gate(monkeypatch,flag):
    calls=[]
    monkeypatch.setattr(main,'pull_registry',lambda:None)
    monkeypatch.setattr(main,'push_registry',lambda:None)
    monkeypatch.setattr(main,'authorize_county',lambda cid:calls.append(cid) or {'authorized':False})
    assert main.main([flag,'el_paso_tx'])==1
    assert calls==['el_paso_tx']


def test_production_readiness_runs_before_any_ingestion_and_defaults_to_read_only():
    text=(Path(__file__).parents[2]/'.github/workflows/production-smoke.yml').read_text()
    assert 'preflight_only:' in text and 'default: true' in text
    assert text.index('validation.production_preflight') < text.index('--production-smoke')
    assert 'if: ${{ !inputs.preflight_only }}' in text
    install=text[text.index('- name: Install dependencies'):text.index('- name: Read-only production readiness')]
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in install
