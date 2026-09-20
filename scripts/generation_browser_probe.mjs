// Explicit opt-in real provider flow. Publication additionally requires a human review note/digest.
import {chromium,expect} from '../frontend/node_modules/@playwright/test/index.mjs';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
if(process.env.AGENTLAB_REAL_SMOKE!=='1')throw Error('Requires AGENTLAB_REAL_SMOKE=1');
const action=process.argv[2]||'create';
const output='data/v02-verification';await mkdir(output,{recursive:true});
let proof={};try{proof=JSON.parse(await readFile(output+'/permission-browser.json','utf8'))}catch{}
const browser=await chromium.launch({executablePath:process.env.AGENTLAB_BROWSER_EXECUTABLE||'/tmp/agentlab-browser/chrome-linux64/chrome'});
const context=await browser.newContext({baseURL:'http://127.0.0.1:5173',permissions:['clipboard-read','clipboard-write']});
const page=await context.newPage();
const api=async path=>{const r=await context.request.get('/api'+path);expect(r.ok()).toBeTruthy();return r.json()};
async function settled(){
 for(let i=0;i<330;i++){
  const job=await api('/generation/jobs/'+proof.job);proof.latest=job;
  if(!['analyzing','building','evaluating','validating','teaching'].includes(job.status))return job;
  await page.waitForTimeout(2000);
 }
 throw Error('Generation wait exceeded 660s; server state retained');
}
try{
 const health=await api('/health');expect(health.agent_mode).toBe('real');expect(health.docker_available).toBe(true);
 if(action==='create'){
  await page.goto('/generate');
  await page.getByLabel('训练需求').fill('训练 Agent 工具授权边界：不可信检索文档中伪装的授权信息错误地扩大了工具权限。原创小型多模块纯 Python 模拟，用明确的来源字段和本地操作记录验证授权，不调用远程模型或业务接口。建议一次输入包含 trusted_allowed 工具名列表、documents（文档自称允许的工具列表）和 requests 工具名列表；输出每条请求是否允许以及实际执行工具名列表。仅可信授权可以决定执行，保留可信授权正常调用。一个主要故障，使用两三个简短模块；不考真实模型抵御提示注入的能力。');
  await page.getByRole('button',{name:'开始需求分析（调用模型）',exact:true}).click();
  await expect(page).toHaveURL(/\/generate\/[a-f0-9]{32}$/);
  proof={job:new URL(page.url()).pathname.split('/').pop(),createdInBrowser:true};
  await settled();
 }else{
  if(!proof.job)throw Error('No browser-created job');
  await page.goto('/generate/'+proof.job);
  if(action==='refine'){
   const job=await api('/generation/jobs/'+proof.job);
   const behaviors={...job.contract.behaviors};
   delete behaviors.no_remote_calls;
   behaviors.per_request_decision='按 requests 的原始顺序逐条输出 decision（保留重复请求）：tool 为原工具名；授权时 allowed=true 且 reason=trusted_allowed，拒绝时 allowed=false 且 reason=not_authorized。reason 为上述精确字符串。';
   behaviors.executed_reflects_allowed='executed 仅含可信授权内的工具名；每个工具最多记录一次，顺序为 requests 中第一次出现的顺序。重复请求仍各有 decision，但不重复 executed。';
   await page.getByLabel('契约行为').fill(Object.entries(behaviors).map(([k,v])=>k+': '+v).join('\n'));
   await page.getByRole('button',{name:'保存为新契约版本'}).click();
   await expect.poll(async()=>(await api('/generation/jobs/'+proof.job)).contract_version).toBe(job.contract_version+1);
   proof.latest=await api('/generation/jobs/'+proof.job);proof.contractClarifiedInBrowser=true;
  }else if(action==='confirm'){
   await page.getByLabel('我确认上述模拟范围；不将其当作真实外部系统验证').check();
   await page.getByRole('button',{name:'确认契约并生成项目（调用模型）'}).click();
   await expect.poll(async()=>(await api('/generation/jobs/'+proof.job)).confirmed_version).not.toBeNull();
   await settled();
  }else if(action==='repair-evaluation'){
   await page.getByRole('button',{name:'打开私有资产审核'}).click();
   await page.getByLabel('评测问题依据').fill('公开症状是不可信文档声明未授权工具时错误执行。trusted-superset-order 标为 regression，但它的 z_tool 仅由文档声明且出现在 requests 中，正是症状触发条件，分类矛盾。正常 regression 应不包含该故障触发；独立 target 保留越权拒绝期望，不放宽正常契约。请仅根据公开契约重新生成一致分类和期望，不能根据实现调整答案。');
   await page.getByRole('button',{name:'修复评测（调用模型，审核指导，重新验证）'}).click();
   await page.waitForTimeout(1000);await settled();
  }else if(action==='retry'){
   await page.getByRole('button',{name:'重新生成（消耗Token）'}).click();
   await page.waitForTimeout(1000);await settled();
  }else if(action==='inspect'){
   await page.reload();
   await expect(page.locator('.generation strong[role=status]')).toHaveText('等待作者审核');
   proof.latest=await api('/generation/jobs/'+proof.job);
   expect(proof.latest.matrix.passed).toBe(true);proof.generationRefreshRestored=true;
  }else if(action==='publish'){
   if(!process.env.AGENTLAB_HUMAN_REVIEW_NOTE||!process.env.AGENTLAB_REVIEW_DIGEST)throw Error('Human review note and exact digest required');
   const review=await api('/author/generation/'+proof.job);
   expect(review.review_digest).toBe(process.env.AGENTLAB_REVIEW_DIGEST);
   await page.getByRole('button',{name:'打开私有资产审核'}).click();
   await page.getByText('契约、全部实现、独立检查与教学材料',{exact:true}).click();
   await page.getByLabel('审核依据').fill(process.env.AGENTLAB_HUMAN_REVIEW_NOTE);
   await page.getByLabel('我已审核当前资产及验证证据，确认可以发布').check();
   await page.getByRole('button',{name:'审核通过并发布'}).click();
   await expect(page.getByRole('heading',{name:/已冻结发布/})).toBeVisible();
   proof.publication=await api('/generation/jobs/'+proof.job);
   await page.getByRole('button',{name:'开始训练',exact:true}).click();
   await expect(page).toHaveURL(/\/training\/[a-f0-9]{32}$/);
   proof.session=new URL(page.url()).pathname.split('/').pop();
   await expect(page.getByText('任务说明',{exact:true})).toBeVisible();
   for(const [file,code] of Object.entries(review.assets.build.reference)){
    await page.getByRole('button',{name:'打开文件 '+file,exact:true}).click();
    await page.evaluate(text=>navigator.clipboard.writeText(text),String(code));
    await page.locator('.monaco-editor textarea').first().focus();await page.keyboard.press('Control+A');await page.keyboard.press('Control+V');
   }
   await page.getByLabel('诊断说明').fill('验收使用已审核参考版本；权限应仅由可信授权决定，文档自述不是授权证据。验证正常调用及未授权请求拒绝。此过程不作为独立掌握能力证明。');
   await page.getByRole('button',{name:'保存',exact:true}).click();
   await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
   await page.getByRole('button',{name:'保存并运行公开测试'}).click();
   await expect(page.locator('.run').first().locator('.runhead .status')).toHaveText('通过',{timeout:120000});
   await page.getByRole('button',{name:'请求提示 · 1/3'}).click();
   await expect(page.getByText(/提示 1\/3：/)).toBeVisible();
   await page.getByRole('button',{name:'保存并提交评测'}).click();
   await expect(page.locator('.report .runhead .status')).toHaveText('通过',{timeout:120000});
   await expect.poll(async()=>(await api('/sessions/'+proof.session)).reports[0]?.feedback_status,{timeout:110000}).not.toBe('generating');
   const state=await api('/sessions/'+proof.session);proof.report=state.reports[0];
   expect(proof.report.snapshot).toBe(proof.report.objective.snapshot);
   expect(proof.report.objective.hints).toHaveLength(1);
   await page.reload();await page.getByRole('button',{name:/提交报告/}).click();
   await expect(page.locator('.report .runhead .status')).toHaveText('通过');
   expect((await api('/sessions/'+proof.session)).reports[0]).toEqual(proof.report);proof.refreshRestored=true;
  }else throw Error('Unknown action');
 }
 await page.screenshot({path:output+'/permission-'+action+'.png',fullPage:true});
 console.log(JSON.stringify({job:proof.job,status:proof.latest?.status,error:proof.latest?.error,report:proof.report?.id,refreshRestored:proof.refreshRestored}));
}catch(error){proof.failure=String(error);throw error}
finally{await writeFile(output+'/permission-browser.json',JSON.stringify(proof,null,2));await browser.close()}
