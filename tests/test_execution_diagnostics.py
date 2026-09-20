import json
from types import SimpleNamespace
import pytest
from backend import executor, generation as g, generation_roles as roles, generation_flow as flow
from backend.execution_diagnostics import ENTRY_PROTOCOL, check_output, exception_diagnostic, behavior_difference
from test_generation_direct import built


@pytest.mark.parametrize('value,schema,path,reason', [
    ('{"ok":true}', {'type':'object'}, '$', 'type'),
    ({'items':[1,'2']}, {'type':'object','properties':{'items':{'type':'array','items':{'type':'integer'}}}}, '$/items/1','type'),
    ({}, {'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']}, '$/ok','required'),
    ('bad', {'type':'string','enum':['ok']}, '$','enum'),
])
def test_schema_diagnostic(value,schema,path,reason):
    with pytest.raises(ValueError) as caught:check_output(value,schema)
    detail=exception_diagnostic(caught.value)
    assert detail['category']=='output_schema_mismatch'
    assert detail['path']==path and detail['reason']==reason
    assert 'value' not in detail


def test_legitimate_string_and_error_sanitization():
    check_output('{"ok":true}',{'type':'string'})
    check_output({'ok':True},{'type':'object'})
    with pytest.raises(ValueError) as caught:check_output({'error':'PRIVATE /host/path\nsecret'},{'type':'object'})
    detail=exception_diagnostic(caught.value)
    assert detail['category']=='program_error' and detail['exception_type']=='unknown'
    assert detail['location']=='unknown' and 'PRIVATE' not in json.dumps(detail)
    assert behavior_difference({'ok':False},{'ok':True})['path']=='$/ok'


def test_matrix_persistence_and_context_boundaries(client,monkeypatch):
    j=built();flow.call(j,'evaluation');flow.call(j,'fingerprint')
    assert roles.context(j,'project_build')['entry']==ENTRY_PROTOCOL
    assert g.context(j,'build')['entry']==ENTRY_PROTOCOL
    monkeypatch.setattr(executor,'availability',lambda:(True,''))
    monkeypatch.setattr(g.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout='sha256:'+'a'*64))
    monkeypatch.setattr(executor,'execute',lambda *a,**kw:'{"sum":3}')
    with pytest.raises(ValueError,match='验证门禁失败'):g.validate(j)
    stored=g.get(j['id'])
    assert all(c['status']=='error' and c['diagnostic']['category']=='output_schema_mismatch' for c in stored['matrix']['checks'])
    assert not stored['matrix']['gates']['fault_trigger']
    diagnosis=roles.context(stored,'diagnosis')
    assert diagnosis['matrix']['checks'][0]['diagnostic']['actual_type']=='string'
    assert 'diagnostic' not in g.public(stored)['matrix']['checks'][0]
    assert 'matrix' not in roles.context(stored,'evaluation')
    stored['pending_plan']={'target_variants':['normal'],'category':'implementation','contract_behavior_ids':[], 'matrix_id':stored['matrix']['id'],'contract_hash':stored['contract_hash']}
    repair=roles.context(stored,'repair_build')
    assert repair['entry']==ENTRY_PROTOCOL
    assert repair['public_observations'][0]['diagnostic']['category']=='output_schema_mismatch'
    private_ids={c['id'] for c in stored['matrix']['checks'] if c['visibility']=='hidden'}
    assert not any(x in json.dumps(repair) for x in private_ids)


@pytest.mark.parametrize('code,schema,category',[
    ('return {"ok": True}',{'type':'object'},None),
    ('return \'{"ok":true}\'',{'type':'object'},'output_schema_mismatch'),
    ('return \'{"ok":true}\'',{'type':'string'},None),
    ('raise ValueError("private exception text")',{'type':'object'},'program_error'),
    ('print("noise"); return {}',{'type':'object'},'invalid_json'),
    ('while True: pass',{'type':'object'},'execution_timeout'),
])
def test_real_docker_diagnostic(tmp_path,code,schema,category):
    ok,reason=executor.availability()
    if not ok:pytest.skip(reason)
    tmp_path.chmod(0o755)
    (tmp_path/'solution.py').write_text('def scenario(data):\n    '+code+'\n')
    if category:
        with pytest.raises((ValueError,RuntimeError,TimeoutError)) as caught:
            check_output(executor.execute(tmp_path,{},timeout=2),schema)
        detail=exception_diagnostic(caught.value)
        assert detail['category']==category
        assert 'private exception text' not in json.dumps(detail)
        if category=='execution_timeout':assert detail['timeout_seconds']==2
    else:check_output(executor.execute(tmp_path,{}),schema)


@pytest.mark.parametrize('error,category',[(FileNotFoundError,'docker_cli_missing'),(PermissionError,'docker_permission_denied')])
def test_docker_start_errors(tmp_path,monkeypatch,error,category):
    (tmp_path/'solution.py').write_text('# not executed')
    def denied(*args,**kwargs):raise error('PRIVATE HOST PATH')
    monkeypatch.setattr(executor.subprocess,'Popen',denied)
    monkeypatch.setattr(executor.subprocess,'run',lambda *a,**kw:None)
    with pytest.raises(RuntimeError) as caught:executor.execute(tmp_path,{})
    detail=exception_diagnostic(caught.value)
    assert detail['category']==category and detail['stage']=='docker_cli'
    assert 'PRIVATE' not in json.dumps(detail)
