import copy,json
from pathlib import Path
import pytest
from backend import generation as g,generation_roles as roles,generation_delivery as delivery


def original(monkeypatch):
    fixture=json.loads((Path(__file__).parent/'fixtures/delivery_failure_1df.json').read_text())
    assets=fixture['assets'];monkeypatch.setattr(g,'asset',lambda j,stage:copy.deepcopy(assets[stage]))
    return fixture['job'],assets


def request_context(job):
    messages=roles.messages(job,'repair_build')
    return json.loads(next(m['content'] for m in messages if m['role']=='user'))


def test_original_failure_delivers_location_and_exact_difference_in_model_request(monkeypatch):
    j,_=original(monkeypatch);ctx=request_context(j);handoff=ctx['repair_handoff']
    edit=handoff['edits'][0]
    assert edit['path']=='agent.py' and set(edit['symbols'])=={'Agent','start'}
    row=next(r for r in handoff['public_requirements'] if r['case_id']=='timeout_degraded_empty')
    assert row['check_id'] in edit['requirements'] and row['objective']=='fault_reproduction'
    diff=next(d for d in row['field_requirements'] if d['path']==['diagnostics'])
    assert diff=={'path':['diagnostics'],'observed':{'present':True,'value':['backend_not_ready','startup_timeout']},'required_value':[],'matches':False}
    assert handoff['matrix_id']==j['matrix']['id']
    assert handoff['build_hash']==j['pending_plan']['must_preserve_hashes']['build']


def test_private_diagnosis_and_hidden_fingerprint_not_in_actual_request(monkeypatch):
    j,assets=original(monkeypatch)
    j['pending_plan']['work_order']['action']['edits'][0]['location']+=' SECRET_LOCATION'
    for field in ('current_behavior','intended_behavior','must_preserve'):
        j['pending_plan']['work_order']['action']['edits'][0][field]='SECRET_REVIEW_TEXT'
    hidden=next(c for c in assets['evaluation']['cases'] if c['visibility']=='hidden')
    assets['fingerprint']['checks'].append({'case_id':hidden['id'],'assertions':[{'path':['diagnostics'],'equals':'SECRET_ASSERTION'}]})
    text=json.dumps(request_context(j))
    assert all(secret not in text for secret in ('SECRET_LOCATION','SECRET_REVIEW_TEXT','SECRET_ASSERTION'))


def test_no_assertion_is_explicit_and_not_invented(monkeypatch):
    j,assets=original(monkeypatch);assets['fingerprint']['checks']=[]
    rows=request_context(j)['repair_handoff']['public_requirements']
    target=next(r for r in rows if r['case_id']=='timeout_degraded_empty')
    assert target['assertion_available'] is False and target['field_requirements']==[]


def test_stale_delivery_rejected(monkeypatch):
    j,_=original(monkeypatch);j['matrix']['id']='new-matrix'
    with pytest.raises(ValueError,match='过期'):request_context(j)


def test_missing_json_value_and_type_semantics():
    assert delivery.observed_value({},['x'])=={'present':False}
    assert delivery.observed_value({'x':None},['x'])=={'present':True,'value':None}
    assert delivery.observed_value([1],['01'])=={'present':False}
    assert delivery.locations('class Agent:\n def start(self): pass','Agent.start() SECRET')==['Agent','start']


def test_flow_passes_delivery_to_actual_adapter_boundary(client,monkeypatch):
    from backend import generation_flow as flow,generation_handoff as h,agent
    from test_handoff import prepared,order
    j=prepared();j['pending_plan']=h.validate_order(j,order(j));j['mode']='real';g.put(j)
    captured=[];files=g.asset(j,'build')['faulty'];files['app.py']+='\nDELIVERY_TEST_MARKER = 1\n'
    def completion(messages,**kwargs):
        captured.append(messages)
        return {'content':json.dumps({'result':{'kind':'modified','variants':{'faulty':files},'explanations':{'faulty':'隔离测试候选，只验证交接请求实际到达适配器。'}}}), '_meta':{'usage':{'completion_tokens':1},'finish_reason':'stop'}}
    monkeypatch.setattr(agent,'completion',completion)
    flow.call(j,'repair_build')
    ctx=json.loads(next(m['content'] for m in captured[0] if m['role']=='user'))
    assert ctx['repair_handoff']['edits'][0]['symbols']==['scenario']
    assert ctx['repair_handoff']['public_requirements']
    saved=json.loads((g.root(j)/j['attempts'][-1]['asset']/'input.json').read_text())
    assert saved==captured[0]


def test_fault_observations_do_not_compete_with_fault_objective(monkeypatch):
    j,_=original(monkeypatch);ctx=request_context(j)
    target=next(r for r in ctx['public_observations'] if r['case']=='timeout_degraded_empty')
    assert 'expected' not in target and target['actual']['diagnostics']==['backend_not_ready','startup_timeout']
    assert ctx['repair_handoff']['response_files']['faulty']==['agent.py','app.py','backend.py','registry.py']


def test_original_delivery_requirement_is_actionable_in_docker(client):
    fixture=json.loads((Path(__file__).parent/'fixtures/delivery_failure_1df.json').read_text())
    j=fixture['job'];j['id']='delivery-'+g.s.ident();assets=fixture['assets']
    from backend import generation_budget as budget
    j['budget']=budget.initialize(budget.BudgetPolicy())
    ok,reason=g.executor.availability()
    if not ok:pytest.skip(reason)
    for stage,value in assets.items():
        directory=g.root(j)/j['assets'][stage];directory.mkdir(parents=True,exist_ok=True)
        (directory/'output.json').write_text(json.dumps(value))
    handoff=delivery.compile_delivery(j)
    target=next(r for r in handoff['public_requirements'] if r['case_id']=='timeout_degraded_empty')
    delta=next(d for d in target['field_requirements'] if d['path']==['diagnostics'])
    assert delta['required_value']==[] and not delta['matches']
    # Test-only candidate: apply exactly the public feedback, never run it on host.
    code=assets['build']['faulty']['agent.py']
    old='self.diagnostics = ["backend_not_ready", "startup_timeout"]'
    assert code.count(old)==1
    assets['build']['faulty']['agent.py']=code.replace(old,'self.diagnostics = []')
    (g.root(j)/j['assets']['build']/'output.json').write_text(json.dumps(assets['build']))
    result=g.validate(j)
    assert result['passed'] and all(result['gates'].values())
    assert len(result['checks'])==30 and all(c['repeat_count']==2 for c in result['checks'])
