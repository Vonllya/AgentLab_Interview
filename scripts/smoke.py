"""Real HTTP smoke for the running app; does not fabricate execution evidence."""
import json
import urllib.request

BASE='http://127.0.0.1:5173'

def call(path,method='GET',body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(BASE+'/api'+path,data=data,method=method,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)

with urllib.request.urlopen(BASE,timeout=10) as response:
    assert 'AgentLab' in response.read().decode()
health=call('/health')
tasks=call('/tasks');assert len(tasks)==3
obj=call('/sessions','POST',{'task_id':'rag'});sid=obj['id']
original=call('/sessions/'+sid)['code']
call('/sessions/'+sid+'/files','PUT',{'code':original+'\n# HTTP smoke\n','diagnosis':'HTTP 保存与恢复检查；尚未执行用户代码。'})
assert call('/sessions/'+sid+'/hint','POST')['level']==1
assert call('/sessions/'+sid+'/chat','POST',{'message':'说明当前证据状态'})['mode']=='mock'
restored=call('/sessions/'+sid)
assert restored['code'].endswith('# HTTP smoke\n') and len(restored['hints'])==1
assert restored['runs']==[]
print(json.dumps({'http_smoke':'passed','session':sid,'docker_available':health['docker_available'],'agent_mode':health['agent_mode'],'execution_evidence':'none'},ensure_ascii=False))
