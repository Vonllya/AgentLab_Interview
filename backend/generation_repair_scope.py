"""Program-owned repair permissions derived from the current execution evidence.

This does not decide whether a test oracle is correct or select a repair algorithm.
"""

def repair_scope(job, evasion_names):
    matrix=job.get('matrix') or {};gates=matrix.get('gates') or {};checks=matrix.get('checks',[])
    versions={}
    for name in ['normal','reference','faulty',*sorted(evasion_names)]:
        rows=[c for c in checks if c.get('version')==name]
        errors=[c['id'] for c in rows if c.get('status')=='error']
        unmet=[];preserve=[];unknown=[]
        def gate(key, requirement):
            value=gates.get(key)
            if value is True:preserve.append(requirement)
            elif value is False:unmet.append(requirement)
            else:unknown.append(requirement)
        if name in ('normal','reference'):
            gate(name,'all_behavior_checks_pass')
        elif name=='faulty':
            gate('fault_trigger','frozen_fault_reproduced_stably')
            gate('fault_regression','all_regression_checks_pass')
        else:
            # An evasion is qualified when rejected on a target AND preserves a
            # regression. Target failure here is success for the task generator.
            if rows:
                (preserve if any(c.get('group')=='target' and c.get('status')=='failed' for c in rows) else unmet).append('wrong_fix_rejected_by_target')
                (preserve if any(c.get('group')=='regression' and c.get('status')=='passed' for c in rows) else unmet).append('at_least_one_regression_passes')
            else:unknown.extend(['wrong_fix_rejected_by_target','at_least_one_regression_passes'])
        if errors:unmet.append('no_execution_errors')
        elif rows:preserve.append('no_execution_errors')
        else:unknown.append('no_execution_errors')
        permission='allowed' if unmet else 'unknown' if unknown else 'forbidden'
        versions[name]={'code_change':permission,'unmet_requirements':unmet,'must_preserve':preserve,
                        'unknown_requirements':unknown,'evidence_ids':[c['id'] for c in rows if 'id' in c]}
    return {'matrix_id':matrix.get('id'),'contract_hash':job.get('contract_hash'),
            'failed_gates':[key for key,value in gates.items() if value is False],
            'allowed_code_variants':[n for n,v in versions.items() if v['code_change']=='allowed'],
            'protected_code_variants':[n for n,v in versions.items() if v['code_change']=='forbidden'],
            'unverified_code_variants':[n for n,v in versions.items() if v['code_change']=='unknown'],
            'variants':versions,
            'other_unmet_requirements':(['fingerprint_must_exclude_normal_and_reference'] if gates.get('fingerprint_discriminates') is False else []),
            'authority':'程序依据当前矩阵计算，模型不得重解释修改权限。允许修改不等于已确定根因；可依现有流程提出有依据的评测或规范问题，不能据此自动改期望。',
            'evasion_meaning':'目标检查失败且至少一个回归通过且无运行错误，表示错误修复已被正确识别，候选已合格、禁止再改；不表示该代码是正确修复。',
            'faulty_meaning':'故障注入版本的目标：指定故障在约定场景下稳定复现，未受影响场景正常。故障命中与回归通过是独立义务，不能相互替代；调整故障注入实现时不得消除指定故障。'}
