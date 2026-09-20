// Resume the already published, user-approved instance; never publish/regenerate or replace old reports.
import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
if(process.env.AGENTLAB_REAL_SMOKE!=='1')throw Error('Requires real provider opt-in');
const dir='data/v02-verification',original=JSON.parse(await readFile(dir+'/approved-flow.json','utf8'));
const proof={session:original.session,instance:original.instance,approvalDigest:original.approvalDigest,priorReport:original.report.id,purpose:original.purpose,started:new Date().toISOString()};
const browser=await chromium.launch({executablePath:process.env.AGENTLAB_BROWSER_EXECUTABLE||'/tmp/agentlab-browser/chrome-linux64/chrome'});
const context=await browser.newContext({baseURL:'http://127.0.0.1:5173'}),page=await context.newPage();
async function api(path){const r=await context.request.get('/api'+path);expect(r.ok()).toBeTruthy();return r.json()}
const state=()=>api('/sessions/'+proof.session);
try{
 expect((await api('/health')).agent_mode).toBe('real');
 const job=await api('/generation/jobs/'+proof.instance);expect(job.status).toBe('published');expect(job.published_version).toBe('1.0.0');
 expect((await api('/author/generation/'+proof.instance)).review_digest).toBe(proof.approvalDigest);
 const oldReport=await api('/reports/'+proof.priorReport);expect(oldReport).toEqual(original.report);
 await page.goto('/training/'+proof.session+'?view=reports#'+proof.priorReport);
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();await expect(page.locator('.progress')).toHaveCount(0);
 await expect(page.getByText('模型反馈 · 已生成',{exact:true})).toBeVisible();
 const message='请通过工具读取公开执行 '+original.fixedRun.id+' 的真实结果，简短说明当前修复快照是否通过本次公开样例，以及这不能证明什么。这是使用参考修复的系统功能验证，不是独立学习能力评估。不要把诊断中的历史失败当成本次执行失败，也不要套用其他题目的重排或过滤场景。';
 await page.getByLabel('给 Agent 的消息').fill(message);
 const chatResponse=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST',{timeout:240000});
 await page.getByRole('button',{name:'发送',exact:true}).click();proof.chat=await (await chatResponse).json();
 expect(proof.chat.mode).toBe('real');expect(proof.chat.status).not.toBe('error');
 await expect(page.locator('.progress')).toHaveCount(0);
 console.log('修复后真实证据对话返回，保留先前对话');
 const before=await state();
 await page.getByRole('button',{name:'保存并提交评测'}).click();
 await expect.poll(async()=>(await state()).reports.length,{timeout:120000,intervals:[1000]}).toBe(before.reports.length+1);
 await expect.poll(async()=>(await state()).reports[0].feedback_status,{timeout:110000,intervals:[1000]}).not.toBe('generating');
 const current=await state();proof.report=current.reports[0];
 expect(proof.report.feedback_status,JSON.stringify(proof.report.feedback_error)).toBe('generated');expect(proof.report.objective.status).toBe('passed');
 expect(proof.report.snapshot).toBe(original.fixedRun.snapshot);expect(proof.report.objective.snapshot).toBe(proof.report.snapshot);
 expect(proof.report.run_id).not.toBe(oldReport.run_id);expect(proof.report.run_id).not.toBe(original.fixedRun.id);
 expect(proof.report.objective.hints).toEqual(oldReport.objective.hints);expect(proof.report.diagnosis).toBe(oldReport.diagnosis);
 expect(await api('/reports/'+oldReport.id)).toEqual(oldReport);
 proof.snapshot=await api('/sessions/'+proof.session+'/snapshots/'+proof.report.snapshot);
 expect(proof.snapshot).toEqual(original.submittedSnapshot);
 proof.reportUrl='/training/'+proof.session+'?view=reports#'+proof.report.id;
 await page.goto(proof.reportUrl);await expect(page.locator('.progress')).toHaveCount(0);
 await expect(page.locator('[id="'+proof.report.id+'"] .runhead .status')).toHaveText('通过');
 await page.reload();
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();await expect(page.locator('.progress')).toHaveCount(0);
 const report=page.locator('[id="'+proof.report.id+'"]');
 await expect(report.getByText('模型反馈 · 已生成',{exact:true})).toBeVisible();
 await expect(report.locator('.runhead .status')).toHaveText('通过');
 const restored=await state();expect(restored.version).toBe('1.0.0');expect(restored.task.version).toBe('1.0.0');
 expect(restored.reports.find(r=>r.id===proof.report.id)).toEqual(proof.report);
 expect((await api('/runs/'+proof.report.run_id)).snapshot).toBe(proof.report.snapshot);
 await report.getByRole('button',{name:proof.report.snapshot.slice(0,16)+' ↗',exact:true}).click();
 await expect(page.locator('.evidence pre')).toContainText('===== app.py =====');await expect(page.locator('.evidence pre')).toContainText('===== documents.py =====');
 await page.getByRole('button',{name:/提交报告/}).click();
 expect(await api('/reports/'+oldReport.id)).toEqual(oldReport);
 expect((await api('/author/generation/'+proof.instance)).review_digest).toBe(proof.approvalDigest);
 expect((await api('/generation/jobs/'+proof.instance)).request_count).toBe(original.generationRequests);
 proof.refreshRestored=true;proof.oldReportUnchanged=true;proof.assetsUnchanged=true;
 await page.screenshot({path:dir+'/approved-final-report.png',fullPage:true});
 console.log(JSON.stringify({report:proof.report.id,run:proof.report.run_id,snapshot:proof.report.snapshot,feedback:proof.report.feedback_status,refresh:true,oldReportUnchanged:true}));
}catch(error){proof.failure=String(error);await page.screenshot({path:dir+'/approved-finish-failure.png',fullPage:true}).catch(()=>{});throw error}
finally{proof.finished=new Date().toISOString();await writeFile(dir+'/approved-finish.json',JSON.stringify(proof,null,2));await browser.close()}
