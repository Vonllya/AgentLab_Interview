// Opt-in real-provider verification. Requires the normal real-mode app to be running.
import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
if(process.env.AGENTLAB_REAL_SMOKE!=='1')throw Error('Set AGENTLAB_REAL_SMOKE=1 to allow real provider use');
const output='data/reliability-verification';await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.AGENTLAB_BROWSER_EXECUTABLE||'/tmp/agentlab-browser/chrome-linux64/chrome',headless:true});
const context=await browser.newContext({baseURL:'http://127.0.0.1:5173',permissions:['clipboard-read','clipboard-write']});
const page=await context.newPage();const proof={};
const api=async(path,method='GET',data)=>{const r=await context.request.fetch('/api'+path,{method,data,timeout:240000});expect(r.ok()).toBeTruthy();return r.json()};
try{
 const health=await api('/health');expect(health.agent_mode).toBe('real');expect(health.docker_available).toBe(true);
 const old=await api('/reports/7f561812a54a4f65860a7db41caadce8');
 const original=await api(`/sessions/${old.session}/snapshots/${old.snapshot}`);
 proof.original={id:old.id,run_id:old.run_id,snapshot:old.snapshot,status:old.feedback_status};
 await page.goto('/');await page.getByRole('button',{name:'开始训练 ↗'}).first().click();
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();
 const id=await page.evaluate(()=>localStorage.getItem('session'));proof.session=id;console.log('session',id);
 // First use a genuinely faulty saved workspace and real public execution.
 await page.getByRole('button',{name:'保存并运行公开测试'}).click();
 await expect(page.locator('.run').first().locator('.runhead .status')).toHaveText('失败',{timeout:120000});
 proof.publicRun=(await api('/sessions/'+id)).runs[0];
 expect(proof.publicRun.checks.some(c=>c.id==='modification-scope'&&c.status==='passed')).toBe(true);
 expect(proof.publicRun.checks.some(c=>c.group==='target'&&c.status==='failed')).toBe(true);
 const prompt='请检查当前保存的代码和最近公开测试，简短回答：范围检查通过是否说明重排与过滤没有问题？另一个假设场景：仅执行了两个候选的完整重排样例，没有任何过滤样例，能否排除过滤问题？两个行为等价且都符合约束的正确实现，是否需要用测试区分它们？请引用证据，不提供修复代码。';
 await page.getByLabel('给 Agent 的消息').fill(prompt);
 const chatResponse=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST',{timeout:240000});
 await page.getByRole('button',{name:'发送',exact:true}).click();proof.reply=await (await chatResponse).json();
 expect(proof.reply.mode).toBe('real');expect(proof.reply.status).not.toBe('error');
 expect(proof.reply.content).not.toMatch(/Mock|本轮工具预算已耗尽|已拦截/);
 proof.tools=(await api('/sessions/'+id)).events.filter(e=>e.role==='tool');
 expect(proof.tools.some(e=>['get_run_result','get_session_evidence'].includes(e.name)&&e.status==='ok')).toBe(true);
 await page.screenshot({path:output+'/real-evidence-reply.png',fullPage:true});
 console.log('reply_ready_for_semantic_review',proof.reply.id);
 // Restore the original failed report's submitted bytes, diagnosis and hint count.
 // This is a new submission; the historical report remains untouched.
 await page.evaluate(text=>navigator.clipboard.writeText(text),original.code);
 await page.locator('.monaco-editor textarea').first().focus();await page.keyboard.press('Control+A');await page.keyboard.press('Control+V');
 await page.getByLabel('诊断说明').fill(old.diagnosis);
 await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
 expect((await api('/sessions/'+id)).code).toBe(original.code);
 for(let level=1;level<=old.objective.hints.length;level++){
  await page.getByRole('button',{name:`请求提示 · ${level}/3`}).click();await expect(page.getByText(new RegExp(`提示 ${level}/3：`))).toBeVisible();
 }
 await page.getByRole('button',{name:'保存并提交评测'}).click();await expect(page.locator('.report')).toBeVisible({timeout:120000});
 await expect.poll(async()=>((await api('/sessions/'+id)).reports[0]?.feedback_status),{timeout:100000,intervals:[1000]}).not.toBe('generating');
 proof.report=(await api('/sessions/'+id)).reports[0];
 console.log('report_result',JSON.stringify({id:proof.report.id,status:proof.report.feedback_status,error:proof.report.feedback_error,attempts:proof.report.feedback_attempts}));
 expect(proof.report.feedback_status).toBe('generated');expect(proof.report.feedback).not.toMatch(/已拦截|模型未返回/);
 expect(proof.report.feedback.length).toBeGreaterThan(20);expect(proof.report.feedback.length).toBeLessThan(650);
 expect(proof.report.snapshot).toBe(old.snapshot);expect(proof.report.run_id).not.toBe(old.run_id);
 expect(proof.report.objective.hints).toHaveLength(old.objective.hints.length);expect(proof.report.diagnosis).toBe(old.diagnosis);
 await page.reload();await page.getByRole('button',{name:/提交报告/}).click();
 await expect(page.getByText('模型反馈 · 已生成',{exact:true})).toBeVisible();await expect(page.locator('.report .markdown')).toBeVisible();
 expect(await api('/reports/'+proof.report.id)).toEqual(proof.report);expect(await api('/reports/'+old.id)).toEqual(old);
 proof.refreshRestored=true;proof.historicalUnchanged=true;
 await page.screenshot({path:output+'/real-report.png',fullPage:true});console.log('real_report_refresh_passed');
}catch(error){proof.failure=String(error);await page.screenshot({path:output+'/live-failure.png',fullPage:true});throw error;}
finally{await writeFile(output+'/live.json',JSON.stringify(proof,null,2));await browser.close();}
