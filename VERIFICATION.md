# 实际验证记录

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
