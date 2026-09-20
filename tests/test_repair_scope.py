import copy
import json
import pytest
from backend.generation_repair_scope import repair_scope
from backend import generation as g, generation_roles as roles, generation_flow as flow, generation_diagnostics as diagnostics
from test_generation_direct import built


def evidence():
    rows=[]
    for name in ('normal','reference','faulty','warn_only','force_ready','fixed_delay'):
        for group in ('target','regression'):
            rows.append({'id':name+'-'+group,'version':name,'group':group,'visibility':'hidden',
                         'status':'passed' if name in ('normal','reference') or (name=='warn_only' and group=='regression') else 'failed'})
    return {'id':'latest','gates':{'normal':True,'reference':True,'fault_trigger':True,'fault_regression':False,'evasion_rejected':False,'no_runtime_errors':True,'fingerprint_discriminates':True},'checks':rows}


def test_latest_failure_permissions_and_independent_fault_obligations():
    job={'matrix':evidence(),'contract_hash':'frozen'}
    scope=repair_scope(job,['warn_only','force_ready','fixed_delay'])
    assert set(scope['allowed_code_variants'])=={'faulty','force_ready','fixed_delay'}
    assert set(scope['protected_code_variants'])=={'normal','reference','warn_only'}
    assert scope['variants']['faulty']['unmet_requirements']==['all_regression_checks_pass']
    assert 'frozen_fault_reproduced_stably' in scope['variants']['faulty']['must_preserve']
    assert scope['variants']['force_ready']['unmet_requirements']==['at_least_one_regression_passes']
    assert scope['variants']['warn_only']['code_change']=='forbidden'
    job['matrix']['checks'].append({'id':'runtime','version':'warn_only','status':'error'})
    assert 'warn_only' in repair_scope(job,['warn_only'])['allowed_code_variants']


def test_unknown_evidence_is_not_approval():
    scope=repair_scope({'matrix':{},'contract_hash':'x'},['evasion'])
    assert scope['allowed_code_variants']==scope['protected_code_variants']==[]
    assert set(scope['unverified_code_variants'])=={'normal','reference','faulty','evasion'}


def test_server_enforces_scope_and_builder_receives_obligations(client):
    job=built();flow.call(job,'evaluation');flow.call(job,'fingerprint')
    project=g.asset(job,'build');names=list(project['evasions']);assert len(names)>=2
    mat=evidence()
    # Use actual fixture evasion names without depending on its code details.
    for row in mat['checks']:
        row['version']={'warn_only':names[0],'force_ready':names[1]}.get(row['version'],row['version'])
    job['matrix']=mat
    proposal={'category':'evasion','failure_ids':['warn_only-target'],
              'contract_behavior_ids':[],'target_variants':[names[0]],'observed_facts':'根据当前执行矩阵提出修改范围验证','hypothesis':'验证服务器权限','change_request':'测试不得修改已经合格的候选代码','evaluation_action':'none','target_cases':[],'requires_contract_confirmation':False}
    with pytest.raises(ValueError,match='已正确被识别'):diagnostics.validate_plan(job,proposal)
    proposal.update(category='implementation',target_variants=['faulty'],failure_ids=['faulty-regression'])
    plan=diagnostics.validate_plan(job,proposal)
    assert 'faulty' in plan['repair_scope']['allowed_code_variants']
    job['pending_plan']=plan
    ctx=roles.context(job,'repair_build')
    assert ctx['program_requirements']['faulty']['unmet_requirements']==['all_regression_checks_pass']
    assert 'evidence_ids' not in ctx['program_requirements']['faulty']
    assert 'repair_scope' in roles.context(job,'diagnosis')
    assert 'repair_scope' not in roles.context(job,'evaluation')
    code=copy.deepcopy(project['faulty']);code['app.py']+='\n# changed\n'
    candidate={'variants':{'faulty':code},'explanations':{'faulty':'仅测试修复权限校验'}}
    job['matrix']['id']='new-matrix'
    with pytest.raises(ValueError,match='矩阵已过期'):diagnostics.merge_repair(job,candidate)
    job['matrix']['id']='latest';job['matrix']['gates']['fault_regression']=True
    with pytest.raises(ValueError,match='程序允许范围'):diagnostics.merge_repair(job,candidate)
