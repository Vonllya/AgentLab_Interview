import {test,expect} from '@playwright/test';
test('创建、编辑草稿、保存、提示、mock 对话、刷新恢复',async({page})=>{
 await page.goto('/');
 await expect(page.getByText('MOCK · 确定性辅导')).toBeVisible();
 await page.getByRole('button',{name:'开始训练 ↗'}).first().click();
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();
 const editor=page.locator('.monaco-editor textarea').first();await editor.focus();await page.keyboard.press('ControlOrMeta+End');await page.keyboard.insertText('\n# browser-save-proof');
 await page.getByLabel('诊断说明').fill('根据测试证据定位，继续检查边界。');
 await expect(page.getByText('● 有未保存修改（草稿已本地保留）')).toBeVisible();
 await page.reload();
 await expect(page.getByLabel('诊断说明')).toHaveValue('根据测试证据定位，继续检查边界。');
 await page.getByRole('button',{name:'保存',exact:true}).click();
 await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
 await expect(page.locator('.view-lines')).toContainText('# browser-save-proof');
 await page.getByRole('button',{name:'请求提示 · 1/3'}).click();
 await expect(page.getByText(/提示 1\/3：/)).toBeVisible();
 await page.getByLabel('给 Agent 的消息').fill('请检查证据');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 await expect(page.getByText(/【Mock 确定性模式】/)).toBeVisible();
 await page.reload();
 await expect(page.getByText(/提示 1\/3：/)).toBeVisible();
 await expect(page.getByLabel('诊断说明')).toHaveValue('根据测试证据定位，继续检查边界。');
 await page.getByRole('button',{name:'请求提示 · 2/3'}).click();
 await expect(page.getByText(/提示 2\/3：/)).toBeVisible();
 await page.getByRole('button',{name:'请求提示 · 3/3'}).click();
 await expect(page.getByRole('button',{name:'已获取全部提示'})).toBeDisabled();
 await page.reload();await expect(page.getByRole('button',{name:'已获取全部提示'})).toBeDisabled();
 await page.screenshot({path:'test-results/workspace.png',fullPage:true});
});
test('真实 Docker 提交报告闭环',async({page,request},testInfo)=>{
 test.setTimeout(240000);
 const health=await (await request.get('/api/health')).json();test.skip(!health.docker_available,'Docker 不可用，禁止宿主降级');
 await page.goto('/');
 await page.locator('.cards article').filter({has:page.getByRole('heading',{name:'RAG 重排后的引用错位'})}).getByRole('button',{name:'开始训练 ↗'}).click();
 await expect(page.getByText('任务说明',{exact:true})).toBeVisible();
 const sessionId=await page.evaluate(()=>localStorage.getItem('session'));
 const reference='def answer(documents, order):\n    return [{"text": documents[i]["text"], "citation": documents[i]["id"]} for i in order]\n\ndef scenario(data):\n    return answer(data["documents"], data["order"])\n';
 async function edit(code:string){
  await page.context().grantPermissions(['clipboard-read','clipboard-write']);
  await page.evaluate(text=>navigator.clipboard.writeText(text),code);
  await page.locator('.monaco-editor textarea').first().focus();
  await page.keyboard.press('ControlOrMeta+A');await page.keyboard.press('ControlOrMeta+V');
 }
 await edit(reference);
 await page.getByLabel('诊断说明').fill('引用随选中的文档流转；验证重排、过滤与空集。');
 await page.getByRole('button',{name:'保存',exact:true}).click();
 await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
 expect((await (await request.get(`/api/sessions/${sessionId}`)).json()).code).toBe(reference);
 const publicResponse=page.waitForResponse(r=>r.url().endsWith(`/sessions/${sessionId}/runs`)&&r.request().method()==='POST');
 await page.getByRole('button',{name:'保存并运行公开测试'}).click();
 const publicRun=await (await publicResponse).json();
 await expect(page.locator('.run').first().locator('.runhead .status')).toHaveText('通过',{timeout:120000});
 await page.getByRole('button',{name:'请求提示 · 1/3'}).click();
 await expect(page.getByText(/提示 1\/3：/)).toBeVisible();
 // New revision after a passing public run: the report must never reuse old evidence.
 const submittedCode=reference+'\n# submission revision B\n';
 await edit(submittedCode);
 await page.getByRole('button',{name:'保存',exact:true}).click();
 await expect(page.getByText('✓ 已保存',{exact:true})).toBeVisible();
 expect((await (await request.get(`/api/sessions/${sessionId}`)).json()).code).toBe(submittedCode);
 const submitResponse=page.waitForResponse(r=>r.url().endsWith(`/sessions/${sessionId}/submit`)&&r.request().method()==='POST');
 await page.getByRole('button',{name:'保存并提交评测'}).click();
 const submission=await (await submitResponse).json();
 expect(submission.id).not.toBe(publicRun.id);
 expect(submission.snapshot).not.toBe(publicRun.snapshot);
 await expect(page.locator('.report')).toBeVisible({timeout:120000});
 await expect(page.locator('.report .runhead .status')).toHaveText('通过');
 const saved=await (await request.get(`/api/sessions/${sessionId}`)).json();
 const report=saved.reports[0];
 expect(report.run_id).toBe(submission.id);
 expect(report.snapshot).toBe(submission.snapshot);
 expect(report.objective.snapshot).toBe(submission.snapshot);
 expect(report.objective.checks.some((c:{visibility:string})=>c.visibility==='hidden')).toBeTruthy();
 expect(report.objective.hints[0].level).toBe(1);
 const snapshot=await (await request.get(`/api/sessions/${sessionId}/snapshots/${submission.snapshot}`)).json();
 expect(snapshot.code).toBe(submittedCode);
 await page.reload();await page.getByRole('button',{name:/提交报告/}).click();
 await expect(page.locator('.report')).toBeVisible();
 await expect(page.locator('.report .runhead .status')).toHaveText('通过');
 const restored=await (await request.get(`/api/sessions/${sessionId}`)).json();
 expect(restored.reports[0].id).toBe(report.id);expect(restored.code).toBe(submittedCode);
 await testInfo.attach('submission-evidence',{body:JSON.stringify({publicRun,submission,report,snapshot},null,2),contentType:'application/json'});
 await page.screenshot({path:testInfo.outputPath('submission-report.png'),fullPage:true});
});

// UI regression only: explicitly injected report states, not provider verification.
test('模型反馈生成中和失败时仍显示客观结果',async({page,request})=>{
 const session=await (await request.post('/api/sessions',{data:{task_id:'rag'}})).json();
 let status='generating';
 await page.route(`**/api/sessions/${session.id}`,async route=>{
  const response=await route.fetch();const body=await response.json();
  body.reports=[{id:'ui-report',run_id:'ui-run',snapshot:'ui-snapshot',diagnosis:'',feedback:'',feedback_status:status,feedback_error:{category:'output_limit',reason:'模型输出预算耗尽，未生成完整反馈'},objective:{id:'ui-run',snapshot:'ui-snapshot',kind:'submission',status:'passed',duration:1,exit_code:0,output:'客观检查已保存',checks:[],hints:[]}}];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');await page.evaluate(id=>localStorage.setItem('session',id),session.id);await page.reload();
 await page.getByRole('button',{name:/提交报告/}).click();
 await expect(page.getByText('模型反馈 · 生成中',{exact:true})).toBeVisible();
 await expect(page.locator('.report .runhead .status')).toHaveText('通过');
 status='failed';
 await expect(page.locator('.report [role="alert"]')).toContainText('output_limit',{timeout:10000});
 await expect(page.getByText('模型反馈 · 生成失败',{exact:true})).toBeVisible();
 await expect(page.locator('.report .runhead .status')).toHaveText('通过');
});

// Rendering checks use explicit fixture content; not a model quality test.
test('工具默认折叠且 Markdown 安全渲染和定位',async({page,request})=>{
 const session=await (await request.post('/api/sessions',{data:{task_id:'rag'}})).json();
 const evidence='abcdef0123456789abcdef0123456789';
 await page.route(`**/api/sessions/${session.id}`,async route=>{
  const response=await route.fetch();const body=await response.json();
  body.events=[{id:evidence,role:'tool',name:'get_run_result',status:'ok',summary:'范围通过；行为失败',content:'{"status":"failed","detail":"<img src=x onerror=alert(1)>"}'},
   {id:'reply',role:'assistant',content:`**范围检查**不能证明功能正确。\n\n- 需要行为证据。\n- [查看证据](#${evidence})\n\n<script>window.pwned=1</script>\n\n[危险链接](javascript:alert(1))\n\n![远程图片](https://invalid.example/tracker)`}];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');await page.evaluate(id=>localStorage.setItem('session',id),session.id);await page.reload();
 const tool=page.locator(`details[id="${evidence}"]`);
 await expect(tool).not.toHaveAttribute('open');await expect(tool.locator('pre')).not.toBeVisible();
 await expect(tool.locator('summary')).toContainText('完成');await expect(tool.locator('summary')).toContainText('范围通过；行为失败');
 await expect(page.locator('.bubble.assistant strong')).toHaveText('范围检查');
 await expect(page.locator('.bubble.assistant li')).toHaveCount(2);
 expect(await page.evaluate(()=>Reflect.get(window,'pwned'))).toBeUndefined();
 await expect(page.locator('.markdown img,.markdown script,.markdown a[href^="javascript:"]')).toHaveCount(0);
 await page.getByRole('link',{name:'查看证据'}).click();await expect(tool).toHaveAttribute('open');
 await expect(tool.locator('pre')).toContainText('<img src=x onerror=alert(1)>');
 await expect(tool).toContainText(evidence);await expect(tool.locator('img')).toHaveCount(0);
});
