"""Add interpretation boundaries to trusted results, never read private test inputs."""
import json
from . import storage as s

BOUNDARIES = [
    '范围检查只证明允许文件/受保护代码范围约束；是否实际修改须看 diff，不证明功能正确。',
    '只有 status=passed 的行为检查支持其已列场景；失败样例不能排除未验证的过滤或其他场景。',
    '代码分析是推断，不是执行观察；测试接受行为等价的多种实现，不要求区分正确方案或匹配参考补丁。',
]


def public_coverage(task, case):
    data=case['input']
    if task=='rag':
        order=data['order']; n=len(data['documents'])
        selected=sorted(order)
        shape='空集' if not selected else '完整集合' if len(selected)==n else '前缀连续子集' if selected==list(range(len(selected))) else '非连续子集' if selected[-1]-selected[0]+1>len(selected) else '连续子集'
        return {'candidate_count':n,'selected_count':len(order),'selected_indices':order,'selection_shape':shape,
                'reordered':order!=sorted(order),'subset':len(order)<n,
                'empty_selection':not order,
                'valid_input_domain':'order 仅含有效且不重复的索引；过滤是选择合法子集，包括非连续子集与空集。非子集、越界或重复索引不属于验收契约。',
                'summary':f'{n} 个候选选取 {len(order)} 项；'+('重排' if order!=sorted(order) else '原相对顺序')+'；'+shape+'；仅此固定样例',
                'not_proven':'不覆盖全部排列、过滤组合或候选数量；单个失败不能排除过滤问题'}
    if task=='retry':
        return {'summary':'正常调用和操作隔离' if not data['failures'] else '响应丢失/暂时失败后的重试',
                'failure_phases':data['failures'],'not_proven':'未列出的失败阶段和重试次数尚未验证'}
    return {'summary':'持久化完成后的中断恢复' if any('stop_after' in c for c in data['calls']) else '正常流程和会话隔离',
            'not_proven':'不证明任意外部系统的 exactly-once'}


def run_evidence(session, run):
    # Read only the immutable public package. Hidden code/input is never opened.
    public={c['id']:c for c in json.loads((s.package(session)/'public_cases.json').read_text())}
    checks=[]
    for check in run.get('checks',[]):
        item={k:check.get(k) for k in ('id','group','visibility','status','duration')}
        scope=check.get('id') in ('modification-scope','constraint')
        item['category']='modification_scope' if scope else 'behavior'
        if scope:
            item.update(coverage={'summary':'允许修改范围'},detail='范围约束检查，不是功能检查',
                        supports='仅范围约束成立' if check.get('status')=='passed' else '范围约束未满足',
                        does_not_prove=['代码确实发生修改','重排正确','过滤正确'])
        else:
            item['coverage']=public_coverage(session['task_id'],public[check['id']]) if check.get('visibility')=='public' and check['id'] in public else {'summary':'具体覆盖未知（未公开）'}
            item['detail']=check.get('detail','')[:1000] if check.get('visibility')=='public' else '仅提供隐藏行为检查状态；不提供输入、源码或异常细节'
            item['supports']={'passed':'仅所列样例行为通过','failed':'存在行为反例；不能排除其他问题'}.get(check.get('status'),'尚无通过结论')
        checks.append(item)
    return {**{k:run.get(k) for k in ('id','snapshot','kind','status','exit_code','duration')},
            'checks':checks,'interpretation_limits':BOUNDARIES}


def tool_summary(name, result, status):
    if status!='ok': return '工具失败，请展开查看原因'
    if name=='read_workspace_file': return '已读取保存代码（代码分析不等于测试结论）'
    if name=='get_workspace_diff': return '已比较初始版本与保存版本' if result else '保存代码与初始版本无差异'
    if name in ('get_run_result','run_public_tests'): return f"执行 {result.get('id','')[:8]} · {result.get('status','未知')}"
    if name=='get_session_evidence': return f"已获取 {len(result.get('runs',[]))} 条执行记录；仅所列覆盖可作依据"
    return '工具已完成；展开查看详情'
