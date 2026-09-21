"""Typed repair handoff, program-derived evidence, and bounded conflict handling."""
import copy
import time
import re
from typing import Annotated, Literal
from pydantic import Field
from .generation_schema import Strict

VERSION='repair-handoff-v1'
def enabled(job):return job.get('handoff_version')==VERSION

class Evidence(Strict):
    check_ids:list[str]=Field(min_length=1,max_length=12)
    behavior_id:str
    quote:str=Field(min_length=4,max_length=1200)

class Resolution(Strict):
    conflict_id:str
    disposition:Literal['different_conditions','classification_error','specification_conflict','insufficient_evidence']
    explanation:str=Field(min_length=15,max_length=1200)

class CodeAction(Strict):
    kind:Literal['edit_code']
    variants:list[str]=Field(min_length=1,max_length=6)
    approach:str=Field(min_length=15,max_length=1400)
    suspected_files:list[str]=Field(default_factory=list,max_length=5,description='诊断推断的相关模块，只能选契约文件；不是已证明故障位置')

class ClassificationChange(Strict):
    case_id:str
    before:Literal['target','regression']
    after:Literal['target','regression']
    design_quote:str=Field(min_length=4,max_length=1200)
    rationale:str=Field(min_length=15,max_length=1200)

class ClassificationAction(Strict):
    kind:Literal['reclassify']
    changes:list[ClassificationChange]=Field(min_length=1,max_length=6)

class FingerprintAction(Strict):
    kind:Literal['repair_fingerprint']
    cases:list[str]=Field(min_length=1,max_length=10)
    design_quote:str=Field(min_length=4,max_length=1200)
    rationale:str=Field(min_length=15,max_length=1200)

class SpecAction(Strict):
    kind:Literal['review_spec']
    paths:list[str]=Field(min_length=1,max_length=8)
    issue:str=Field(min_length=15,max_length=1400)

class EvidenceAction(Strict):
    kind:Literal['need_evidence']
    missing:str=Field(min_length=15,max_length=1200)
    proposed_verification:str=Field(min_length=15,max_length=1200)

class WorkOrder(Strict):
    action:Annotated[CodeAction|ClassificationAction|FingerprintAction|SpecAction|EvidenceAction,Field(discriminator='kind')]
    evidence:list[Evidence]=Field(min_length=1,max_length=6)
    resolutions:list[Resolution]=Field(default_factory=list,max_length=8)

class ConflictPair(Strict):
    left_ref:str
    right_ref:str
    explanation:str=Field(min_length=15,max_length=1200)

class Modified(Strict):
    kind:Literal['modified']
    variants:dict[str,dict[str,str]]=Field(min_length=1,max_length=6)
    explanations:dict[str,str]=Field(min_length=1,max_length=6)

class Rejected(Strict):
    kind:Literal['constraint_conflict']
    pairs:list[ConflictPair]=Field(min_length=1,max_length=4)

class Insufficient(Strict):
    kind:Literal['insufficient_evidence']
    requirement_refs:list[str]=Field(min_length=1,max_length=8)
    missing:str=Field(min_length=15,max_length=1200)
    proposed_verification:str=Field(min_length=15,max_length=1200)

class BuildDecision(Strict):
    result:Annotated[Modified|Rejected|Insufficient,Field(discriminator='kind')]

class NeedsReview(ValueError):pass


def evidence_state(job):
    from . import generation as g
    # New execution IDs or rewritten explanations alone are not new evidence.
    m=job.get('matrix') or {}
    return g.digest({'contract':job.get('contract_hash'),'build':m.get('build_hash'),
        'evaluation':m.get('evaluation_hash'),'fingerprint':m.get('fingerprint_hash'),
        'checks':[{k:c.get(k) for k in ('case','version','status','actual','expected','fault_match','stable','diagnostic')} for c in m.get('checks',[])]})


def obligations(job,targets):
    from .generation_repair_scope import repair_scope
    from . import generation as g
    from .generation_direct import output_paths
    public_paths=output_paths(job['contract']['output_schema'])
    scope=repair_scope(job,g.asset(job,'build')['evasions']);result={}
    for name in targets:
        v=scope['variants'][name]
        for key in v['unmet_requirements']+v['must_preserve']:
            ref='requirement:'+name+':'+key
            result[ref]={'variant':name,'requirement':key,'state':'unmet' if key in v['unmet_requirements'] else 'preserve'}
        rows=[c for c in (job.get('matrix') or {}).get('checks',[]) if c.get('version')==name and c.get('status')!='passed']
        for behavior in sorted({b for c in rows for b in c.get('covers',[]) if b in job['contract']['behaviors']}):
            related=[c for c in rows if behavior in c.get('covers',[])]
            paths=set()
            for c in related:
                path=(c.get('diagnostic') or {}).get('path','')
                normalized=re.sub(r'/[0-9]+(?=/|$)','/*',path.removeprefix('$')) or '/'
                if path and (normalized=='/' or any(p==normalized or p.startswith(normalized+'/') for p in public_paths)):paths.add(path)
            result['behavior:'+behavior]={'public_rule':job['contract']['behaviors'][behavior],
                'failed_check_groups':sorted({c.get('group','unknown') for c in related}),
                'observed_mismatch_paths':sorted(paths),
                'observation':'关联失败检查声明覆盖此公开行为；覆盖标签不是该行为每项都错的证明。列出的失配字段来自实际比较，未提供隐藏输入和完整期望；不能假定所有公开样例都失败。'}
    if 'faulty' in targets:result['frozen_fault']={'rule':job['private_fault_requirements']}
    return result


def record_conflict(job,kind,payload):
    from . import generation as g
    state=evidence_state(job)
    # Ignore paraphrasing: same conflict kind/references under same evidence.
    refs=sorted({r for p in payload.get('pairs',[]) for r in (p['left_ref'],p['right_ref'])} or payload.get('requirement_refs',[]))
    signature=g.digest({'state':state,'kind':kind,'refs':refs})
    previous=[c for c in job.get('handoff_conflicts',[]) if c['signature']==signature]
    item={'id':g.s.ident(),'kind':kind,'state':state,'signature':signature,'time':time.time(),
          'matrix_id':(job.get('matrix') or {}).get('id'),'details':payload}
    job.setdefault('handoff_conflicts',[]).append(item);job['open_conflict']=item
    g.put(job)
    if previous:raise NeedsReview('同一执行证据下再次出现相同交接冲突，自动纠错已停止；请在作者审核中核对冲突双方及验证依据。')
    return item


def validate_order(job,raw):
    from . import generation as g, generation_diagnostics as d
    order=WorkOrder.model_validate(raw).model_dump();a=order['action'];kind=a['kind']
    checks={c['id']:c for c in job['matrix']['checks']};behaviors=job['contract']['behaviors']
    for e in order['evidence']:
        if not set(e['check_ids'])<=set(checks):raise ValueError('工单引用不属于当前矩阵')
        if e['behavior_id'] not in behaviors or e['quote'] not in behaviors[e['behavior_id']]:raise ValueError('工单依据必须逐字引用指定公开行为')
    conflict=job.get('open_conflict')
    if conflict and conflict['state']==evidence_state(job):
        relevant=[r for r in order['resolutions'] if r['conflict_id']==conflict['id']]
        if len(relevant)!=1:raise ValueError('必须明确回应当前冲突ID及冲突双方，不能忽略或仅重复原工单')
        allowed={'edit_code':'different_conditions','reclassify':'classification_error','review_spec':'specification_conflict','need_evidence':'insufficient_evidence','repair_fingerprint':'different_conditions'}
        if relevant[0]['disposition']!=allowed[kind]:raise ValueError('冲突处理分支与工单动作不一致')
    elif order['resolutions']:raise ValueError('不能引用过期或不存在的冲突')
    ids=list(dict.fromkeys(i for e in order['evidence'] for i in e['check_ids']))
    if len(ids)>20:raise ValueError('请引用最多20个代表检查，不要列出全部重复失败')
    plan={'category':'implementation','failure_ids':ids,'contract_behavior_ids':list(dict.fromkeys(e['behavior_id'] for e in order['evidence'])),
          'target_variants':[],'observed_facts':'工单依据已引用当前检查及公开行为，具体见结构化work_order。',
          'hypothesis':'模型提案，待独立审核与实际验证。','change_request':'由结构化工单选择后续动作，不执行自由文字中的额外授权。',
          'evaluation_action':'none','target_cases':[],'requires_contract_confirmation':False}
    if kind=='edit_code':
        if not set(a['suspected_files'])<=set(job['contract']['files']):raise ValueError('疑似模块必须是契约允许的文件')
        plan.update(target_variants=a['variants'],change_request=a['approach'])
    elif kind=='reclassify':
        cases={c['id']:c for c in g.asset(job,'evaluation')['cases']}
        if len({x['case_id'] for x in a['changes']})!=len(a['changes']):raise ValueError('检查重复')
        for change in a['changes']:
            c=cases.get(change['case_id'])
            if not c or c['group']!=change['before'] or change['before']==change['after']:raise ValueError('分类修改必须引用当前真实旧值并发生变化')
            if change['design_quote'] not in job['private_fault_requirements']:raise ValueError('分类必须引用冻结故障范围；不能仅因检查失败重分类')
            if not any(checks[i]['case']==change['case_id'] for i in ids):raise ValueError('分类修改缺少对应执行检查引用')
        plan.update(category='evaluation',evaluation_action='classification',target_cases=[x['case_id'] for x in a['changes']])
    elif kind=='repair_fingerprint':
        if a['design_quote'] not in job['private_fault_requirements']:raise ValueError('指纹修改缺少冻结设计依据')
        plan.update(category='evaluation',evaluation_action='fingerprint',target_cases=a['cases'])
    elif kind=='review_spec':
        for path in a['paths']:
            if path not in ['/scenario','/symptom','/input_domain','/simulation','/constraints',*('/behaviors/'+b for b in behaviors)]:raise ValueError('规范审查只能指向现有公开规范路径')
        plan.update(category='contract',change_request=a['issue'])
    else:plan.update(category='unknown',change_request=a['missing'])
    checked=d.validate_plan(job,plan);checked['work_order']=order
    return checked


def builder_result(job,raw):
    from . import generation_diagnostics as d
    value=BuildDecision.model_validate(raw).model_dump()['result']
    if value['kind']=='modified':
        try:return d.merge_repair(job,{k:value[k] for k in ('variants','explanations')})
        except ValueError as exc:
            if '未改变' not in str(exc):raise
            record_conflict(job,'unchanged_candidate',{'requirement_refs':list(obligations(job,job['pending_plan']['target_variants'])),
                'missing':'构建返回原代码，没有候选修改或新的行为证据；需解释工单冲突或更换有依据的处理分支。'})
            return None
    known=obligations(job,job['pending_plan']['target_variants'])
    if value['kind']=='constraint_conflict':
        for pair in value['pairs']:
            if pair['left_ref']==pair['right_ref'] or not {pair['left_ref'],pair['right_ref']}<=set(known):raise ValueError('冲突必须引用两个不同且真实的工单义务ID')
    elif not set(value['requirement_refs'])<=set(known):raise ValueError('证据不足必须引用真实工单义务')
    record_conflict(job,value['kind'],{**value,'requirements':known})
    return None


def rejection_guard(job,stage,exc):
    """At most one further correction for the same rejected action/evidence."""
    from . import generation as g
    if stage not in ('diagnosis','repair_build','evaluation','fingerprint'):return
    state=evidence_state(job);key=g.digest({'state':state,'stage':stage,'error_type':type(exc).__name__,'reason':str(exc)[:600]})
    entries=job.setdefault('handoff_rejections',[]);entries.append({'key':key,'stage':stage,'state':state,'reason':str(exc)[:1400]})
    if sum(x['key']==key for x in entries)>=2:
        raise NeedsReview('同一证据下纠错连续被拒绝，未产生可执行的新工单；停止自动重复，需作者核对记录。')


def stage_candidate(job,stage,ref):
    job.setdefault('candidate_history',[]).append({'stage':stage,'asset':ref,'status':'pending','time':time.time()})
    job.setdefault('candidate_assets',{})[stage]=ref


def accept_candidates(job):
    from . import generation as g
    if not job.get('matrix',{}).get('passed'):raise ValueError('候选未通过实际门禁')
    matrix=job['matrix']
    if matrix.get('contract_hash')!=job.get('contract_hash') or any(matrix.get(stage+'_hash')!=g.digest(g.asset(job,stage)) for stage in ('build','evaluation','fingerprint') if stage in job['assets']):
        raise ValueError('候选与通过矩阵的资产摘要不一致，禁止接受')
    for stage,ref in job.pop('candidate_assets',{}).items():
        old=job['assets'].get(stage)
        if old:job.setdefault('asset_revisions',[]).append({'stage':stage,'asset':old,'replaced_at':time.time()})
        job['assets'][stage]=ref
        for item in job.get('candidate_history',[]):
            if item['asset']==ref:item.update(status='accepted',matrix_id=job['matrix']['id'])
    job.pop('open_conflict',None)
    g.put(job)


def record_validation(job):
    from . import generation as g
    m=job['matrix']
    for item in job.get('candidate_history',[]):
        if item['asset'] in job.get('candidate_assets',{}).values():item.update(status='passed' if m['passed'] else 'rejected',matrix_id=m['id'])
    state=evidence_state(job);seen=job.setdefault('handoff_validations',[])
    # Compare observed behavior, not source hashes, to avoid comment-only progress.
    observed=g.digest({'contract':job['contract_hash'],'checks':[{k:c.get(k) for k in ('case','version','group','status','actual','expected','fault_match')} for c in m['checks']]})
    repeats=sum(x['observed']==observed for x in seen);seen.append({'state':state,'observed':observed,'matrix_id':m['id']})
    if not m['passed'] and repeats>=1:raise NeedsReview('候选执行仍得到相同失败结果，没有新的行为证据；停止自动重复，等待作者复核。')
