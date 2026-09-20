"""Untrusted model assets: JSON only, no generated evaluator imports on the host."""
import ast
import json
import re
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

PROTOCOL='agentlab-generated-json-v1'
ENVIRONMENT='Python 3.10.16 标准库；平台固定 Docker；无网络，8秒/检查，128MiB'
ENTRY='from app import scenario\n'

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class Request(Strict):
    requirement:str=Field(min_length=8,max_length=6000)
    minutes:int|None=Field(default=None,ge=10,le=120)
    difficulty:str=Field(default='',max_length=100)
    preference:str=Field(default='',max_length=500)

class Contract(Strict):
    title:str=Field(min_length=3,max_length=100)
    scenario:str=Field(min_length=10,max_length=1800)
    symptom:str=Field(min_length=5,max_length=800)
    capabilities:list[str]=Field(min_length=1,max_length=8)
    minutes:int=Field(ge=10,le=120)
    input_schema:dict
    output_schema:dict
    behaviors:dict[Annotated[str,Field(pattern='^[a-z][a-z0-9_]{0,40}$')],str]=Field(min_length=2,max_length=10)
    constraints:list[str]=Field(min_length=1,max_length=12)
    input_domain:str=Field(min_length=10,max_length=1500)
    exclusions:list[str]=Field(min_length=1,max_length=12)
    files:list[str]=Field(min_length=2,max_length=5)
    simulation:str=Field(max_length=1500)

    @model_validator(mode='after')
    def check(self):
        if 'app.py' not in self.files or len(self.files)!=len(set(self.files)):
            raise ValueError('业务文件必须含 app.py 且不重复')
        if any(not re.fullmatch('[a-z][a-z0-9_]{0,30}\\.py',n) or n in ('solution.py','os.py','sys.py','json.py','site.py') for n in self.files):
            raise ValueError('非法或保留模块名')
        if any(not re.fullmatch('[a-z][a-z0-9_]{0,40}',n) for n in self.behaviors):raise ValueError('行为 ID 无效')
        if len(json.dumps(self.model_dump(),ensure_ascii=False))>14000:raise ValueError('契约过大')
        for schema in (self.input_schema,self.output_schema):validate_schema(schema)
        return self

class Design(Strict):
    assessment:Literal['generatable','clarify','simulation','unsupported']
    rationale:str=Field(min_length=5,max_length=1500)
    questions:list[str]=Field(max_length=5)
    contract:Contract|None
    private_fault_requirements:str=Field(max_length=2000)
    @model_validator(mode='after')
    def check(self):
        if self.assessment in ('generatable','simulation') and not self.contract:raise ValueError('缺少契约')
        if self.assessment=='simulation' and not self.contract.simulation:raise ValueError('模拟范围必填')
        return self

class Project(Strict):
    normal:dict[str,str]
    faulty:dict[str,str]
    reference:dict[str,str]
    evasions:dict[str,dict[str,str]]=Field(min_length=2,max_length=3)
    fault_explanation:str=Field(min_length=10,max_length=2500)
    evasion_explanations:dict[str,str]

class Case(Strict):
    id:str=Field(pattern='^[a-z][a-z0-9_-]{0,45}$')
    group:Literal['regression','target']
    visibility:Literal['public','hidden']
    covers:list[str]=Field(min_length=1,max_length=10)
    input:Any
    expected:Any
    faulty_expected:Any=None

class Evaluation(Strict):
    cases:list[Case]=Field(min_length=4,max_length=10)
    evasion_checks:list[str]=Field(min_length=2,max_length=6)
    @model_validator(mode='after')
    def check(self):
        if len({c.id for c in self.cases})!=len(self.cases):raise ValueError('检查 ID 重复')
        for visibility in ('public','hidden'):
            if not any(c.visibility==visibility and c.group=='target' for c in self.cases):raise ValueError('公开/隐藏必须各有目标检查')
        if not any(c.group=='regression' for c in self.cases):raise ValueError('缺少正常回归')
        if not any(c.group=='target' and c.faulty_expected is not None and c.faulty_expected!=c.expected for c in self.cases):raise ValueError('缺少可复现故障的明确行为指纹')
        return self

class Teaching(Strict):
    brief:str=Field(min_length=30,max_length=2400)
    hints:list[str]=Field(min_length=3,max_length=3)
    followups:list[str]=Field(min_length=2,max_length=6)
    consistency_notes:str=Field(min_length=10,max_length=1200)
    @model_validator(mode='after')
    def check(self):
        for text in [self.brief,*self.hints,*self.followups]:
            if len(text)>2400 or re.search(r'```|def\s+\w+\(|BEGIN PATCH',text):raise ValueError('教学材料不能包含代码补丁')
        return self


def validate_schema(schema,depth=0):
    if depth>8 or not isinstance(schema,dict) or schema.get('type') not in ('object','array','string','integer','number','boolean','null'):raise ValueError('只支持有界基础 JSON schema')
    allowed={'type','properties','required','additionalProperties','items','enum','description'}
    if set(schema)-allowed:raise ValueError('不支持的 JSON schema 字段：'+','.join(sorted(set(schema)-allowed)))
    if 'enum' in schema and (not isinstance(schema['enum'],list) or not schema['enum']):raise ValueError('enum 必须为非空数组')
    if 'additionalProperties' in schema and type(schema['additionalProperties']) is not bool:raise ValueError('additionalProperties 仅支持布尔值')
    required=schema.get('required',[])
    if not isinstance(required,list) or any(not isinstance(k,str) for k in required):raise ValueError('required 必须是字段名数组')
    if schema['type']=='object':
        props=schema.get('properties',{})
        if not isinstance(props,dict) or len(props)>30 or set(schema.get('required',[]))-set(props):raise ValueError('对象 schema 无效')
        for sub in props.values():validate_schema(sub,depth+1)
    if schema['type']=='array':validate_schema(schema.get('items'),depth+1)


def conforms(value,schema):
    kind=schema['type']
    valid={'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),'integer':type(value) is int,'number':type(value) in (int,float),'boolean':type(value) is bool,'null':value is None}[kind]
    if not valid or ('enum' in schema and value not in schema['enum']):return False
    if kind=='object':
        props=schema.get('properties',{})
        if any(k not in value for k in schema.get('required',[])):return False
        if schema.get('additionalProperties') is False and set(value)-set(props):return False
        return all(conforms(v,props[k]) for k,v in value.items() if k in props)
    if kind=='array':return len(value)<=200 and all(conforms(v,schema['items']) for v in value)
    return True


def validate_project(project,contract):
    if set(project.evasions)&{'normal','faulty','reference'}:raise ValueError('规避名称与基线角色冲突')
    # AST is parsed, never compiled/imported/executed. Actual behavior runs in Docker.
    for name,files in [('normal',project.normal),('faulty',project.faulty),('reference',project.reference),*project.evasions.items()]:
        if not re.fullmatch('[a-z][a-z0-9_]{0,40}',name):raise ValueError('规避名称无效')
        if set(files)!=set(contract.files):raise ValueError('所有版本必须提供契约的完整文件集合')
        if sum(len(v.encode()) for v in files.values())>60000:raise ValueError('单项目超过 60KiB')
        for filename,code in files.items():
            if len(code.encode())>24000:raise ValueError('单文件超过 24KiB')
            ast.parse(code,filename=filename)
    if project.normal==project.faulty:raise ValueError('故障版本不能等于正常版本')
    if set(project.evasion_explanations)!=set(project.evasions):raise ValueError('规避说明不完整')


def validate_evaluation(evaluation,contract):
    covered=set()
    for case in evaluation.cases:
        if set(case.covers)-set(contract.behaviors):raise ValueError('检查覆盖了契约外行为')
        covered.update(case.covers)
        if len(json.dumps(case.model_dump()))>12000:raise ValueError('单个测试数据过大')
        if not conforms(case.input,contract.input_schema) or not conforms(case.expected,contract.output_schema):raise ValueError('输入/期望值不符合契约 schema')
        if case.faulty_expected is not None and not conforms(case.faulty_expected,contract.output_schema):raise ValueError('故障指纹必须是有效行为输出，不能是运行错误')
    if covered!=set(contract.behaviors):raise ValueError('未覆盖全部公开行为契约；缺失行为='+json.dumps(sorted(set(contract.behaviors)-covered),ensure_ascii=False)+'；已有覆盖='+json.dumps({k:[c.id for c in evaluation.cases if k in c.covers] for k in contract.behaviors},ensure_ascii=False)+'。请补充有输入和正确期望的实际检查，不得仅增加covers标签；一个检查可覆盖多项行为，总数仍限10项。')
