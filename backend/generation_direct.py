"""Merged project design/build, with independent public-specification review.

Only new application jobs opt in. No user contract-confirmation phase; no code
is executed here. Legacy records retain their original workflow and assets.
"""
import copy
import difflib
import json
import time
from typing import Literal
from pydantic import Field, model_validator
from .generation_schema import Strict, Contract, Project, validate_project
from .contract_revision import Question
from .generation_protocol import EvaluationPatch

VERSION='direct-build-v1'
def enabled(job):return job.get('project_flow')==VERSION

class Bundle(Strict):
    assessment:Literal['generatable','simulation','clarify','unsupported']
    rationale:str=Field(min_length=10,max_length=1500)
    questions:list[Question]=Field(max_length=3)
    contract:Contract|None
    private_fault_requirements:str=Field(max_length=2000)
    project:Project|None

    @model_validator(mode='after')
    def complete(self):
        if self.assessment in ('generatable','simulation'):
            if not self.contract or not self.project or len(self.private_fault_requirements)<10 or self.questions:
                raise ValueError('可构建项目必须同时提供公开规范、全部版本及私有故障设计，不夹带需求问题')
            validate_project(self.project,self.contract)
            if self.assessment=='simulation' and not self.contract.simulation:raise ValueError('必须说明本地模拟范围')
        elif self.project is not None:raise ValueError('未明确或不支持的需求不能先构建项目')
        if (self.assessment=='clarify')!=bool(self.questions):raise ValueError('仅用户需求歧义可以提出问题')
        return self

from .generation_fault_model import FaultModel

class ModeledBundle(Bundle):
    fault_model: FaultModel | None
    @model_validator(mode='after')
    def frozen_model(self):
        if self.project:
            if self.fault_model is None: raise ValueError('可构建项目必须提供冻结故障模型')
            from .generation_fault_model import validate_model
            validate_model(self.fault_model.model_dump(),self.contract.model_dump())
        elif self.fault_model is not None: raise ValueError('尚未构建项目不能先提供故障模型')
        return self

class Issue(Strict):
    path:str=Field(pattern=r'^/(behaviors/[a-z][a-z0-9_]*|input_domain|simulation|scenario|symptom|constraints|exclusions|input_schema|output_schema)$')
    reason:str=Field(min_length=10,max_length=1200)

class OutputRule(Strict):
    path:str=Field(max_length=150)
    quote:str=Field(min_length=4,max_length=1800)
    explanation:str=Field(min_length=10,max_length=800)

class SpecReview(Strict):
    contract_hash:str=Field(pattern='^[a-f0-9]{64}$')
    decision:Literal['approve','revise','need_user','unsupported']
    reason:str=Field(min_length=10,max_length=1800)
    issues:list[Issue]=Field(max_length=8)
    questions:list[Question]=Field(max_length=3)
    output_rules:list[OutputRule]=Field(max_length=40)
    @model_validator(mode='after')
    def coherent(self):
        if (self.decision=='revise')!=bool(self.issues):raise ValueError('只有退回设计缺项时必须提供具体字段问题')
        if (self.decision=='need_user')!=bool(self.questions):raise ValueError('仅用户需求歧义提出问题')
        return self

class EvaluationDecision(Strict):
    decision:Literal['patch','specification_issue','reject_plan']
    reason:str=Field(min_length=10,max_length=1800)
    patch:EvaluationPatch|None
    issues:list[Issue]=Field(max_length=8)
    @model_validator(mode='after')
    def coherent(self):
        if (self.decision=='patch')!=(self.patch is not None):raise ValueError('只有patch决策能提供补丁')
        if (self.decision=='specification_issue')!=bool(self.issues):raise ValueError('规范缺项必须指出具体字段，其余决策不改规范')
        return self

def output_paths(schema,prefix=''):
    if schema['type']=='object' and schema.get('properties'):
        return [p for k,v in schema['properties'].items() for p in output_paths(v,prefix+'/'+k)]
    if schema['type']=='array':return output_paths(schema['items'],prefix+'/*')
    return [prefix or '/']

class ReviewEvidenceError(ValueError):
    """Public-spec evidence only; structured feedback survives summary truncation."""
    def __init__(self, errors, contract_hash):
        self.feedback={'kind':'review_evidence_invalid','contract_hash':contract_hash,
            'errors':errors[:8],'omitted_count':max(0,len(errors)-8),
            'instruction':'只从公开规则逐字复制连续原文作为quote，不改标点、不拼接。候选来源仅供定位，不证明语义充分；若找不到支持字段取值的规则，返回revise及具体规范路径，不编造引用或默认批准。'}
        first=errors[0]
        super().__init__('输出判定依据不是公开规则的连续原文：'+first['field']+
            '，输出路径='+first['output_path']+'，问题='+first['reason']+
            '；共'+str(len(errors))+'处。详见同轮validation_feedback，不要重复原提案。')


def evidence_sources(contract):
    return {**{'/behaviors/'+k:v for k,v in contract['behaviors'].items()},
            '/input_domain':contract['input_domain'],'/simulation':contract['simulation'],
            **{'/constraints/'+str(i):v for i,v in enumerate(contract['constraints'])}}


def review_evidence_errors(contract, rules):
    sources=evidence_sources(contract);errors=[]
    for index,rule in enumerate(rules):
        quote=rule['quote']
        if any(quote in text for text in sources.values()):continue
        # Similarity is a navigation aid only, NEVER a validation/approval criterion.
        ranked=sorted(sources.items(),key=lambda item:difflib.SequenceMatcher(None,quote,item[1],autojunk=False).ratio(),reverse=True)
        candidates=[]
        for source,text in ranked[:2]:
            matcher=difflib.SequenceMatcher(None,quote,text,autojunk=False)
            match=matcher.find_longest_match(0,len(quote),0,len(text))
            start=max(0,match.b-80);excerpt=text[start:start+600]
            candidates.append({'source_path':source,'excerpt':excerpt,'excerpt_start':start,
                               'truncated':start>0 or start+len(excerpt)<len(text)})
        best=ranked[0][1]
        differences=[{'operation':op,'quote_span':[i,j],'source_span':[a,b],
                      'quote_text':quote[i:j][:120],'source_text':best[a:b][:120]}
                     for op,i,j,a,b in difflib.SequenceMatcher(None,quote,best,autojunk=False).get_opcodes() if op!='equal']
        errors.append({'field':f'/output_rules/{index}/quote','output_path':rule['path'],
                       'submitted_quote':quote,'reason':'not_contiguous_verbatim_public_source',
                       'candidate_sources':candidates,'nearest_source_differences':differences[:4],
                       'differences_omitted':max(0,len(differences)-4)})
    return errors


def validate_review(job,raw):
    from . import generation as g
    result=SpecReview.model_validate(raw).model_dump()
    if result['contract_hash']!=job['contract_hash']:raise ValueError('规范审查依据已过期')
    if result['decision']=='approve':
        if not job.get('contract') or 'build' not in job['assets']:raise ValueError('缺少完整项目，不能批准规范')
        paths=output_paths(job['contract']['output_schema'])
        rules=result['output_rules']
        found={r['path'] for r in rules}
        if found!=set(paths):
            raise ValueError('须逐项核对所有输出字段的确定性规则；缺失路径='+json.dumps(sorted(set(paths)-found))+'；未知路径='+json.dumps(sorted(found-set(paths)))+'；path须原样使用output_paths，数组元素为/*；同字段可按分支提供多条规则')
        errors=review_evidence_errors(job['contract'],rules)
        if errors:raise ReviewEvidenceError(errors,job['contract_hash'])
    return result

def install_bundle(job):
    from . import generation as g
    candidate=job['assets']['project_build']
    if job.get('installed_bundle')==candidate:return
    bundle=g.asset(job,'project_build')
    prior=job.get('contract')
    if prior:
        job.setdefault('contract_history',[]).append({'origin_job':job['id'],'version':job['contract_version'],'contract':copy.deepcopy(prior),'contract_hash':job['contract_hash'],'assets':copy.deepcopy(job.get('previous_bundle_assets',{})),'matrix':copy.deepcopy(job.get('matrix')),'confirmation':copy.deepcopy(job.get('confirmation'))})
    job.pop('candidate_assets',None);job.pop('open_conflict',None)
    job['assets']={'project_build':candidate}
    if bundle['project']:
        directory=g.root(job)/('bundle-build-'+g.s.ident());directory.mkdir()
        (directory/'output.json').write_text(json.dumps(bundle['project'],ensure_ascii=False))
        job['assets']['build']=directory.name
    job.update(contract=bundle['contract'],contract_hash=g.digest(bundle['contract']),contract_version=job['contract_version']+1,
               confirmed_version=None,private_fault_requirements=bundle['private_fault_requirements'],assessment=bundle['assessment'],rationale=bundle['rationale'],questions=[],matrix=None,installed_bundle=candidate)
    for key in ('coverage_repair','evaluation_review_guided','review_digest','spec_approval','contract_clarity','evaluation_repair','pending_plan','contract_candidate','contract_decision','contract_origin_plan','spec_dispute','rejected_evaluation_plan','evaluation_candidate','preflight_review'):
        job.pop(key,None)
    g.put(job)

def apply_review(job):
    from . import generation as g
    asset=job['assets']['spec_review'];review=validate_review(job,g.asset(job,'spec_review'))
    if job.get('applied_spec_review')==asset:return job['checkpoint'] if job['status'] not in ('awaiting_requirement','unsupported') else None
    job['applied_spec_review']=asset
    job.setdefault('spec_reviews',[]).append({'asset':asset,'contract_version':job['contract_version'],**review})
    if review['decision']=='approve':
        job['confirmed_version']=job['contract_version']
        job['confirmation']={'source':'independent_specification_review','time':time.time(),'hash':job['contract_hash'],'not_user_approval':True}
        job['spec_approval']={'contract_hash':job['contract_hash'],'asset':asset}
        job['contract_clarity']={'contract_hash':job['contract_hash'],'reason':review['reason']}
        job.pop('spec_review_feedback',None)
        job.pop('preflight_review',None)
        if job.get('contract_origin_plan',{}).get('evaluation_action')=='expectation':
            job['evaluation_repair']={**job.pop('contract_origin_plan'),'contract_grounded':job['contract_hash']};job['evaluation_review_guided']=True;stage='evaluation'
        else:
            from .generation_flow import next_after_asset
            stage='diagnosis' if (job.get('spec_dispute') or job.get('contract_origin_plan')) and job.get('matrix') else next_after_asset(job)
            job.pop('contract_origin_plan',None)
    elif review['decision']=='revise':
        job['spec_review_feedback']={'reason':review['reason'],'issues':review['issues']};stage='project_build'
    elif review['decision']=='need_user':
        job.update(status='awaiting_requirement',requirement_question={'id':asset.removeprefix('call-'),'review_asset':asset,'contract_hash':job['contract_hash'],'questions':review['questions'],'reason':review['reason']},error=None);stage=None
    else:job.update(status='unsupported',error={'category':'unsupported','reason':review['reason']});stage=None
    job['checkpoint']=stage or 'project_build';g.put(job);return stage

def validate_bundle(job,raw):
    from .generation_fault_model import enabled
    value=(ModeledBundle if enabled(job) else Bundle).model_validate(raw).model_dump()
    if enabled(job) and job.get('installed_bundle') and value.get('project'):
        from . import generation as g
        prior=g.asset(job,'project_build').get('fault_model')
        if value['fault_model']!=prior or value['private_fault_requirements']!=job['private_fault_requirements']:
            raise ValueError('规范补齐不能静默改变冻结故障模型；请重新创建项目')
    feedback=job.get('spec_review_feedback')
    if feedback and job.get('contract') and value['contract']:
        allowed=[i['path'] for i in feedback['issues']]
        def changes(a,b,path=''):
            if isinstance(a,dict) and isinstance(b,dict):
                for k in set(a)|set(b):
                    if k not in a or k not in b:yield path+'/'+k
                    else:yield from changes(a[k],b[k],path+'/'+k)
            elif a!=b:yield path
        diff=list(changes(job['contract'],value['contract']))
        if not diff:raise ValueError('规范补齐未改变任何公开规则，请处理独立审查指出的缺项')
        unauthorized=[path for path in diff if not any(path==p or path.startswith(p+'/') for p in allowed)]
        if unauthorized:raise ValueError('规范补齐修改了未授权字段，必须保持无关公开约定；请恢复字段：'+json.dumps(sorted(unauthorized))+'；允许修改：'+json.dumps(allowed))
    return value

def answer(id,body):
    from . import generation as g, storage as s
    with s.LOCK:
        job=g.get(id);q=job.get('requirement_question') or {}
        previous=next((x for x in job.get('requirement_answers',[]) if x['id']==body.question_id),None)
        if previous:
            if previous['answers']!=body.answers:raise ValueError('不能更改已提交的回答')
            return g.public(job)
        if job['status']!='awaiting_requirement' or id in g.ACTIVE or body.expected_revision!=job.get('revision',0) or q.get('id')!=body.question_id:raise ValueError('需求问题或状态已变化')
        if set(body.answers)!={x['id'] for x in q['questions']}:raise ValueError('必须回答全部当前问题')
        job.setdefault('requirement_answers',[]).append({'id':body.question_id,'questions':q['questions'],'answers':body.answers,'time':time.time()})
        job.pop('requirement_question',None);job.pop('spec_review_feedback',None)
        job.update(status='interrupted',checkpoint='project_build',revision=job.get('revision',0)+1,error=None);g.put(job)
        try:return g.launch(id,'project_build')
        except ValueError as exc:
            job['error']={'category':'busy','reason':str(exc)};g.put(job);return g.public(job)
