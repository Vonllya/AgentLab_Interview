"""Validate routing; no private diagnosis text crosses into implementation context."""
import copy
import json
from .generation_repair_scope import repair_scope
from .generation_roles import RepairPlan,VariantRepair
from .generation_schema import Project,Contract,validate_project,Evaluation,validate_evaluation
from . import generation_protocol as protocol


def validate_plan(job,raw):
    from . import generation as g
    plan=RepairPlan.model_validate(raw).model_dump();matrix=job.get('matrix') or {};checks={c['id'] for c in matrix.get('checks',[])}
    rejected=job.get('rejected_evaluation_plan')
    if rejected and rejected['evaluation_hash']==g.digest(g.asset(job,'evaluation')) and plan['category']=='evaluation':
        before=rejected['plan']
        if plan['evaluation_action']==before['evaluation_action'] and set(plan['target_cases'])==set(before['target_cases']):
            raise ValueError('独立评测已退回同一修复方向，请根据evaluation_objection诊断规范缺项或实现，不重复相同提案')
    if not set(plan['failure_ids'])<=checks:raise ValueError('诊断引用不属于当前矩阵')
    if not set(plan['contract_behavior_ids'])<=set(job['contract']['behaviors']):raise ValueError('诊断引用契约外行为')
    p=g.asset(job,'build');variants={'normal','faulty','reference',*p['evasions']}
    if not set(plan['target_variants'])<=variants:raise ValueError('诊断指定未知版本')
    if plan['category'] in ('implementation','evasion'):
        if not plan['target_variants'] or plan['evaluation_action']!='none' or plan['target_cases']:raise ValueError('category=implementation/evasion 必须有target_variants，evaluation_action=none、target_cases=[]；替换真正错误的候选代码，不是补测试或接受假规避通过')
        if plan['category']=='evasion' and not set(plan['target_variants'])<=set(p['evasions']):raise ValueError('规避修复不可改基线')
    if plan['category']=='evaluation':
        if plan['target_variants'] or plan['evaluation_action']=='none':raise ValueError('评测修复不能修改实现')
        cases={c['id'] for c in g.asset(job,'evaluation')['cases']}
        if not set(plan['target_cases'])<=cases:raise ValueError('未知检查ID')
        if plan['evaluation_action']!='add_coverage' and not plan['target_cases']:raise ValueError('需指定评测修改范围')
        # Gate evidence distinguishes an erroneous oracle from an erroneous fault fingerprint.
        if plan['evaluation_action']=='expectation' and matrix.get('gates',{}).get('normal') and matrix.get('gates',{}).get('reference'):
            if 'faulty_expected' in plan['change_request'] or 'fault_match' in plan['change_request']:
                raise ValueError('动作不一致：faulty_expected/fault_match属于fingerprint，不是正确答案expected；fault_regression需单独核对classification')
    scope=repair_scope(job,p['evasions'])
    if plan['category'] in ('implementation','evasion') and matrix.get('gates'):
        denied=set(plan['target_variants'])-set(scope['allowed_code_variants'])
        if denied:
            label='该规避已正确被识别；' if denied<=set(scope['protected_code_variants']) & set(p['evasions']) else '目标版本已通过门禁或证据不足（故障注入版本应稳定触发指定错误；目标检查失败可能正是要求保留的故障，不应将其修成正常行为）；'
            raise ValueError(label+'禁止修改='+json.dumps(sorted(denied),ensure_ascii=False)+
                '；程序允许修改='+json.dumps(scope['allowed_code_variants'],ensure_ascii=False)+
                '；未通过门禁='+json.dumps(scope['failed_gates'],ensure_ascii=False)+'；请依据repair_scope选择未完成事项')
    plan['repair_scope']=scope
    plan['matrix_id']=matrix['id'];plan['contract_hash']=job['contract_hash']
    plan['must_preserve_hashes']={k:g.digest(g.asset(job,k)) for k in ('build','evaluation')}
    plan['guidance_source']='implementation_informed'
    return plan


def merge_repair(job,raw):
    from . import generation as g
    repair=VariantRepair.model_validate(raw);plan=job['pending_plan'];old=g.asset(job,'build')
    if set(repair.variants)!=set(plan['target_variants']) or set(repair.explanations)!=set(repair.variants):raise ValueError('修复必须只提供指定版本与说明')
    if job['contract_hash']!=plan['contract_hash'] or g.digest(old)!=plan['must_preserve_hashes']['build']:raise ValueError('修复依据已过期')
    if g.digest(g.asset(job,'evaluation'))!=plan['must_preserve_hashes']['evaluation']:raise ValueError('修复期间评测已变化')
    if plan.get('matrix_id') and plan['matrix_id']!=(job.get('matrix') or {}).get('id'):raise ValueError('修复矩阵已过期，需重新诊断')
    if (job.get('matrix') or {}).get('gates'):
        allowed=repair_scope(job,old['evasions'])['allowed_code_variants']
        if not set(repair.variants)<=set(allowed):raise ValueError('修复越出当前程序允许范围；允许版本='+json.dumps(allowed))
    versions={k:old[k] for k in ('normal','faulty','reference')};versions.update(old['evasions'])
    if all(versions[k]==files for k,files in repair.variants.items()):raise ValueError('修复未改变代码，需重新诊断')
    new=copy.deepcopy(old)
    for name,files in repair.variants.items():
        if name in ('normal','faulty','reference'):new[name]=files
        else:new['evasions'][name]=files;new['evasion_explanations'][name]=repair.explanations[name]
        if name=='faulty':new['fault_explanation']=repair.explanations[name]
    validate_project(Project.model_validate(new),Contract.model_validate(job['contract']))
    if new==old:raise ValueError('修复未改变资产，需重新诊断，不能重复执行相同矩阵')
    return new


def validate_evaluation_revision(job,raw):
    from . import generation as g
    evaluation=protocol.evaluation(job,raw)
    plan=job.get('evaluation_repair')
    if not plan:return evaluation.model_dump()
    if g.digest(g.asset(job,'build'))!=plan['must_preserve_hashes']['build']:raise ValueError('评测修复期间实现已变化')
    old={c['id']:c for c in g.asset(job,'evaluation')['cases']};new={c.id:c.model_dump() for c in evaluation.cases}
    if not set(old)<=set(new):raise ValueError('不能删除独立检查以提高通过率')
    for id,before in old.items():
        after=new[id];allowed=set()
        if id in plan['target_cases']:
            if plan['evaluation_action']=='classification':allowed={'group','classification_reason'} if protocol.enabled(job) else {'group'}
            if plan['evaluation_action']=='fingerprint':allowed={'faulty_expected'}
            if plan['evaluation_action']=='expectation' and plan.get('contract_grounded')==job['contract_hash'] and (job.get('contract_clarity') or {}).get('contract_hash')==job['contract_hash']:allowed={'expected'}
        if any(before.get(k)!=after.get(k) for k in set(before)|set(after) if k not in allowed):raise ValueError('未经授权修改既有输入、期望、覆盖或可见性')
    if plan['evaluation_action']!='add_coverage' and set(old)!=set(new):raise ValueError('本次修复未授权追加检查')
    result=evaluation.model_dump()
    if result==g.asset(job,'evaluation'):raise ValueError('评测修复无变化')
    return result
