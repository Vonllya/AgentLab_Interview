import React from 'react';
export function revealEvidence(id:string){
 const el=document.getElementById(id);if(!el)return;
 let parent=el.parentElement;while(parent){if(parent instanceof HTMLDetailsElement)parent.open=true;parent=parent.parentElement}el.scrollIntoView({block:'center'});
}
const attemptLabel=(a:any)=>a.outcome==='returned_to_diagnosis'?'已返回冲突或证据缺项':a.status==='completed'?'资产校验通过（非最终验收）':a.status==='failed'?(({provider:'模型请求失败',authentication:'模型鉴权失败',permission:'模型访问被拒绝',configuration:'模型配置不可用',rate_limit:'模型请求被限流',provider_http:'模型服务错误',connection:'模型连接失败',output_limit:'模型输出预算耗尽',empty_content:'模型返回空正文',response_format:'响应格式错误',diagnosis_rejected:'诊断提案被拒绝',patch_rejected:'修复补丁被拒绝',asset_invalid:'生成资产校验失败'} as Record<string,string>)[a.failure_kind as string]||'调用或资产校验失败'):a.status==='running'?'生成中':a.status==='outcome_unknown'?'超时或中断，结果未知':a.status;
export function ProgressEvidence({job}:{job:any}) {
 const usage=job.usage_summary;
 return <section className="panel form" aria-label="修复进展与实际用量"><h3>修复进展与实际用量</h3>
 <p>当前检查点：{job.checkpoint||job.stage} · 剩余模型请求 {Math.max(0,(job.budget?.policy.requests||0)-(job.budget?.requests||0))} 次。</p>
 <p>{job.handoff_version?'工单按动作分派；相同证据下重复冲突、重复拒绝或候选执行无变化时停止自动纠错，等待作者复核。':'失败后按原角色流程继续处理，直到通过、预算耗尽或出现需处理的阻塞；不再按无进展提前终止。'}</p>
 {usage&&<p>{usage.mock?'MOCK 用量，不能作为真实供应商消耗':'供应商返回用量'}：{Object.entries(usage.fields).map(([name,value]:[string,any])=><span key={name}>{name} 已知合计 {value.reported}，{value.missing} 次未返回； </span>)}平台输出预算记账值在上方单独显示，不等同供应商实际用量或费用。</p>}
 <details><summary>阶段执行记录（{job.attempts?.length||0}）</summary>{job.attempts?.map((a:any,i:number)=><p key={i}>{a.role||a.stage} · {attemptLabel(a)} · 调用 #{a.attempt}</p>)}</details>
 <details><summary>历史进展记录（只读，不参与当前控制）（{job.progress_history?.length||0}）</summary>{job.progress_history?.map((p:any)=><div key={p.id}><p>执行 <a href={'#matrix-'+p.matrix_id} onClick={()=>revealEvidence('matrix-'+p.matrix_id)}>{p.matrix_id.slice(0,12)}</a> · {p.reused?'复用相同资产的已有执行证据':'实际执行'} · {p.improved?'有新进展／首次基线':'尚无有效进展'}</p><p>变化资产：{p.changed_assets.join('、')||'无'}；解决 {p.resolved.length} 项，新增问题 {p.introduced.length} 项，新反例 {p.new_witnesses.length} 项。</p></div>)}</details>
 </section>;
}
export function AuthorSummary({review}:{review:any}) {
 const a=review.summary;if(!a)return null;
 return <section aria-label="作者审核摘要"><h3>当前资产审核摘要</h3>
 <h4>原始需求与公开约束</h4><p>{a.request.requirement}</p><p>{a.contract.scenario}</p><p>{a.contract.symptom}</p><ul>{Object.entries(a.contract.behaviors||{}).map(([id,text])=><li key={id}>{id}：{String(text)}</li>)}</ul><p>输入范围：{a.contract.input_domain}</p><ul>{a.contract.constraints?.map((v:string,i:number)=><li key={i}>{v}</li>)}</ul>
 <h4>项目与主要故障（仅作者）</h4><p>文件：{a.files.join('、')}</p><p>{a.fault}</p><p>参考修复改动文件：{a.reference_changed_files?.join('、')||'未生成差异'}</p><p>{a.reference_note}</p>
 <details><summary>参考修复代码与思路审核</summary>{Object.entries(review.assets?.build?.reference||{}).map(([path,code])=><div key={path}><h4>{path}</h4><pre className="review-assets">{String(code)}</pre></div>)}</details>
 <h4>实际验证结果</h4><p>执行矩阵：{a.binding.matrix_id||'尚未执行'}{a.binding.matrix_reused_from_source?'（沿用来源资产执行证据，本批尚无新矩阵）':''}；未通过门禁：{a.issues.failed_gates.join('、')||'无（仍需人工审核）'}。</p>
 {a.variant_results.map((v:any)=><details key={v.variant}><summary>{v.variant} · {v.checks.length} 项执行检查</summary><p>{v.claim}</p>{v.checks.map((c:any)=><div key={c.id}><p>{c.case} · {c.status} · 行为 {c.covers?.join('、')}</p><pre className="review-assets">{JSON.stringify({expected:c.expected,actual:c.actual,error:c.error},null,2)}</pre><a href={'#check-'+c.id} title={c.id} onClick={()=>revealEvidence('check-'+c.id)}>证据 {c.id.slice(0,12)}</a></div>)}</details>)}
 <details><summary>契约修订记录（旧版扩展审计只读）（{a.contract_changes.length}）</summary>{a.contract_changes.map((c:any)=><div key={c.id}><p>v{c.from_version} → {c.to_version||'未变更'}：{c.proposal.reason}</p>{c.review.impact_checks?.map((x:any)=><p key={x.path}>{x.path}：{x.meaning}；依据「{x.quote}」；{JSON.stringify(x.change_effects)}</p>)}</div>)}</details>
 <h4>模拟范围、未覆盖范围与问题</h4><p>{a.simulation||'本地确定性项目'}</p><p>不考察：{a.exclusions.join('、')}</p><p>未执行覆盖标签：{a.issues.uncovered_behaviors.join('、')||'无；不意味着覆盖全部输入域'}</p>{a.issues.error&&<p>{a.issues.error.reason}</p>}<ul>{a.limits.map((v:string)=><li key={v}>{v}</li>)}</ul>
 <details><summary>历史执行矩阵（{review.validation_history?.length||0}）</summary>{review.validation_history?.map((m:any)=><div key={m.id} id={'matrix-'+m.id}><p>执行 {m.id} · {m.passed?'通过':'未通过'}</p>{m.checks.map((c:any)=><p key={c.id} id={'check-'+c.id}>{c.version} / {c.case} · {c.status} · {c.id}</p>)}</div>)}</details>
 <h4>批准绑定</h4><p>实例 {a.binding.instance} · 契约 v{a.binding.contract_version}</p><p className="review-assets">审核摘要：{a.binding.review_digest||'尚未达到审核状态'}</p><details><summary>完整资产摘要</summary><pre className="review-assets">{JSON.stringify(a.binding,null,2)}</pre></details>
 </section>;
}

export function HandoffEvidence({review}:{review:any}) {
 if(!review.handoff_conflicts?.length&&!review.candidate_history?.length&&!review.evidence_request)return null;
 return <section aria-label="修复交接证据"><h3>修复交接证据（仅作者）</h3>
 {review.handoff_conflicts?.map((c:any)=><details key={c.id}><summary>冲突 {c.id.slice(0,12)} · {c.kind}</summary>
 <p>绑定执行：{c.matrix_id}</p>{c.details?.pairs?.map((p:any,i:number)=><div key={i}><p>要求 A：{p.left_ref}；要求 B：{p.right_ref}</p><p>{p.explanation}</p></div>)}
 {c.details?.missing&&<p>缺少证据：{c.details.missing}</p>}{c.details?.proposed_verification&&<p>建议验证：{c.details.proposed_verification}</p>}
 <pre className="review-assets">{JSON.stringify(c.details?.requirements,null,2)}</pre></details>)}
 {review.evidence_request&&<p>待补证据：{review.evidence_request.missing}；建议验证：{review.evidence_request.proposed_verification}</p>}
 {review.candidate_history?.map((c:any,i:number)=><p key={i}>候选 {c.stage} · {c.status} · 执行 {c.matrix_id||'尚未执行'} · {c.asset}</p>)}
 </section>;
}
