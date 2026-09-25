"""Pre-execution coverage feedback and bounded, explicitly non-blind completion."""
import copy
import json
from . import generation_fault_model as fm

class CoverageError(ValueError):
    category='coverage_incomplete'
    def __init__(self, feedback):
        self.feedback=feedback
        super().__init__('冻结规则分类后覆盖不足：'+str({k:feedback[k] for k in ('missing_target_visibilities','has_regression','missing_behaviors')}))


def summary(job, raw):
    classified=fm.classify(job,raw)
    cases=classified['cases']
    coverage={b:[c['id'] for c in cases if b in c['covers']] for b in job['contract']['behaviors']}
    return {'missing_behaviors':[b for b,ids in coverage.items() if not ids], 'coverage':coverage,
            'case_count':len(cases),'case_limit':10,
            'missing_target_visibilities':[v for v in ('public','hidden') if not any(c['visibility']==v and c['group']=='target' for c in cases)],
            'has_regression':any(c['group']=='regression' for c in cases),
            'classifications':[{'case_id':c['id'],'visibility':c['visibility'],'proposed_group':old['group'],'effective_group':c['group']} for old,c in zip(raw['cases'],cases)],
            'execution_performed':False,'meaning':'分类来自冻结输入规则，不是Docker执行事实；检查主题不能替代触发条件。'}


def validate(job, raw):
    from .generation_protocol import IndependentBehaviorEvaluation
    raw=IndependentBehaviorEvaluation.model_validate(raw).model_dump()
    repair=job.get('coverage_repair')
    if repair:
        if repair['contract_hash']!=job['contract_hash']:raise ValueError('覆盖补全依据已过期')
        before=IndependentBehaviorEvaluation.model_validate(repair['base_evaluation']).model_dump();old={c['id']:c for c in fm.classify(job,before)['cases']}
        new={c['id']:c for c in fm.classify(job,raw)['cases']}
        if any(new.get(k)!=v for k,v in old.items()) or raw['evasion_checks']!=before['evasion_checks']:
            raise ValueError('覆盖补全只能追加检查，不能改原输入、期望、可见性、覆盖声明或规避要求')
    feedback=summary(job,raw)
    if feedback['missing_target_visibilities'] or not feedback['has_regression'] or feedback['missing_behaviors']:
        raise CoverageError(feedback)
    return fm.classify(job,raw)


def begin_or_continue(job, exc):
    """Called before generic handoff guards. No matrix exists at this checkpoint."""
    from . import generation as g
    from .generation_handoff import NeedsReview
    repair=job.get('coverage_repair')
    if not repair:
        raw=json.loads((g.root(job)/job['evaluation_candidate']['asset']/'rejected.json').read_text())
        repair={'contract_hash':job['contract_hash'],'base_evaluation':copy.deepcopy(raw),
                'base_hash':g.digest(raw),'attempts':0,'source_asset':job['evaluation_candidate']['asset']}
        job['coverage_repair']=repair
    if repair['attempts']>=2:
        err=NeedsReview('执行前覆盖补全已尝试两次仍未通过；未执行Docker。请核对冻结触发规则与具体缺项，不能修改正确期望来放行。')
        err.category='coverage_incomplete';raise err
    repair['attempts']+=1
    job['evaluation_review_guided']=True
    g.put(job)
