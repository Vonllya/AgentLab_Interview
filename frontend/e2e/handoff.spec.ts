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
