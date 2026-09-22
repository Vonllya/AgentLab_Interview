import copy
import json
import pytest
from pydantic import ValidationError
from backend import generation_handoff as h, generation_roles as roles
from test_handoff import prepared, order


def test_focused_edit_requires_locations_and_real_change(client):
 j=prepared();raw=order(j)
 old=copy.deepcopy(raw);old['action']={'kind':'edit_code','variants':['faulty'],'approach':'这段说明实际要求重新分类，不是修改代码。'}
 with pytest.raises(ValidationError):h.validate_order(j,old)
 for field in ['location','current_behavior','intended_behavior','must_preserve']:
  bad=copy.deepcopy(raw);bad['action']['edits'][0].pop(field)
  with pytest.raises(ValidationError):h.validate_order(j,bad)
 bad=copy.deepcopy(raw);bad['action']['edits'][0]['variant']='normal'
 with pytest.raises(ValueError,match='覆盖'):h.validate_order(j,bad)
 bad=copy.deepcopy(raw);edit=bad['action']['edits'][0];edit['intended_behavior']=edit['current_behavior']
 with pytest.raises(ValueError,match='相同'):h.validate_order(j,bad)
 assert h.validate_order(j,raw)['target_variants']==['faulty']


def test_private_descriptions_not_forwarded_to_builder_and_legacy_readable(client):
 j=prepared();raw=order(j);raw['action']['edits'][0]['current_behavior']='PRIVATE_DIAGNOSTIC_SENTINEL hidden input interpretation'
 j['pending_plan']=h.validate_order(j,raw)
 ctx=roles.context(j,'repair_build')
 assert ctx['suspected_modules']['files']==['app.py']
 assert 'PRIVATE_DIAGNOSTIC_SENTINEL' not in json.dumps(ctx)
 # Historical persisted work orders remain readable; no rewrite or forced migration.
 j['pending_plan']['work_order']['action']={'kind':'edit_code','variants':['faulty'],'approach':'历史说明保持不变，不重新执行模型生成。','suspected_files':['app.py']}
 assert roles.context(j,'repair_build')['suspected_modules']['files']==['app.py']
 assert 'edits' in h.WorkOrder.model_json_schema()['$defs']['CodeAction']['required']
