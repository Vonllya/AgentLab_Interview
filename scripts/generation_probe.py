"""Opt-in real generation requests. Does not publish or claim human review."""
import argparse
import json
import os
import time
from pathlib import Path
import httpx

SCENARIOS={
 'tool_side_effect':'希望训练工具调用副作用的故障排查：本地模拟通知发送，响应丢失后同一逻辑操作重试导致重复通知。需要小型原创多模块项目，正常操作与重试有确定性可观察输出，可验证不同逻辑操作隔离。只模拟本地记录，不接真实邮件或支付。预计45分钟。',
 'workflow_state':'希望训练工作流恢复机制：本地任务计划已把完成状态持久化，重开恢复时却重复已完成步骤。需要原创小型多模块实现，输出可观察的执行序列和状态，覆盖多会话隔离与已结束流程恢复。只模拟本地文件或SQLite，不宣称解决任意系统exactly-once。预计45分钟。',
 'permission_boundary':'希望训练Agent工具授权边界：工具白名单正确，但不可信检索文档中伪装的授权信息影响了工具执行权限。要求原创小型多模块纯Python模拟，用明确角色/来源字段和本地副作用记录验证授权决策，不调用真实模型，不声称验证模型抵御提示注入的能力。只考工程权限边界，保留可信用户已授权工具的正常调用，预计40分钟。'
}


def main():
    if os.getenv('AGENTLAB_REAL_SMOKE')!='1':raise SystemExit('Requires AGENTLAB_REAL_SMOKE=1')
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['design','confirm','retry','inspect']);parser.add_argument('target');args=parser.parse_args()
    output=Path('data/v02-verification');output.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url=os.getenv('AGENTLAB_PROBE_API','http://127.0.0.1:8000/api'),timeout=30) as client:
        def api(path,method='GET',data=None):
            response=client.request(method,path,json=data);response.raise_for_status();return response.json()
        assert api('/health')['agent_mode']=='real'
        if args.action=='design':
            job=api('/generation/jobs','POST',{'requirement':SCENARIOS[args.target],'minutes':45,'difficulty':'进阶','preference':'标准库、本地模拟、单一主要故障、可复现行为'})
            id=job['id'];api('/generation/jobs/'+id+'/analyze','POST')
            (output/(args.target+'-id.txt')).write_text(id)
        else:
            id=args.target;job=api('/generation/jobs/'+id)
            if args.action=='confirm':api('/generation/jobs/'+id+'/confirm','POST',{'version':job['contract_version'],'simulation_confirmed':True})
            if args.action=='retry':api('/generation/jobs/'+id+'/retry','POST')
        deadline=time.monotonic()+650
        while True:
            job=api('/generation/jobs/'+id)
            (output/(id+'.json')).write_text(json.dumps(job,ensure_ascii=False,indent=2))
            if job['status'] not in ('analyzing','building','evaluating','validating','teaching') or time.monotonic()>deadline:break
            time.sleep(2)
        print(json.dumps({'id':id,'status':job['status'],'assessment':job['assessment'],'rationale':job['rationale'],'contract':job.get('contract') if args.action=='design' else None,'error':job['error'],'matrix':job['matrix'].get('gates') if job.get('matrix') else None},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
