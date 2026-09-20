"""Versioned generation assets. JSON assertions only; never execute model code here."""
import copy
import json
from typing import Any, Literal
from pydantic import Field, model_validator
from .generation_schema import Strict, Case, Evaluation, Contract, validate_evaluation

VERSION = 'separated-evidence-v2'

def enabled(job):
    return job.get('generation_protocol') == VERSION

class BehaviorCase(Case):
    classification_reason: str = Field(min_length=10, max_length=600)
    @model_validator(mode='after')
    def no_fault_guess(self):
        if self.faulty_expected is not None:
            raise ValueError('独立正确性检查不得猜测故障输出')
        return self

class BehaviorEvaluation(Strict):
    cases: list[BehaviorCase] = Field(min_length=4, max_length=10)
    evasion_checks: list[str] = Field(min_length=2, max_length=6)
    @model_validator(mode='after')
    def groups(self):
        if len({c.id for c in self.cases}) != len(self.cases):
            raise ValueError('检查 ID 重复')
        if not all(any(c.visibility == v and c.group == 'target' for c in self.cases) for v in ('public', 'hidden')):
            raise ValueError('公开/隐藏必须各有目标检查')
        if not any(c.group == 'regression' for c in self.cases):
            raise ValueError('需要不触发主要故障的正常回归')
        return self

def evaluation(job, raw):
    value = (BehaviorEvaluation if enabled(job) else Evaluation).model_validate(raw)
    validate_evaluation(value, Contract.model_validate(job['contract']))
    return value

class Assertion(Strict):
    path: list[str] = Field(max_length=8, description='JSON对象键或数组下标；空列表表示整个结果。不支持表达式或代码。')
    equals: Any

class Fingerprint(Strict):
    case_id: str = Field(max_length=46)
    design_quote: str = Field(min_length=4, max_length=1000)
    reason: str = Field(min_length=10, max_length=1000)
    assertions: list[Assertion] = Field(min_length=1, max_length=8)

class FaultChecks(Strict):
    checks: list[Fingerprint] = Field(min_length=1, max_length=10)

def matches(actual, check):
    for assertion in check['assertions']:
        value = actual
        try:
            for part in assertion['path']:
                if isinstance(value, dict): value = value[part]
                elif isinstance(value, list) and part.isdigit() and str(int(part)) == part: value = value[int(part)]
                else: return False
        except (KeyError, IndexError, TypeError): return False
        # JSON true is not JSON 1, unlike Python equality.
        if json.dumps(value, sort_keys=True) != json.dumps(assertion['equals'], sort_keys=True): return False
    return True

def validate_faults(job, raw):
    from . import generation as g
    value = FaultChecks.model_validate(raw).model_dump()
    if len(json.dumps(value).encode()) > 24000: raise ValueError('故障断言资产过大')
    cases = {c['id']: c for c in g.asset(job, 'evaluation')['cases']}
    seen = set()
    for check in value['checks']:
        id = check['case_id']
        if id in seen or id not in cases or cases[id]['group'] != 'target': raise ValueError(f'检查 {id}：故障断言必须引用唯一目标检查，只选candidate_cases')
        seen.add(id)
        if check['design_quote'] not in job['private_fault_requirements']: raise ValueError(f'检查 {id}：故障断言必须引用冻结的故障设计，不得引用公开契约或改写原文')
        if matches(cases[id]['expected'], check): raise ValueError(f'检查 {id}：故障断言不能命中正确期望；你给的是正确行为，请描述修复前错误状态或选择实际触发故障的其他目标输入')
    plan=job.get('evaluation_repair')
    if plan and plan['evaluation_action']=='fingerprint' and 'fingerprint' in job['assets']:
        before=g.asset(job,'fingerprint')
        targets=set(plan['target_cases'])
        old={c['case_id']:c for c in before['checks']};new={c['case_id']:c for c in value['checks']}
        if {k:v for k,v in old.items() if k not in targets}!={k:v for k,v in new.items() if k not in targets}:
            raise ValueError('故障断言修复越过指定检查范围')
        if old==new:raise ValueError('故障断言修复无变化')
    return value

class FieldPatch(Strict):
    case_id: str = Field(max_length=46)
    field: Literal['expected', 'faulty_expected', 'group']
    before: Any
    after: Any
    reason: str = Field(min_length=10, max_length=800)

class EvaluationPatch(Strict):
    evaluation_hash: str = Field(pattern='^[a-f0-9]{64}$')
    action: Literal['classification', 'expectation', 'fingerprint', 'add_coverage']
    changes: list[FieldPatch] = Field(max_length=10)
    additions: list[dict] = Field(max_length=6)

def merge_patch(job, raw):
    from . import generation as g
    patch = EvaluationPatch.model_validate(raw)
    old = g.asset(job, 'evaluation'); plan = job['evaluation_repair']
    if patch.evaluation_hash != g.digest(old): raise ValueError('评测补丁依据已过期')
    if patch.action != plan['evaluation_action']: raise ValueError('补丁动作与授权动作不一致')
    result = copy.deepcopy(old); cases = {c['id']: c for c in result['cases']}
    if patch.action == 'add_coverage':
        if patch.changes or not patch.additions: raise ValueError('补覆盖只能追加新检查')
        result['cases'].extend(patch.additions)
    else:
        if patch.additions or not patch.changes: raise ValueError('字段修复只能提供指定字段补丁，不能追加检查')
        field = {'classification':'group', 'expectation':'expected', 'fingerprint':'faulty_expected'}[patch.action]
        seen = set()
        for change in patch.changes:
            if change.case_id not in plan['target_cases'] or change.case_id in seen or change.field != field:
                raise ValueError('补丁越权或重复；动作只授权一个字段')
            seen.add(change.case_id)
            if change.before != cases[change.case_id].get(field): raise ValueError('补丁旧值不匹配')
            if change.before == change.after: raise ValueError('补丁无变化')
            cases[change.case_id][field] = change.after
            if field == 'group' and enabled(job): cases[change.case_id]['classification_reason'] = change.reason
    return result
