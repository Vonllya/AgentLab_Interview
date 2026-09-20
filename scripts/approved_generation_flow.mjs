// Opt-in functional verification for the exact instance explicitly approved by the owner.
// Author assets stay in this test process; chat receives only saved student code/public evidence.
import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
if(process.env.AGENTLAB_REAL_SMOKE!=='1')throw Error('Explicit real-provider opt-in required');
const dir='data/v02-verification',id='81a3a18745ed4eaba0813d8b3f6d99b4';
const digest='1bc32e924954166a81386b76a7f66dceda9b61469d0da06baca1ca7ad8b4c3c1';
const preflight=JSON.parse(await readFile(dir+'/approved-publication-preflight.json','utf8'));
expect(preflight.review_digest).toBe(digest);expect(preflight.verified).toBe(true);
const proof={instance:id,approvalDigest:digest,purpose:'系统功能验证；使用参考修复，不作为真实用户学习效果证据',started:new Date().toISOString(),steps:[]};
const browser=await chromium.launch({executablePath:process.env.AGENTLAB_BROWSER_EXECUTABLE||'/tmp/agentlab-browser/chrome-linux64/chrome'});
const context=await browser.newContext({baseURL:'http://127.0.0.1:5173',permissions:['clipboard-read','clipboard-write']});
const page=await context.newPage();
async function api(path){const r=await context.request.get('/api'+path);expect(r.ok(),path).toBeTruthy();return r.json()}
async function mark(step){proof.steps.push({step,time:new Date().toISOString()});await writeFile(dir+'/approved-flow.json',JSON.stringify(proof,null,2));console.log(step)}
async function state(){return api('/sessions/'+proof.session)}
async function executePublic(expected){
 const count=(await state()).runs.length;
 await page.getByRole('button',{name:'保存并运行公开测试'}).click();
 await expect.poll(async()=>(await state()).runs.length,{timeout:15000}).toBeGreaterThan(count);
 await expect.poll(async()=>(await state()).runs[0].status,{timeout:120000,intervals:[1000]}).toBe(expected);
 await expect(page.locator('.run').first().locator('.runhead .status')).toHaveText(expected==='passed'?'通过':'失败');
 return (await state()).runs[0];
}
try{
 const health=await api('/health');expect(health.agent_mode).toBe('real');expect(health.docker_available).toBe(true);
 const job=await api('/generation/jobs/'+id),review=await api('/author/generation/'+id);
 expect(job.status).toBe('awaiting_review');expect(job.contract_version).toBe(2);expect(job.confirmed_version).toBe(2);
 expect(job.matrix.id).toBe(preflight.matrix);expect(job.matrix.passed).toBe(true);expect(review.review_digest).toBe(digest);
 proof.generationRequests=job.request_count;
 await page.goto('/generate/'+id);
 await page.getByRole('button',{name:'打开私有资产审核'}).click();
 await page.getByText('契约、全部实现、独立检查与教学材料',{exact:true}).click();
 await page.getByLabel('审核依据').fill('用户已阅读作者审核摘要并明确批准本实例、契约v2、矩阵a2415e5ba601438297af5d1fd32ed2d1及摘要'+digest+'。仅批准本地内部试用的纯Python模拟授权决策与记录，接受reason、decision重复保留与executed去重约定；不证明真实工具副作用、身份认证或模型注入防御。题面、提示、规避命名和时长问题留待后续版本，当前资产不变。后续自动化使用参考修复仅验证系统功能。');
 await page.getByLabel('我已审核当前资产及验证证据，确认可以发布').check();
 await page.getByRole('button',{name:'审核通过并发布'}).click();
 await expect(page.getByRole('heading',{name:/已冻结发布/})).toBeVisible();
 proof.publication=await api('/generation/jobs/'+id);
 expect(proof.publication.published_version).toBe('1.0.0');expect(proof.publication.request_count).toBe(job.request_count);
 await mark('已按用户批准通过正常作者页面发布');
 // Enter from the library, not the author shortcut.
 await page.getByRole('link',{name:'题库',exact:true}).click();await expect(page).toHaveURL(/\/library$/);
 const card=page.locator('.cards article').filter({has:page.getByRole('link',{name:job.contract.title,exact:true})});
 await expect(card).toContainText('生成任务 · v1.0.0');
 const tasks=await api('/tasks'),task=tasks.find(t=>t.id===proof.publication.published_task);
 expect(task.source).toBe('generated');expect(task.generation_mode).toBe('real');
 for(const key of ['reference','normal','evasions','hidden_cases','fault_explanation','private_assets'])expect(task).not.toHaveProperty(key);
 await card.getByRole('link',{name:job.contract.title,exact:true}).click();
 await expect(page).toHaveURL(new RegExp('/library/'+task.id+'$'));
 await page.getByRole('button',{name:'开始训练 ↗',exact:true}).click();
 await expect(page).toHaveURL(/\/training\/[a-f0-9]{32}$/);proof.session=new URL(page.url()).pathname.split('/').pop();
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();
 const initial=await state();expect(initial.task_id).toBe(task.id);expect(initial.version).toBe('1.0.0');
 expect(initial.permissions.readable.sort()).toEqual(['app.py','authz.py','documents.py','solution.py']);
 for(const [file,code] of Object.entries(review.assets.build.faulty))expect(initial.files[file]).toBe(code);
 const publicTests=await api('/sessions/'+proof.session+'/public-tests');
 expect(publicTests.cases.every(c=>c.visibility==='public'&&!('faulty_expected' in c))).toBe(true);
 for(const path of ['private/hidden_cases.json','private/reference/app.py','../private/author.json','/etc/passwd']){
  const response=await context.request.get('/api/sessions/'+proof.session+'/files',{params:{path}});
  expect([400,403,404,422]).toContain(response.status());
 }
 for(const file of initial.permissions.readable){await page.getByRole('button',{name:'打开文件 '+file,exact:true}).click();await expect(page.locator('.editor .panelhead')).toContainText(file)}
 await mark('题库创建、多文件浏览和公开接口私有路径拒绝通过');
 proof.faultRun=await executePublic('failed');
 expect(proof.faultRun.checks.some(c=>c.id==='trusted-only-basic'&&c.status==='failed')).toBe(true);
 expect(proof.faultRun.checks.filter(c=>c.group==='regression').every(c=>c.status==='passed')).toBe(true);
 expect(proof.faultRun.checks.some(c=>['error','timeout'].includes(c.status))).toBe(false);
 await mark('故障代码实际公开执行：目标越权失败、正常回归通过');
 // True model call before copying any reference code into the learner workspace.
 const prompt='这是系统功能验收，不是学习效果评估。请通过工具读取当前保存的 app.py 和 documents.py，并获取公开执行 '+proof.faultRun.id+' 的结果。简短说明哪项公开证据支持授权边界异常、正常回归证明了什么，以及尚不能验证什么。不要提供完整修复代码，不要请求隐藏测试或参考答案。';
 await page.getByLabel('给 Agent 的消息').fill(prompt);
 const pending=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST',{timeout:240000});
 await page.getByRole('button',{name:'发送',exact:true}).click();proof.chat=await (await pending).json();
 expect(proof.chat.mode).toBe('real');expect(proof.chat.status).not.toBe('error');expect(proof.chat.content.length).toBeGreaterThan(30);
 const afterChat=await state();proof.chatTools=afterChat.events.filter(e=>e.role==='tool');
 expect(proof.chatTools.some(e=>e.name==='read_workspace_file'&&e.status==='ok')).toBe(true);
 expect(proof.chatTools.some(e=>['get_run_result','get_session_evidence'].includes(e.name)&&e.status==='ok')).toBe(true);
 await mark('真实模型工具读取与基于公开证据的回复已返回（待语义复核）');
 await page.screenshot({path:dir+'/approved-chat.png',fullPage:true});
 for(const [file,code] of Object.entries(review.assets.build.reference)){
  await page.getByRole('button',{name:'打开文件 '+file,exact:true}).click();
  await page.evaluate(text=>navigator.clipboard.writeText(text),String(code));
  await page.locator('.monaco-editor textarea').first().focus();await page.keyboard.press('Control+A');await page.keyboard.press('Control+V');
 }
 const diagnosis='系统功能验证：直接使用已审核参考修复，不作为真实用户学习效果证据。公开故障执行中 trusted-only-basic 出现文档扩大授权；正常回归仍通过。参考修复仅从 trusted_allowed 构造授权集合，保留正常调用、逐条decision和executed首次出现去重。验证范围仅为纯Python模拟决策与记录，不涉及真实副作用、身份认证或模型提示注入防御。';
 await page.getByLabel('诊断说明').fill(diagnosis);
 await expect(page.getByText('● 有未保存修改（草稿已本地保留）',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
 const saved=await state();for(const [file,code] of Object.entries(review.assets.build.reference))expect(saved.files[file]).toBe(code);
 proof.fixedRun=await executePublic('passed');expect(proof.fixedRun.snapshot).not.toBe(proof.faultRun.snapshot);
 await page.getByRole('button',{name:'请求提示 · 1/3'}).click();await expect(page.getByText(/提示 1\/3：/)).toBeVisible();
 await mark('全部文件保存、参考修复公开测试与一次提示通过');
 await page.getByRole('button',{name:'保存并提交评测'}).click();
 await expect(page.locator('.report .runhead .status')).toHaveText('通过',{timeout:120000});
 await expect.poll(async()=>(await state()).reports[0]?.feedback_status,{timeout:110000,intervals:[1000]}).not.toBe('generating');
 proof.report=(await state()).reports[0];
 expect(proof.report.feedback_status,JSON.stringify(proof.report.feedback_error)).toBe('generated');expect(proof.report.feedback.length).toBeGreaterThan(30);
 expect(proof.report.snapshot).toBe(proof.fixedRun.snapshot);expect(proof.report.objective.snapshot).toBe(proof.report.snapshot);
 expect(proof.report.run_id).toBe(proof.report.objective.id);expect(proof.report.run_id).not.toBe(proof.fixedRun.id);
 expect(proof.report.run_id).not.toBe(proof.faultRun.id);expect(proof.report.objective.hints).toHaveLength(1);expect(proof.report.diagnosis).toBe(diagnosis);
 proof.submittedSnapshot=await api('/sessions/'+proof.session+'/snapshots/'+proof.report.snapshot);
 for(const [file,code] of Object.entries(review.assets.build.reference))expect(proof.submittedSnapshot.files[file]).toBe(code);
 await mark('新的提交执行通过并生成真实模型反馈');
 await page.goto('/training/'+proof.session+'?view=reports#'+proof.report.id);
 await expect(page.locator('.progress')).toHaveCount(0);await page.reload();
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();await expect(page.locator('.progress')).toHaveCount(0);
 await expect(page.getByText('模型反馈 · 已生成',{exact:true})).toBeVisible();
 await expect(page.locator('.report .runhead .status')).toHaveText('通过');
 const restored=await state();expect(restored.reports[0]).toEqual(proof.report);expect(restored.version).toBe('1.0.0');expect(restored.task.version).toBe('1.0.0');
 expect((await api('/runs/'+proof.report.run_id)).snapshot).toBe(proof.report.snapshot);
 await page.getByRole('button',{name:proof.report.snapshot.slice(0,16)+' ↗',exact:true}).click();
 await expect(page.locator('.evidence pre')).toContainText('===== app.py =====');await expect(page.locator('.evidence pre')).toContainText('===== documents.py =====');
 await page.getByRole('button',{name:/提交报告/}).click();
 expect((await api('/author/generation/'+id)).review_digest).toBe(digest);
 expect((await api('/generation/jobs/'+id)).request_count).toBe(proof.generationRequests);
 proof.refreshRestored=true;await mark('刷新、版本、多文件快照与新执行关联一致；未重新生成任务');
 await page.screenshot({path:dir+'/approved-report.png',fullPage:true});
}catch(error){proof.failure=String(error);await page.screenshot({path:dir+'/approved-failure.png',fullPage:true}).catch(()=>{});throw error}
finally{proof.finished=new Date().toISOString();await writeFile(dir+'/approved-flow.json',JSON.stringify(proof,null,2));await browser.close()}
