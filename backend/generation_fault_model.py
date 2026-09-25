"""Bounded, private fault model. Interprets JSON predicates, never generated code.

Opt-in for new jobs only. Rules are proposed before tests and execution; their
semantic accuracy still requires independent review and author approval.
"""
import ast
import copy
import json
from typing import Any, Literal
from pydantic import Field, model_validator
from .generation_schema import Strict

VERSION = 'fault-model-v1'
def enabled(job): return job.get('fault_model_version') == VERSION

class Predicate(Strict):
    path: list[str] = Field(max_length=8)
    quantifier: Literal['value', 'any', 'all']
    operator: Literal['eq', 'ne', 'lt', 'le', 'gt', 'ge']
    value: Any
    @model_validator(mode='after')
    def scalar(self):
        if self.value is not None and type(self.value) not in (str, int, float, bool):
            raise ValueError('谓词仅允许JSON标量，不接受代码或表达式')
        if len(json.dumps(self.value)) > 500: raise ValueError('谓词值过长')
        return self

class Trigger(Strict):
    # Disjunction of conjunctions: bounded, no recursive arbitrary expressions.
    any_of: list[list[Predicate]] = Field(min_length=1, max_length=4)
    @model_validator(mode='after')
    def bounded(self):
        if any(not 1 <= len(branch) <= 4 for branch in self.any_of):
            raise ValueError('每个触发分支需1至4个谓词')
        return self

class FaultModel(Strict):
    trigger: Trigger
    affected_paths: list[list[str]] = Field(min_length=1, max_length=8)
    preservation: str = Field(min_length=10, max_length=800)

class Impact(Strict):
    case_id: str
    triggers: bool
    affected_paths: list[list[str]] = Field(max_length=8)
    rationale: str = Field(min_length=10, max_length=700)


def lookup(value, path):
    for part in path:
        if isinstance(value, dict) and part in value: value = value[part]
        elif isinstance(value, list) and part.isdigit() and str(int(part)) == part and int(part) < len(value): value = value[int(part)]
        else: raise ValueError('触发条件路径不存在：' + '/'.join(path))
    return value


def predicate(data, raw):
    rule = Predicate.model_validate(raw)
    value = lookup(data, rule.path)
    values = [value] if rule.quantifier == 'value' else value
    if not isinstance(values, list): raise ValueError('any/all谓词必须指向数组')
    def compare(actual):
        if rule.operator in ('eq', 'ne'):
            equal = json.dumps(actual, sort_keys=True) == json.dumps(rule.value, sort_keys=True)
            return equal if rule.operator == 'eq' else not equal
        if type(actual) not in (int, float) or type(rule.value) not in (int, float):
            raise ValueError('顺序比较仅支持JSON数字；不做隐式转换')
        return {'lt': actual < rule.value, 'le': actual <= rule.value,
                'gt': actual > rule.value, 'ge': actual >= rule.value}[rule.operator]
    results = [compare(v) for v in values]
    return any(results) if rule.quantifier == 'any' else all(results)


def triggers(model, data):
    branches = Trigger.model_validate(model['trigger']).model_dump()['any_of']
    # Evaluate every path; a true branch must not mask malformed predicates.
    return any([all([predicate(data, p) for p in branch]) for branch in branches])


def frozen(job):
    from . import generation as g
    return g.asset(job, 'project_build')['fault_model']


def classify(job, raw):
    """Only group/reason are derived. Inputs, expected outputs and IDs unchanged."""
    result = copy.deepcopy(raw)
    model = frozen(job)
    for case in result['cases']:
        hit = triggers(model, case['input'])
        case['group'] = 'target' if hit else 'regression'
        case['classification_reason'] = ('冻结触发规则命中；此输入可能受主要故障影响。' if hit else
                                         '冻结触发规则未命中；故障版必须保留此输入的正确行为。')
    return result


def validate_impacts(job, value):
    from . import generation as g
    if value['review']=='conflict':
        from .generation_handoff import NeedsReview
        raise NeedsReview('冻结故障模型与独立影响审核存在矛盾：'+value['review_reason'])
    cases = g.asset(job, 'evaluation')['cases']; model = frozen(job)
    impacts = value['impacts']
    if len(impacts) != len(cases) or {i['case_id'] for i in impacts} != {c['id'] for c in cases}:
        raise ValueError('影响审核必须恰好覆盖每个独立检查')
    by_id = {i['case_id']: i for i in impacts}
    for case in cases:
        impact = by_id[case['id']]; hit = triggers(model, case['input'])
        if impact['triggers'] != hit or case['group'] != ('target' if hit else 'regression'):
            raise ValueError('影响审核与冻结触发规则冲突：' + case['id'])
        if impact['affected_paths'] != (model['affected_paths'] if hit else []):
            raise ValueError('影响字段与冻结模型冲突：' + case['id'])
    allowed = model['affected_paths']
    for check in value['checks']:
        if any(a['path'] not in allowed for a in check['assertions']):
            raise ValueError('指纹不能断言冻结影响范围之外的字段：' + check['case_id'])


def semantic_equal(before, after):
    """AST equality only proves unchanged syntax ignoring layout/comments.

No claims about semantic equivalence of arbitrary different Python programs.
"""
    if set(before) != set(after): return False
    return all(ast.dump(ast.parse(before[p]), include_attributes=False) ==
               ast.dump(ast.parse(after[p]), include_attributes=False) for p in before)


def agenda(job):
    from . import generation as g
    from .generation_repair_scope import repair_scope
    evaluation = g.asset(job, 'evaluation')
    desired = classify(job, evaluation)
    inconsistent = [c['id'] for c, d in zip(evaluation['cases'], desired['cases']) if c['group'] != d['group']]
    if inconsistent:
        return {'action': 'reclassify', 'cases': inconsistent, 'variants': [],
                'reason': '检查分类与执行前冻结触发规则矛盾；先处理分类，禁止修改代码迎合矛盾检查。'}
    scope = repair_scope(job, g.asset(job, 'build')['evasions'])
    if scope['other_unmet_requirements']:
        return {'action': 'review_spec', 'cases': [], 'variants': [],
                'reason': '正确版本也命中故障指纹，需要先核对规范与冻结设计，不能凭实际输出改指纹。'}
    return {'action': 'edit_code', 'cases': [], 'variants': scope['allowed_code_variants'],
            'requirements': {k: scope['variants'][k] for k in scope['allowed_code_variants']},
            'matrix_id': job['matrix']['id'], 'reason': '分类已受冻结规则约束；只允许修改仍有未满足执行义务的版本。'}


def validate_action(job, action):
    assigned = agenda(job)
    # Evidence collection / concrete specification objections remain valid exits.
    if action['kind'] in ('need_evidence', 'review_spec'): return
    if action['kind'] != assigned['action']:
        raise ValueError('工单动作与程序事项不一致：' + json.dumps(assigned, ensure_ascii=False))
    if action['kind'] == 'edit_code' and not set(action['variants']) <= set(assigned['variants']):
        raise ValueError('工单版本越过程序事项授权')
    if action['kind'] == 'reclassify' and {c['case_id'] for c in action['changes']} != set(assigned['cases']):
        raise ValueError('只能修正程序识别的分类冲突')


def counterexamples(job):
    from . import generation as g
    from .generation_repair_scope import repair_scope
    current = job['matrix']; previous = (job.get('validation_history') or [None])[-1]
    old = {(c['version'], c['case']): c for c in (previous or {}).get('checks', [])}
    rows = []
    for c in current['checks']:
        before = old.get((c['version'], c['case']))
        # A target failure is NOT automatically a repair failure for faulty/evasions.
        rows.append({k: c.get(k) for k in ('id','case','version','group','status','fault_match','stable','visibility')} |
                    {'same_observation': bool(before and all(before.get(k)==c.get(k) for k in ('status','actual','fault_match'))),
                     'previously_passed_now_failed': bool(before and before['status']=='passed' and c['status']!='passed')})
    return {'matrix_id': current['id'], 'scope': repair_scope(job, g.asset(job,'build')['evasions']),
            'observations': rows, 'note': '通过变失败仅为观测变化；是否违反保留义务须按版本及scope判断。'}


def preserves_unaffected(actual, expected, paths, prefix=None):
    """Compare every output subtree outside the explicitly affected paths."""
    prefix = prefix or []
    if prefix in paths: return True
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(actual) != set(expected): return False
        return all(preserves_unaffected(actual[k], expected[k], paths, prefix+[k]) for k in expected)
    if isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected): return False
        return all(preserves_unaffected(a, e, paths, prefix+[str(i)]) for i,(a,e) in enumerate(zip(actual,expected)))
    return json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)


def schema_at(schema, path):
    """Resolve literal object keys / concrete array indices; no glob execution."""
    node = schema
    for part in path:
        if node.get('type')=='object' and part in node.get('properties',{}):node=node['properties'][part]
        elif node.get('type')=='array' and part.isdigit() and str(int(part))==part:node=node['items']
        else:raise ValueError('故障模型路径不属于公开JSON接口：'+'/'.join(path))
    return node


def validate_model(model, contract):
    for path in model['affected_paths']:
        if len(path)>8:raise ValueError('影响路径过深')
        schema_at(contract['output_schema'],path)
    for branch in model['trigger']['any_of']:
        for pred in branch:
            node=schema_at(contract['input_schema'],pred['path'])
            if pred['quantifier']!='value':
                if node['type']!='array':raise ValueError('any/all触发规则必须指向输入数组')
                node=node['items']
            if pred['operator'] in ('lt','le','gt','ge') and node['type'] not in ('number','integer'):
                raise ValueError('数字比较触发规则必须指向数字接口')
