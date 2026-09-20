"""Presentation-only cost and author summaries; never changes generation decisions."""



def usage(job):
    fields=('prompt_tokens','completion_tokens','total_tokens')
    attempts=job.get('attempts',[])
    result={k:{'reported':0,'missing':0} for k in fields}
    for a in attempts:
        u=(a.get('metadata') or {}).get('usage') or {}
        for k in fields:
            v=u.get(k)
            if type(v) is int and v>=0:result[k]['reported']+=v
            else:result[k]['missing']+=1
    return {'calls':len(attempts),'fields':result,'mock':job.get('mode')=='mock'}


def author_summary(job):
    from . import generation as g
    assets={k:g.asset(job,k) for k in job['assets']};project=assets.get('build',{});contract=job.get('contract') or {};m=job.get('matrix') or {}
    return {'request':job['request'],'contract':contract,'contract_changes':job.get('contract_reviews',[]),'files':contract.get('files',[]),'fault':project.get('fault_explanation','尚未生成'),'reference_changed_files':[p for p,code in project.get('reference',{}).items() if project.get('faulty',{}).get(p)!=code],'reference_note':'参考代码在下方私有资产中；具体修复正确性以行为检查和人工审查为准。','variant_results':[{'variant':name,'claim':project.get('evasion_explanations',{}).get(name,''),'checks':[c for c in m.get('checks',[]) if c.get('version')==name]} for name in dict.fromkeys(c.get('version') for c in m.get('checks',[]))],'simulation':contract.get('simulation'),'exclusions':contract.get('exclusions',[]),'issues':{'failed_gates':[k for k,v in m.get('gates',{}).items() if not v],'error':job.get('error'),'uncovered_behaviors':sorted(set(contract.get('behaviors',{}))-{b for c in m.get('checks',[]) for b in c.get('covers',[])})},'binding':{'instance':job['id'],'task_version':job.get('published_version',job.get('target_version','1.0.0')),'contract_version':job['contract_version'],'contract_hash':job.get('contract_hash'),'matrix_id':m.get('id'),'matrix_reused_from_source':bool(job.get('inherited_matrix_id') and job['inherited_matrix_id']==m.get('id')),'review_digest':job.get('review_digest'),'asset_hashes':{k:g.digest(v) for k,v in assets.items()}},'limits':['检查通过仅代表本次有限输入；覆盖标签不证明全部输入域。','模型生成的期望、反例和教学材料仍须人工审核。','本地所有者可读取私有资产；不得将它们加入学习者上下文。']}
