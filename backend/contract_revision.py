"""Grounded local contract amendments, independent of implementation/test outputs."""
import copy
import re
import time
from typing import Annotated, Any, Literal
from pydantic import Field, model_validator
from .generation_schema import Strict, Contract, ENVIRONMENT

DEFAULTS={
    'runtime':ENVIRONMENT,
    'interface':'平台只读 solution.py 从 app 导入 scenario；scenario(data) 接收并返回 JSON。',
    'single_fault':'每题一个主要故障；不访问真实支付、云资源或外部业务接口。',
}

class Question(Strict):
    id:str=Field(pattern='^[a-z][a-z0-9_]{0,30}$')
    text:str=Field(min_length=10,max_length=600)
    options:list[Annotated[str,Field(min_length=1,max_length=300)]]=Field(min_length=2,max_length=3)
    impact:str=Field(min_length=5,max_length=600)

class Patch(Strict):
    path:str=Field(min_length=2,max_length=180,pattern=r'^/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*$',description='JSON Pointer，必须以/开头，例如/behaviors/sum或/constraints/0；禁止behaviors.sum点号写法')
    op:Literal['replace','add']='replace'
    before:Any
    after:Any
    source:str=Field(max_length=100)
    quote:str=Field(min_length=1,max_length=1200)
    reason:str=Field(min_length=10,max_length=800)

class Proposal(Strict):
    contract_hash:str=Field(pattern='^[a-f0-9]{64}$')
    decision:Literal['correction','need_user','clear']
    reason:str=Field(min_length=10,max_length=1000)
    changes:list[Patch]=Field(max_length=4)
    questions:list[Question]=Field(max_length=3)
    @model_validator(mode='after')
    def coherent(self):
        if self.decision=='correction' and (not self.changes or self.questions):raise ValueError('局部修订必须有补丁且不能夹带需求问题')
        if self.decision!='correction' and self.changes:raise ValueError('未明确的需求不能先修改契约')
        if (self.decision=='need_user')!=bool(self.questions):raise ValueError('仅需求歧义必须提供具体问题与选项')
        if len({q.id for q in self.questions})!=len(self.questions):raise ValueError('问题ID重复')
        return self

class Check(Strict):
    proposal_hash:str=Field(pattern='^[a-f0-9]{64}$')
    verdict:Literal['approve','revise']
    reason:str=Field(min_length=10,max_length=1200)


def sources(job):
    values={f'request.{k}':v for k,v in job['request'].items() if isinstance(v,str) and v}
    if job.get('revision_request'):values['author.clarification']=job['revision_request']
    for event in job.get('requirement_answers',[]):
        for key,value in event['answers'].items():values[f"answer.{event['id']}.{key}"]=value
    return values


def context(job,checking=False):
    from . import generation as g
    value={'contract':job['contract'],'contract_hash':job['contract_hash'],'requirement_sources':sources(job),'published_defaults':DEFAULTS,
           'answered_questions':job.get('requirement_answers',[]),'scope':job.get('contract_issue',{'behavior_ids':[]}),
           'rule':'只根据需求与公开约定解释契约；没有代码、测试期望、执行输出或私有诊断可供迎合。'}
    if checking:
        candidate=job['contract_candidate'];value.update(proposal=candidate['proposal'],proposal_hash=candidate['hash'])
    elif job.get('contract_review_feedback'):value['previous_check']=job['contract_review_feedback']
    return value


def patched(job,raw):
    proposal=Proposal.model_validate(raw)
    if proposal.contract_hash!=job['contract_hash']:raise ValueError('契约修订依据已过期')
    data=copy.deepcopy(job['contract']);seen=[];evidence={**sources(job),**{'default.'+k:v for k,v in DEFAULTS.items()}}
    allowed={'title','scenario','symptom','input_domain','simulation','behaviors','constraints','exclusions','input_schema','output_schema'}
    for change in proposal.changes:
        path=change.path
        if not path.startswith('/') or '~' in path or '..' in path:raise ValueError('非法契约字段路径')
        parts=path[1:].split('/')
        if parts[0] not in allowed or any(not p or not re.fullmatch('[a-zA-Z0-9_-]+',p) for p in parts):raise ValueError('不允许修改该契约字段')
        if parts[0] in ('behaviors','constraints','exclusions','input_schema','output_schema') and len(parts)<2:raise ValueError('必须指定局部字段，不能重写整个行为或接口集合')
        if any(path==p or path.startswith(p+'/') or p.startswith(path+'/') for p in seen):raise ValueError('补丁路径重复或重叠')
        seen.append(path)
        if not change.source.startswith('answer.') and len(change.quote)<4:raise ValueError('需求或平台引用过短')
        if change.source not in evidence or change.quote not in evidence[change.source]:raise ValueError('修订必须引用真实需求原文或公开默认约定')
        if change.source.startswith('default.') and parts[0] not in ('constraints','simulation'):raise ValueError('平台运行默认值不能决定用户业务语义')
        if len(str(change.after).encode())>6000:raise ValueError('单项补丁过大')
        parent=data
        try:
            for part in parts[:-1]:
                if isinstance(parent,list) and (not part.isdigit() or str(int(part))!=part):raise ValueError()
                parent=parent[int(part)] if isinstance(parent,list) else parent[part]
            if isinstance(parent,list) and (not parts[-1].isdigit() or str(int(parts[-1]))!=parts[-1]):raise ValueError()
            key=int(parts[-1]) if isinstance(parent,list) else parts[-1]
            if isinstance(parent,list):
                if type(key) is not int or key<0:raise ValueError()
                exists=key<len(parent)
            elif isinstance(parent,dict):exists=key in parent
            else:raise ValueError()
            if change.op=='replace':
                if not exists or isinstance(change.before,dict) or parent[key]!=change.before or change.before==change.after:raise ValueError()
                parent[key]=change.after
            else:
                if exists or change.before is not None:raise ValueError()
                if isinstance(parent,list):
                    if key!=len(parent):raise ValueError()
                    parent.append(change.after)
                else:parent[key]=change.after
        except (ValueError,TypeError,IndexError,KeyError):raise ValueError('字段不存在、旧值不符或不是最小有效补丁') from None
    # Pydantic validates the full interface/file/size contract after exact local edits.
    return Contract.model_validate(data).model_dump()


def validate_proposal(job,raw):
    parsed=Proposal.model_validate(raw).model_dump();patched(job,parsed)
    return parsed


def validate_check(job,raw):
    parsed=Check.model_validate({k:v for k,v in raw.items() if k!='impact_checks'}).model_dump()
    if parsed['proposal_hash']!=job['contract_candidate']['hash']:raise ValueError('独立校核未绑定当前补丁')
    proposal=job['contract_candidate']['proposal'];patched(job,proposal)
    return parsed


def apply(job):
    from . import generation as g
    candidate=job['contract_candidate'];decision=job['contract_decision'];proposal=candidate['proposal']
    validate_check(job,decision['result'])
    if job['status'] in ('published','cancelled'):raise ValueError('禁止修改已发布或已取消记录')
    if proposal['decision']=='correction' and job.get('confirmed_version')!=job['contract_version']:raise ValueError('未确认的契约不能自动替代用户确认')
    audit={'id':s_id(),'origin_job':job['id'],'time':time.time(),'from_version':job['contract_version'],'proposal_hash':candidate['hash'],'proposal':copy.deepcopy(proposal),'review':copy.deepcopy(decision['result']),'proposal_asset':candidate['asset'],'review_asset':decision['asset']}
    job.setdefault('contract_reviews',[]).append(audit)
    job.pop('contract_candidate');job.pop('contract_decision')
    if decision['result']['verdict']=='revise':
        job['contract_review_feedback']=decision['result']['reason'];job['checkpoint']='contract_review';g.put(job);return 'contract_review'
    job.pop('contract_review_feedback',None)
    if proposal['decision']=='need_user':
        job.update(status='awaiting_requirement',requirement_question={'id':audit['id'],'contract_hash':job['contract_hash'],'questions':proposal['questions'],'reason':proposal['reason']},error=None)
        g.put(job);return None
    if proposal['decision']=='clear':
        job['contract_clarity']={'contract_hash':job['contract_hash'],'review_id':audit['id'],'reason':proposal['reason']}
        origin=job.get('contract_origin_plan') or {}
        if origin.get('category')=='evaluation' and origin.get('evaluation_action')=='expectation':
            # Independent evaluator sees contract + its own inputs, NEVER implementation outputs.
            job['evaluation_repair']={**origin,'contract_grounded':job['contract_hash']};job['evaluation_review_guided']=True;job['checkpoint']='evaluation'
            g.put(job);return 'evaluation'
        job['checkpoint']='diagnosis';g.put(job);return 'diagnosis'
    updated=patched(job,proposal)
    old={'origin_job':job['id'],'version':job['contract_version'],'contract_hash':job['contract_hash'],'contract':copy.deepcopy(job['contract']),'assets':copy.deepcopy(job['assets']),'matrix':copy.deepcopy(job.get('matrix')),'confirmation':copy.deepcopy(job.get('confirmation'))}
    job.setdefault('contract_history',[]).append(old)
    version=job['contract_version']+1
    # Conservatively invalidate all executable evidence even if model calls this wording-only.
    job.update(contract=updated,contract_hash=g.digest(updated),contract_version=version,confirmed_version=version,
               assets={},matrix=None,revision=job.get('revision',0)+1,checkpoint='build',stage='build',error=None)
    job['confirmation']={'time':time.time(),'hash':job['contract_hash'],'source':'grounded_local_correction','review_id':audit['id'],'previous_version':version-1}
    audit.update(to_version=version,impact='rebuild_and_revalidate_all',new_hash=job['contract_hash'])
    for key in ('candidate_assets','open_conflict','review_digest','review','pending_plan','evaluation_repair','contract_clarity','contract_origin_plan','contract_issue','requirement_question','completed_diagnosis','format_error','stagnation_count','diagnostic_strategy','strategy_changed_at','diagnosis_rejections'):
        job.pop(key,None)
    g.put(job);return 'build'


def s_id():
    from . import storage as s
    return s.ident()


def answer(id,body):
    from . import generation_direct as direct, generation as generation
    if direct.enabled(generation.get(id)):return direct.answer(id,body)
    from . import storage as s, generation as g
    with s.LOCK:
        job=g.get(id);question=job.get('requirement_question') or {}
        previous=next((a for a in job.get('requirement_answers',[]) if a['id']==body.question_id),None)
        if previous:
            if previous['answers']!=body.answers:raise ValueError('同一问题已回答，不能用重复请求改写')
            return g.public(job)
        if job['status']!='awaiting_requirement' or id in g.ACTIVE:raise ValueError('当前没有待回答的需求问题')
        if body.expected_revision!=job.get('revision',0) or body.question_id!=question.get('id') or question.get('contract_hash')!=job['contract_hash']:raise ValueError('需求问题或契约已变化，请刷新')
        if set(body.answers)!={q['id'] for q in question['questions']}:raise ValueError('必须回答当前全部问题，不能夹带其他问题')
        event={'id':body.question_id,'answers':body.answers,'time':time.time(),'questions':question['questions']}
        job.setdefault('requirement_answers',[]).append(event);job.pop('requirement_question',None)
        job.update(status='interrupted',checkpoint='contract_review',revision=job.get('revision',0)+1,error=None)
        job.pop('contract_review_feedback',None);g.put(job)
        try:return g.launch(id,'contract_review')
        except ValueError as exc:
            job['error']={'category':'busy','reason':str(exc)};g.put(job);return g.public(job)
