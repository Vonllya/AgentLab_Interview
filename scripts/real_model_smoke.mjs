// Opt-in integration against an already running, real-mode local application.
// Does not load or print model credentials. Creates a new training session.
import {chromium, expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
if(process.env.AGENTLAB_REAL_SMOKE!=='1')throw Error('Set AGENTLAB_REAL_SMOKE=1 to authorize real provider requests');
const output='data/model-verification';await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.AGENTLAB_BROWSER_EXECUTABLE||'/tmp/agentlab-browser/chrome-linux64/chrome',headless:true});
const context=await browser.newContext({baseURL:'http://127.0.0.1:5173',permissions:['clipboard-read','clipboard-write']});
const page=await context.newPage();
const api=async(path,method='GET',data)=>{const res=await context.request.fetch('/api'+path,{method,data,timeout:240000});expect(res.ok()).toBeTruthy();return res.json()};
const proof={};
try{
 const health=await api('/health');expect(health.agent_mode).toBe('real');expect(health.docker_available).toBe(true);
 await page.goto('/');await expect(page.getByText('真实模型模式',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'开始训练 ↗'}).first().click();
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();
 const id=await page.evaluate(()=>localStorage.getItem('session'));proof.session=id;console.log('session',id);
 const code='def answer(documents, order):\n    return [{"text": documents[i]["text"], "citation": documents[i]["id"]} for i in order]\n\ndef scenario(data):\n    return answer(data["documents"], data["order"])\n';
 async function edit(value){await page.evaluate(text=>navigator.clipboard.writeText(text),value);await page.locator('.monaco-editor textarea').first().focus();await page.keyboard.press('Control+A');await page.keyboard.press('Control+V');}
 await edit(code);await page.getByLabel('诊断说明').fill('引用随选中文档流转，保留重排与过滤；已验证公开场景，还需确认不同候选数量和空集回归。');
 await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
 expect((await api('/sessions/'+id)).code).toBe(code);
 await page.getByRole('button',{name:'保存并运行公开测试'}).click();
 await expect(page.locator('.run').first().locator('.runhead .status')).toHaveText('通过',{timeout:120000});
 proof.publicRun=(await api('/sessions/'+id)).runs[0];
 const prompt='请检查我当前保存的代码和最近测试结果，指出还有什么需要验证，不要直接提供完整修复代码。';
 await page.getByLabel('给 Agent 的消息').fill(prompt);
 const response=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST',{timeout:240000});
 await page.getByRole('button',{name:'发送',exact:true}).click();proof.reply=await (await response).json();
 expect(proof.reply.mode).toBe('real');expect(proof.reply.status).not.toBe('error');
 expect(proof.reply.content).not.toMatch(/Mock|预算已耗尽|已拦截|模型未返回/);
 let saved=await api('/sessions/'+id);proof.tools=saved.events.filter(e=>e.role==='tool');
 expect(proof.tools.some(e=>e.name==='read_workspace_file'&&e.status==='ok')).toBe(true);
 expect(proof.tools.some(e=>['get_session_evidence','get_run_result'].includes(e.name)&&e.status==='ok')).toBe(true);
 expect(proof.tools.some(e=>proof.reply.content.includes(e.id))||proof.reply.content.includes(proof.publicRun.id)).toBe(true);
 expect(saved.hints).toHaveLength(0);console.log('real_chat_tools_and_reply_passed',proof.tools.map(e=>e.name));
 await page.getByRole('button',{name:'请求提示 · 1/3'}).click();await expect(page.getByText(/提示 1\/3：/)).toBeVisible();
 const submitted=code+'\n# live submission revision\n';await edit(submitted);await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'保存并提交评测'}).click();
 await expect(page.locator('.report')).toBeVisible({timeout:120000});
 await expect(page.getByText('模型反馈 · 生成中',{exact:true})).toBeVisible();proof.sawGenerating=true;
 await expect(page.locator('.report .runhead .status')).toHaveText('通过');
 await expect.poll(async()=>{const rs=(await api('/sessions/'+id)).reports;return rs[0]?.feedback_status},{timeout:180000,intervals:[2000]}).not.toBe('generating');
 saved=await api('/sessions/'+id);proof.report=saved.reports[0];
 console.log('report_status',proof.report.feedback_status,proof.report.feedback_error||'',proof.report.feedback_model||{});
 expect(proof.report.feedback_status).toBe('generated');expect(proof.report.feedback.length).toBeGreaterThan(30);expect(proof.report.feedback).not.toMatch(/已拦截|模型未返回/);
 expect(proof.report.feedback).toContain(proof.report.run_id);
 expect(proof.report.snapshot).not.toBe(proof.publicRun.snapshot);expect(proof.report.run_id).not.toBe(proof.publicRun.id);
 expect(proof.report.objective.snapshot).toBe(proof.report.snapshot);expect(proof.report.objective.hints).toHaveLength(1);
 expect((await api(`/sessions/${id}/snapshots/${proof.report.snapshot}`)).code).toBe(submitted);
 await page.getByRole('button',{name:'请求提示 · 2/3'}).click();await expect(page.getByText(/提示 2\/3：/)).toBeVisible();
 await page.getByRole('button',{name:'请求提示 · 3/3'}).click();await expect(page.getByRole('button',{name:'已获取全部提示'})).toBeDisabled();
 saved=await api('/sessions/'+id);const eventCount=saved.events.length;
 for(let i=0;i<2;i++){const reject=await context.request.post(`/api/sessions/${id}/hint`);expect(reject.status()).toBe(400);expect((await reject.json()).detail).toBe('已获取全部提示');}
 saved=await api('/sessions/'+id);expect(saved.events.length).toBe(eventCount);expect(saved.hints).toHaveLength(3);expect(saved.reports[0]).toEqual(proof.report);
 await page.reload();await page.getByRole('button',{name:/提交报告/}).click();
 await expect(page.getByText('模型反馈 · 已生成',{exact:true})).toBeVisible();await expect(page.locator('.report .prose')).toHaveText(proof.report.feedback);
 await expect(page.getByRole('button',{name:'已获取全部提示'})).toBeDisabled();expect((await api('/reports/'+proof.report.id))).toEqual(proof.report);
 proof.refreshRestored=true;proof.hintCap=true;
 await page.screenshot({path:output+'/real-report.png',fullPage:true});console.log('real_report_refresh_hint_cap_passed',proof.report.id);
}catch(error){proof.failure=String(error);await page.screenshot({path:output+'/failure.png',fullPage:true});throw error;}
finally{await writeFile(output+'/live.json',JSON.stringify(proof,null,2));await browser.close();}
