import json
import pytest
from backend import generation_evidence as e,generation_handoff as h,generation_roles as roles,generation_flow as f
from test_generation_evidence import ready
from test_handoff import order


def test_no_evidence_accepts_omitted_or_empty(client):
 j=ready();assert not e.response_contract(j)['required']
 p=order(j);assert h.validate_order(j,p)
 p['evidence_responses']={};assert h.validate_order(j,p)
 schema=roles.messages(j,'diagnosis')[0]['content']
 assert '"maxProperties": 0' in schema
 assert '当前没有补充证据' in schema


def test_current_check_ids_are_not_stale_and_feedback_delivered(client):
 j=ready();p=order(j);check=j['matrix']['checks'][0]['id']
 p['evidence_responses']={check:'这是当前矩阵检查的说明，但填错了字段，不是旧资产。'}
 with pytest.raises(e.EvidenceResponseError) as exc:h.validate_order(j,p)
 feedback=exc.value.feedback
 assert feedback['matrix_check_ids']==[check] and feedback['stale_ids']==[]
 assert feedback['allowed_ids']==[] and '省略或为{}' in str(exc.value)
 f.failure(j,'diagnosis',exc.value)
 ctx=roles.context(j,'diagnosis')
 assert ctx['validation_feedback']==feedback
 assert ctx['evidence_response_contract']['allowed_ids']==[]


def test_missing_unknown_and_short_are_specific(client):
 j=ready();record=e.resolve(j,{'requests':[{'kind':'file','variant':'faulty','path':'app.py','question':'核对故障业务入口'}]});id=record['id']
 with pytest.raises(e.EvidenceResponseError) as exc:e.validate_responses(j,{'unknown':'not a valid id'})
 assert exc.value.feedback['missing_ids']==[id] and exc.value.feedback['unknown_ids']==['unknown']
 with pytest.raises(e.EvidenceResponseError) as exc:e.validate_responses(j,{id:'短'})
 assert exc.value.feedback['short_ids']==[id]
 e.validate_responses(j,{id:'已核对入口代码，后续仍需结合实际行为矩阵决定修复。'})
 assert '"minLength": 15' in roles.messages(j,'diagnosis')[0]['content']
 j['contract_hash']='next-version'
 with pytest.raises(e.EvidenceResponseError) as exc:e.validate_responses(j,{id:'旧记录不能用于新资产'})
 assert exc.value.feedback['stale_ids']==[id]
