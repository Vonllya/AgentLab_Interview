import {test,expect} from '@playwright/test';

test('工单冲突停止、作者证据及刷新恢复（离线接口夹具）',async({page})=>{
 const id='b'.repeat(32);
 const job={id,request:{requirement:'MOCK 工单冲突展示夹具，不代表真实生成'},status:'needs_manual_review',stage:'diagnosis',checkpoint:'diagnosis',mode:'mock',policy_version:'roles-v1',handoff_version:'repair-handoff-v1',request_count:4,attempts:[],contract_version:0,error:{category:'handoff_conflict',reason:'相同证据下再次出现冲突，已停止自动纠错'},budget:{policy:{requests:24},requests:4}};
 let posts=0;
 await page.route('**/api/generation/jobs/'+id,route=>route.fulfill({json:job}));
 await page.route('**/api/author/generation/'+id,route=>route.fulfill({json:{trust:'作者私有测试夹具',handoff_conflicts:[{id:'c'.repeat(32),kind:'constraint_conflict',matrix_id:'evidence-matrix',details:{pairs:[{left_ref:'保留冻结故障',right_ref:'通过回归',explanation:'同一输入不能同时包含与缺少相同诊断标记。'}]}}],candidate_history:[{stage:'build',status:'rejected',matrix_id:'evidence-matrix',asset:'candidate-test'}]}}));
 page.on('request',req=>{if(req.method()==='POST')posts++});
 await page.goto('/generate/'+id);
 await expect(page.getByRole('status').filter({hasText:'交接冲突待人工复核'})).toBeVisible();
 await page.getByRole('button',{name:'打开私有资产审核'}).click();
 await expect(page.getByText('自动纠错已停止。请核对冲突双方和已有证据；恢复前需要提供新的依据，不会自动重发模型请求。')).toBeVisible();
 await page.getByText('冲突 '+ 'c'.repeat(12)+' · constraint_conflict',{exact:true}).click();
 await expect(page.getByText('同一输入不能同时包含与缺少相同诊断标记。',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'审核通过并发布'})).toBeDisabled();
 await page.reload();await expect(page.getByRole('status').filter({hasText:'交接冲突待人工复核'})).toBeVisible();
 expect(posts).toBe(0);
});

test('构建错误分类及格式修复标识（离线接口夹具）',async({page})=>{
 const id='d'.repeat(32);
 await page.route('**/api/generation/jobs/'+id,route=>route.fulfill({json:{id,request:{requirement:'MOCK 格式错误展示'},status:'needs_manual_review',stage:'project_build',mode:'mock',policy_version:'roles-v1',request_count:3,contract_version:0,budget:{policy:{requests:24},requests:3},attempts:['json_syntax','schema_shape','asset_constraint'].map((failure_kind,i)=>({stage:'project_build',status:'failed',failure_kind,attempt:i+1,format_repair_of:i?'prior-response':null,format_repair_attempt:i}))}}));
 await page.goto('/generate/'+id);await page.getByText('阶段执行记录（3）',{exact:true}).click();
 for(const text of ['JSON语法错误','字段结构错误','资产约束不合格','原响应格式修复 1/2'])await expect(page.getByText(text,{exact:false}).first()).toBeVisible();
});

test('证据暂停分类和作者补充记录（离线夹具）',async({page})=>{
 const id='e'.repeat(32);
 await page.route('**/api/generation/jobs/'+id,route=>route.fulfill({json:{id,request:{requirement:'MOCK 证据补充'},status:'needs_manual_review',stage:'diagnosis',mode:'mock',policy_version:'roles-v1',contract_version:0,attempts:[],error:{category:'evidence_repeated',reason:'已经提供相关证据，重复请求已停止'}}}));
 await page.route('**/api/author/generation/'+id,route=>route.fulfill({json:{diagnostic_evidence:[{id:'evidence-12345678',binding:{matrix_id:'matrix-current',build_hash:'snapshot-fixed'},status:'completed',results:[{request:{kind:'file',question:'读取故障入口'},status:'available',trust:'代码不是通过证明',code:'<script>alert(1)</script>'}]}]}}));
 await page.goto('/generate/'+id);await expect(page.getByRole('status').filter({hasText:'诊断证据待复核'})).toBeVisible();
 await page.getByRole('button',{name:'打开私有资产审核'}).click();await page.getByText('补充证据 evidence-123 · completed',{exact:false}).click();
 await expect(page.getByText('代码不是通过证明',{exact:true})).toBeVisible();await page.getByText('证据详情',{exact:true}).click();
 await expect(page.getByText('<script>alert(1)</script>',{exact:false})).toBeVisible();
});

test('执行前覆盖失败不会显示代码工单冲突（离线夹具）',async({page})=>{
 const id='f'.repeat(32);
 await page.route('**/api/generation/jobs/'+id,route=>route.fulfill({json:{id,request:{requirement:'覆盖补全边界展示'},status:'needs_manual_review',stage:'evaluation',checkpoint:'evaluation',mode:'mock',policy_version:'roles-v1',contract_version:0,budget:{policy:{requests:24},requests:3},request_count:3,attempts:[{role:'评测 Agent',status:'failed',failure_kind:'coverage_incomplete',attempt:1,coverage_completion:true}],error:{category:'coverage_incomplete',reason:'执行前覆盖补全已尝试两次仍未通过；未执行Docker。'}}}));
 await page.goto('/generate/'+id);
 await expect(page.locator('strong[role=status]')).toHaveText('执行前覆盖待复核');
 await page.getByText('阶段执行记录（1）',{exact:true}).click();
 await expect(page.getByText('评测 Agent · 执行前覆盖不足 · 调用 #1',{exact:false})).toBeVisible();
 await expect(page.getByText('故障范围指导的覆盖补全（非盲测）',{exact:false})).toBeVisible();
 await expect(page.getByText('交接冲突待人工复核',{exact:true})).toHaveCount(0);
 await page.reload();await expect(page.locator('strong[role=status]')).toHaveText('执行前覆盖待复核');
});

test('规范局部补丁错误分类及刷新恢复（离线夹具）',async({page})=>{
 const id='a'.repeat(32);
 await page.route('**/api/generation/jobs/'+id,route=>route.fulfill({json:{id,request:{requirement:'规范补齐展示'},status:'needs_manual_review',stage:'project_build',checkpoint:'project_build',mode:'mock',policy_version:'roles-v1',contract_version:1,budget:{policy:{requests:24},requests:3},request_count:3,attempts:[{role:'构建 Agent',status:'failed',failure_kind:'spec_patch_invalid',attempt:1,specification_patch:true}],error:{category:'spec_patch_exhausted',reason:'规范补齐达到有界尝试上限，原资产不变'}}}));
 await page.goto('/generate/'+id);
 await expect(page.locator('strong[role=status]')).toHaveText('规范补齐待复核');
 await page.getByText('阶段执行记录（1）',{exact:true}).click();
 await expect(page.getByText('规范字段补丁不合格',{exact:false})).toBeVisible();
 await expect(page.getByText('局部规范补丁（冻结资产由程序保留）',{exact:false})).toBeVisible();
 await expect(page.getByText('执行前覆盖不足',{exact:false})).toHaveCount(0);
 await page.reload();await expect(page.locator('strong[role=status]')).toHaveText('规范补齐待复核');
});
