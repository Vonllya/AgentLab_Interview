"""Opt-in bounded real specialist repair of historical failures; never publishes."""
import json,os,time,hashlib,argparse
from pathlib import Path
import httpx
PARENTS={'tool':'71a94a226ec742c5b778ae9b39997193','workflow':'17683c1deb9c4bd4aea75279524205b4'}
NOTES={'tool':'请根据冻结契约复核：合法重复请求的is_retry约定下故障版可能等价正确；按retry标记去重的规避可能同样等价正确；按recipient去重需要不同operation_id同recipient覆盖。分别诊断、只改对应资产，不改原有正确期望。', 'workflow':'请复核两个规避版本是否与参考实现行为等价；不能强行用测试拒绝正确等价实现。保留有效正常版、故障版、参考和既有正确期望，只修真正错误的候选或补契约内覆盖。'}
if __name__=='__main__':
 if os.getenv('AGENTLAB_REAL_SMOKE')!='1':raise SystemExit('Requires AGENTLAB_REAL_SMOKE=1')
 parser=argparse.ArgumentParser();parser.add_argument('case',choices=PARENTS);parser.add_argument('--inspect',action='store_true');parser.add_argument('--tag',default='first');parser.add_argument('--requests',type=int,default=16);args=parser.parse_args()
 out=Path('data/roles-verification');out.mkdir(exist_ok=True,parents=True)
 with httpx.Client(base_url='http://127.0.0.1:18000/api',timeout=30) as c:
  def api(path,body=None):
   r=c.get(path) if body is None else c.post(path,json=body)
   r.raise_for_status();return r.json()
  assert api('/health')['agent_mode']=='real'
  if args.inspect:id=(out/(args.case+'-'+args.tag+'-child.txt')).read_text()
  else:
   parent=api('/generation/jobs/'+PARENTS[args.case])
   child=api('/generation/jobs/'+parent['id']+'/regenerate',{'expected_revision':parent['revision'],'idempotency_key':'roles-'+args.tag+'-'+args.case,'new_batch':True,'repair_note':NOTES[args.case],'budget':{'requests':args.requests,'output_tokens':72000,'input_bytes':600000,'seconds':1200,'validations':8}})
   id=child['id'];(out/(args.case+'-'+args.tag+'-child.txt')).write_text(id)
  while True:
   job=api('/generation/jobs/'+id);(out/(args.case+'-'+args.tag+'-public.json')).write_text(json.dumps(job,ensure_ascii=False,indent=2))
   print(json.dumps({'id':id,'status':job['status'],'stage':job['stage'],'requests':job['request_count'],'round':job.get('repair_round'),'error':job['error']},ensure_ascii=False),flush=True)
   if job['status'] not in ('analyzing','building','evaluating','validating','teaching','diagnosing','repairing_build','waiting_backoff'):break
   time.sleep(10)
  review=api('/author/generation/'+id);(out/(args.case+'-'+args.tag+'-author.json')).write_text(json.dumps(review,ensure_ascii=False,indent=2))
