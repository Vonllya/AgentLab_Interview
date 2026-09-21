"""Bounded specialist-role coordinator; failed attempts continue without user retry clicks."""
import copy
import json
import queue
import threading
import time
from pydantic import ValidationError
from . import generation as g, generation_budget as budget, generation_roles as roles, generation_diagnostics as diagnostics, contract_revision as contracts, agent, storage as s
from . import generation_protocol as protocol, generation_direct as direct, generation_handoff as handoff
from .generation_schema import Contract,Project,validate_project,Teaching,Request

STATES={'project_build':'building','spec_review':'reviewing_spec','design':'analyzing','build':'building','evaluation':'evaluating','fingerprint':'evaluating','diagnosis':'diagnosing','repair_build':'repairing_build','validation':'validating','teaching':'teaching','contract_review':'clarifying_contract','contract_check':'checking_contract','contract_apply':'checking_contract'}
ACTIVE_STATES=set(STATES.values())|{'waiting_backoff'}


def check(job):
    current=g.get(job['id'])
    if current['status']=='cancelled':raise InterruptedError('用户已取消')
    if current.get('coordinator_token')!=job.get('coordinator_token'):raise InterruptedError('旧协调器已失效')
    if budget.remaining(job)<=0:raise budget.Exhausted('本批执行时间预算耗尽')


def save_candidate(job,stage,output,directory):
    if handoff.enabled(job) and job.get('matrix') and stage in ('build','evaluation','fingerprint'):
        (directory/'output.json').write_text(json.dumps(output,ensure_ascii=False))
        handoff.stage_candidate(job,stage,directory.name);job['revision']=job.get('revision',0)+1
        return
    old=job['assets'].get(stage)
    if old:job.setdefault('asset_revisions',[]).append({'stage':stage,'asset':old,'hash':g.digest(g.asset(job,stage)),'replaced_at':time.time()})
    (directory/'output.json').write_text(json.dumps(output,ensure_ascii=False))
    job['assets'][stage]=directory.name;job['revision']=job.get('revision',0)+1
    g.put(job)


def call(job,stage):
    check(job);messages=roles.messages(job,stage);encoded=json.dumps(messages,ensure_ascii=False)
    with s.LOCK:
        check(job);cap=budget.reserve(job,stage,len(encoded.encode()))
        directory=g.root(job)/('call-'+s.ident());directory.mkdir(parents=True)
        (directory/'input.json').write_text(encoded)
        audit={'stage':stage,**roles.identity(job,stage),'attempt':1+sum(a['stage']==stage for a in job['attempts']),'contract_version':job['contract_version'],'input_hash':g.digest(messages),'started':time.time(),'status':'running','reserved_tokens':cap,'asset':directory.name,'blind':stage=='evaluation' and not job.get('evaluation_review_guided',False)}
        job['attempts'].append(audit);job['request_count']+=1;job.update(stage=stage,status=STATES[stage],active_action={'stage':stage,'asset':directory.name});g.put(job)
    meta={};settled=False;raw=None
    try:
        if job['mode']=='mock':
            from .generation_mock import role_response
            raw=role_response(stage,copy.deepcopy(roles.context(job,stage)));meta={'model':'MOCK deterministic roles','usage':{'completion_tokens':0},'finish_reason':'stop'}
        else:
            result=queue.Queue(maxsize=1)
            def invoke():
                try:result.put((True,agent.completion(messages,purpose='generation',timeout=min(90,budget.remaining(job)),output_limit=cap)))
                except Exception as exc:result.put((False,exc))
            threading.Thread(target=invoke,daemon=True).start()
            deadline=time.monotonic()+min(100,budget.remaining(job))
            while True:
                check(job)
                if time.monotonic()>=deadline:raise agent.ModelFailure('timeout','角色调用超时，迟到响应不能推进资产')
                try:ok,response=result.get(timeout=min(.2,max(.01,deadline-time.monotonic())));break
                except queue.Empty:continue
            if not ok:raise response
            meta=response.get('_meta',{});text=response.get('content') or ''
            if len(text.encode())>300000:raise ValueError('模型资产超过300KiB')
            (directory/'response.txt').write_text(text);raw=json.loads(text)
        budget.settle(job,audit,meta);settled=True;check(job)
        parsed=roles.schema(job,stage).model_validate(raw).model_dump()
        if stage=='project_build':parsed=direct.validate_bundle(job,parsed)
        if stage=='spec_review':parsed=direct.validate_review(job,parsed)
        if stage=='build':validate_project(Project.model_validate(parsed),Contract.model_validate(job['contract']))
        if stage=='repair_build':
            parsed=handoff.builder_result(job,parsed) if handoff.enabled(job) else diagnostics.merge_repair(job,parsed)
            if parsed is None:
                audit.update(status='completed',finished=time.time(),metadata=meta,outcome='returned_to_diagnosis')
                (directory/'output.json').write_text(json.dumps(raw,ensure_ascii=False))
                job.pop('active_action',None);g.put(job)
                return {'handoff_return':True}
        if stage=='evaluation':
            if direct.enabled(job) and job.get('evaluation_repair'):
                if parsed['decision']!='patch':
                    job['spec_dispute']={k:parsed[k] for k in ('decision','reason','issues')}
                    job['rejected_evaluation_plan']={'plan':copy.deepcopy(job['evaluation_repair']),'evaluation_hash':g.digest(g.asset(job,'evaluation'))}
                else:parsed=parsed['patch']
            if not (direct.enabled(job) and job.get('spec_dispute') and isinstance(parsed,dict) and parsed.get('decision') in ('specification_issue','reject_plan')):
                if protocol.enabled(job) and job.get('evaluation_repair'):parsed=protocol.merge_patch(job,parsed)
                parsed=diagnostics.validate_evaluation_revision(job,parsed)
        if stage=='fingerprint':parsed=protocol.validate_faults(job,parsed)
        if stage=='diagnosis':parsed=handoff.validate_order(job,parsed) if handoff.enabled(job) else diagnostics.validate_plan(job,parsed)
        if stage=='contract_review':parsed=contracts.validate_proposal(job,parsed)
        if stage=='contract_check':parsed=contracts.validate_check(job,parsed)
        audit.update(status='completed',finished=time.time(),output_hash=g.digest(parsed),metadata=meta)
        (directory/'output.json').write_text(json.dumps(parsed,ensure_ascii=False))
        if stage=='contract_review':job['contract_candidate']={'proposal':parsed,'hash':g.digest(parsed),'asset':directory.name}
        elif stage=='contract_check':job['contract_decision']={'result':parsed,'asset':directory.name}
        elif stage=='evaluation' and parsed.get('decision') in ('specification_issue','reject_plan'):pass
        elif stage!='diagnosis':
            if stage=='project_build':job['previous_bundle_assets']=copy.deepcopy(job['assets'])
            save_candidate(job,'build' if stage=='repair_build' else stage,parsed,directory)
        else:job.setdefault('diagnoses',[]).append(parsed)
        if stage=='evaluation':job.pop('evaluation_candidate',None)
        job.pop('active_action',None);job.pop('format_error',None);g.put(job)
        return parsed
    except Exception as exc:
        if stage=='evaluation' and raw is not None and not job.get('evaluation_repair') and direct.enabled(job):
            (directory/'rejected.json').write_text(json.dumps(raw,ensure_ascii=False))
            job['evaluation_candidate']={'asset':directory.name,'contract_hash':job['contract_hash']}
        meta=getattr(exc,'metadata',meta)
        if not settled:budget.settle(job,audit,meta)
        reason=({'category':'cancelled','reason':'调用被取消，响应不再推进资产'} if isinstance(exc,InterruptedError) else agent.model_error(exc) if isinstance(exc,agent.ModelFailure) else {'category':'asset_validation','reason':str(exc)[:1500]})
        if isinstance(exc,direct.ReviewEvidenceError):reason['validation_feedback']=exc.feedback
        audit['failure_kind']=(reason['category'] if isinstance(exc,agent.ModelFailure) else 'response_format' if isinstance(exc,(json.JSONDecodeError,ValidationError)) else 'diagnosis_rejected' if stage=='diagnosis' else 'patch_rejected' if job.get('evaluation_repair') or stage=='repair_build' else 'asset_invalid')
        audit.update(status='outcome_unknown' if reason['category'] in ('timeout','cancelled') else 'failed',finished=time.time(),metadata=meta,error=reason)
        job.pop('active_action',None);g.put(job);raise


def failure(job,stage,exc):
    reason=agent.model_error(exc) if isinstance(exc,agent.ModelFailure) else {'category':'validation' if stage=='validation' else 'asset_validation','reason':str(exc)[:1800]}
    if isinstance(exc,direct.ReviewEvidenceError):reason['validation_feedback']=exc.feedback
    item={'id':s.ident(),'stage':stage,'time':time.time(),'contract_version':job['contract_version'],'matrix_id':(job.get('matrix') or {}).get('id'),'error':reason}
    job.setdefault('failure_history',[]).append(item);job['error']=reason
    # Schema errors may echo private values: keep them only in that same role's context.
    job['format_error']={'stage':stage,'reason':reason['reason']}
    if 'validation_feedback' in reason:job['format_error']['validation_feedback']=reason['validation_feedback']
    g.put(job);return reason


def next_after_asset(job):
    if direct.enabled(job):
        if 'project_build' not in job['assets']:return 'project_build'
        if (job.get('spec_approval') or {}).get('contract_hash')!=job.get('contract_hash'):return 'spec_review'
    if 'build' not in job['assets']:return 'build'
    if 'evaluation' not in job['assets']:return 'evaluation'
    if protocol.enabled(job) and 'fingerprint' not in job['assets']:return 'fingerprint'
    if (job.get('matrix') or {}).get('passed'):
        matrix=job['matrix']
        if matrix['build_hash']==g.digest(g.asset(job,'build')) and matrix['evaluation_hash']==g.digest(g.asset(job,'evaluation')) and (not protocol.enabled(job) or matrix.get('fingerprint_hash')==g.digest(g.asset(job,'fingerprint'))):
            return 'review' if 'teaching' in job['assets'] else 'teaching'
    return 'validation'


def invalidate(job):
    if 'teaching' in job['assets']:
        job.setdefault('asset_revisions',[]).append({'stage':'teaching','asset':job['assets'].pop('teaching')})
    job.pop('review_digest',None)

def finish_asset(job,stage):
    invalidate(job)
    if handoff.enabled(job) and stage=='evaluation' and protocol.enabled(job) and job.get('candidate_assets',{}).get('evaluation'):
        job.pop('evaluation_repair',None);job.pop('pending_plan',None);g.put(job)
        return 'fingerprint'
    if stage=='evaluation' and protocol.enabled(job) and 'fingerprint' in job['assets']:
        job.setdefault('asset_revisions',[]).append({'stage':'fingerprint','asset':job['assets'].pop('fingerprint')})
    job.pop('evaluation_repair',None);job.pop('pending_plan',None)
    g.put(job)
    return next_after_asset(job)


def run(id,start):
    job=g.get(id);stage=start;budget.begin(job);g.put(job)
    try:
        while True:
            check(job);job['budget']['actions']=job['budget'].get('actions',0)+1
            if job['budget']['actions']>200:raise budget.Exhausted('本批协调操作次数预算耗尽')
            job['checkpoint']=stage;g.put(job)
            try:
                if stage=='project_build':
                    call(job,stage);direct.install_bundle(job);stage='spec_review';continue
                if stage=='spec_review':
                    call(job,stage);stage=direct.apply_review(job)
                    if stage is None:break
                    continue
                if stage=='design':
                    design=call(job,'design')
                    job.update(assessment=design['assessment'],rationale=design['rationale'],questions=design['questions'],contract=design['contract'],private_fault_requirements=design['private_fault_requirements'],status='awaiting_contract',error=None)
                    if design['contract']:job['contract_version']+=1;job['contract_hash']=g.digest(design['contract'])
                    break
                if stage in ('build','evaluation','repair_build','fingerprint'):
                    result=call(job,stage)
                    if stage=='repair_build' and result.get('handoff_return'):
                        stage='diagnosis';continue
                    if stage=='evaluation' and result.get('decision') in ('specification_issue','reject_plan'):
                        job.pop('evaluation_repair',None)
                        stage='spec_review' if result['decision']=='specification_issue' else 'diagnosis'
                    else:stage=finish_asset(job,stage)
                    continue
                if stage=='validation':
                    ok,reason=g.executor.availability()
                    if not ok:job.update(status='waiting_environment',error={'category':'environment','reason':reason});break
                    budget.validation(job);g.put(job);g.validate(job);stage='teaching';continue
                if stage=='diagnosis':
                    plan=job.pop('completed_diagnosis',None) or call(job,'diagnosis');job['repair_round']=job.get('repair_round',0)+1
                    job['progress_reason']={'category':plan['category'],'behaviors':plan['contract_behavior_ids'],'matrix_id':plan['matrix_id']}
                    if handoff.enabled(job) and plan.get('work_order',{}).get('action',{}).get('kind')=='need_evidence':
                        job['evidence_request']=plan['work_order']['action'];raise handoff.NeedsReview('工单缺少必要证据，已记录具体缺项与建议验证；不凭猜测修改或自动重复调用。')
                    clear=(job.get('contract_clarity') or {}).get('contract_hash')==job['contract_hash']
                    if plan['evaluation_action']=='expectation' and clear:
                        job['evaluation_repair']={**plan,'contract_grounded':job['contract_hash']};job['evaluation_review_guided']=True;stage='evaluation';g.put(job);continue
                    if plan['requires_contract_confirmation'] or plan['category'] in ('contract','unknown') or plan['evaluation_action']=='expectation':
                        if direct.enabled(job):
                            job['contract_origin_plan']=plan;stage='spec_review';g.put(job);continue
                        if (job.get('contract_clarity') or {}).get('contract_hash')==job['contract_hash'] and plan['evaluation_action']!='expectation':
                            raise ValueError('契约已独立核对清楚，请修实现或评测，不能无依据重复改契约')
                        job['contract_origin_plan']=plan
                        job['contract_issue']={'behavior_ids':plan['contract_behavior_ids'],'category':plan['category'],'evaluation_action':plan['evaluation_action']}
                        stage='contract_review';g.put(job);continue
                    if plan['category']=='environment':
                        ok,reason=g.executor.availability()
                        if not ok:job.update(status='waiting_environment',error={'category':'environment','reason':reason});break
                        raise ValueError('环境检查通过，不能把行为失败归因环境；请依据具体执行诊断')
                    if plan['category']=='evaluation':
                        job['evaluation_repair']=plan;job['evaluation_review_guided']=True
                        stage='fingerprint' if protocol.enabled(job) and plan['evaluation_action']=='fingerprint' else 'evaluation'
                    else:job['pending_plan']=plan;stage='repair_build'
                    g.put(job);continue
                if stage=='contract_review':
                    call(job,stage);stage='contract_check';continue
                if stage=='contract_check':
                    call(job,stage);stage='contract_apply';continue
                if stage=='contract_apply':
                    stage=contracts.apply(job)
                    if stage is None:break
                    continue
                if stage=='teaching':call(job,'teaching');stage='review';continue
                if stage=='review':
                    job.update(status='awaiting_review',stage='review',error=None)
                    job['review_digest']=g.digest({'contract':job['contract_hash'],'assets':{k:g.digest(g.asset(job,k)) for k in g.review_keys(job)},'matrix':job['matrix']})
                    break
                raise ValueError('未知协调器检查点')
            except handoff.NeedsReview:raise
            except budget.Exhausted:raise
            except InterruptedError:raise
            except Exception as exc:
                reason=failure(job,stage,exc)
                if handoff.enabled(job) and not isinstance(exc,agent.ModelFailure):handoff.rejection_guard(job,stage,exc)
                if reason['category'] in ('authentication','permission','configuration'):
                    job['status']='waiting_provider';break
                if reason['category'] in ('rate_limit','provider_http','connection'):
                    if reason['category']=='provider_http' and getattr(exc,'metadata',{}).get('http_status',500)<500:
                        job['status']='waiting_provider';break
                    job['status']='waiting_backoff';g.put(job)
                    delay=max(1,getattr(exc,'metadata',{}).get('retry_after_seconds',min(30,2**min(5,len(job['failure_history'])))))
                    until=time.monotonic()+delay
                    while time.monotonic()<until:check(job);time.sleep(.1)
                # Timeouts/output-limit/schema errors retry with budget; no fixed 3-failure terminal.
                if stage=='validation':
                    if not g.executor.availability()[0]:job['status']='waiting_environment';break
                    stage='diagnosis'
                elif stage=='evaluation' and direct.enabled(job) and not job.get('matrix') and reason['category']=='asset_validation' and len(job['attempts'])>=2 and all(a['stage']=='evaluation' and a['status']=='failed' and a.get('error',{}).get('category')=='asset_validation' for a in job['attempts'][-2:]):
                    job['preflight_review']=True;stage='spec_review';g.put(job)
                elif stage in ('repair_build','evaluation','fingerprint') and job.get('matrix') and len([f for f in job['failure_history'][-2:] if f['stage']==stage])==2:
                    stage='diagnosis'
    except handoff.NeedsReview as exc:
        job.update(status='needs_manual_review',error={'category':'handoff_conflict','reason':str(exc)})
    except budget.Exhausted as exc:
        job.update(status='budget_exhausted',error={'category':'budget_exhausted','reason':str(exc)})
    except InterruptedError:
        # cancellation persisted by API wins; never write late assets/status.
        pass
    finally:
        budget.end(job);g.put(job)
        with s.LOCK:g.ACTIVE.discard(id)
        g.POOL.release()


def resume(id,note=''):
    job=g.get(id)
    if job['status'] not in ('interrupted','waiting_environment','waiting_provider','awaiting_contract_review','no_progress','needs_manual_review'):raise ValueError('当前状态需要明确创建新预算批次')
    if job['status']=='needs_manual_review' and len(note.strip())<10:raise ValueError('请先在作者审核中核对冲突并提供新的依据，不能原样恢复自动循环')
    if job['status']=='awaiting_contract_review' and len(note.strip())<10:raise ValueError('请先核对作者诊断并提供至少10字修复依据，或确认新契约')
    if note:job['repair_note']=note[:2000]
    # Old transient schema guidance must not re-impose the rolled-back protocol.
    # failure_history/attempts remain unchanged for audit.
    if job.get('reliability_version'):job.pop('format_error',None)
    stage=job.get('checkpoint','design')
    if direct.enabled(job) and stage=='project_build' and job.get('attempts') and job['attempts'][-1]['stage']==stage and job['attempts'][-1]['status']=='completed':
        direct.install_bundle(job);stage='spec_review'
    elif direct.enabled(job) and stage=='spec_review' and job.get('attempts') and job['attempts'][-1]['stage']==stage and job['attempts'][-1]['status']=='completed':
        stage=direct.apply_review(job)
        if stage is None:return g.public(job)
    elif job['status'] in ('awaiting_contract_review','no_progress','needs_manual_review'):stage='diagnosis'
    elif stage=='design' and 'design' in job['assets']:
        design=g.asset(job,'design');job.update(contract=design['contract'],assessment=design['assessment'],rationale=design['rationale'],questions=design['questions'],private_fault_requirements=design['private_fault_requirements'],status='awaiting_contract',error=None)
        if design['contract']:job['contract_version']+=1;job['contract_hash']=g.digest(design['contract'])
        g.put(job);return g.public(job)
    elif stage=='diagnosis' and job.get('attempts') and job['attempts'][-1]['stage']=='diagnosis' and job['attempts'][-1]['status']=='completed' and job.get('diagnoses'):
        job['completed_diagnosis']=job['diagnoses'][-1]
    elif stage in ('contract_review','contract_check','contract_apply'):
        if job.get('contract_decision'):stage='contract_apply'
        elif job.get('contract_candidate'):stage='contract_check'
    elif stage in ('build','evaluation','repair_build','fingerprint','teaching'):
        completed=job['attempts'] and job['attempts'][-1]['stage']==stage and job['attempts'][-1]['status']=='completed'
        if completed:
            saved=json.loads((g.root(job)/job['attempts'][-1]['asset']/'output.json').read_text())
            if handoff.enabled(job) and stage=='repair_build' and job['attempts'][-1].get('outcome')=='returned_to_diagnosis':
                stage='diagnosis'
            elif direct.enabled(job) and stage=='evaluation' and saved.get('decision') in ('reject_plan','specification_issue'):
                job.pop('evaluation_repair',None);stage='spec_review' if saved['decision']=='specification_issue' else 'diagnosis'
            else:stage=next_after_asset(job) if stage=='teaching' else finish_asset(job,stage)
    elif stage=='validation' and (job.get('matrix') or {}).get('passed'):stage=next_after_asset(job)
    g.put(job);return g.launch(id,stage)


def regenerate(id,body):
    """Atomic receipt + child creation, with parent immutable. Explicit budget authorization."""
    with s.LOCK:
        request_id=g.digest({'source':id,'key':body.idempotency_key})
        payload_hash=g.digest(body.model_dump())
        try:
            receipt=s.get('generation_request',request_id)
            if receipt['payload_hash']!=payload_hash:raise ValueError('同一幂等键不能复用不同参数')
            return g.public(g.get(receipt['child']))
        except KeyError:pass
        source=g.get(id)
        if source.get('revision',0)!=body.expected_revision:raise ValueError('资产修订已变化，请刷新')
        if source['status'] in g.ACTIVE_STATES or id in g.ACTIVE or source['status'] in ('published','cancelled'):raise ValueError('当前状态不能重新生成；已发布需创建新版本')
        if not body.new_batch:
            if source.get('policy_version')!=budget.POLICY:raise ValueError('旧记录需明确授权新预算批次，原记录保持不变')
            # Receipt is written before launch; a duplicated resume cannot issue another call.
            s.put('generation_request',request_id,{'child':id,'payload_hash':payload_hash})
            try:return resume(id,body.repair_note)
            except Exception:
                with s.connect() as db:db.execute('DELETE FROM objects WHERE kind=? AND id=?',('generation_request',request_id))
                raise
        if body.budget is None:raise ValueError('新增批次必须明确提供预算')
        child=copy.deepcopy(source);child_id=s.ident()
        for key in ('review_digest','review','published_task','published_version','coordinator_token','active_action','format_error','pending_plan','evaluation_repair','completed_diagnosis'):
            child.pop(key,None)
        child.update(id=child_id,created=time.time(),parent_job=id,policy_version=budget.POLICY,batch_id=child_id,budget=budget.initialize(body.budget),status='interrupted',stage='design',attempts=[],request_count=0,validation_count=0,failure_history=[],diagnoses=[],asset_revisions=[],validation_history=[],revision=0,error=None,repair_note=body.repair_note,mode=agent.mode())
        for key in ('reliability_version','progress_history','stagnation_count','diagnostic_strategy','strategy_changed_at','regression_cases','diagnosis_rejections'):child.pop(key,None)
        child['inherited_failure']=source.get('error');child['inherited_matrix_id']=(source.get('matrix') or {}).get('id')
        # Copy immutable selected assets, never edit parent directories/records.
        import shutil
        child['handoff_version']=handoff.VERSION
        refs=set(child['assets'].values())|set(child.get('candidate_assets',{}).values())
        if child.get('evaluation_candidate'):refs.add(child['evaluation_candidate']['asset'])
        refs.update(child[k]['asset'] for k in ('contract_candidate','contract_decision') if child.get(k))
        for ref in refs:shutil.copytree(g.root(source)/ref,g.root(child)/ref)
        if child.get('contract') and child.get('confirmed_version')==child.get('contract_version'):
            start='diagnosis' if child.get('matrix') and not child['matrix'].get('passed') and all(k in child['assets'] for k in ('build','evaluation')) else next_after_asset(child)
        else:start='design' if not child.get('contract') else None
        if direct.enabled(child):
            start=source['checkpoint'] if source.get('checkpoint') in ('project_build','spec_review') else ('diagnosis' if child.get('matrix') and not child['matrix'].get('passed') else next_after_asset(child))
        child['checkpoint']=start or 'build';child['status']='interrupted' if start else 'awaiting_contract'
        with s.connect() as db:
            db.execute('INSERT INTO objects VALUES (?,?,?,?)',('generation',child_id,None,json.dumps(child,ensure_ascii=False)))
            db.execute('INSERT INTO objects VALUES (?,?,?,?)',('generation_request',request_id,None,json.dumps({'child':child_id,'payload_hash':payload_hash})))
        if source['status']=='awaiting_requirement':
            start=None;child['status']='awaiting_requirement';g.put(child)
        elif source.get('checkpoint') in ('contract_review','contract_check','contract_apply'):
            start='contract_apply' if child.get('contract_decision') else 'contract_check' if child.get('contract_candidate') else 'contract_review'
            child['checkpoint']=start;g.put(child)
        if start:
            try:g.launch(child_id,start)
            except ValueError as exc:
                child=g.get(child_id);child['error']={'category':'busy','reason':str(exc)};g.put(child)  # Explicit resumable child; never silently issue paid calls later.
        return g.public(g.get(child_id))
