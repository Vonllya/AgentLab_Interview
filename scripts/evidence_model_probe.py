"""Opt-in live semantic probe with one real Docker execution, not a new task/test pack."""
import json
import os
import time
from pathlib import Path
from backend import agent, storage as s, workspace as w, evidence, executor

if os.getenv('AGENTLAB_REAL_SMOKE')!='1' or agent.mode()!='real':
    raise SystemExit('Require AGENTLAB_REAL_SMOKE=1 and real model configuration')
output=s.ROOT/'data/reliability-verification'
s.DATA=output/'probe-data';s.init()
session=w.create('rag');snapshot=w.snapshot(session)
case={'id':'two-doc-full-reorder','input':{'documents':[{'id':'d0','text':'内容0'},{'id':'d1','text':'内容1'}],'order':[1,0]},'expected':[{'text':'内容1','citation':'d1'},{'text':'内容0','citation':'d0'}]}
actual=executor.execute(s.DATA/'snapshots'/snapshot,case['input'])
assert actual!=case['expected'], 'The controlled faulty two-document reorder must fail behavior'
assert not w.constraints(session,w.read(session))
run_id=s.ident()
packet={'id':run_id,'source':'验证脚本调用现有 Docker 执行器；独立补充实验，不是平台公开测试清单',
        'snapshot':snapshot,'checks':[
          {'id':'modification-scope','category':'modification_scope','status':'passed','supports':'允许修改范围约束成立','does_not_prove':['发生修改','重排正确','过滤正确']},
          {'id':case['id'],'category':'behavior','status':'failed','coverage':evidence.public_coverage('rag',case),'expected':case['expected'],'actual':actual}],
        'interpretation_limits':evidence.BOUNDARIES}
messages=[{'role':'system','content':agent.SYSTEM},
          {'role':'user','content':'以下是独立实验的真实执行证据，本题没有其他已执行样例。请用三条短句回答：范围通过能否证明已修改且功能正确？能否排除过滤问题？若两个备选实现都满足契约，测试是否需要区分它们？引用证据，不提供修复代码。\n'+json.dumps(packet,ensure_ascii=False)}]
proof={'evidence':packet,'created':time.time()}
try:
    msg=agent.completion(messages)
    proof.update(reply=agent.safe_response(msg['content']),metadata=msg['_meta'])
    print(json.dumps({'id':run_id,'reply':proof['reply'],'metadata':proof['metadata']},ensure_ascii=False))
except Exception as exc:
    proof.update(error=agent.model_error(exc),metadata=getattr(exc,'metadata',{}))
    print(json.dumps(proof['error'],ensure_ascii=False))
    raise SystemExit(1) from None
finally:
    (output/'controlled-evidence.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
