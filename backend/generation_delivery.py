"""Compile actionable builder handoffs from code locations and public evidence.

Reviewer prose and hidden checks are never copied. No generated code is executed.
"""
import ast
import re
from . import generation_protocol as protocol


def locations(code, proposed):
    try:
        tree=ast.parse(code)
    except SyntaxError:
        return []
    names={node.name for node in ast.walk(tree) if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))}
    return sorted(names & set(re.findall(r'[A-Za-z_][A-Za-z_0-9]*',proposed)))


def observed_value(actual,path):
    value=actual
    try:
        for part in path:
            if isinstance(value,dict):value=value[part]
            elif isinstance(value,list) and part.isdigit() and str(int(part))==part:value=value[int(part)]
            else:return {'present':False}
    except (KeyError,IndexError,TypeError):return {'present':False}
    return {'present':True,'value':value}


def compile_delivery(job):
    from . import generation as g
    plan=job['pending_plan'];matrix=job.get('matrix') or {};project=g.asset(job,'build')
    evaluation=g.asset(job,'evaluation')
    if plan['matrix_id']!=matrix.get('id') or plan['contract_hash']!=job['contract_hash']:
        raise ValueError('交接执行或契约依据已过期')
    if plan['must_preserve_hashes']['build']!=g.digest(project) or plan['must_preserve_hashes']['evaluation']!=g.digest(evaluation):
        raise ValueError('交接代码或评测资产已变化')
    public={c['id']:c for c in evaluation['cases'] if c['visibility']=='public'}
    faults=g.asset(job,'fingerprint') if 'fingerprint' in job['assets'] else {'checks':[]}
    fault_by_case={c['case_id']:c for c in faults['checks']}
    rows=[]
    for row in matrix.get('checks',[]):
        if row.get('visibility')!='public' or row['case'] not in public or row['version'] not in plan['target_variants']:continue
        case=public[row['case']];kind='correct_behavior';assertions=[]
        if row['version']=='faulty' and case['group']=='target':
            kind='fault_reproduction'
            assertions=fault_by_case.get(row['case'],{}).get('assertions',[])
            if not assertions and not protocol.enabled(job) and case.get('faulty_expected') is not None:
                assertions=[{'path':[],'equals':case['faulty_expected']}]
        elif row['version'] in ('normal','reference') or case['group']=='regression':
            assertions=[{'path':[],'equals':case['expected']}]
        else:kind='evasion_rejection'  # Do not tell an evasion to become correct.
        differences=[]
        for assertion in assertions:
            observation=observed_value(row.get('actual'),assertion['path']) if 'actual' in row else {'present':False}
            differences.append({'path':assertion['path'],'observed':observation,'required_value':assertion['equals'],
                                'matches':bool('actual' in row and protocol.matches(row['actual'],{'assertions':[assertion]}))})
        rows.append({'check_id':row['id'],'case_id':row['case'],'variant':row['version'],'input':case['input'],
                     'status':row['status'],'objective':kind,'assertion_available':bool(assertions),
                     'field_requirements':differences,'error':{'category':'execution_error'} if row['status']=='error' else None})
    # Prioritize concrete unmet obligations over passing/unspecified observations.
    rows.sort(key=lambda row:not any(not x['matches'] for x in row['field_requirements']))
    selected=rows[:12]
    versions={k:project[k] for k in ('normal','faulty','reference')};versions.update(project['evasions'])
    action=plan.get('work_order',{}).get('action',{});edits=[]
    for edit in action.get('edits',[]):
        variant,path=edit['variant'],edit['path']
        if variant not in plan['target_variants'] or path not in versions[variant]:raise ValueError('交接位置越过授权范围')
        symbols=locations(versions[variant][path],edit.get('location',''))
        edits.append({'variant':variant,'path':path,'symbols':symbols,'location_verified':bool(symbols),
                      'location_authority':'诊断建议中存在于当前代码的名称；未证明这些位置是根因',
                      'requirements':[row['check_id'] for row in selected if row['variant']==variant]})
    return {'matrix_id':matrix['id'],'contract_hash':job['contract_hash'],'build_hash':g.digest(project),
            'evaluation_hash':g.digest(evaluation),'fingerprint_hash':g.digest(faults),
            'response_files':{name:sorted(versions[name]) for name in plan['target_variants']},
            'response_protocol':'modified.variants必须返回所选版本的完整文件映射，包括未修改文件；edits仅是定位建议，不是局部文件补丁协议。',
            'edits':edits,'public_requirements':selected,'omitted_public_checks':max(0,len(rows)-len(selected)),
            'instruction':'按edits定位并按public_requirements的逐字段实际值/目标值提出代码修改。fault_reproduction的required_value是必须保留的错误表现，不是正确答案；correct_behavior才要求正确输出。requirements是该版本的公开执行义务，不证明每个文件都是根因。assertion_available=false表示未提供故障断言，不得猜测为通过。与冻结设计矛盾时返回constraint_conflict。私有诊断原文未转发；隐藏输入和断言未转发。'}
