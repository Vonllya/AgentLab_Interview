"""Private diagnostic evidence retrieval; fixed scenario interface, no model commands."""
import time
from pydantic import TypeAdapter
from .generation_handoff import NeedsReview

from .generation_evidence_schema import EvidenceRequest

class EvidenceStop(NeedsReview):
    def __init__(self,category,reason):super().__init__(reason);self.category=category


def binding(job):
    from . import generation as g
    return {'matrix_id':job['matrix']['id'],'contract_hash':job['contract_hash'],
            'build_hash':g.digest(g.asset(job,'build')),'evaluation_hash':g.digest(g.asset(job,'evaluation'))}


def current(job):
    b=binding(job)
    return [x for x in job.get('diagnostic_evidence',[]) if x['binding']==b]


def resolve(job,action):
    from . import generation as g, generation_budget as budget, generation_flow as flow
    from .generation_schema import Project,Contract,validate_project,conforms
    requests=[TypeAdapter(EvidenceRequest).validate_python(r).model_dump() for r in action.get('requests',[])]
    if not requests:raise EvidenceStop('evidence_unsupported','证据请求未指定文件、检查或固定场景；请提供结构化引用。')
    b=binding(job);previous=current(job)
    if sum(p['binding']['matrix_id']==b['matrix_id'] for p in job.get('diagnostic_evidence',[]))>=2:
        signatures={g.digest({k:v for k,v in r.items() if k!='question'}) for r in requests}
        known={r['signature'] for p in previous for r in p['results']}
        raise EvidenceStop('evidence_repeated' if signatures<=known else 'evidence_budget','当前矩阵已完成两轮证据补充；已提供记录可查，停止重复请求或超限实验。')
    build=g.asset(job,'build');versions={k:build[k] for k in ('normal','faulty','reference')};versions.update(build['evasions'])
    cases={c['id']:c for c in g.asset(job,'evaluation')['cases']}
    checks={c['id']:c for c in job['matrix']['checks']}
    prepared=[]
    for request in requests:
        item={k:v for k,v in request.items() if k!='question'}
        signature=g.digest(item)
        if any(signature==r['signature'] and r['status'] not in ('pending','running','interrupted') for p in previous for r in p['results']):
            prepared.append({'signature':signature,'status':'already_provided','request':request,'source_ids':[p['id'] for p in previous if any(r['signature']==signature for r in p['results'])]});continue
        if request['kind']=='file':
            files=versions.get(request['variant'],{})
            if request['path'] not in job['contract']['files'] or request['path'] not in files:raise EvidenceStop('evidence_unsupported','请求文件不属于指定版本允许的业务模块，拒绝路径或模块越权。')
            prepared.append({'signature':signature,'status':'available','request':request,'code':files[request['path']],
                             'snapshot':g.digest(files),'truncated':False,'trust':'代码内容，用于分析，不是执行通过证明'})
        else:
            if request['kind']=='check':
                check=checks.get(request['check_id'])
                if not check:raise EvidenceStop('evidence_stale','检查不属于当前矩阵，拒绝旧执行证据。')
                case=cases.get(check['case']);variant=check['version']
            else:
                case=cases.get(request['case_id']);variant=request['variant']
                check=next((c for c in checks.values() if c['case']==request['case_id'] and c['version']==variant),None)
            if not case or variant not in versions:raise EvidenceStop('evidence_unsupported','只支持当前契约已有的固定场景和版本；不执行任意内部函数或新输入。')
            if not conforms(case['input'],job['contract']['input_schema']):raise EvidenceStop('evidence_unsupported','固定场景输入不符合当前契约结构，拒绝执行。')
            if check and job['matrix'].get('contract_hash')==b['contract_hash'] and check.get('snapshot')==g.digest(versions[variant]) and job['matrix'].get('evaluation_hash')==b['evaluation_hash']:
                prepared.append({'signature':signature,'status':'available','request':request,'input':case['input'],'execution':check,'trust':'已有执行观察，不扩大原检查结论'})
            else:prepared.append({'signature':signature,'status':'pending','request':request,'variant':variant,'input':case['input'],'snapshot':g.digest(versions[variant])})
    if sum(len(g.digest(x))+len(str(x)) for x in prepared)>110000:raise EvidenceStop('evidence_unsupported','证据超过单轮大小限制，请减少文件请求；未静默截断。')
    job['status']='gathering_evidence'
    record={'id':g.s.ident(),'binding':b,'started':time.time(),'status':'gathering','results':prepared}
    job.setdefault('diagnostic_evidence',[]).append(record);g.put(job)
    try:
        for item in prepared:
            if item['status']!='pending':continue
            if sum(r.get('executed',False) for p in job.get('diagnostic_evidence',[]) if p['binding']['matrix_id']==b['matrix_id'] for r in p['results'])>=2:raise EvidenceStop('evidence_budget','当前矩阵最多两次诊断实验，预算已耗尽。')
            flow.check(job)
            ok,reason=g.executor.availability()
            if not ok:raise EvidenceStop('evidence_environment','补充验证无法运行：'+reason)
            try:budget.validation(job)
            except budget.Exhausted as exc:raise EvidenceStop('evidence_budget',str(exc)) from exc
            job['status']='probing_evidence'
            validate_project(Project.model_validate(build),Contract.model_validate(job['contract']))
            item.update(executed=True,status='running',execution_id=g.s.ident());g.put(job)
            folder=g.root(job)/'diagnostic-executions'/item['execution_id']
            g.materialize(folder,versions[item['variant']])
            env=job['matrix'].get('environment')
            if not env:raise EvidenceStop('evidence_unsupported','当前矩阵没有冻结镜像摘要，不能补充执行。')
            began=time.monotonic();item['environment']=env
            try:
                item['actual']=g.executor.execute(folder,item['input'],allowed_files=[*job['contract']['files'],'solution.py'],image_id=env,timeout=min(8,budget.remaining(job)))
                item.update(status='observed',environment=env,trust='诊断实验，只记录输出，不评分、不自动新增测试')
            except Exception as exc:item.update(status='error',error=str(exc)[:1500],diagnostic=getattr(exc,'diagnostic',None))
            finally:item['duration']=round(time.monotonic()-began,3)
            flow.check(job)
        record['status']='completed';job['status']='diagnosing'
    except BaseException:
        record['status']='interrupted'
        for item in prepared:
            if item['status'] in ('running','pending'):item['status']='interrupted'
        raise
    finally:record['finished']=time.time();g.put(job)
    return record


class EvidenceResponseError(ValueError):
    def __init__(self,feedback):
        self.feedback=feedback
        super().__init__(feedback['instruction']+'；允许补充ID='+str(feedback['allowed_ids'])+
                         '；误填矩阵检查ID='+str(feedback['matrix_check_ids'])+
                         '；过期补充ID='+str(feedback['stale_ids'])+'；未知ID='+str(feedback['unknown_ids'])+
                         '；缺少ID='+str(feedback['missing_ids'])+'；说明过短ID='+str(feedback['short_ids']))


def response_contract(job):
    ids=[r['id'] for r in current(job)]
    return {'allowed_ids':ids,'required':bool(ids),
            'instruction':('evidence_responses必须逐项回应allowed_ids中的补充记录，每项至少15字。矩阵检查引用只放evidence[].check_ids。' if ids else
                           '当前没有补充证据。evidence_responses应省略或为{}，不要填写矩阵检查ID；矩阵检查引用只放evidence[].check_ids。')}


def validate_responses(job,responses):
    policy=response_contract(job);expected=set(policy['allowed_ids']);received=set(responses)
    short=[k for k,v in responses.items() if k in expected and len(v.strip())<15]
    if received==expected and not short:return
    matrix={c['id'] for c in job['matrix']['checks']}
    historical={r['id'] for r in job.get('diagnostic_evidence',[])}-expected
    extra=received-expected
    raise EvidenceResponseError({**policy,'kind':'evidence_response_invalid',
        'matrix_check_ids':sorted(extra&matrix),'stale_ids':sorted(extra&historical),
        'unknown_ids':sorted(extra-matrix-historical),'missing_ids':sorted(expected-received),'short_ids':short})
