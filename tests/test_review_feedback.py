import copy
import json
import pytest
from backend import generation as g, generation_direct as direct, generation_flow as flow
from backend import generation_roles as roles, generation_mock as mock
from test_generation_direct import built


def test_punctuation_feedback_identifies_actual_field_and_source():
    source='返回status=ok与result，此时不输出error字段：echo返回args.text。'
    contract={'behaviors':{'dispatch':source},'input_domain':'输入范围','simulation':'本地模拟','constraints':[]}
    quote='返回status=ok与result，此时不输出error字段。'
    rules=[{'path':'/call/status','quote':quote}]
    errors=direct.review_evidence_errors(contract,rules)
    assert len(errors)==1
    error=errors[0]
    assert error['field']=='/output_rules/0/quote' and error['output_path']=='/call/status'
    assert error['submitted_quote']==quote
    assert error['candidate_sources'][0]['source_path']=='/behaviors/dispatch'
    assert error['nearest_source_differences']
    assert direct.review_evidence_errors(contract,[{'path':'/call/status','quote':source}])==[]
    # Similarity does not approve punctuation substitutions or stitched text.
    stitched='输入范围\n本地模拟'
    assert direct.review_evidence_errors(contract,[{'path':'/x','quote':stitched}])


def test_feedback_survives_audit_persistence_and_next_call(client,monkeypatch):
    j=built();original=mock.role_response
    good=original('spec_review',roles.context(j,'spec_review'))
    assert good['decision']=='approve'
    bad=copy.deepcopy(good);bad['output_rules'][0]['quote']+='不存在的改写'
    captured=[]
    def respond(stage,ctx):
        captured.append(copy.deepcopy(ctx))
        return bad if len(captured)==1 else good
    monkeypatch.setattr(mock,'role_response',respond)
    with pytest.raises(direct.ReviewEvidenceError) as caught:flow.call(j,'spec_review')
    flow.failure(j,'spec_review',caught.value)
    j=g.get(j['id'])
    feedback=j['format_error']['validation_feedback']
    assert feedback==j['attempts'][-1]['error']['validation_feedback']
    assert feedback==j['failure_history'][-1]['error']['validation_feedback']
    assert feedback['errors'][0]['submitted_quote']==bad['output_rules'][0]['quote']
    assert '/output_rules/0/quote' in j['error']['reason']
    assert 'validation_feedback' not in roles.context(j,'project_build')
    assert 'validation_feedback' not in roles.context(j,'evaluation')
    stale=copy.deepcopy(j);stale['contract_hash']='a'*64
    assert 'validation_feedback' not in roles.context(stale,'spec_review')
    flow.call(j,'spec_review')
    assert captured[1]['validation_feedback']==feedback
    request=json.loads((g.root(j)/j['attempts'][-1]['asset']/'input.json').read_text())
    assert json.loads(request[-1]['content'])['validation_feedback']==feedback
    assert 'format_error' not in j
    assert j['attempts'][-1]['status']=='completed'
    assert 'project' not in captured[1] and 'private_fault_requirements' not in captured[1]


def test_feedback_bounds_and_no_false_approval():
    contract={'behaviors':{'rule':'x'*1800},'input_domain':'a','simulation':'b','constraints':[]}
    errors=direct.review_evidence_errors(contract,[{'path':'/x','quote':'y'*1800} for _ in range(40)])
    exc=direct.ReviewEvidenceError(errors,'a'*64)
    assert len(exc.feedback['errors'])==8 and exc.feedback['omitted_count']==32
    assert len(json.dumps(exc.feedback).encode())<32000
    assert all(len(c['excerpt'])<=600 for e in exc.feedback['errors'] for c in e['candidate_sources'])
