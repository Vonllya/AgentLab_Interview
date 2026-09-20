"""Bounded diagnostics; never include raw Docker output or generated exception text."""
import re
from .generation_schema import conforms

ENTRY_PROTOCOL = ('平台只读 solution.py 从 app 导入 scenario。app.scenario(data) 必须直接返回符合 '
    'output_schema 的 Python 值，由平台统一进行一次 JSON 序列化。object 返回 dict，array 返回 list；'
    '不要用 json.dumps 将对象或数组变成字符串。仅当契约类型为 string 时返回字符串。'
    '例如对象契约：return {"status": "ok"}。禁止打印日志；顶层 error 保留给运行错误。')


def typed_error(cls, message, category, stage, **details):
    exc = cls(message)
    exc.diagnostic = dict(category=category, stage=stage, summary=message, **details)
    return exc


def json_type(value):
    return {dict:'object', list:'array', str:'string', int:'integer', float:'number',
            bool:'boolean', type(None):'null'}.get(type(value), 'unknown')


def schema_issue(value, schema, path='$'):
    if conforms(value, schema):
        return None
    actual = json_type(value)
    if actual != schema['type'] and not (schema['type']=='number' and actual=='integer'):
        return dict(path=path, reason='type', expected_type=schema['type'], actual_type=actual)
    if 'enum' in schema and value not in schema['enum']:
        return dict(path=path, reason='enum', expected_type=schema['type'], actual_type=actual)
    if isinstance(value, dict):
        props=schema.get('properties', {})
        for key in schema.get('required', []):
            if key not in value:
                return dict(path=path+'/'+key.replace('~','~0').replace('/','~1'), reason='required', expected_type=props[key]['type'], actual_type='missing')
        if schema.get('additionalProperties') is False and set(value)-set(props):
            return dict(path=path, reason='additional_properties', expected_type='object', actual_type=actual)
        for key, sub in props.items():
            if key in value:
                issue=schema_issue(value[key], sub, path+'/'+key.replace('~','~0').replace('/','~1'))
                if issue:return issue
    if isinstance(value, list):
        if len(value)>200:
            return dict(path=path, reason='array_limit', expected_type='array', actual_type=actual)
        for index, item in enumerate(value):
            issue=schema_issue(item, schema['items'], path+'/'+str(index))
            if issue:return issue
    return dict(path=path, reason='schema', expected_type=schema['type'], actual_type=actual)


def check_output(value, schema):
    if isinstance(value, dict) and 'error' in value:
        reported=value['error']
        exception_type=reported if isinstance(reported,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}',reported) else 'unknown'
        raise typed_error(ValueError, '任务返回运行错误；不能当作故障命中', 'program_error', 'scenario',
                          exception_type=exception_type, location='unknown', provenance='untrusted_worker_output')
    issue=schema_issue(value,schema)
    if issue:
        issue['path']=issue['path'][:512]
        raise typed_error(ValueError, '输出不符合契约；不能当作故障命中', 'output_schema_mismatch', 'schema_validation', **issue)


def exception_diagnostic(exc):
    if hasattr(exc,'diagnostic'):return exc.diagnostic
    if isinstance(exc,TimeoutError):
        return dict(category='execution_timeout',stage='execution',summary='执行超时',timeout_seconds='unknown')
    return dict(category='execution_error',stage='unknown',summary='执行失败；详细归因未知',exception_type=type(exc).__name__)


def behavior_difference(actual, expected, path='$'):
    """First differing location only; values remain in author-only matrix fields."""
    if type(actual)==type(expected) and isinstance(actual,dict) and actual.keys()==expected.keys():
        for key in sorted(expected):
            if actual[key]!=expected[key]:return behavior_difference(actual[key],expected[key],path+'/'+key.replace('~','~0').replace('/','~1'))
    if isinstance(actual,list) and isinstance(expected,list) and len(actual)==len(expected):
        for i,(left,right) in enumerate(zip(actual,expected)):
            if left!=right:return behavior_difference(left,right,path+'/'+str(i))
    return dict(category='behavior_mismatch',stage='behavior_comparison',path=path[:512],expected_type=json_type(expected),actual_type=json_type(actual))
