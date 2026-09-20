# 实际验证记录

## 2026-09-18 多 Agent 修改方案与按钮文案

新增 `docs/MULTI_AGENT_GENERATION_PLAN.md`，包含独立角色、错误诊断、自动修复路由、统一预算、恢复与幂等、具体文件/API修改及验收。此文档是待实施方案，不代表后台多 Agent/自动循环已实现。

按钮与已有浏览器探针定位名称改为“重新生成（消耗Token）”，仍调用旧retry，title提示沿用当前预算、耗尽不自动追加。未触发生成，没有调用供应商，也没有改动已发布资产、训练记录或两类失败任务。

实际执行 `npm --prefix frontend run build`：TypeScript及Vite构建通过，5.27秒，保留原Monaco大包警告；`node --check scripts/generation_browser_probe.mjs`、`git diff --check`均通过。未运行新的多Agent行为或浏览器验收，不将方案描述计作功能通过。

## 2026-09-17 固定资产获人工批准后的真实发布与训练闭环

**本轮完成：通过正常作者页面发布，经题库新建训练，执行故障代码、编辑并保存多文件参考修复、真实模型工具对话、提交真实反馈、刷新与快照核对。自动化使用参考修复，仅作为系统功能验证，不作为真实用户学习效果证据。**

### 批准和资产不变性

用户阅读作者审核摘要后明确批准实例 `81a3a18745ed4eaba0813d8b3f6d99b4`、契约v2、矩阵 `a2415e5ba601438297af5d1fd32ed2d1`、审核摘要 `1bc32e924954166a81386b76a7f66dceda9b61469d0da06baca1ca7ad8b4c3c1`。批准仅覆盖本地内部试用的纯Python模拟授权决策与记录；接受公开接口约定，不证明真实工具副作用、身份认证或真实模型提示注入防御。

发布前重新从契约、构建、评测、教学和矩阵计算摘要，与批准值相同；发布后再次核对摘要及冻结包18个文件哈希。题面、提示、规避命名和45分钟估计未变，留作后续版本事项。任务发布为 `gen_81a3a18745ed4eaba0813d8b3f6d99b4@1.0.0`，生成请求仍为5次，没有重新生成。作者审核备注记录的是用户明确批准，不把AI复核当人工批准。

### 实际流程与证据

| 项目 | 实际结果 |
| --- | --- |
| 题库及详情 | 真实生成任务可见，版本1.0.0；由题库点击创建会话 `da9289d9c1e94273806c3f7d6b2d1539`，不是作者快捷入口 |
| 私有资产边界 | 训练文件仅 solution.py/app.py/authz.py/documents.py；公开测试仅public且无faulty_expected；文件接口拒绝隐藏测试、参考目录、路径穿越及绝对路径请求；未把作者资产传入辅导上下文 |
| 故障公开执行 | `e9496cdd1f564eb89f2caf8195a603b6`，2.719秒，退出1；trusted-only-basic失败，3个正常回归通过，无运行错误；故障快照 `665731f467261580bcc01e68884dc4e9d6cc7b0fab4952f29ba44defa1842214` |
| 多文件修复 | 浏览4文件、通过编辑器写入参考版本并保存全部；app.py/documents.py发生变化，authz.py保持同一逻辑；保存后的文件逐一比较正确 |
| 修复公开执行 | `8e2ab2348e414b2f8893fbba037dfcc8`，2.927秒，退出0；4个公开行为检查及范围检查通过 |
| 真实训练对话 | 第一轮真实调用read_workspace_file两次、get_run_result一次，解释故障公开反例；第二轮读取通过证据及diff，区分前后快照与范围检查；调用/返回/后续回复均真实持久化 |
| 提示 | 实际请求L1一次；两次提交报告均保留该次提交的同一提示记录 |
| 最终提交 | `ac15c0e2c3644628a5b3ca7e01a844f2`，5.181秒，退出0；8个公开/隐藏行为检查及范围检查通过；独立于先前公开运行 |
| 最终报告 | `f319bd8af6ed4e38b26000f4019484fd`，反馈generated；模型 `deepseek-v4-flash`，首轮预算1200，finish_reason=stop，实际usage={"prompt_tokens": 1621, "completion_tokens": 176, "total_tokens": 1797, "reasoning_tokens": null} |
| 快照和恢复 | 最终报告、提交执行和修复公开执行均绑定 `3ad296a1df9ae704ee711fe3d059aae30a0975a3b7ad0d7bdf6cf912195452a7`；页面刷新恢复版本、报告与执行；点击快照显示全部提交文件；旧故障快照不同 |

报告深链接：`http://127.0.0.1:5173/training/da9289d9c1e94273806c3f7d6b2d1539?view=reports#f319bd8af6ed4e38b26000f4019484fd`。

### 实际失败、修复与语义复核

- 第一条浏览器脚本没有全程成功：发布、真实故障/修复执行、对话和反馈已完成，但刷新后过早操作报告标签，初始化恢复测试标签导致快照按钮detached/超时。后续使用报告深链接并等待初始化，正常点击查看快照，未用强制点击掩盖问题。原失败保留 `approved-flow.json`；继续流程结果为 `approved-finish.json`。
- 第一份报告 `d8393149001941dabd19dcb4f739c1bd` 的供应商正文真实返回，但把已通过的提交执行描述为故障暴露证据，不能计为准确反馈；聊天还机械引用RAG范围说明。定位到平台反馈输入未强调用户历史陈述与本次执行的来源区别，范围说明也未按任务区分。
- 仅修改平台 evidence/反馈提示：明确本次执行状态及证据范围，历史诊断是用户陈述、不能嫁接到通过执行；非RAG任务使用通用功能边界。没有改变报告预算、重试机制或任务资产。原报告完整保留，在同一代码快照上创建新提交与新报告。
- 对最后真实回复进行AI语义复核（不是另一次人工批准）：能正确引用通过执行、区分历史故障与当前快照、指出仅模拟决策、参考修复不代表独立学习。最终反馈没有再把通过执行说成故障反例。单次改善不证明模型反馈已普遍可靠。

### 实际命令

```bash
curl --max-time 8 -s http://127.0.0.1:8000/api/health
docker info --format '{{.ServerVersion}}'
node --check scripts/approved_generation_flow.mjs
AGENTLAB_REAL_SMOKE=1 node scripts/approved_generation_flow.mjs
.venv/bin/python -m pytest tests/test_report_reliability.py tests/test_model_feedback.py -q -o junit_family=xunit1 --junitxml=data/v02-verification/approved-feedback-regression.xml
node --check scripts/approved_generation_finish.mjs
AGENTLAB_REAL_SMOKE=1 node scripts/approved_generation_finish.mjs
.venv/bin/python -m pytest tests/test_platform.py tests/test_model_feedback.py tests/test_report_reliability.py -q -o junit_family=xunit1 --junitxml=data/v02-verification/approved-platform-regression.xml
```

Docker 29.8.0就绪，服务真实模型模式；首组回归26通过、0跳过，3.77秒；最终平台/模型/报告回归46通过、0跳过，7.09秒（两组重叠，不相加计数）。最终 `docker ps -a --filter label=agentlab=true --format '{{.Names}} {{.Status}}'` 无输出，无残留任务容器；`git diff --check` 和两个浏览器脚本语法检查通过。本轮未重跑全部acceptance，不把此前109项冒充本轮重新执行。完整性复核见 `approved-publication-preflight.json` 和 `approved-final-integrity.json`；前后两类失败任务的持久化记录哈希相同，没有为本次闭环强行改为成功。

### 另外两类失败仍保留

工具副作用：构建生成器的“故障版”在合法重试范围内实际去重，故障触发门禁正确拦截；同时独立测试缺少“不同操作相同收件人”，没识别按收件人去重。属于构建错误加覆盖不足，不是Docker故障。工作流：原契约跨调用状态设计错误、一次构建JSON无效；最终的所谓规避与参考行为等价，属于生成器错误分类，不能强迫测试区分正确实现。两者仍failed且未发布，门禁未降低。


## 2026-09-17 前轮 V0.2 生成与导航验收（当时待人工审核，保留历史）

### 实现和实际修复

新增三个真实路由板块、独立上下文生成、结构化资产校验、Docker 验证矩阵、作者审核、冻结发布与版本关联。保留四道旧题、提示上限和提交时报告快照。未新增 CI 或个人工程项目导入。

实际发现并修复：发布循环变量覆盖任务版本造成查找 `reference/manifest.json`；浏览器用例在路由完成前读取 session 导致取到旧值；真实契约使用不支持的 schema 关键字及大写行为 ID，现将明确限制写入生成 schema/指令；工作流最初依赖跨调用状态，已显式重新设计契约 v2；重试错误提示保留旧错误，已改用当前失败；已完成阶段的恢复在 error 为 null 时异常，已修复并加入回归。生成镜像按已验证本地 digest 固定，禁自动拉取；后续验证矩阵保留历史。

### 已执行，不能混同的证据

- `data/acceptance/run-pb1oxt`：98 通过、1 失败，发布版本变量错误；没有将该轮算通过。
- `data/acceptance/run-D0waiG`：102 后端通过、无跳过；构建通过；浏览器7通过1失败（测试读取会话时机错误）。
- `AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE=.../data/v02-verification/browser-fixed.json npm --prefix frontend run test:e2e -- --reporter=list,json`：修复后8通过、0跳过、0 flaky，46.2秒；包含原任务、进阶任务、MOCK生成审核发布训练三条实际 Docker 浏览器闭环。MOCK 流程不算真实生成或人工审核。
- `AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh > data/v02-verification/acceptance-final.log 2>&1`：**109 后端通过，0 跳过，188.55秒；构建通过；8 浏览器通过，0 跳过/失败/flaky，45.17秒**。证据目录 `data/acceptance/run-Dn52Tm`，判定器逐项确认旧18、新8、生成发布训练及三条浏览器闭环，非仅脚本退出码。
- 最新生成恢复/校验/评测修复补充回归：21通过、1明确 deselected（Docker流程由完整验收另行实际执行），3.15秒；`data/v02-verification/generation-final-unit.xml`。覆盖契约重新设计、非法schema、取消、预算、独立上下文、空错误恢复和验证矩阵历史。
- 最新全部生成专项 `.venv/bin/python -m pytest tests/test_generation.py -v -o junit_family=xunit1 --junitxml=data/v02-verification/generation-final-all.xml`：**22通过、0跳过，32.90秒**，包含实际 Docker 发布/新版本/训练报告回归；这是最终评测修复后的代码。完整回归109项是之前一次执行，不与这22项相加宣称独立数量。
- 最后 `npm --prefix frontend run build`：通过，5.20秒，仍有已知 Monaco 大包警告。
- 本次恢复后 `docker info --format '{{.ServerVersion}}'`：29.8.0，普通用户可连接。
- `npm --prefix frontend run build`：TypeScript 与构建通过，5.16秒；Monaco 大包警告仍在。
- `pytest tests/test_generation.py -q -k 'not generated_docker'`：首次15通过1失败，定位 null error 的恢复缺陷；后续完整验收结果另记。

### 真实模型案例（失败保留）

1. 工具副作用 `71a94a226ec742c5b778ae9b39997193`：设计两次 schema 失败后成功；三次构建/验证都未触发预设故障、未识别规避，达到上限停止。独立评测只生成一次，没有为实现改答案。没有发布。
2. 工作流恢复 `17683c1deb9c4bd4aea75279524205b4`：原契约不适合单次隔离，显式澄清并确认 v2；首次构建 JSON 解析失败；修复后的两轮 Docker 矩阵正常版、参考、故障稳定触发及正常回归均通过，但规避识别失败。构建三次预算耗尽，禁止发布。不是依赖或镜像错误。
3. 权限边界 `81a3a18745ed4eaba0813d8b3f6d99b4`：从真实浏览器输入需求；设计成功后在页面显式保存契约 v2，明确 reason 字符串和重复请求语义，再确认本地模拟。首轮独立评测把故障触发样例标为 regression，实际失败 gate 为 fault_regression；正常版与参考已通过，未将该失败送回构建来迎合错误测试。补充作者评测问题修复入口，保存具体公开契约依据及旧评测，第二轮不传实现、标记为审核指导（非完全盲测）。真实模型重新生成评测后 **40项 Docker 检查完成：正常8/8、参考8/8；故障5个目标失败、3个正常回归通过且重复运行稳定；两种规避分别6失败/2通过与5失败/3通过，全部门禁通过，27.604秒**。随后真实教学调用完成，累计5次模型请求（设计、构建、两次评测、教学）。矩阵 `a2415e5ba601438297af5d1fd32ed2d1`。当前 awaiting_review，未发布。

真实浏览器实际命令：

```bash
AGENTLAB_REAL_SMOKE=1 node scripts/generation_browser_probe.mjs create
AGENTLAB_REAL_SMOKE=1 node scripts/generation_browser_probe.mjs refine
AGENTLAB_REAL_SMOKE=1 node scripts/generation_browser_probe.mjs confirm
AGENTLAB_REAL_SMOKE=1 node scripts/generation_browser_probe.mjs repair-evaluation
AGENTLAB_REAL_SMOKE=1 node scripts/generation_browser_probe.mjs inspect
```

最终浏览器刷新后仍为 awaiting_review，矩阵通过状态恢复；`docker ps -a --filter label=agentlab=true --format '{{.Names}}'` 输出为空，无本次容器残留。

记录 `data/v02-verification/permission-browser.json` 和各阶段截图；工程复核材料 `data/v02-verification/PERMISSION_REVIEW.md`。模型 `deepseek-v4-flash`，生成请求 max_tokens=12000，thinking disabled；每次实际 usage/结束原因保存在阶段审计，未输出密钥或隐藏推理。最后版本的教学没有完整补丁，L1较直接，45分钟未校准。工程复核由 AI 辅助完成，**不是人工审核**。

上述是真实供应商结果，不沿用旧供应商成功记录。作者实际人工审核与真实实例发布→训练→报告→刷新闭环仍待完成，不能用离线表单自动点击冒充人工认可。已准备显式需要审核备注与当前摘要的 publish 浏览器探针，尚未运行该动作。旧轮验证矩阵仅最终状态完整持久化，后续代码已增加矩阵历史保存；旧失败未宣称可完全重放。


## 2026-09-16 V0.1.1 进阶任务与多文件验收

**最终分项结果：后端 88/88 通过，其中旧 Docker 18/18、新任务 Docker 8/8 均实际执行；修复后的浏览器 5/5 通过；均无跳过。真实模型完成跨模块工具调查，新任务提交真实反馈成功，浏览器刷新后仍可查看。** 本轮不新增 CI 或 V0.2 功能。

### 实现与发现的问题

- 新增 `rag_versioning@1.0.0`，单一预设故障为索引更新追加新片段却没有清除同文档旧片段。其他模块遵循公开契约。3 个公开场景、11 个隐藏行为场景；正常基线和参考修复均是完整六文件实现。
- manifest 驱动读取/编辑/固定运行资产权限；五业务模块可编辑，入口只读。保存完整集合后一次切换工作区修订指针；多文件快照以稳定路径/内容摘要寻址。旧题与旧摘要保持原样，未迁移历史报告。Agent diff、报告 diff、文件树、保存全部与快照查看已接入。
- Docker 只读挂载精确白名单集合，worker 仅追加 `/workspace` 模块路径；其余执行隔离与限制不变。公开诊断轨迹明确标记用户代码来源，隐藏轨迹不返回，宿主只比较结构化行为。
- **浏览器首次验收失败**：仅切换 Monaco 模型时，旧 `onChange` 监听把新文件内容写进旧文件草稿，`context_builder.py` 被入口内容覆盖，Docker 返回 `ImportError`。预设故障没有被错误算作复现。按会话/文件给 Editor 独立 React key，切换时卸载旧监听，并拒绝只读回调写入。新增浏览只读/多文件不变、保存后六文件精确比对回归。
- 初次在受限沙箱中运行 TestClient 回归挂起，终止的是本次测试进程；沙箱外重跑 44 项通过。没有降级为宿主执行任务代码。

### 实际命令与结果

| 命令 | 结果与证据 |
| --- | --- |
| `docker build -t agentlab-runner:0.1 -f backend/Dockerfile .` | 成功。镜像 config digest `sha256:2ac8a190f4faeaa085c16b3cf6e359c6801dabf901fb6ed2ed19853840999b4e`；保留原隔离选项。 |
| `.venv/bin/python -m pytest tests/test_versioning_docker.py -v -o junit_family=xunit1 --junitxml=data/v011-verification/task-matrix.xml` | 接平台前实际 7 passed / 0 skipped，36.90 秒。[任务矩阵](data/v011-verification/task-matrix.xml)。 |
| `.venv/bin/python -m pytest tests/test_platform.py tests/test_model_feedback.py tests/test_report_reliability.py -q` | 沙箱外 44 passed，7.25 秒。保留提示上限、反馈失败与受控重试逻辑。 |
| `.venv/bin/python -m pytest tests/test_multifile.py tests/test_versioning_docker.py -v -o junit_family=xunit1 --junitxml=data/v011-verification/multifile.xml` | 15 passed / 0 skipped，46.74 秒；包括多文件实际 Docker 提交与提交后隔离。[证据](data/v011-verification/multifile.xml)。 |
| `AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh` | **此次脚本退出 1**：后端 88 passed、构建成功；浏览器 4 passed / 1 failed，原因是上述文件切换缺陷。保留[首次完整记录](data/acceptance/run-1YiYUf/browser.json)，不伪称该次脚本成功。 |
| `AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE=/home/vonllya/workspace/AgentLab_Interview/data/v011-verification/browser-fixed.json npm --prefix frontend run test:e2e -- --reporter=list,json` | 修复后 5 passed / 0 skipped / 0 flaky，30.0 秒，包含新旧两条完整提交闭环。[最终浏览器记录](data/v011-verification/browser-fixed.json)。 |
| `.venv/bin/python scripts/verify_acceptance.py browser data/v011-verification/browser-fixed.json` | `passed:true`，逐条确认两条必需流程存在且真实通过。[核对结果](data/v011-verification/browser-fixed.verified.json)。 |
| `npm --prefix frontend run build` | 文件切换修复后再次通过 TypeScript 检查与 Vite 构建，6.15 秒。只有原有大 bundle 警告。 |
| `git diff --check`；`git diff --name-only -- tasks/rag tasks/retry tasks/resume` | 均无输出：格式检查通过；旧三题任务版本未修改。 |
| `docker ps -a --filter label=agentlab=true --format '{{.Names}} {{.Status}}'` | 验收及真实联调后无输出，无残留训练容器。 |

最终依据是同一后端版本的 88 项结果，加上仅前端切换修复后的完整 5 项浏览器结果；没有再次整套运行 `acceptance.sh`，不将第一次非零退出改写为成功。完整入口现已要求旧 18 项、新 8 项 Docker 名称及两条浏览器流程，缺少或跳过任一项均不通过。

### 验收覆盖核对

[后端逐项核对](data/acceptance/run-1YiYUf/pytest.verified.json)：旧 13 项全部实际执行，扩展到的旧 18 项也全部通过；新增 8 项全部通过，无 failure/error/skipped。

- 正常基线与参考修复分别通过全部 14 个行为输入。故障版的正常回归通过，更新样例重复执行仍返回 `refund:1:0`、旧规则；参考期望为 v2 新规则。测试先要求有效结构且无运行错误，加载失败、无输出和超时不计预设症状。
- 四种规避均在指定行为检查上被拒绝：清空全库→文档隔离；无条件覆盖→延迟低版本；仅排序优先新版本→旧关键词及残留片段；只改内存→重开后持久化。规避版本先通过正常回归，排除依赖/路径/镜像加载错误。
- 文件 API 和 Agent 同白名单，拒绝私有资产、绝对/穿越/未知路径与符号链接。只读文件不可保存；缺失或超限的文件集合不产生部分保存。顺序不同的同内容保存摘要一致，各业务模块变更均改变摘要；旧摘要算法保留。
- 提交后的代码、诊断和提示继续变化，不影响既有多文件快照、报告输入和提示次数；报告与新提交执行 ID/快照一致，不复用旧公开运行。
- 新浏览器闭环：创建进阶训练→查看多个模块及只读入口→编辑两个文件→切换并刷新草稿→保存全部→公开测试→L1→再改第三文件→提交→查看 15 条客观检查和六文件快照→继续编辑/取 L2→刷新后旧报告仍保留 L1 及旧代码。mock 用于这组界面自动化，未算作真实模型证明。
- 旧三题故障/正常/参考/规避、真实无限循环超时、容器异常退出、后台重启 interrupted 与清理、提示上限、输出预算受控重试/最终失败、客观证据保留、Markdown 安全展示回归均通过。

### 真实供应商联调与人工审阅（独立于确定性测试）

先确认原 16 个会话没有进行中的执行/反馈，再停止空闲开发服务以便隔离验收；完成后用 `./scripts/start.sh > data/v011-verification/development.log 2>&1` 恢复正常数据目录和真实模式。未检查或打印 `.env` 内容、密钥或隐藏推理；启动脚本按已有配置正常加载。

实际命令：`AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.versioning_model_probe`。这次创建新训练，未重写旧报告。[联调记录](data/v011-verification/real-model.json)。

- 会话 `89c0091d185e4418930065c3e176de19`；故障公开运行 `51ebc9f7286c49caba59bce52a30b4dd` 确认为行为失败。
- 模型真实调用 `read_workspace_file` 读取 `pipeline.py`、`index_store.py`、`retrieval.py`，随后读取运行结果、会话证据和题面，共 6 个成功工具调用；真实后续回复 ID `b45ad9641c3e41518ff2dc53ea0fbfd6`。没有使用固定聊天或 mock 代替。
- 人工审阅回复：能指出更新后旧候选/旧片段仍在、区分代码推断和运行观察，指出 `version-unrelated` 的答案正确但完整片段集合失败；明确轨迹不是独立通过证明、未测场景不能视为通过。未输出完整补丁。
- 质量限制：用户要求简短但实际回复约 1632 字符；有关排序/截断“耦合”的解释及将“检索过滤”列作追问容易混淆契约。本题要求从索引清除旧片段，仅排序或过滤答案并不满足；不能据此认为其他正常模块也有故障。程序化评测已拒绝相关规避，但不声称一次模型回复的全部措辞均理想。
- 新提交执行 `087c0eac98d74b6d9ddc6a5a4c14ae18`：14 行为检查 + 1 范围检查全部通过。快照 `e0c190a87c4c5f891771494bb2f83c831b163df309abd56d6450934a6a7f4b40`。
- 真实报告 `d1e24536c4594909af06c5b24b499625` 状态 generated。`deepseek-v4-flash`，首轮预算 1200、thinking disabled、输入 2896 字符；供应商 usage：prompt 1081、completion 173、total 1254，reasoning 分项未知（null）；finish_reason stop、正文非空、parsed、HTTP 200，未触发重试。报告预算/重试机制没有改变。
- `node --input-type=module` 的 Playwright 只读联调打开上述真实会话，两次加载/刷新均看到同一报告 ID、客观通过和“模型反馈 · 已生成”。[刷新核对](data/v011-verification/real-browser.json)、[截图](data/v011-verification/real-report-refresh.png)。

### 失败、跳过和剩余限制

已修复：上述 Monaco 跨文件草稿污染。已处理：沙箱导致的 TestClient 挂起，沙箱外重跑通过。最终测试跳过数为 0；本轮没有 Docker 或真实供应商环境阻塞。

没有验证并发写索引、崩溃事务恢复、非法输入、分布式一致性，本就不在任务范围。真实辅导只进行一次最小联调，不代表跨供应商稳定性、长期质量或完全可靠的提示等级语义；权限和 L3 上限仍由程序强制。完整工作区修订暂不自动回收；模型回复可偏长或产生不理想建议。非 root/no-network 等执行边界保持，隐藏测试只隔离正常应用流程，不防本机源码所有者。版本化用例不是防主动作弊的形式化证明。


## 2026-09-15 报告可靠性、证据语义与对话展示续验

本节对应最新失败报告，不沿用 09-14 的成功结论。**最终全量后端 73 项通过，其中 18 项 Docker 测试实际执行通过；完整浏览器验收 4 项通过，最终展示回归 2 项通过。真实同类提交生成短报告并刷新恢复；人工质量检查与自动化通过分开记录。**

### 最新失败请求与根因

最新失败报告为 `7f561812a54a4f65860a7db41caadce8`，运行 `50aa036020c145ec93f5c2e4516a2bd8`，快照 `71f3172aa1ca3b198861c354e1fdf8ff7e83e6d4e81a21327ff0e80653753915`。持久化证据确认：预算 **4096**，输入 **956 token**，输出 **4096 token**，total **5052**，结束原因 **length**，反馈状态 failed/output_limit。不能将此前成功的报告当作这次成功。

当时运行中的后端 PID 304814 确认模式 real、模型 `deepseek-v4-flash`、密钥存在，未配置额外推理参数；API 地址经只读判断为官方 DeepSeek 域名，没有打印密钥或完整 `.env`。**原失败请求没有保存模型名称、正文长度、reasoning token 分项或解析状态，这些历史字段明确记为未知；不能断言这次 4096 token 全用于推理。** [原失败记录与未知字段](data/reliability-verification/latest-failure.json)。

原请求将同一个 4096 输出预算用于开放式、多维度的报告反馈；没有独立报告推理配置、简短结构与 output_limit 重试。输入 956 token 不足以支持“输入过长”这一归因。当前模型的官方文档说明默认开启推理，并支持 `thinking.type=disabled`；据此为证据摘要型报告请求显式选择非推理模式，而非再次统一调高 token。[供应商参数依据](https://api-docs.deepseek.com/guides/thinking_mode/)

可恢复原提交代码、诊断、检查和提示记录；本次将这些代码/诊断及同等级提示恢复到独立训练后重新判分并生成报告，**是恢复原提交内容后的新请求，不是原 HTTP 请求逐字节重放**。旧请求未保存完整报文或原模型正文，不宣称重现了当时所有响应细节。

### 实现边界

- 报告仅取提交快照、提交时诊断和提示 ID/等级、对应运行检查。没有聊天历史、重复提示正文或原始工具日志；检查只保留状态和简要覆盖，diff/诊断截断时标记遗漏。反馈要求三条短句、总计不超过 300 汉字，不推断缺失的用户思考过程。
- 报告首轮 **1200 token**；仅 output_limit 自动重试 **一次**，第二轮进一步缩短 diff/诊断、省去详细覆盖，并限制为 **1800 token**。总输出预算最多 **3000 token**，最多两次请求，每次等待最多 **40 秒**，整体预算 **90 秒**。非 output_limit 错误不自动重试。
- 仅官方 DeepSeek API 的 `deepseek-v4-*` 报告请求发送 `thinking.type=disabled`；未知供应商不发送猜测的专有参数。聊天仍保留原工具预算，不把固定文案当作报告成功。
- `feedback_attempts` 保存尝试编号、状态、起止时间、原 run/snapshot、输入哈希、实际模型/预算/推理请求配置、输入字符数、供应商 usage、结束原因、正文空值与解析状态。缺失字段为 null/unknown，不从字符数估算 token。超时迟到响应不能修改已失败报告；服务重启结束未完成状态。底层在途供应商请求不保证立即取消或免计费。
- 没有新增手动重试入口。自动重试不重新判分，不读取后续工作区，不改变客观结果或提交证据。三份原有报告完整 JSON 哈希均与备份一致。
- 证据解释层只读取版本化公开数据，不修改 Docker 执行器、判分机制或原始记录。明确区分修改范围与行为检查；是否改动看 diff，功能看对应样例。RAG 显式返回候选数、实际索引、重排/子集/空集和子集形状。当前公开样例是 **4 选 2 的前缀连续子集**，并非完全未测过滤，也不支持“过滤已全面排除”。隐藏输入、源码和堆栈不进入聊天工具，覆盖未知不猜测。
- 提示词约束实验在合法输入域内；两个正确备选实现可以等价，不将故障初始版与修复版混为等价。简单问题默认简短确认、关键依据与追问，不机械重复长模板。L3 逻辑未重做。
- 工具原始 JSON 默认折叠，显示工具名称、状态与摘要；证据短标签可定位，详情保留完整 ID。Markdown 使用 react-markdown，不启用原始 HTML，屏蔽图片和不可信链接；已知证据在解析后的文本节点中转为链接，避免破坏既有 Markdown。报告已知短检查锚点只映射到本报告运行。[渲染安全依据](https://github.com/remarkjs/react-markdown#security)

### 确定性回归与浏览器验证

| 项目 | 实际结果 | 证据 |
|---|---|---|
| 完整 `acceptance.sh` | 72 后端通过、18/18 Docker 通过、4 浏览器通过，0 跳过 | [run-52owRe](data/acceptance/run-52owRe) |
| 补充引用绑定后全量后端 | **73 passed**，0 失败/跳过，105.67 秒 | [pytest-final.xml](data/reliability-verification/pytest-final.xml) |
| Docker 逐名门禁 | **18/18**，原 13 项也全部执行 | [核验结果](data/reliability-verification/pytest-final.verified.json) |
| 最终聚焦回归 | 44 项通过 | [focused.xml](data/reliability-verification/focused.xml) |
| TypeScript/Vite 最终构建 | 通过，Vite 4.99 秒 | 实际执行 `npm --prefix frontend run build`，仅既有大包提醒 |
| 最终 Markdown/反馈 UI | 2 passed，0 跳过，6.1 秒 | [ui-final.json](data/reliability-verification/ui-final.json) |
| 真实报告链接/刷新只读核对 | 链接均指向本报告运行，实际点击成功 | [links.json](data/reliability-verification/links.json)、[截图](data/reliability-verification/final-report-links.png) |
| 历史报告与提交绑定 | 3 份原报告不变，新报告 run/snapshot/诊断/提示一致 | [persistence.json](data/reliability-verification/persistence.json) |

新增/扩展回归覆盖空正文、格式错误、usage 缺失、output_limit 一次重试成功与最终失败、非限额错误不重试、等待超时与迟到响应、原提交证据不变、范围/功能边界、未知覆盖、公开样例形状、已知检查引用绑定、工具折叠以及 Markdown 脚本/图片/危险 URL 不执行。测试替身只算确定性验证，不算真实模型调用。

### 真实联调与人工质量审阅

最终浏览器会话 `aa596180800b45f09404b2789abc3437`：故障代码真实公开测试失败 → 普通模型聊天观察证据 → 恢复原失败报告的提交代码/空诊断/三级提示到新训练 → 保存并提交 → 短反馈 → 刷新恢复。

新报告 `7fda08e747224051962eb0b19a414c22`，运行 `ac7c0fb1ba9f4c3b80a314f3fe00a6d1`，与原失败报告使用完全相同的代码快照，但执行 ID 不同。提示数仍为提交时的 3；原报告没有被改写。

最终真实报告请求：模型 `deepseek-v4-flash`，max_tokens **1200**，请求 thinking disabled；输入 **2616 字符 / 1081 token**；输出 **264 token**，total **1345**；HTTP **200**，finish_reason **stop**，parse_status **parsed**，content_empty **false**。正文含 Markdown 与完整引用共 **449 字符，其中 157 汉字**，成功保存并刷新恢复。reasoning_tokens 未返回，记录为 null，**不声称为 0**。首轮即成功，因此真实供应商自动重试路径没有触发，重试成功/失败只通过确定性回归验证。[本次完整实测证据](data/reliability-verification/live.json)

人工逐项对照回复和实际检查，没有用匹配固定措辞来判定模型理解正确：

1. 页面回复正确指出范围通过不等于改过代码或功能通过，并引用目标行为失败与空 diff；未将范围替代功能。
2. 页面混合“实际 4 选 2”与“假设两元素完整重排”的表达仍有歧义风险。因此额外使用现有 Docker 执行器运行一个**真实独立两元素完整重排故障实验**，实际返回内容/引用错位，范围约束通过且没有过滤样例。模型明确回答“不能排除过滤问题”，没有猜测未执行过滤通过。这是验证脚本的独立实验，不是新增任务或假造平台公开运行。
3. 对“两个都正确且满足契约的备选方案”，真实回复明确无需由测试区分或匹配参考补丁。
4. 最终报告使用提交 diff 和对应检查，公开覆盖有限、隐藏覆盖未知；引用可定位，未将缺失诊断当作已展示思考。

独立实验 `d3be86ee95e941bebc84a3e551c7838a` 的真实模型回复仅三条短句；输入 842 token，输出 364 token（供应商明确返回其中 reasoning_tokens=208），finish_reason stop。这里只保存可见回复与用量，不存隐藏推理。[独立真实实验](data/reliability-verification/controlled-evidence.json) · [人工审阅记录](data/reliability-verification/semantic-review.json)

**中间质量问题如实保留：** 首轮报告成功但检查锚点错误，回复建议了不合法的“非子集过滤”；第二轮又误称非连续子集和行为等价重构。已分别补精确输入域/实际索引与子集形状、故障基线语义和引用绑定。[第一轮](data/reliability-verification/live-before-review-fixes.json) · [第二轮](data/reliability-verification/live-second-review.json)。这些是质量修复过程，不能将其供应商 HTTP 成功包装成当时反馈质量通过。

### 实际命令、中断和剩余限制

```bash
.venv/bin/python scripts/docker_check.py
AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh
.venv/bin/python -m pytest tests -q -o junit_family=xunit1 --junitxml=data/reliability-verification/pytest-final.xml
.venv/bin/python scripts/verify_acceptance.py pytest data/reliability-verification/pytest-final.xml
.venv/bin/python -m pytest tests/test_model_feedback.py tests/test_platform.py tests/test_report_reliability.py -q --junitxml=data/reliability-verification/focused.xml
npm --prefix frontend install react-markdown@10.1.0 --fetch-retries=0 --fetch-timeout=15000
npm --prefix frontend run build
./scripts/start.sh
AGENTLAB_REAL_SMOKE=1 node scripts/reliability_smoke.mjs
set -a; source .env; set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.evidence_model_probe
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/reliability-verification/ui-final.json" npm --prefix frontend run test:e2e -- --grep '模型反馈生成中和失败|工具默认折叠' --reporter=list,json
docker ps -aq --filter label=agentlab=true
```

中断后最初 Docker 预检为 cli_error，验收退出 2，未执行测试；用户说明刚重启 Docker，复查 CLI/服务/镜像均 ready 后才继续。[首次阻塞记录](data/acceptance/run-1fPtaN/docker.json)。没有安装另一套 Engine、修改 socket 权限或降级为宿主执行。依赖首次沙箱下载因 EPERM 失败，经审批在沙箱外安装成功；中断前不可查询的测试未计通过。中间确定性测试暴露局部变量遮蔽及过长的重试说明文本，修复后重跑通过。最终标签容器查询为空。

**当前无 Docker 或现有供应商调用阻塞。** 没有跨供应商验证、长时间可靠性统计或对所有问法的准确率评估；混合真实与假设场景的措辞仍需用户结合工具证据审阅。单次或少量成功不证明稳定性。旧失败报告保持原状；没有手动重试按钮。底层供应商在途请求可能晚于本地等待超时结束，但迟到结果不会把报告改回成功。没有增加 V0.2 功能，也没有修改既有 Docker 隔离和提交快照语义。

## 2026-09-14 真实模型反馈与 L3 提示修复验收

**本次结果：真实普通聊天与真实提交报告均通过，刷新恢复、L3 上限和历史快照保持通过；后端 63 项通过（全部 18 项 Docker 测试实际执行），前端构建通过，反馈状态浏览器回归 1 项通过。没有将 mock 或跳过计作真实模型验证。**

### 根因与配置追踪

1. `.env` 文件存在；真实用户后端 PID 278721 的进程环境确认 API 地址、模型名称、密钥均存在，模式为 real。不是仅看到文件就认定已加载。启动脚本 `scripts/start.sh` 使用 `set -a; source .env; set +a`，再启动 uvicorn；直接启动 uvicorn 不会自行读取 `.env`。只检查存在性，没有打印配置值、密钥或供应商隐藏推理。
2. 原报告 `1a05b7c494a64732893ebf9f4f86dd39` 保存的是 `feedback_status=unavailable` 和“模型未返回反馈”。沿 `runs.perform → agent.report_feedback → completion` 复现原请求：HTTP **200**，`finish_reason=length`，正文是长度 **0** 的字符串；900 个 completion token 全部为 reasoning token。不是正文格式不兼容或解析丢失，也不是本次供应商鉴权失败。[原响应安全元数据](data/model-verification/provider-reproduction.json)。复现时只调用模型，并将写库函数替换为空操作，未重写原报告。
3. 原适配器固定 `max_tokens=900`，不足以给当前推理模型同时生成推理和正文；代码把空正文替换成固定文案。另有 `runs.perform` 的 `except Exception: pass`，会静默吞掉其他反馈异常，使界面无法说明失败原因。
4. 固定提示走 `/hint`，普通聊天走 `/chat`，模式路由没有进入 mock。提示根因是 `min(level+1,3)` 只限制等级，没有限制新增提示和 assistant 事件，因此 L3 会重复。
5. 首次修复后的真实聊天确实执行了工具，但 6 次调用用完后循环直接输出固定预算提示，没有最终模型回复。[第一次联调失败记录](data/model-verification/live-first-failure.json)。已在原有 4 次模型请求上限内预留无工具总结轮；没有增加工具调用次数或开放提示权限。

### 修复范围

- 输出预算改为 4096 token（包含推理），单次 HTTP 阶段超时 60 秒；正文按字符串或标准 text 内容块解析。`length`、空正文、不兼容结构均明确失败，不再把空文案当作成功。
- 报告在客观结果持久化后显示 `generating`，完成后保存 `generated` 或 `failed`。失败记录脱敏的类别与简洁原因：配置、HTTP 鉴权/权限/限流、连接、超时、输出上限、空正文、格式或内部错误。服务重启将未完成反馈标为中断失败。客观结果保留。
- 工具循环保留最后一次模型请求总结已观察证据；若供应商要求带回本轮 reasoning_content，只在内存请求上下文中传递，不写事件、日志或报告。
- 服务端在锁内检查 L3 上限，超额返回 HTTP 400“已获取全部提示”，不写提示或对话事件；前端禁用按钮并显示同样文案。
- 没有改变提交时代码、诊断、提示列表的快照语义，没有重新生成或迁移已有报告。

### 实际真实联调

使用现有配置重启空闲后端前，通过 SQLite backup 保存 [before.sqlite3](data/model-verification/before.sqlite3)，并保存已有报告哈希。未停止前端、未修改用户工作副本、未使用 sudo。修复后进程仍为真实模式且三项配置均存在：[进程配置存在性](data/model-verification/process.json)。

成功会话：`1e518af6ed1e4263a2537d124ff38b6d`。

浏览器实际执行：创建 RAG 训练 → Monaco 编辑 → 保存并核对文件 → Docker 公开测试通过 → 发送指定普通消息 → 请求 L1 → 修改为新的提交版本 → 保存并提交 → 查看生成中和真实报告 → 获取 L2/L3 → 刷新恢复。

指定普通消息：

> 请检查我当前保存的代码和最近测试结果，指出还有什么需要验证，不要直接提供完整修复代码。

实际模型工具：`get_task_brief`、`list_workspace_files`、`get_workspace_diff`、`get_session_evidence`、`read_workspace_file`、`get_run_result`，均有持久化事件与成功结果。后续真实回复引用工具事件与公开运行 ID，区分已观察与待验证；聊天没有新增提示。不是固定回复，也没有提供完整修复补丁。

提交报告：`f4a13c84bdab432eaeb1713e048dc2dc`；执行：`cf2dd619469c4b0cb0de0937d58331a7`；快照：`054696c868e4d89003352a0a0758457a7b7ddbb0b59174471f70eee80d5cec86`。

- 新提交执行与公开测试的 ID、快照均不同，报告/执行/实际快照代码一致。
- 供应商反馈结束原因为 **stop**；输出用量 **3269 token**，保存可见反馈 **2025 字符**，状态 generated；回复引用实际提交执行 ID。
- 页面实际观察到生成中，随后显示已生成；刷新后文字与数据库/API 内容完全相同。
- 提交时只有 L1，因此报告仍是 **1 次提示**。后续获取 L2/L3 后，超额直接请求接口两次均返回 400；提示总数维持 3，事件总数不变，按钮禁用。
- 现有原历史报告完整 JSON 哈希与备份一致；新报告后续也未因提示变化而改变。

[真实联调完整证据](data/model-verification/live.json) · [报告截图](data/model-verification/real-report.png) · [持久化核对](data/model-verification/persistence.json)。原失败历史报告保留原状；本次成功来自新提交，没有用后来代码或提示改写旧报告。

### 实际命令与结果

命令均在仓库根目录执行。需要访问本地服务、浏览器或 Docker 的命令经执行审批在沙箱外运行；没有宿主执行用户任务代码。

```bash
# 真实模式由已授权的 .env 提供，未输出其内容
set -a; source .env; set +a
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000

# 真实浏览器闭环（已启动真实后端和前端）
AGENTLAB_REAL_SMOKE=1 node scripts/real_model_smoke.mjs

# 全量后端及 Docker 回归，随后逐名检查实际执行情况
.venv/bin/python -m pytest tests -q -o junit_family=xunit1 --junitxml=data/model-verification/pytest.xml
.venv/bin/python scripts/verify_acceptance.py pytest data/model-verification/pytest.xml

npm --prefix frontend run build

# 此项仅测试 UI 状态：浏览器注入反馈状态，不冒充真实供应商结果
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/model-verification/ui.json" npm --prefix frontend run test:e2e -- --grep '模型反馈生成中和失败' --reporter=list,json

docker ps -aq --filter label=agentlab=true
```

| 项目 | 通过 | 失败 | 跳过/未验证 | 证据或原因 |
|---|---:|---:|---|---|
| 后端全量最终回归 | 63 | 0 | 0 | [pytest.xml](data/model-verification/pytest.xml)，102.19 秒 |
| 其中 Docker 实测 | 18/18 | 0 | 0 | [逐名核验](data/model-verification/pytest.verified.json)，含三题故障/正常/参考/规避、超时、重启和清理 |
| TypeScript + Vite | 通过 | 0 | 0 | 实际构建完成，Vite 4.75 秒；仅原有大包提醒 |
| 真实普通聊天 + 提交 + 刷新 | 1 条闭环 | 0（最终） | 0 | `live.json`；使用实际供应商，不是 mock |
| 反馈生成中/失败 UI 回归 | 1 | 0 | 0 | [ui.json](data/model-verification/ui.json)，4.6 秒；显式 UI 替身 |
| 原历史报告不变 | 1 | 0 | 0 | 完整 JSON SHA-256 对照，提示与快照不变 |
| 执行资源清理 | 通过 | 0 | 0 | 最终 docker ps 输出为空 |

新增 14 项参数化后端回归覆盖输出预算/正文、失败分类与脱敏、客观结果保留、生成中状态、重启中断、并发 L3、真实适配器工具协议与提示拒绝、总结轮和提交证据不变。已有提示测试改为验证第三次后拒绝；不再把旧重复行为当作期望。

**中间失败与中断也保留：** 原 900 token 真实请求复现为空正文；第一次真实聊天因工具预算终止失败，修复总结轮后第二次完整闭环成功。一次中间单测仍断言旧固定文案“预算”，改为检查结构化 `tool_budget` 错误及无提示副作用后，全量 63 项通过。最初沙箱内单测未完成，已终止并在沙箱外重跑，不计为通过。

**未验证与限制：** 本次没有重跑整个 `acceptance.sh` 或全部 mock 浏览器流程（前次完整结果保留在下节）；本次实际运行的是全量后端、构建、真实模型浏览器闭环和针对反馈失败的 UI 回归。没有跨供应商/跨模型兼容与长期稳定性评估；更长输出仍可能触发输出上限，此时显示明确失败并保留客观结果。HTTP 阶段超时不是严格端到端墙钟截止。当前真实配置最小联调无剩余阻塞，不据此声称所有模型均兼容。

## 2026-09-14 最终续验：Docker 与 Mock 完整闭环通过

**最终整套 `./scripts/acceptance.sh` 退出 0：49 项后端测试通过，其中全部 18 项 Docker 用例实际执行通过；浏览器 2 项通过，无失败、无跳过。真实模型供应商联调未配置，单独未验证，不阻塞本次 Docker 验收。**

最终证据目录：[data/acceptance/run-hBroIe](data/acceptance/run-hBroIe)。这是实际执行结果，不沿用前两轮的 skipped 结论。

### 权限原因、处理范围与仍需刷新旧进程

在沙箱外以普通用户只读核对得到：

- 账户：`vonllya`，UID 1000；`id vonllya` 和 `getent group docker` 已包含 docker（GID 1001）。
- 当前旧进程：`id` 仅含 `vonllya(1000),sudo(27)`，没有 docker。
- `/var/run/docker.sock` 实际目标 `/run/docker.sock`：`root:docker`、`660`。
- 因此是**已配置的账户组权限尚未应用到当前进程**，不是需要再添加组。没有执行 usermod、chmod、chown，没有安装另一套 Engine，没有使用 sudo 运行项目。
- 沙箱中的 nobody/nogroup 是隔离映射视图，没有用该视图修改真实 socket。

使用 `sg docker -c '…' < /dev/null` 显式启动普通用户子进程：实际 UID/EUID 均为 1000，GID 为 docker，附加组保留 sudo/vonllya/docker；`docker info` 成功返回 Server **29.7.2**。未索取、读取或保存密码。`sg` 的作用范围仅限该子进程及其后代。

**结束前再次复核，旧 Codex 进程仍没有 docker 组，普通直接调用仍报 permission denied。** 本次验收不依赖假设它已刷新。后续使用请先保存工作、退出旧 Codex/后端，关闭旧 WSL 终端或 VS Code WSL 远程连接，再重新打开 Ubuntu，确认 `id -nG` 含 docker 且 `docker info` 成功，从该终端重新启动 Codex 和后端。无需再次执行 sudo/usermod。本次没有强制终止用户的旧 Codex 进程。

[权限原始核对记录](data/acceptance-2026-09-14/permissions.txt) · [具体刷新步骤](docs/DOCKER_SETUP.md)

### 实际执行顺序与最终结果

首次在同一个已应用 docker 组的普通用户子进程中，依照要求顺序执行：

```bash
sg docker -c 'id && docker info --format "{{.ServerVersion}}" && docker build -t agentlab-runner:0.1 -f backend/Dockerfile . && .venv/bin/python scripts/docker_check.py && AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh' < /dev/null
```

镜像已真实构建；Docker CLI、服务连接、镜像三项预检均为 ready。基础镜像下载较慢，最后一层约 395 秒下载完成，没有更换运行边界或在宿主执行任务代码。

发现并修复下述测试问题后，最终执行：

```bash
sg docker -c 'AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh' < /dev/null
```

| 最终项目 | 通过 | 失败 | 跳过 | 执行证据 |
|---|---:|---:|---:|---|
| 后端 pytest | **49** | 0 | 0 | [pytest.xml](data/acceptance/run-hBroIe/pytest.xml)，100.51 秒 |
| 其中真实 Docker 用例 | **18/18** | 0 | 0 | [逐项门禁核对](data/acceptance/run-hBroIe/pytest.verified.json)，包含原 13 项及新增 5 项 |
| TypeScript + Vite 构建 | 通过 | 0 | 0 | 同一验收命令实际构建，4.66 秒 |
| Chromium 用户流程 | **2/2** | 0 | 0 | [browser.json](data/acceptance/run-hBroIe/browser.json)，16.4 秒；[门禁结果](data/acceptance/run-hBroIe/browser.verified.json) |
| 验收后项目残留容器 | **0 个** | — | — | [environment-final.json](data/acceptance/run-hBroIe/environment-final.json)，只读检查全部 agentlab=true 标签 |

镜像 `agentlab-runner:0.1` 的 ID 为 `sha256:3a5d6ea0e1c85aff2e8caae0fe52b1ae6a8c7f90df130a5dd3d4ee8297547dd4`，镜像用户为 `65534:65534`，入口为 `python -I /opt/worker.py`。最终环境记录保存了实际 UID、组、服务版本和镜像标识。

验收检查器现在要求明确列出的全部 18 项 Docker 测试存在并通过；不能因为删掉新增用例、pytest 退出 0 或浏览器跳过就放行。

### 三题真实行为矩阵

| 任务 | 故障版实际行为 | 正常版 | 参考修复 | 规避验收 |
|---|---|---|---|---|
| A / RAG | 10 项中 6 项命中预设引用错位，其余 4 项通过；重复执行结果一致 | 10/10 | 10/10 | 关闭重排/忽略过滤被拒绝 |
| B / retry | 8 项中 5 项命中预设重复记录，其余 3 项通过；重复执行结果一致 | 8/8 | 8/8 | 禁用重试被拒绝 |
| C / resume | 7 项中 5 项命中预设重复副作用日志，其余 2 项通过；重复执行结果一致 | 7/7 | 7/7 | 遇任意检查点就直接返回、遗漏未完成步骤，被拒绝 |

故障版本的“测试用例通过”表示**验证到了预设故障**，不表示故障代码通过题目验收。检查先确认正常场景可执行，拒绝把意外加载错误计为目标失败；之后检查内容/引用错位、records 数量增加或持久化日志重复，不比较代码是否与参考补丁相同。[完整矩阵摘要](data/acceptance/run-hBroIe/matrix-summary.json)，各项实际/期望结果保存在 pytest 的 matrix 属性中。

### 完整浏览器提交、快照与刷新证据

实际操作链：创建 RAG 会话 → 剪贴板粘贴修复代码 → 编辑诊断、保存 → 运行真实公开测试并通过 → 请求 L1 提示 → 将代码改为版本 B、再次保存 → 提交并重新执行公开与隐藏检查 → 查看报告 → 刷新 → 恢复同一报告与代码。

- 公开执行 ID：`60e729077c33457c87e4b09b2a1d2c6c`，快照 `88cc7f822997272290a7859fe4ac13d6a014499a06de7e072da4dd2870e7b1be`。
- 提交执行 ID：`c21fef5a814f43eb8713913bbfefe535`，快照 `0b69542e681950f119ddedfa35d72297a7c303721caf876482dfa1b2f86a55f5`。
- 报告 ID：`7637af00e1d5419cbcc8508912bccbee`。报告绑定提交执行及提交快照，与旧公开执行快照不同；10 项行为检查 + 1 项修改范围检查均通过，L1 提示记录存在。
- 逐字验证已保存代码和快照源码，刷新后报告 ID、代码与快照关联不变。另一个真实 API 用例验证提交之后继续编辑工作副本也不能改变提交快照。

[浏览器提交证据与最终持久化运行记录](data/acceptance/run-hBroIe/submission-evidence.json) · [API 提交后编辑隔离证据](data/acceptance/run-hBroIe/api-submission-evidence.json) · [实际报告截图](docs/submission-report.png)

### 超时、失败、重启与清理

真实容器无限循环触发超时；显式 `os._exit(7)` 被识别为容器异常退出码 7。API 运行分别持久化为 timeout / error，不停留在 queued/running，并核对该运行容器已清理。

重启用例先观察到真实运行容器，再杀死测试后端进程并重新启动；恢复后状态为 interrupted、取消标记存在。持续观察超过一个单项执行期限，未出现遗留 grader 再次启动容器。每个 Docker 用例还有独立运行标签的清理断言。结束后的全项目标签检查为 0 个残留容器。[重启证据](data/acceptance/run-hBroIe/restart-evidence.json)

### 本轮失败与修复历史（未隐藏失败尝试）

1. 第一次整套验收：[run-dBJEvY](data/acceptance/run-dBJEvY/pytest.xml)，**43 通过、6 失败、0 跳过**；其中 Docker 18/18 已通过。两个平台单元测试将整个 `subprocess.Popen` 替换为只理解 pytest 参数的替身；Docker 可用后，替身误拦截清理命令并抛 KeyError，导致配额未释放和后续连锁失败。修复为仅替换带 `AGENTLAB_GRADE_CONFIG` 的可信 grader 调用，其余命令仍调用真实 Popen，未关闭清理逻辑。
2. 第二次整套验收：[run-sHpUSW](data/acceptance/run-sHpUSW/pytest.xml)，后端 **49/49** 通过；浏览器 **1 通过、1 失败**。多行 `keyboard.insertText` 被 Monaco 按输入处理而自动缩进，将 `scenario` 错嵌入 `answer`，真实公开测试返回 AttributeError。保留了[失败浏览器报告](data/acceptance/run-sHpUSW/browser.json)与失败截图。修复测试交互为浏览器真实剪贴板粘贴，并在运行前逐字检查服务端保存源码；没有通过文件 API 代替 UI 编辑。
3. 定向浏览器复测 **2/2** 通过，20.3 秒；随后再次运行整个验收脚本，得到上述最终 **49/49 + 2/2、零跳过**结果。
4. JUnit 使用兼容 record_property 的 xunit1 格式，保留任务矩阵与快照审计属性。仅剩现有 Starlette/AnyIO 弃用警告及 Monaco 构建体积警告，未将它们隐藏为通过条件。

没有新增产品功能，没有修改 Docker socket 权限、重新配置用户附加组或切换宿主执行。

### 剩余事项

- **真实模型供应商联调：未验证。** 环境变量和 `.env` 都未提供配置；没有发起供应商调用，mock/HTTP stub 不计作真实模型验证。[配置存在性记录（无密钥）](data/acceptance-2026-09-14/model-presence.json)
- **旧终端/Codex/后端权限刷新：需要用户保存工作后重新打开。** 本次普通用户子进程验收已完成，但不能改变其父进程的附加组。
- 本次验证范围是本地单用户 Docker + Mock 训练闭环，不声称真实模型指导质量已验证，也不扩大为公网/多用户安全保证。

---


## 2026-09-13 续验结论：阻塞，未通过完整 V0.1 验收

本轮没有新增产品功能。没有在宿主机执行任务代码，没有将 mock 计为真实模型联调。

### 环境事实与阻塞

- 系统：WSL2，Ubuntu 22.04.5 LTS。
- `command -v docker`：无输出；`docker version`：退出 127，command not found。
- 常见 Docker socket 和 `/mnt/wsl/docker-desktop` 未发现；`DOCKER_HOST`、`DOCKER_CONTEXT` 未设置。
- 分层检查结果：`cli_missing`，`cli=false`、`daemon=null`、`image=null`。null 表示未检查，**不能写成服务未启动或镜像不存在**；没有出现足以判断 Docker 组权限不足的证据。
- 因 CLI 不可用，**本轮未构建镜像，未执行任何真实用户代码**。Windows 是否已安装 Docker Desktop 不能从当前 WSL 中这些检查确定。
- `AGENT_MODE`、`MODEL_BASE_URL`、`MODEL_NAME`、`MODEL_API_KEY` 均未设置，`.env` 不存在。没有发起真实模型请求，没有输出密钥。

对应环境的具体操作步骤见 [Docker / WSL2 配置与错误分类](docs/DOCKER_SETUP.md)。启用 Desktop 的当前 Ubuntu WSL 集成后，必须在同一终端确认 `docker info` 成功，再构建镜像并续验。

### 本轮实际执行结果

| 命令 / 项目 | 通过 | 失败 | 跳过 | 实际结果 |
|---|---:|---:|---:|---|
| `.venv/bin/python -m pytest tests -q --junitxml=data/acceptance-review/pytest.xml` | 31 | 0 | 18 | 退出 0，2.40 秒；这些通过项是平台回归，不是 Docker 行为矩阵 |
| 原有 13 项 Docker 用例逐项核对 | **0** | 0 | **13** | JUnit 中原 13 个测试名全部存在，全部 skipped；不是已执行通过 |
| `npm --prefix frontend run build` | 1 | 0 | 0 | TypeScript 与生产构建退出 0，4.79 秒；仍有 Monaco 大包警告 |
| Chromium / Playwright | 1 | 0 | 1 | 编辑、保存、草稿与会话刷新恢复、提示、mock 对话通过；真实提交闭环跳过，4.1 秒 |
| `./scripts/acceptance.sh` | 0 | 0 | 后续阶段未启动 | **退出 2：CLI 缺失，验收阻塞**；不是整套验收成功 |
| `scripts/verify_acceptance.py pytest ...` | 0 | 1 个验收门禁 | — | **退出 1**，核对到 original_docker_passed=0/13 |
| `scripts/verify_acceptance.py browser ...` | 0 | 1 个验收门禁 | — | **退出 1**，必需的真实 Docker 提交用例 skipped |
| 真实模型提供商联调 | 0 | 0 | 未配置，未执行 | HTTP 协议/工具循环的 stub 回归不能替代真实联调 |

浏览器实际命令（自动启动独立测试后端，执行结束由 Playwright 清理服务）：

```bash
AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome \
PLAYWRIGHT_JSON_OUTPUT_FILE=/home/vonllya/workspace/AgentLab_Interview/data/acceptance-review/browser.json \
npm --prefix frontend run test:e2e -- --reporter=list,json
```

原始结果保存在 [pytest.xml](data/acceptance-review/pytest.xml)、[browser.json](data/acceptance-review/browser.json)、[分层 Docker 检查](data/acceptance-review/docker.json)、[构建日志](data/acceptance-review/build.log)、[门禁退出码与核对明细](data/acceptance-review/gate-status.json)。`data/acceptance/run-*/docker.json` 保存 `acceptance.sh` 的实际预检记录。pytest 有一条现存 Starlette / AnyIO 弃用警告。

### 18 个跳过的 Docker 用例具体包含什么

原有 13 项保留原名称逐项追踪：三题 × 故障/正常/参考版本（9），关闭重排/关闭重试规避（2），真实无限循环超时（1），真实 API 提交证据流程（1）。

本轮增加 5 项验收回归：任务 C 见到任何检查点就直接返回的规避（1），真实容器异常退出码 7（1），API 运行的 timeout/error 终态与容器清理（2），真实后端进程被杀后重启、清理运行容器并保持 interrupted（1）。这 5 项也全部因 Docker 缺失跳过。

| 任务 | 故障特征待验证 | 参考修复与正常回归 | 规避方式 | 本轮执行 |
|---|---|---|---|---|
| A / rag | 内容顺序正确但 citation 映射不同，重复运行结果稳定 | 含排列、过滤、空集和不同候选数量 | 关闭重排/忽略过滤 | 全部未执行 |
| B / retry | 实际 records 数量大于逻辑写入数，正常请求可用 | 含写入前失败、响应丢失、独立操作、耗尽重试 | 禁用重试 | 全部未执行 |
| C / resume | 持久化副作用日志出现重复步骤，正常执行可用 | 含不同中断点、终态恢复、状态隔离 | 检测到任意检查点就返回，遗漏后续步骤 | 全部未执行 |

不能确认三题故障已复现、参考修复已通过或规避已被实际拒绝；这些结论必须等待真实 Docker 证据。

### 本轮发现并修复的验收问题

1. Docker 原检查把“服务不可达”和“镜像不存在”混为一类。现在先查 CLI，再查服务，再查镜像；权限、连接、超时、镜像缺失分开，未检查项为 null，并以固定消息输出，避免泄露环境内容。
2. 原 `acceptance.sh` 依赖命令退出码，可能接受 skipped。现在保存 JUnit/Playwright JSON 并核对原 13 个 Docker 测试名称、失败/跳过，以及真实提交浏览器用例；缺失或跳过不能放行。门禁拒绝跳过的回归已通过。
3. 原故障/规避断言只验证输出不同，可能把程序加载错误当作目标失败。现在先验证正常探测，拒绝意外错误对象，并检查 citation 错位、重复记录、重复日志等预设故障特征；参考版本按全部行为逐项比较。**增强的 Docker 断言尚未实跑**。
4. 原真实浏览器用例没有排除旧证据复用。现在在公开测试通过后再修改为版本 B、保存并提交；必须断言新的 run ID / snapshot、隐藏检查、提交快照源码、提示记录和刷新后的同一报告。API 用例还检查提交后的新编辑不能改变提交快照。**这两条完整流程仍未实跑**。
5. 容器/可信执行器错误原先可能聚合成 failed；现在 error、timeout 与行为 failed 分开，且不只根据 pytest 退出码标记通过。四种终态聚合回归已通过；真实容器异常流程未执行。
6. 后端重启清理现有容器后，遗留 pytest 进程可能继续下一个检查。现在先持久化 interrupted 和取消标记，再清理该运行的容器；可信 grader 每项启动前检查标记，整体超时也写标记。取消后的 grader 不会启动容器的宿主控制逻辑回归通过；真实杀进程/重启/资源清理仍未执行，不能声称实际 Docker 资源清理已经通过。
7. 单项超时消息现在显示实际配置秒数，避免 1 秒验收却报告“8 秒”。

### 续验命令与剩余完成条件

```bash
# 完成 docs/DOCKER_SETUP.md 中 WSL 集成或 Engine 配置后
cd /home/vonllya/workspace/AgentLab_Interview
docker info
docker build -t agentlab-runner:0.1 -f backend/Dockerfile .
.venv/bin/python scripts/docker_check.py
AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh
```

若上述 `/tmp` 浏览器已清理，先执行 `frontend/node_modules/.bin/playwright install chromium`，再运行 `./scripts/acceptance.sh`。剩余条件是：原 13 项及新增 Docker 生命周期回归实际执行并通过、真实浏览器提交报告与快照链路通过；真实模型联调需提供配置后单独验证。当前仍不能宣布 V0.1 完整验收通过。

---

## 2026-09-12 上轮记录（保留历史，不作为本轮执行结果）

验证日期：2026-09-12。工作区从空目录建立，未发现适用 AGENTS.md。

## 已执行

| 命令 | 实际结果 |
|---|---|
| `python3 --version` / `node --version` | Python 3.10.12 / Node 22.23.2 |
| `docker --version` | 退出 127，Docker 未安装 |
| `.venv/bin/pip install -r requirements.txt` | 沙箱内代理连接被拒绝；获准联网重试后安装成功，生成 requirements.lock.txt |
| `npm --prefix frontend install` | 获准联网安装成功；首次审计 3 个 high |
| `npm --prefix frontend audit --json` | 定位 Vite、Playwright 旧版本公告 |
| `npm --prefix frontend install --save-dev --save-exact vite@6.4.3 @playwright/test@1.63.0` | 成功，审计 0 vulnerabilities；锁文件已更新 |
| `npm --prefix frontend run build` | TypeScript 检查与生产构建通过；仅保留 Python Monaco 支持；仍有 Monaco 大包警告（约 2.52 MB / gzip 666 KB） |
| `.venv/bin/python -m compileall -q backend tests tasks` | 通过；这是语法编译，不是任务行为执行 |
| `.venv/bin/python -m pytest tests -q` | 最终回归：17 passed, 13 skipped，2.20 秒；Starlette/AnyIO 一条弃用警告 |
| `./scripts/start.sh` | 沙箱拒绝监听；获准后真实启动 Vite 5173 和 Uvicorn 8000，绑定 127.0.0.1 |
| `.venv/bin/python scripts/smoke.py` | 真实 HTTP 页面、创建会话、代码/诊断保存、提示、mock 对话、重新查询恢复全部通过。会话 ID `5e2660678e8c48b1af73e8ecf962753a`，执行记录为空，未伪造测试结果 |
| `./scripts/acceptance.sh` | 按预期退出 2：未安装 Docker，完整验收阻塞 |

后端 TestClient 在受限沙箱的 AnyIO 线程通信阶段挂起；诊断命令使用 `faulthandler_timeout=10` 定位，获准在沙箱外执行同一测试后正常完成。用户任务代码没有在宿主机执行。

17 个已通过测试覆盖：会话隔离、路径/符号链接边界、Host/Origin、提示逐级权限、工具参数与跨会话访问、mock 标识、模型 HTTP 协议适配测试、模型工具循环与预算、失败继续、代码输出拦截、Docker 参数、输出限额、受控传输超时清理、重启 interrupted、快照关联、并发配额和隐藏检查结果脱敏。

其中报告绑定测试使用明确标注的基础设施 stub；超时/输出限额测试使用可信固定子进程。它们不构成用户代码已通过真实 Docker 验收的证据。

## 仍需真实 Docker 验证

13 个测试被显式 skip：三题 × 故障/正常/参考版本（9），禁用重排和禁用重试规避（2），真实无限循环超时（1），真实 API 提交闭环（1）。因此目前**没有声称**三个正常版本通过、三个故障版本稳定失败、三个参考修复通过；这些矩阵只有 Docker 上实际执行后才能确认。

```bash
docker build -t agentlab-runner:0.1 -f backend/Dockerfile .
.venv/bin/python -m pytest tests/test_docker_acceptance.py -v
./scripts/acceptance.sh
```

## 模型与浏览器

未提供模型密钥，未对真实供应商发送调用；真实适配器只有 HTTP 协议和工具循环的确定性自动化测试。mock 在界面和回复中明确标识。

Chromium 153.0.8010.12 已实际下载并校验归档（官方 ETag/MD5 `8d9cec9d3099ecd7e826e429ec663ca9`）。普通下载过慢，直连完整下载未在 180 秒内完成；最终复用已有字节、分段直连下载完成，停止本任务的多余下载。真实浏览器结果：**1 passed, 1 skipped，2.9 秒**。已检查[实际工作区截图](docs/workspace.png)。实际运行命令：

```bash
AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome AGENTLAB_REUSE_SERVER=1 npm --prefix frontend run test:e2e
```

通过的浏览器用例实际操作了 Monaco 编辑器、保存、未保存草稿刷新恢复、提示、mock 对话及再次刷新。需要 Docker 的真实修复提交和报告刷新恢复用例明确跳过，没有伪造通过。

**结论：已交付可运行的编辑/辅导/持久化应用及容器评测实现，但未满足“完整闭环实际可用”的最终完成标准。安装 Docker 后还必须执行三题矩阵和真实提交 E2E。真实模型提供商调用也待配置密钥后验证。**

## 2026-09-18：roles-v1 多角色生成与自动修复

本轮实际实现，不是只改按钮。新增 `generation_budget.py / generation_roles.py / generation_diagnostics.py / generation_flow.py`：独立上下文角色、失败诊断、限定资产修复、共享预算、取消/中断审计、幂等新批次。前端“重新生成（消耗Token）”现在展开剩余预算恢复/明确授权新批次；不再把旧 retry 直接当作新生成。已发布实例、旧失败记录不迁移。

实现与原方案的最小兼容差异：每个角色以独立 schema 的资产请求/响应调用，程序供给允许的上下文并启动执行，没有另外嵌套模型工具循环；不存在额外未记账请求。评测修复沿用 evaluating 状态，审计标记 review_guided。20分钟为活动执行上限，等待作者确认不计时。复杂自然语言契约仍靠作者审核，不能声称程序证明测试语义正确。

### 实际发现与修复

1. 第一个 Docker 自动修复测试夹具把 faulty 源码设成与 normal 完全相同，被已有资产协议提前拒绝，未到 Docker。改为源码不同但行为等价的候选，实际验证到 fault_trigger=false，再由角色替换故障版；独立评测、normal/reference/evasions 哈希不变。
2. 首轮真实诊断把“故障版正确触发，目标行为检查 failed”误认为应修的生成问题。新增门禁语义校验：fault_trigger/fault_regression 都通过时禁止无关修改 faulty；正常/参考及已被正确拒绝的规避也不能被无关修复。不得以个别 failed 标签代替生成门禁。
3. 真实诊断把 evasion 代码修改与 add_coverage 混为一个提案。程序拒绝；强化互斥字段说明与真正错误候选的定义。不能接受假规避通过、删除规避或构造契约外输入来提高通过率。
4. 真实构建角色重复提交相同代码、只改说明。增加代码无变化拒绝和两次失败后的重新诊断；明确“修题包的规避资产”不是“替学习者修好代码”。部分真实候选仍未被既有检查识别，保留失败，不宣称已解决生成质量。
5. 诊断输入重复包含多个相同代码文件。按内容哈希去重，并去掉矩阵的重复环境/耗时字段，保持完整行为值、检查ID和版本映射。修复上下文只选目标版本的公开反例，程序补入对应公开输入；隐藏输入和诊断自由文字不传给构建角色，截断明确标记。最后一项公开反例整理有确定性/Docker回归覆盖，本轮未再次消费真实供应商请求验证其质量增益。
6. 新验收脚本把角色 Docker 测试设为必测后，原脚本自测的“完整 XML”夹具缺少该项，首次全量验收失败。补全夹具，仍严格拒绝 skipped/missing，并重跑全量。

### 真实供应商联调：全部尝试均保留

使用原配置由本地服务加载，不打印配置或密钥。实际请求模型名（适配器记录）为 `deepseek-v4-flash`；不额外推断供应商内部路由。generation 参数沿用现有适配器（thinking disabled），各角色受独立输出上限及共享账本控制。以下全部为真实请求，均未发布，也没有把自动化审阅当人工批准。矩阵次数不把父记录继承的旧矩阵算作新执行。

| 子批次 ID | 来源 | 实际请求 | 新矩阵（完成/启动） | 最终结果 |
| --- | --- | ---: | ---: | --- |
| 4857e84609ae45ed8c8aec962ea159bc | 工作流旧失败 | 12 | 5/6 | 工程验收主动取消：发现诊断误修预期故障，停止进一步消费；部分最后矩阵未完成，不算通过 |
| b9323ac4d19d45058b550ea22d91fad5 | 工作流旧失败 | 7 | 0/0 | 输入预算不足；诊断提案同时要求规避修复与修改评测，被程序拒绝 |
| 35034b81660546fa8bb1e500eeaf539e | 工具副作用旧失败 | 12 | 6/6 | 输入预算不足；fault_trigger、evasion_rejected 仍失败，正常/参考/回归与运行协议通过 |
| afc712ea261c4e9585c0e9e40fa939b6 | 工作流旧失败 | 13 | 0/0 | 输入预算不足；重复无代码变化修复被拒绝，不执行无效的新矩阵 |
| c1d991469da34f1e99c38aa78b726c40 | 工作流旧失败 | 8 | 2/2 | 8次请求预算耗尽；仅 evasion_rejected 未通过，正常/参考/故障触发/回归/运行协议通过 |

实际命令：

```bash
# 现有 .env 仅由 shell 加载到服务进程，不打印
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 18000
AGENTLAB_REAL_SMOKE=1 .venv/bin/python scripts/roles_probe.py workflow
AGENTLAB_REAL_SMOKE=1 .venv/bin/python scripts/roles_probe.py workflow --tag gatefix
AGENTLAB_REAL_SMOKE=1 .venv/bin/python scripts/roles_probe.py tool --tag scoped
AGENTLAB_REAL_SMOKE=1 .venv/bin/python scripts/roles_probe.py workflow --tag scoped
AGENTLAB_REAL_SMOKE=1 .venv/bin/python scripts/roles_probe.py workflow --tag candidate --requests 8
.venv/bin/python -m scripts.verify_roles_evidence
```

每批请求/输出/输入/活动时间预算及脱敏 usage、模型响应、失败提案、修复版本保存在该生成记录中；聚合核对为 `data/roles-verification/final-evidence.json`。首轮脚本在增加 `--tag` 前运行，证据名为 workflow-public/author.json；后续按 tag 独立保存。

结论：真实调用、程序拒绝非法/无效提案、连续诊断修复、真实 Docker 重验与预算停止已观察到；**本轮没有真实模型自动修复成功的实例**，没有新的真实发布或训练闭环。不能把 MOCK 成功、正常版本通过或某次 HTTP 200 当作真实题包生成成功。已有授权权限任务的真实发布/训练记录仍保留，但不能用于证明此次自动修复成功。

### 保护已有证据

`verify_roles_evidence` 核对三个原生成记录（批准权限实例和两条旧失败记录）及已发布包19个文件，与本轮修改前哈希完全相同。人工批准摘要仍为 `1bc32e924954166a81386b76a7f66dceda9b61469d0da06baca1ca7ad8b4c3c1`。旧报告 `f319bd8af6ed4e38b26000f4019484fd`、执行与客观结果仍绑定同一快照 `3ad296a1df9ae704ee711fe3d059aae30a0975a3b7ad0d7bdf6cf912195452a7`，训练版本仍为1.0.0。

### 确定性与工程验收命令

```bash
.venv/bin/python -m pytest tests/test_generation.py -q -k 'not generated_docker'
.venv/bin/python -m pytest tests/test_generation.py -q -k generated_docker
.venv/bin/python -m pytest tests/test_generation_flow.py -q -k 'not docker'
.venv/bin/python -m pytest tests/test_generation_flow.py -q -k docker
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome npm --prefix frontend run test:e2e -- --grep '自动诊断修复' --reporter=list
npm --prefix frontend run build
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh
```

单独执行结果：旧生成单元21通过/1未选择；旧生成 Docker 发布训练1通过/21未选择；新增 Docker 自动限定修复1通过；浏览器自动诊断修复/预算耗尽/新批次确认/刷新恢复1通过；TypeScript与Vite构建通过（仍有已有的大包提示）。`未选择`只表示定向命令筛选，不计为执行通过；最终全量结果见下方追加记录。

确定性测试包含供应商超时、429退避、鉴权失败、取消迟到回复、未知用量保守记账、重启中断、检查点恢复、契约歧义等待、作用域/期望不可变、输入去重、新批次幂等和忙状态。评测分类路由的单元用受控门禁夹具；它不是实际 Docker 执行证据。实际 Docker 测试使用隔离 mock 角色输出验证工程机制，仍不是模型生成能力证明。

对最终真实失败的人工复核：工具副作用最终矩阵中两个规避均为4个target与3个regression全部通过，故障触发也未成立；工作流最终矩阵中两个规避均为4个target与4个regression全部通过。二者 no_runtime_errors=true，失败不是镜像、依赖、路径或运行异常冒充。现有输出未产生可由独立检查拒绝的错误候选；仅凭检查全通过不能进一步证明它们在全部输入域等价正确，也不能断言测试覆盖完整。门禁继续拒绝发布是正确结果，生成角色的语义纠错质量仍不足。

上述5批累计52次真实请求，供应商 usage 汇总：prompt_tokens=733498、completion_tokens=59641、total_tokens=793139；这三个字段均有返回（0次缺失）。没有把未返回的 reasoning_tokens 推算为0，也未推算货币费用。

### 最终全量结果（已实际执行）

- 首轮 `data/acceptance/run-f7eKjF`：130通过、1失败、0跳过；失败为新增必测项未加入验收脚本自测XML夹具。未把这轮写成验收通过。
- 修复后 `data/acceptance/run-zVfm3y`：**131个后端测试全部通过，0失败、0跳过**，用时226.91秒；`pytest.verified.json` 确认原有18/18 Docker、进阶8/8、生成发布训练及角色自动限定修复均实际执行通过。新增角色协调器测试19项包含在131项中。
- TypeScript类型检查与Vite生产构建通过；有已有的大包体积提示，没有改动打包策略来掩盖它。
- **9个浏览器测试全部通过，0失败、0跳过、0 flaky**，用时71.93秒。包含导航/深链接/草稿隔离、旧题和多文件训练、生成审核发布训练、自动修复→预算耗尽→明确新预算→自动修复到待审核→刷新恢复。生成角色为显著标记的MOCK，执行为真实Docker，不计真实模型修复成功。
- `git diff --check` 通过；`.env`和data未纳入Git跟踪。未创建CI，未发布任何新的真实模型题目。

工程机制验收通过；真实模型修复质量验收未通过。可从 `/generate` 新建角色生成，或打开旧失败记录点击“重新生成（消耗Token）”明确授权新批次；自动检查通过仍须人工审核才能发布。固定四题和原已批准权限任务继续可用。未来更换模型或调整提示仍需独立复验，不能把本轮MOCK成功外推成真实生成可靠性。

验收后 `docker ps -a --filter label=agentlab=true` 无输出，无残留执行容器；真实数据目录无活动生成任务。已关闭专用18000验收服务，按原配置恢复8000后端及现有5173前端：`/generate` HTTP200、agent_mode=real、docker_available=true；最后失败批次刷新读取仍为budget_exhausted/8次请求。此检查没有发起模型调用。

## 契约局部澄清与需求追问（2026-09-18）

本轮实现用户批准的规则：需求明确但契约歧义/转述错误，由契约 Agent 提出局部补丁，再由独立上下文校核；只有原始需求存在无法推定的选择时才询问用户。补丁必须引用原需求、用户澄清或适用的平台默认约束；程序验证原值、契约哈希、字段权限、JSON Pointer 路径及大小。独立校核通过不等于人工发布批准。

每次有效修改产生新契约版本，保存旧契约、确认记录、资产与矩阵引用。为避免局部措辞改变行为而漏验，采用保守兼容方案：重新生成全部下游资产并执行 Docker 验证。已发布资产不可原位改写。契约校核上下文不包含实现、私有故障说明或测试实际结果；契约明确时可在独立依据约束下修正指定测试期望，不允许删除检查、修改无关期望或迎合参考实现。新角色共用现有请求、Token 和执行预算，失败在剩余预算内继续，预算耗尽停止；已完成检查点不重复付费。需求问题、回答草稿、修订审计及状态支持刷新恢复；新预算不能绕过待回答问题。

### 实际执行

```bash
.venv/bin/python -m pytest tests/test_contract_revision.py tests/test_generation_flow.py -q -k 'not docker'
.venv/bin/python -m pytest tests/test_contract_revision.py -q -k docker
npm --prefix frontend run build
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh
.venv/bin/python -m scripts.verify_roles_evidence > data/contract-revision-verification/protected-audit.json
git diff --check
docker ps -a --filter label=agentlab=true --format '{{.ID}} {{.Status}}'
```

- 最新定向确定性回归：35通过、2未选择；单独局部修订 Docker 测试：1通过、17未选择。筛选项不计为通过。
- 全量验收证据 `data/acceptance/run-yShmI0`：后端149通过、0失败、0跳过，246.33秒；验证器确认原有18/18 Docker、进阶8/8、生成发布训练、角色修复及契约修订 Docker 流程均实际通过。
- TypeScript检查与Vite构建通过；保留已有的大包体积警告。
- 浏览器10通过、0失败、0跳过、0 flaky，92.32秒。新增流程覆盖需求追问、草稿刷新、提交澄清、局部修订到v2、重新执行矩阵与刷新恢复；生成角色为显著标识的MOCK，执行为真实Docker。原导航、多文件、提交报告流程也通过。
- 最后的路径schema及提示说明增强发生于全量后端测试加载之后；随后在最终代码上重新执行上述35项定向回归，并进行真实模型成功联调。没有将未执行的重复全量验证计为通过。
- 保护审计通过：三个原始生成记录、已发布包19个文件与修改前完全一致；原人工批准摘要及报告 `f319bd8af6ed4e38b26000f4019484fd` 的快照绑定不变。容器清理检查无残留；`git diff --check` 通过。

### 真实模型局部联调：一次失败、一次成功

按已有配置运行（运行时加载.env，不打印密钥）：

```bash
set -a
source .env
set +a
AGENTLAB_REAL_SMOKE=1 AGENTLAB_DATA="$PWD/data/contract-revision-probe" .venv/bin/python -m scripts.contract_revision_probe
```

执行两次，均在专用数据目录使用构造的“原需求明确包含负数、契约误写忽略负数”场景，不声称复现原先完整生成失败输入。请求模型标识为 `deepseek-v4-flash`，thinking禁用。

1. 首次 `e1c9ebd4c79d4bfd8e28277d69c133ea`：实际1次请求，模型理解正确但返回 `behaviors.sum`，不符合JSON Pointer；程序拒绝并保留原契约。证据 `data/contract-revision-verification/provider.json`。修复为在schema和提示中明确路径格式及例子，没有放宽校验。
2. 第二次 `17c538a550db4217a1e2eed58ed6255b`：实际2次请求，提议与独立校核成功；仅 `/behaviors/sum` 从“只累加正数，忽略负数”改为“返回所有整数的算术和，包括负数”，引用原需求，其他字段不变。保存v2及审计，停在build检查点，不发布。证据 `data/contract-revision-verification/provider-17c538a550db4217a1e2eed58ed6255b.json`。人工检查含义确认是最小、符合原需求的修订，独立校核未把原有排除项扩大或降低标准。

本轮合计3次真实请求，供应商usage合计 prompt_tokens=3709、completion_tokens=608、total_tokens=4317；reasoning_tokens未返回，标记未知。没有保存隐藏推理或估算费用。

### 限制

确定性测试验证程序边界，MOCK浏览器验证流程，真实联调仅验证上述局部提议与独立校核。单例成功不证明语义审查普遍可靠，也不证明之前工具副作用、工作流的完整生成失败已经修复；原失败与预算记录保持不变。本轮未重新生成或发布这些实例。发布仍需人工批准，不把Agent校核当作用户批准。README、ARCHITECTURE.md及docs/GENERATION_FORMAT.md已同步更新。

验收后已按原配置恢复8000后端（真实模型模式）与既有5173前端；只读健康检查返回 agent_mode=real、docker_available=true，`/generate` HTTP200。恢复检查未产生新模型请求。

## 七项生成可靠性优化（2026-09-19）

### 实现范围

1. 本地不可变失败档案与追加复验，原始数据和后续尝试分离；人工最小脱敏夹具进入 `tests/fixtures/generation_regressions/`，完整需求/代码/执行留在忽略Git的data目录。
2. 诊断声明证据充分性、缺失证据与对应检查/行为；证据不足只能先补契约内覆盖，不能直接改实现或契约。当前检查ID显式列出，历史诊断只保留路由摘要。
3. 持久化逐轮资产/结果摘要、解决与新增问题、反例、用量；相同资产和镜像复用完整证据但标记复用。连续无进展切换根因审查，仍无进展进入no_progress，保留剩余预算；新批次须明确授权。新契约不继承旧停滞计数。
4. 规避反例关联同一输入的正常版/参考通过及候选行为失败、正常回归、无运行错误；名称和异常不算证明。新矩阵有独立反例门禁。输入域及期望的自然语言含义仍须作者审查，不能用程序比较冒充语义证明。
5. 契约校核逐补丁检查六种行为影响与需求引用；无依据的改变不可批准，旧证据保留，下游重新验证。
6. 前端分别显示实际供应商已知用量、缺失次数、预算记账、剩余请求及逐轮进展；无进展结束可见，不自动重开付费批次。
7. 作者摘要直接展示需求/约束、文件/故障、参考改动文件及代码、执行反例与可定位证据、范围/问题、批准绑定。私有内容不进入训练API/Agent；摘要变化清空旧勾选，发布端继续重算绑定。旧冻结摘要算法不改。

### 回归档案与实际重放

```bash
.venv/bin/python -m scripts.generation_regressions archive 71a94a226ec742c5b778ae9b39997193
.venv/bin/python -m scripts.generation_regressions archive 17683c1deb9c4bd4aea75279524205b4
.venv/bin/python -m scripts.generation_regressions replay 99a4100c4e4308cfbc6d0c108fb3e2e9aec47457af5e9cd5f4a4bd086538c4b9
.venv/bin/python -m scripts.generation_regressions replay 2b7851019ff4520f38121e09bf8e0ffcd81a7c2c71a8c7e7e6f4a1ff0d92fb08
```

两次重放均在实际Docker中完成，所有原门禁结果与原档案一致，no_runtime_errors=true；不是依赖、镜像、加载或路径错误。工具案例fault_trigger=false、evasion_rejected=false；工作流fault_trigger=true、evasion_rejected=false。新重放记录分别为 `6135862f0e2b46f2b4187b46fa3371e0`、`3d6db88fed08446bac9d520fd7663fda`。原任务记录没有被覆盖。

以前真实契约修订的非法点号路径案例 `e1c9ebd4c79d4bfd8e28277d69c133ea` 也从其隔离数据目录归档；集中副本案例为 `9bd48f707f28d3b1abd634c5babefbcbe4e27b6772ff6d6a0ab18421cd37e156`。它是格式拒绝证据，缺少完整可执行资产，不能当成Docker重放成功；最小路径拒绝由确定性测试执行。三个集中档案都通过摘要校验。

### 工程验证与中间问题

```bash
.venv/bin/python -m pytest tests/test_generation_reliability.py tests/test_generation_flow.py tests/test_contract_revision.py -q -k 'not docker'
.venv/bin/python -m pytest tests/test_generation_reliability.py -q
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh
.venv/bin/python -m pytest tests/test_generation_reliability.py tests/test_contract_revision.py tests/test_generation_flow.py -q
```

- 初次构建发现新增摘要JSX缺少括号，已修复；契约回归初轮33通过、2失败，原夹具未提供新增语义审查字段，补齐夹具后通过，未放宽保护。
- 第一阶段相关确定性回归44通过、2未选择。随后新增模块10项含真实Docker全部通过。
- 全量 `data/acceptance/run-XqGbKy`：**162通过、0失败、0跳过**，266.60秒；验收验证器确认原18/18 Docker、进阶8/8、生成发布训练、自动修复、契约局部修订及新增归档/同资产复用测试实际执行。
- 该轮 TypeScript/Vite 构建通过，仍有原大包提示；浏览器 **11通过、0失败、0跳过、0 flaky**，108.11秒。包含新增失败证据/无进展结束/作者摘要/刷新及失败不可发布；MOCK只验证模型流程，实际执行使用Docker。
- 之后补充新契约停滞隔离、归档符号链接保护两项及最终证据标识；在最终相关代码上 **52项回归全部通过**，68.41秒，包含三个相关Docker流程。没有把全量162描述成最终164项全量重跑。

### 真实模型复验：三批均未达到发布条件

运行前仅通过shell加载现有.env，不输出密钥。每批为新记录，不更改原始失败案例；最多8/8/4次请求，48000输出记账Token、350000输入字节、900秒活动时间、5轮验证上限，没有无限追加预算。

```bash
set -a
source .env
set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.generation_regressions repair 99a4100c4e4308cfbc6d0c108fb3e2e9aec47457af5e9cd5f4a4bd086538c4b9 --requests 8
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.generation_regressions repair 2b7851019ff4520f38121e09bf8e0ffcd81a7c2c71a8c7e7e6f4a1ff0d92fb08 --requests 8
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.generation_regressions repair 2b7851019ff4520f38121e09bf8e0ffcd81a7c2c71a8c7e7e6f4a1ff0d92fb08 --requests 4
```

| 新记录 | 实际请求 | 新矩阵 | 实际结果 |
|---|---:|---:|---|
| 7147f4fe2ff24225b8a6cae157b7dddc（工具） | 4 | 1 | 补覆盖后规避检查有执行反例，正常/参考及回归通过；fault_trigger仍false。后续两次诊断误引检查ID，输入字节预算不足结束。 |
| 06293ac95b4144b7b10c6bf121c2354f（工作流） | 5 | 0 | 证据不足却请求改实现的路由矛盾，与错误ID交替出现，被程序拒绝；输入预算不足结束。 |
| 13fd0569aa174c58beef3b1524394c56（工作流，收紧ID后） | 4 | 0 | 未再出现错误ID；一次诊断有效进入补覆盖，但评测返回无变化被拒绝；请求预算耗尽。 |

新矩阵为0的批次仍引用来源档案矩阵，不能声称这些旧结果验证了本批新修复。汇总为 `data/reliability-v2-verification/real-summary.json`，人工含义检查为同目录 `manual-quality-review.json`；每个案例attempts目录保留完整复验摘要。模型请求标识为deepseek-v4-flash；本轮13次请求，供应商返回prompt_tokens合计236305、completion_tokens合计15356、total_tokens合计251661；字段均有返回，reasoning_tokens未返回为未知，不估算费用。

人工检查发现：工具案例中不同operation_id使用相同接收方/正文的反例有明确operation_isolation依据；另一个“首次出现is_retry=true”的检查虽符合结构范围，但与retry_detection中“已有逻辑操作”的语义关系仍需澄清。基线通过不能自动认可该期望，未给予发布批准。工作流的没有新反例不能证明规避在全部输入域正确，也不能证明不存在合法反例。

因此，本轮完成的是证据、诊断约束、停滞控制与审核机制，不是证明真实生成成功率已提高。旧两类失败仍未整体解决，模型诊断路由与独立评测的语义质量仍是限制；没有改期望迎合实现，没有删除门禁，没有发布新真实任务。自然语言输入域和语义校核仍依赖模型及作者审查，不是形式验证。

### 最终浏览器复验与保护检查

```bash
npm --prefix frontend run build
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/reliability-v2-verification/browser-final.json" npm --prefix frontend run test:e2e -- --reporter=list,json
.venv/bin/python scripts/verify_acceptance.py browser data/reliability-v2-verification/browser-final.json
.venv/bin/python -m scripts.verify_roles_evidence > data/reliability-v2-verification/protected-audit.json
git diff --check
docker ps -a --filter label=agentlab=true --format '{{.ID}} {{.Status}}'
```

最终生产构建与类型检查通过；最终浏览器11通过，0失败/0跳过/0 flaky，107.88秒，证据验证器通过。保护检查确认三条原始任务记录、已发布19个文件及旧报告快照完全不变。Git未跟踪.env或data；没有新增CI。Docker清理检查无残留执行容器，临时验收后端已关闭。真实联调均已终止，无自动追加预算或发布。

已恢复原8000后端与既有5173前端；只读检查返回agent_mode=real、docker_available=true，`/generate` HTTP200。恢复检查没有发起模型调用。

## 用户要求回退七项优化中的前五项（2026-09-19）

回退自动失败回归集、新增证据充分性路由、停滞检测与相同资产矩阵复用、额外规避反例门禁、六维契约语义校核。保留第六项成本/进度与第七项作者摘要展示，并继续保留更早的有界角色调度、局部契约补丁、独立校核、需求追问、Docker执行、提示与历史快照语义。此前关于七项优化的验证记录是历史记录，不代表前五项仍启用。

具体移除自动归档模块/CLI/最小案例目录内的专用JSON夹具；本地data档案和所有原始资产不删除，回退前相关源码备份在 `data/rollback-first-five/source-before/`。展示辅助模块不再影响生成决策；作者摘要改为按版本展示已有执行结果，不计算额外反例门禁。新任务不写reliability_version，旧字段只读兼容。

历史no_progress记录允许显式恢复剩余预算，从diagnosis继续；没有自动启动任何用户旧任务。恢复旧协议记录时清除临时的已撤回schema纠错提示，但保留failure_history和attempts。历史已完成contract_check的impact_checks扩展仍可读取，不再强制提供它。独立校核本身没有撤回，所以不能保证所有契约歧义循环因此消失。

已实际执行：

```bash
.venv/bin/python -m pytest tests/test_generation_reliability.py tests/test_contract_revision.py tests/test_generation_flow.py -q -k 'not docker'
npm --prefix frontend run build
.venv/bin/python -m pytest tests/test_generation_reliability.py -q -k 'not docker'
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh
```

定向回归42通过、3未选择；补充旧格式提示兼容后7通过、1未选择；未选择项不算执行通过。构建/类型检查通过，保留已有的大包警告。新的回退测试替换已撤回机制的测试，检查预算终止而非停滞终止、旧记录恢复、不再增加门禁、不缓存矩阵、无自动归档、保留局部契约校核与展示隐私边界。完整验收与浏览器复跑结果见下文。

本轮未发起真实模型请求，未发布新任务，不以MOCK验收宣称生成率提高。

数据保护核对通过：最近用户创建的4条生成记录哈希完全不变，46个本地失败档案/发布文件完全不变；较早的三条原始生成记录、已批准包19个文件和旧报告快照也通过原保护审计。证据为 `data/rollback-first-five/protected-after.json` 与 `earlier-protected-audit.json`。`.env`与data没有被Git跟踪，`git diff --check`通过。

### 回退后的完整验收与浏览器失败记录

`./scripts/acceptance.sh` 的本次证据目录为 `data/acceptance/run-jQUc0h`。后端 **157通过、0失败、0跳过**，284.53秒；证据校验确认原18项Docker、进阶8项Docker、生成发布训练、角色修复、局部契约修正及回退专项Docker均实际执行通过。TypeScript/Vite构建通过。

首次浏览器为 **10通过、1失败、0跳过**，110.20秒，因此本次整套脚本退出1，不能记为整套通过。失败是多文件流程在点击 ingestion.py 后标题仍为 pipeline.py，5秒等待超时；发生在该流程编辑和执行之前。训练文件切换实现本轮未修改。错误现场保留为 `data/rollback-first-five/first-browser-failure.md`。

使用相同测试原样复跑（没有添加自动重试、修改断言或延长等待）：

```bash
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/rollback-first-five/browser-versioning-recheck.json" npm --prefix frontend run test:e2e -- --grep '进阶多文件 Docker' --reporter=list,json --trace=on
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/rollback-first-five/browser-final.json" npm --prefix frontend run test:e2e -- --reporter=list,json
```

单项复跑 **1通过**，24.6秒，实际完成多文件编辑、保存、Docker执行、提交、提示快照与刷新恢复。首次超时没有稳定复现，根因未确认，不声称已修复此偶发问题。

最终完整浏览器复跑 **11通过、0失败、0跳过、0 flaky**，109.95秒；`scripts/verify_acceptance.py browser data/rollback-first-five/browser-final.json` 校验通过。没有修改训练文件切换代码或加入测试重试来获得通过。此结果不抹去首次失败，也不证明偶发超时已解决。

`docker ps -a --filter label=agentlab=true --format '{{.ID}} {{.Status}}'` 无残留执行容器。已恢复正常8000后端及既有5173前端；只读检查 agent_mode=real、docker_available=true、/generate HTTP200。恢复服务未触发模型请求。

## 分离故障指纹、检查分类与修复调度（2026-09-19）

### 根因复核与实际改动

对3c0efb715d084149912ed06ecc0f79e8及dfa88272fdfa4805a34b74a164386bf2的48次调用只读审查：全部HTTP200且正文非空，非供应商连接问题。初始完整故障JSON指纹与私有故障设计不一致，且触发重试故障的场景误标regression。诊断将faulty_expected修复误选expectation，平台反复契约校核再回到相同无效修复。详细审查在data/analysis/latest-generation-review-20260919.md。

新建记录启用separated-evidence-v2；已有记录不迁移。独立正确性评测不再生成故障输出；单独有界调用根据冻结私有故障设计及候选目标输入生成JSON路径/equals故障断言。执行前冻结、匹配正确期望即拒绝，实际正常/参考不得命中；故障需重复执行稳定命中。新门禁仅适用于新协议，原六项及Docker边界保持。新评测修复采用哈希、旧值、动作与字段范围受控的补丁；classification与expectation不得互改、追加需单独授权。相同已明确契约不重复进入expectation契约审查；诊断上下文明确fault_regression不由fault_match决定，并给每个规避的实际门禁证据。中断恢复补充完成资产的确定性收尾。前端显示响应格式、诊断拒绝、补丁拒绝、供应商类别，“资产校验通过”不表示最终验收。

### 确定性与实际Docker验证

```bash
.venv/bin/python -m pytest tests/test_generation.py tests/test_generation_flow.py tests/test_contract_revision.py tests/test_generation_reliability.py -q -k 'not docker'
.venv/bin/python -m pytest tests/test_generation_protocol.py tests/test_generation.py tests/test_generation_flow.py tests/test_contract_revision.py tests/test_generation_reliability.py -q -o junit_family=xunit1 --junitxml=data/repair-protocol-verification/generation.xml
.venv/bin/python -m pytest tests -q -o junit_family=xunit1 --junitxml=data/repair-protocol-verification/pytest-final.xml
npm --prefix frontend run build
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/repair-protocol-verification/browser-final.json" npm --prefix frontend run test:e2e -- --reporter=list,json
.venv/bin/python scripts/verify_acceptance.py pytest data/repair-protocol-verification/pytest-final.xml
.venv/bin/python scripts/verify_acceptance.py browser data/repair-protocol-verification/browser-final.json
.venv/bin/python -m pytest tests/test_generation_protocol.py tests/test_generation_flow.py -q -k 'not docker'
.venv/bin/python -m pytest tests/test_generation_protocol.py tests/test_diagnostics.py -q -o junit_family=xunit1 --junitxml=data/repair-protocol-verification/protocol-final.xml
```

- 初始兼容定向63通过、4未选择；生成完整定向73通过，157.68秒，包括新旧协议实际Docker。
- 新测试首次4通过1失败：测试夹具直接调用完成后未将状态恢复interrupted，触发“此生成正在执行”。修正测试夹具生命周期，未放松生产并发控制；复跑通过。
- 全量后端 **165通过、0失败、0跳过**，357.64秒。验证器确认原18项、进阶8项、生成发布训练、自动修复、契约修订、旧回退兼容及新协议分类补丁Docker实际执行通过。
- 类型检查和Vite构建通过，保留已有大包警告；浏览器 **11通过、0失败、0跳过、0 flaky**，132.51秒。覆盖新协议生成审核发布训练恢复、私有指纹不进入公开API、失败类型展示、原三导航/多文件/报告/提示。发布是MOCK自动化表单测试，不作为真实人工批准。
- 最后补充每个规避的实际证据摘要后，定向 **26通过、2未选择**；调整故障断言校验在矩阵创建前完成并加入验收证据要求后，最终定向 **18通过、0跳过**，38.84秒，含实际Docker。最终共有166个测试，但不声称166项全量重跑；165项全量与最后变更的定向验证分开记录。

### 真实模型联调：保留两次失败，不自动发布

```bash
set -a
source .env
set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.repair_protocol_probe
```

修复提示前后各执行一次上述命令。脚本只读原已确认契约与私有故障设计，在data/repair-protocol-verification/real-isolated创建新记录；不重新调用需求设计，不修改原始两批记录，不发布。每批12次请求、64000输出记账Token、450000输入字节、600秒、5轮验证上限。供应商实际模型标识deepseek-v4-flash，thinking disabled；未读取或打印密钥。

|新记录|调用|实际验证|结果|
|---|---:|---:|---|
|6563a569ec8a4193b3e892c32658584b|12|0|构建和独立评测完成；10次故障断言被拒绝，原因是命中正确期望或引用不在私有设计中。请求耗尽，未进Docker。|
|1618b334d0f84fa98d85c952a4472ae3|12|3轮|首次故障断言通过；模型正确诊断并用字段补丁修复分类，重跑后fault_regression通过。随后规避修复变成正确实现，诊断又反复选择已被识别的另一规避，被程序拒绝，请求耗尽。|

第一次暴露新提示不够明确：故障角色看到完整正确期望，且未明确只选择真正触发故障的目标输入。改为仅给目标输入、不含正确期望；明确描述修复前错误状态，引用私有故障原文，反馈包含具体错误检查。没有放松断言必须区分正常/参考的门禁。第二次后的规避证据上下文补强仅做确定性回归，未再追加第三批真实请求。

供应商实报usage：首批prompt35261/completion11239/total46500；第二批prompt88399/completion7739/total96138，合计142638 Token。reasoning_tokens未返回，不估算费用。元数据与每次失败分别保存在real-<实例ID>.json；所有调用资产及矩阵在隔离数据库目录。

人工含义检查（不是发布批准）：第二批指纹只检查原故障设计所述的空注册和错误ready；分类补丁将backend_ready_after_attempts=2的顺序检查从regression改target，原输入与正确expected完全保持，依据是该输入确实触发一次拉取故障。矩阵557881ac1e4e4e1192a446ca982440fa→5d5fd4d5230341eb889c4cf3dde2da23→202ef3349cec4389adbeeb0779db6aa0分别记录初始、分类修复、规避修复；最终normal/reference/fault_trigger/fault_regression/no_runtime_errors/fingerprint_discriminates通过，evasion_rejected失败。不能把第二批描述为整题生成成功，也不代表所有领域的成功率已提高。

### 数据保护与限制

保护基线核对 **218条原数据库记录、19个已发布文件全部不变**，证据protected-before.json/protected-after.json。没有迁移历史快照或失败记录，没有自动发布；新协议仅用于新创建生成记录。自然语言引用存在性与补丁权限不是语义正确性的形式证明，契约、分类、预设故障含义及教学材料仍需作者审核；规避生成与模型诊断质量仍有真实失败。当前真实联调仅复用已确认的一个场景契约，不算三个领域或从需求设计到发布全链路的真实成功。

最终清理检查无agentlab执行容器残留。正常8000后端已加载新代码恢复，既有5173前端可用；只读检查agent_mode=real、docker_available=true、/generate HTTP200，未触发模型请求。

## 2026-09-19 合并契约与构建：direct-build-v1

本轮只将新任务的规范设计并入项目构建，保留独立评测、故障复现检查、失败诊断与教学阶段。新建API不再调用design，也不等待用户确认技术契约；内部公开规范仍版本化保存，独立可验证性审查后自动冻结。旧生成记录、四道固定任务、已发布实例及训练证据保留原语义。没有新建真实发布实例。

### 实现与失败修复

- 一个构建上下文输出公开规范及正常、故障、参考、规避项目；独立spec_review不读取实现或私有故障，检查输出字段的公开判定规则。平台设计缺项退回构建，只有用户目标歧义才提出问题。
- 局部补齐只准修改指出的公开字段，归档旧规范/资产/矩阵，使下游测试、指纹和教学失效并重新验证。独立审查记录不是人工发布批准；审核摘要绑定Bundle与审查资产。
- 评测修复可明确返回specification_issue或reject_plan，不再被迫提交无变化补丁；保留旧检查并回到对应审查/诊断。已完成构建、审查与评测拒绝结果可以从持久化检查点继续，避免重复模型调用。
- 初次定向8项测试为7通过1失败，全量为173通过1失败：MOCK共享可变规范对象，局部补齐同时改了比较基准，误报“无变化”并耗尽预算。修复为深拷贝角色上下文，匹配真实请求的序列化隔离。修复后定向8项全部通过；初次全量XML保留为pytest-before-fixes.xml。
- 初次真实探测在请求前被适配器拒绝：合并阶段设16000Token，超过既有12000上限。改回12000，不扩大报告或模型适配器预算；新增预算边界回归。
- 真实响应暴露数组路径和多分支规则协议不清晰：输出规则允许同字段多分支引用，仍必须覆盖全部且不能出现未知路径；错误提供具体缺失/未知路径。局部补齐错误返回未授权字段清单，提示明确受支持的JSON schema子集。没有放宽实际行为门禁。

### 实际命令

```bash
.venv/bin/python -m pytest tests/test_generation_direct.py -q -o junit_family=xunit1 --junitxml=data/direct-build-verification/direct.xml
.venv/bin/python -m pytest tests -q -o junit_family=xunit1 --junitxml=data/direct-build-verification/pytest-final.xml
npm --prefix frontend run build
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/direct-build-verification/browser-final.json" npm --prefix frontend run test:e2e -- --reporter=list,json
.venv/bin/python scripts/verify_acceptance.py browser data/direct-build-verification/browser-final.json
```

浏览器使用隔离MOCK数据及真实Docker：11通过、0失败、0跳过、0 flaky，110.01秒。包括直接构建→独立评测→人工审核表单（MOCK自动化，不作为实际人工批准）→发布→训练→真实Docker提交→报告刷新；检查没有契约确认按钮、没有design调用、存在独立规范审查。旧契约局部修订、四题训练、多文件、三导航、报告失败与安全Markdown回归也通过。类型检查和Vite构建通过；保留已有大包警告。

全量后端最终结果见本节末尾，不能把前一次失败退出或跳过当作通过。

### 真实模型探测：未完成整题生成

```bash
set -a
source .env
set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.direct_build_probe
```

三次均在data/direct-build-verification/real-isolated使用同类原始需求“Agent 启动时后端未就绪，导致空工具注册”，不复制之前已确认契约，不手动确认技术规范，不写生产训练数据，不发布。每批上限12请求、64000输出记账Token、450000输入字节、600秒、5轮验证。供应商deepseek-v4-flash、thinking disabled；未读取或输出密钥内容。

|记录|实际结果|
|---|---|
|b594e85753494d29b774fda01e56040a|4次适配器调用均因本地预算校验失败，未发供应商请求；缺失usage按保守预留计费额度，随后预算耗尽。不算真实模型联调。|
|4d5715dc75724a8c8e0cd377afde0a8c|12次真实请求。构建先使用不支持的minimum/maximum被拒；纠正后独立审查要求补齐探测次数/时序等规范。4次擅改非指定字段被拦，之后成功局部补齐；审查输出路径/重复规则问题耗尽余下请求，未进Docker。|
|315d44bb39384eb3af0a9563ee478df4|12次真实请求。构建前两次给出概要而非源码，类型/语法检查拒绝；第三次完整构建通过，独立审查通过并自动冻结规范，无用户确认。独立评测8次未通过：遗漏determinism行为覆盖，另有11项超出10项上限、缺公开/隐藏目标、检查ID过长等格式问题。预算耗尽，未进Docker。|

第二批供应商实报prompt47175/completion39197/total86372；第三批prompt24410/completion28239/total52649，合计139021Token。reasoning_tokens未知，不推算费用。每次调用的脱敏元数据、错误和阶段输入输出保存在real-<记录ID>.json及隔离任务资产；第一批无供应商usage，不填造实际0Token用量。

人工含义复核不是发布批准：第二批指出探测次数计数与探测时刻规范不足确有依据，但将schema已限定字符串元素的非字符串情形也列为问题，说明审查仍可能过度要求；第三批模型确实根据同一规范构建各版本并交给不读实现的独立评测，未需要用户确认。程序检查覆盖映射不等于已证明确定性或语义正确；没有执行矩阵就不声称项目正确、故障复现成功或合并后生成率提高。没有为获得成功降低门禁或追加无限预算。

### 数据与服务

核对原219条数据库记录和19个已发布文件：全部哈希不变，证据protected-before.json/protected-after.json。浏览器前检查没有活动生成、执行、报告，暂停正常后端后使用隔离数据；结束后恢复正常配置后端，/api/health显示agent_mode=real、docker_available=true。未触发生产模型请求。真实生成到训练的闭环本轮仍未完成；MOCK全链路只能证明工程机制。

最终全量后端 **177通过、0失败、0跳过**，352.79秒；Starlette/anyio弃用警告保留。`scripts/verify_acceptance.py pytest data/direct-build-verification/pytest-final.xml`逐项核对通过：原13项/全部18项Docker均实际执行，进阶8项及生成发布、自动修复、旧契约修订、回退、指纹协议、合并构建Docker流程全部执行通过。最后仅修正新版本分支的“无需确认”说明，重新定向执行 `tests/test_generation_direct.py`：**11通过、0跳过**，20.99秒（direct-final.xml）。前端类型构建与浏览器结果如上，没有把MOCK算作供应商验证。最终 `docker ps -a --filter name=agentlab` 无执行容器残留，`git diff --check` 通过。

## 2026-09-19 执行前评测纠错修复（最小范围）

依据最近失败记录d7bf5d8786804d9ebf529a2e319bca90：22次评测全部遗漏determinism覆盖，20次报笼统覆盖错误、2次先报公开/隐藏目标缺失，未进入Docker。保留原始实例与资产。

本轮修改：覆盖错误列出缺失行为及已有case映射；失败候选保存为非正式rejected.json，只反馈给原评测角色。首次执行前连续两次资产校验失败复用现有spec_review，审查只看覆盖/分类元数据，判断补检查或局部补规范，不读取隐藏输入/期望/代码。没有新增角色、预算、自动批准或提前停止策略。新批次复制候选引用，中断沿用原检查点。

为避免只补determinism标签就声称验证完成，direct-build-v1所有生成检查均做两次独立Docker调用，记录两份结果及一致性；重复运行错误仍是error。发布检查冻结repeat_count=2，训练实际执行并保存一致性证据；历史已发布题没有此字段，不修改。诊断收到第二次结果，报告重复不一致时不显示误导性的“期望与首次实际相同”。每调用隔离/超时及总预算不变，执行开销增加；两次样例一致不证明全域确定性。

实际执行命令：

```bash
.venv/bin/python -m pytest tests/test_generation_direct.py tests/test_generation_protocol.py -q
.venv/bin/python -m pytest tests -q -o junit_family=xunit1 --junitxml=data/preflight-verification/pytest.xml
.venv/bin/python -m pytest tests/test_generation_direct.py -q -o junit_family=xunit1 --junitxml=data/preflight-verification/direct.xml
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/preflight-verification/browser.json" npm --prefix frontend run test:e2e -- --grep '生成审核发布及 Docker' --reporter=list,json
```

首轮定向22项通过，77.87秒。浏览器定向1项通过、0跳过，57.1秒：MOCK生成→人工审核表单自动化→发布→真实Docker训练提交→报告刷新；不能算真实生成质量或真实人工批准。本轮没有前端源码变化，没有重跑全量浏览器或前端构建。最终后端结果见本节末尾。

### 原失败资产的真实复测

```bash
set -a
source .env
set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.preflight_probe
```

新隔离记录42ecf600380f4411bf32cfe59b9774e0，复制原失败记录的公开规范、各项目版本与最后评测候选，**没有重新生成需求或规范**。上限8请求、40000输出记账Token、300000输入字节、600秒、3轮矩阵；不发布，不改变原记录。

- #1独立评测直接通过：原来遗漏覆盖的阻塞已解除，不再重复22次相同错误。
- #2故障断言使用整数数组下标而协议要求字符串，被校验拒绝；#3纠正通过。
- 实际矩阵86ec9aca70244257b415c2a33f629afc：40项检查，各两次独立执行。normal/reference/fault_trigger/no_runtime_errors/fingerprint_discriminates通过；fault_regression/evasion_rejected失败。
- #4诊断、#5构建修复执行；重新运行矩阵a4d6925a873f400d82501a4f92bed434，仍为相同两项门禁失败，40项各两次。#6诊断后，#7、#8修复未改变代码，被既有校验拒绝，8请求预算耗尽。

因此本轮证明**原评测覆盖阻塞得到解除并实际进入执行验证**，不代表整题生成成功。后续模型分类/规避修复质量仍有问题，没有迎合实现改期望、接受假规避或为成功追加预算。本次没有触发真实spec_review回退分支，该分支由确定性回归验证；不把MOCK分支测试描述为真实模型诊断成功。

供应商实报prompt67012/completion7824/total74836Token，未打印密钥或隐藏推理；缺失推理用量不推算。隔离调用与矩阵保存在data/preflight-verification/real-isolated及real-42ecf600380f4411bf32cfe59b9774e0.json。

最终全量 **180通过、0失败、0跳过**，407.84秒；验收脚本逐项确认原13/全部18项Docker、进阶8项及全部生成协议Docker流程均实际通过。最终定向14项通过，47.39秒，特别核对重复执行证据进入提交报告及诊断。最后补充畸形候选ID脱敏，定向3项通过、11未选择，1.39秒；沙箱内首次运行无输出被终止，获准使用既有测试权限环境重跑通过，不把被终止测试算成功。Starlette/anyio弃用警告保留。

生产220条原记录、19个已发布文件哈希全部不变（protected-before/after.json）。`git diff --check`通过，Docker无执行容器残留。正常后端已恢复，health为real模型模式、Docker可用；不会自动重试原失败实例或发布新题。

## 2026-09-20 三角色合并及唯一一批真实测试

新建任务启用consolidated-v1：项目构建统一承担project_build/repair_build；评测统一承担spec_review/evaluation/fingerprint/diagnosis；教学承担teaching。保留阶段输入构造、阶段预算与上下文隔离：测试不看实现，指纹不看实际输出，失败分析可见当前实现及矩阵。不是三个自主聊天的进程，也不是把完整上下文合并成一份。学习者辅导与报告不改，历史记录保持原策略。

除统一角色注册、共享职责提示、audit role_id/role_policy与前端说明外，构建修复使用程序生成的工单指定矩阵、目标及各版本保持条件；诊断不再携带前两份诊断与旧失败正文，加入冻结故障设计和当前failed_gates，移除重复一致输出的副本，旧记录保留审计。这些调整减少职责和执行指令歧义，不保证模型解释一致或修复成功。自由文本仍可矛盾，但不会成为第二套修改权限；实际正确性依赖执行门禁。

### 实际验证与中间问题

```bash
.venv/bin/python -m pytest tests/test_consolidated_roles.py tests/test_generation_direct.py tests/test_generation_protocol.py tests/test_generation_flow.py -q -o junit_family=xunit1 --junitxml=data/consolidation-verification/pytest.xml
npm --prefix frontend run build
AGENTLAB_REUSE_SERVER=1 AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome PLAYWRIGHT_JSON_OUTPUT_FILE="$PWD/data/consolidation-verification/browser.json" npm --prefix frontend run test:e2e -- --grep '生成审核发布及 Docker' --reporter=list,json
.venv/bin/python -m pytest tests/test_consolidated_roles.py -q
```

- 相关后端回归45通过、0跳过，124.66秒，包括实际Docker生成/修复/提交及历史流程兼容；新增三项专门检查角色归属、阶段隔离、最新证据与构建工单。没有声称全量183项重跑。
- 前端TypeScript/Vite通过，保留已有大包警告。
- 首次浏览器失败：公开阶段接口过滤了新role_id/role_policy，数据库与模型调用正常。补充这两个非敏感字段，定向3项回归通过，1.19秒。
- 第二次浏览器在刷新初始化尚未完成时点击报告，随后初始化将标签重置到测试证据。调整测试等待“保存”按钮可用再操作，没有改动训练产品代码；过早交互的既有竞态仍属限制。两次失败JSON分别保留browser-before-fix.json和browser-refresh-race.json。
- 最终浏览器定向1通过、0跳过、0 flaky，48.2秒：MOCK生成→角色归属检查→自动化审核表单→发布→真实Docker训练→提交报告→刷新恢复。MOCK发布只验证系统流程，不是实际人工批准，不算真实模型生成成功。未重跑全量浏览器。

### 一批真实模型测试（没有为了成功重开第二批）

```bash
set -a
source .env
set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.consolidation_probe
```

实例81777a84e57d40c2b6748dc2007e8303；需求“Agent 启动时后端未就绪，导致空工具注册”，15分钟、偏低难度。从需求开始生成，不复制旧契约或实现；隔离数据目录data/consolidation-verification/real-isolated，不修改生产记录、不发布。预算保持默认24请求、96000输出记账Token、600000输入字节、1200秒、10轮矩阵。

结果：**生成失败，输入预算耗尽**。20次真实请求全部HTTP200，输出未因length截断；供应商实际usage prompt148889/completion27470/total176359Token，推理用量未返回，不推算。输入已用557940字节，下次需要69530，超过600000；输出记账27470，活动299.20秒。实际执行**3轮**矩阵，每轮40项，每项两次独立Docker调用。中间口头更新曾误报4轮，此处按持久化记录纠正为3轮。

阶段与原因：

1. #1构建返回文件说明而非源码映射，被拒；#2构建完成。#3规范审查要求明确超时边界、日志及工具选择优先级；#4补齐擅改未授权字段，被拒；#5局部补齐完成，#6审查通过。
2. #7评测缺少公开/隐藏目标组合，被拒；#8纠正并完成，#9故障指纹一次通过。
3. 首轮矩阵eec9f6eea1304b35b2d7dcac919073ca：normal/reference/fault_trigger/no_runtime_errors/fingerprint_discriminates通过，fault_regression/evasion_rejected失败。未出现上次把故障版修成正常版的情况。
4. 核心不一致：私有故障设计规定registered恒为空、没有就绪轮询，保留的只是日志开头、诊断格式等字段级行为；两个regression却要求完整JSON符合正常启动或正常超时：ready_after=0需要注册3工具，超时需要waited=1000ms及完整超时日志。故障版均不能通过。不是简单给已有失败检查改标签就能解决，需要构建可保留完整回归场景的故障，或先明确可验证的设计范围并重验，不能降低正确期望。
5. #10/#12等评测分析优先修改fixed_sleep规避；#11/#13的代码改动后，6da23980e4d6437b8887f4a37608a09c与d8a457dce21b49269959e29a18420c85两轮矩阵仍为相同两项门禁失败。fixed_sleep固定等待一个poll，ready_after=0的回归仍输出waited=100ms而非0；try_except仍与故障版一样不能通过回归。
6. 后续修复4次返回未变化代码（#15、#16、#18、#20），被平台拒绝。说明文字声称ready_after=0回归通过，但没有执行证据支持。评测反复聚焦fixed_sleep，没有解决fault_regression，也没有改善另一规避。#19结构化目标仍为fixed_sleep，文字却建议try_except；构建工单仍只授权fixed_sleep，没有被文字扩大权限。此处说明语义矛盾仍存在，角色合并本身不是纠错能力保证。

三个完整矩阵均有真实一致性证据；没有接受模型自报成功，没有降低门禁，没有发布。角色合并与去除旧诊断并未在这一个案例上带来整题成功；不能据单次试验判断生成率升降。本次没有到达真实教学、发布或训练报告阶段。

### 保护与剩余限制

原221条数据库记录及19个已发布文件哈希全部不变，protected-before/after.json可核对。正常后端恢复最终代码，不自动重试旧失败记录。没有额外新增Agent、CI或训练功能。角色归属/上下文隔离/工单权限已验证，故障设计可验证性、回归分类和模型反复给无效代码仍有局限，不能把自动资产校验或MOCK闭环当作真实题目质量已获证明。

## 2026-09-20 入口返回协议与结构化执行诊断（仅方案前两项）

根因：构建上下文原先只说“返回 JSON”，没有区分 Python 返回值与 JSON 传输文本；生成验证将程序 error 和输出 schema 不符统一记成笼统错误。此次统一旧 build、新 project_build 与 repair_build 的入口约定：返回契约对应的 Python 值，序列化由平台完成一次。合法 string 契约不受影响，未增加自动解码补救。

新增可选诊断记录：schema 首个错误路径/期望类型/实际类型/原因，程序异常类型（不可信来源、位置 unknown），JSON 协议错误、输出上限、超时秒数、Docker CLI 缺失/权限错误和容器退出码。仅凭退出码不能确认环境根因，125/126/127 只标记可能启动失败。行为不符记录首个差异路径和类型，原 actual/expected 继续留在作者矩阵。诊断随原检查 ID、版本、快照持久化；失败分析可读取，构建修复只读取公开反例，公开矩阵及训练上下文不新增私有数据。历史记录不迁移，镜像/worker、容器隔离参数、调度、预算、门禁不改。

中间验证记录：
- 沙箱内 `.venv/bin/python -m pytest tests/test_execution_diagnostics.py -q -k 'not real_docker'` 输出前五项后卡住，已终止该测试进程；不计作通过。随后在可用 Docker 权限环境运行。
- 首轮针对性回归命令同下（XML 为 `pytest.xml`）：31 passed、4 failed。新增 OSError 捕获误包裹其子类 TimeoutError，导致超时变为通信错误；已修正为保留已分类异常及原 TimeoutError 类型。
- 定位命令 `.venv/bin/python -m pytest tests/test_execution_diagnostics.py tests/test_executor.py -x -q`：11 passed、1 failed，确认同一超时分类问题。

最终回归命令：
```bash
.venv/bin/python -m pytest tests/test_execution_diagnostics.py tests/test_executor.py tests/test_consolidated_roles.py tests/test_docker_acceptance.py -q -o junit_family=xunit1 --junitxml=data/entry-diagnostics-verification/pytest-final.xml
git diff --check
.venv/bin/python -m compileall -q backend/execution_diagnostics.py backend/executor.py backend/generation.py backend/generation_roles.py tests/test_execution_diagnostics.py
```

范围说明：新增测试使用 MOCK 验证上下文/矩阵持久化与权限过滤，使用真实受限 Docker 验证对象、错误字符串、合法字符串、程序异常、无效 JSON 和超时。未调用真实模型、未重试旧生成实例、未发布任务；本轮不验证生成成功率，也未改动方案第三至第五项。前端无改动，未重跑浏览器；完整后端套件未重跑。已运行的非 reload 后端需要重新启动才能载入这些 Python 修改，本轮未终止应用服务。

最终结果：**37 passed，0 failed，0 skipped，127.90 秒**；逐项核对 JUnit，包含原 `test_docker_acceptance.py` 全部 **18 项**及新增诊断 **14 项**（其中真实 Docker 6 项），另有传输测试 2 项及角色隔离测试 3 项。类型/矩阵错误未被算作故障命中；超时终态、容器失败及清理回归通过。`git diff --check`、上述 compileall 均通过。仅有现有 Starlette/AnyIO 弃用警告。

## 2026-09-20 规范审查提供具体纠错证据并加载到服务

实际根因：实例 `22b1af6eeefc4ba9a168256c1e660351` 的第6–24次调用都被同一句引用错误拒绝。校验器知道具体失败规则却未返回字段和文本差异；调用审计和下一轮输入又仅保留截断错误字符串。以 `/call/status` 为例，模型将原文“此时不输出error字段：echo…”引用为“此时不输出error字段。”，不是连续原文。另有拼接不同规则的引用。

修复：新增绑定契约哈希的结构化 `validation_feedback`，贯通校验器 → 调用审计 → 失败历史 → 下一轮实际模型输入。指出字段位置、输出路径、原引用、候选公开来源与文本差异；最多8项并记录遗漏数量。候选只帮助定位，不自动替换引用或批准语义；跨规则拼接仍拒绝。新增同阶段/同契约过滤，保留独立评测上下文边界。范围检查和 Pydantic 错误原本已有字段位置，本轮未改变其规则；本次未声称所有历史通用错误都已改为结构化反馈。

实际命令与结果：
```bash
.venv/bin/python -m pytest tests/test_review_feedback.py tests/test_generation_direct.py tests/test_consolidated_roles.py -q -o junit_family=xunit1 --junitxml=data/review-feedback-verification/pytest.xml
.venv/bin/python -m compileall -q backend/generation_direct.py backend/generation_flow.py backend/generation_roles.py tests/test_review_feedback.py
git diff --check
# 使用现有配置，脚本仅允许最多2次真实调用，不输出密钥：
set -a; source .env; set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -c "import runpy; runpy.run_path('data/review-feedback-verification/probe.py', run_name='__main__')"
curl --fail --silent http://127.0.0.1:8000/api/health
```

- 确定性/流程回归：**20 passed，0 skipped，41.71秒**。覆盖具体标点错误、拼接原文拒绝、反馈大小限制、持久化、下一次模型请求真实携带反馈、修正响应通过、旧契约反馈隔离和角色上下文隔离；包含原直接生成流程中的 Docker 回归。compileall/diff检查通过。仅已有Starlette/AnyIO弃用警告。
- 原始失败响应静态重放：原第6–24次共 **19份**响应仍被拒绝，但全部获得可定位反馈；未放松原文引用门禁，未改原资产。
- 真实联调：隔离记录 `7d992ddc611f488789672e1f7feb8d65`，加载原版本2公开规范和最后失败响应，送入具体反馈；**第1次调用返回approve且引用校验通过**。模型 deepseek-v4-flash，HTTP200，finish_reason=stop，输入3903 token、输出979 token，总4882 token，正文非空。未执行第2次调用，没有生成新项目或发布。
- 人工质量边界：模型修正了上次两处非连续引用；这证明此次反馈足以纠正引用格式，不证明其对所有字段语义充分性的判断正确。原规范仍应核对输出scenario回显等规则是否明确；未进行完整生成/Docker矩阵/发布/训练闭环，不能将本次approve当人工审核通过。
- 生效确认：重新核查没有活动生成、run或报告反馈后优雅停止旧后端PID2308778，使用原配置启动新后端PID2438682（8000），应用启动成功。健康接口返回real及docker_available=true。重启前后 **220条非task持久化记录的SHA-256全部相同**，摘要见本地验证目录 protected-before/after.json。前端/Docker未重启，历史失败保留。
- 辅助只读重放命令首次误用系统python3，因无pydantic失败；改用项目`.venv/bin/python`后完成。没有执行生成代码或修改依赖。
- 未扩大预算、未增加Agent、未修改报告快照或评分门禁。此次不保证纠错循环在所有问题上都能收敛，也未进行全后端/全浏览器回归。

## 2026-09-20 程序决定未完成门禁与代码修改范围（仅第一项）

新增 `backend/generation_repair_scope.py`：程序从当前矩阵生成逐版本未完成义务、必须保留项和允许/禁止/证据不足的代码修改范围。故障复现通过不能豁免回归；错误修复候选被目标识别且保留回归才合格。诊断模型收到明确权限清单，不能反向解释布尔值。提案保存绑定矩阵/契约的清单；返回修复再次校验当前范围及矩阵ID，不能以旧授权改新矩阵中已合格版本。构建上下文只有目标版本的义务，不新增隐藏输入或隐藏检查ID。独立评测、契约异议、冻结故障、最终Docker门禁不变。

实际命令：
```bash
.venv/bin/python -m pytest tests/test_repair_scope.py tests/test_consolidated_roles.py tests/test_generation_flow.py tests/test_generation_protocol.py -q -o junit_family=xunit1 --junitxml=data/repair-scope-verification/pytest.xml
.venv/bin/python -m pytest tests/test_repair_scope.py -q -o junit_family=xunit1 --junitxml=data/repair-scope-verification/pytest-scope-final.xml
.venv/bin/python -m compileall -q backend/generation_repair_scope.py backend/generation_roles.py backend/generation_diagnostics.py tests/test_repair_scope.py
# 现有配置，最多一次真实诊断；不修代码、不生成、不发布：
set -a; source .env; set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -c "import runpy; runpy.run_path('data/repair-scope-verification/probe.py', run_name='__main__')"
curl --fail --silent http://127.0.0.1:8000/api/health
git diff --check
```

- 首轮：33 passed、1 failed、0 skipped，81.41秒。新增测试夹具缺少visibility导致构建上下文读取KeyError，补齐夹具字段；产品代码无需为不完整夹具放宽权限。定位命令 `pytest tests/test_repair_scope.py -x -q` 为2 passed、1 failed，同一原因。
- 修正夹具后3项新增测试全部通过（0.27秒）；其余31项在首轮已通过。合计34个不同测试均已有通过记录，非宣称完整套件在最后一次统一重跑。覆盖最近失败语义、运行错误解锁、未知证据、已合格版本拒绝、故障回归允许修改、过期矩阵、义务传递与原角色/协议/Docker流程回归。compileall、diff检查通过。
- 真实原矩阵重放：`5a36c41b8c934dae90a1a1d5879df013` 的最终矩阵产生 allowed={faulty, fixed_delay, force_ready}、protected={normal, reference, warn_only}，断言通过。
- 一次真实诊断：隔离记录 `0aa2cb503c474c3c9625a3e2bcc9c4ee`，deepseek-v4-flash、HTTP200、stop，输入25386/输出681 token，总26067。模型选择 implementation/faulty，指出三个正常回归失败，保留normal/reference/warn_only，提案结构及权限校验通过。没有执行任何修复或新矩阵。
- 人工质量限制：模型自由文本提出恢复重试循环，与冻结故障“跳过循环”仍可能矛盾，并存在空清单原因的过度归因；权限合规不能证明具体修法正确。自由诊断文本原本不会直接作为构建指令，本轮维持该边界。未声称原项目已生成成功；后续修复仍需实际验证。本轮未实现无进展识别、调整修复优先级或增加预算。
- 服务生效：确认无活动任务后优雅重启原PID2438682，新PID2464389监听8000；健康real、Docker可用。重启前后221条非task记录摘要完全一致。原资产/失败记录未修改；新真实调用只写隔离验证目录。未重跑全浏览器或全后端套件。
