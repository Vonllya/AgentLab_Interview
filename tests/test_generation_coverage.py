import copy
import json
from pathlib import Path
import pytest
from backend import generation as g, generation_flow as flow, generation_roles as roles, generation_mock as mock
from backend import generation_coverage as coverage, generation_protocol as protocol
from test_fault_model import modeled


def replay():
    fixture=json.loads((Path(__file__).parent/'fixtures/coverage_failure_98ab.json').read_text())
    j=modeled();j['contract']=fixture['contract'];j['contract_hash']=g.digest(j['contract'])
    path=g.root(j)/j['assets']['project_build']/'output.json';bundle=json.loads(path.read_text());bundle['fault_model']=fixture['fault_model'];path.write_text(json.dumps(bundle))
    j['assets'].pop('evaluation');j['assets'].pop('fingerprint');g.put(j)
    return j,fixture['evaluation']


def reject(j,raw,monkeypatch):
    monkeypatch.setattr(mock,'role_response',lambda stage,payload:copy.deepcopy(raw))
    with pytest.raises(coverage.CoverageError) as err:flow.call(j,'evaluation')
    flow.failure(j,'evaluation',err.value);coverage.begin_or_continue(j,err.value)
    return err.value


def complete(raw):
    result=copy.deepcopy(raw)
    added=copy.deepcopy(next(c for c in raw['cases'] if c['id']=='target-delay-wait'))
    added.update(id='public-delay-wait',visibility='public')
    result['cases'].append(added)
    return result


def test_real_failure_feedback_and_isolated_completion(client,monkeypatch):
    j,raw=replay();before=roles.context(j,'evaluation')
    assert 'coverage_completion' not in before and 'frozen_fault_model' not in json.dumps(before)
    error=reject(j,raw,monkeypatch)
    assert error.feedback['missing_target_visibilities']==['public']
    ctx=roles.context(j,'evaluation')
    assert ctx['coverage_feedback']==ctx['validation_feedback']
    assert ctx['coverage_feedback']['missing_target_visibilities']==['public']
    item=next(c for c in ctx['coverage_feedback']['classifications'] if c['case_id']=='target-delay-no-wait')
    assert item['proposed_group']=='target' and item['effective_group']=='regression'
    assert ctx['coverage_completion']['frozen_fault_model']
    assert not {'project','matrix','actual','previous_variants'} & set(ctx)
    fixed=complete(raw);monkeypatch.setattr(mock,'role_response',lambda stage,payload:fixed)
    parsed=flow.call(j,'evaluation')
    assert j['attempts'][-1]['blind'] is False
    assert g.public(j)['attempts'][-1]['coverage_completion'] is True
    assert 'coverage_repair' not in j and j['coverage_repairs'][-1]['status']=='completed'
    assert parsed['cases'][0]['group']=='regression'
    assert parsed['cases'][-1]['visibility']=='public'
    assert [c['expected'] for c in parsed['cases'][:-1]]==[c['expected'] for c in raw['cases']]


def test_no_oracle_mutation_and_no_code_handoff(client,monkeypatch):
    j,raw=replay();reject(j,raw,monkeypatch)
    bad=complete(raw);bad['cases'][0]['expected']['status']='ok'
    with pytest.raises(ValueError,match='只能追加'):protocol.evaluation(j,bad)
    # Resume at the persisted completion checkpoint: two retries total, no Docker or diagnosis.
    assert g.POOL.acquire(blocking=False)
    flow.run(j['id'],'evaluation');finished=g.get(j['id'])
    assert finished['status']=='needs_manual_review'
    assert finished['error']['category']=='coverage_incomplete'
    assert finished['matrix'] is None
    assert not finished.get('handoff_rejections')
    assert finished['coverage_repair']['attempts']==2
    assert len([a for a in finished['attempts'] if a['stage']=='evaluation' and a['status']=='failed'])==3


def test_malformed_feedback_is_unknown_not_original_classification(client,monkeypatch):
    j,raw=replay();reject(j,raw,monkeypatch)
    p=g.root(j)/j['evaluation_candidate']['asset']/'rejected.json';p.write_text('{}')
    assert roles.preflight_summary(j)['classification_status']=='unknown'


def test_preexecution_resume_never_enters_code_diagnosis(client,monkeypatch):
    j,raw=replay();j.update(status='needs_manual_review',checkpoint='evaluation');g.put(j)
    calls=[]
    monkeypatch.setattr(g,'launch',lambda id,stage:calls.append((id,stage)) or {})
    flow.resume(j['id'],'已核对冻结触发规则，需要补充公开等待就绪场景。')
    assert calls==[(j['id'],'evaluation')]
