# AgentLab Interview V0.1

本地单用户 Agent 工程实操训练：选题 → 编辑 → 保存快照 → Docker 真实行为测试 → 逐级提示 → 提交新评测 → 查看证据报告 → 刷新恢复。

**当前交付状态：2026-09-15 已修复报告请求预算与重试、证据解释边界及安全 Markdown 展示。完整 Docker/浏览器验收通过；最新真实同类提交生成短反馈并刷新恢复，真实证据解释另行人工审阅。单次供应商成功不等于稳定性已证明。** 详情见 [VERIFICATION.md](VERIFICATION.md)；旧终端组权限的刷新步骤见 [DOCKER_SETUP.md](docs/DOCKER_SETUP.md)。

## 前置条件与启动

- Linux/macOS 上的 Python 3.10+、Node.js 22.12+、npm。
- 可运行 Linux 容器的 Docker Engine / Docker Desktop，当前用户可执行 `docker info`。
- 初始化需要联网安装依赖、拉取 Python 基础镜像；训练时容器无网络。

```bash
cp .env.example .env
./scripts/init.sh
./scripts/start.sh
```

访问 http://127.0.0.1:5173 。后端为 http://127.0.0.1:8000 ，API 文档 `/docs`。不需要模型密钥，默认 **MOCK · 确定性辅导**。停止时 Ctrl+C；SQLite、会话和代码保存在 `data/`。不要使用多 worker 启动后端：本版是单进程服务，内部限同时两次执行。

如果没有 Docker，可先安装应用依赖并体验编辑、保存、逐级提示与 mock 对话；**测试与提交禁用**：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend ci
./scripts/start.sh
```

Docker 就绪后构建镜像并点击界面“重新检查”：

```bash
docker build -t agentlab-runner:0.1 -f backend/Dockerfile .
```

## 真实模型

修改 `.env` 后重启：

```dotenv
AGENT_MODE=real
MODEL_BASE_URL=https://your-provider.example/v1
MODEL_NAME=your-tool-capable-model
MODEL_API_KEY=your-local-secret
```

适配器实际发送兼容 Chat Completions 的 HTTP 请求，要求供应商支持 `tools`/`tool_calls`。地址填 API 根路径，程序追加 `/chat/completions`；密钥仅后端持有。只发送允许的已保存文件、题面、可见证据和用户说明，不发送隐藏测试、参考修复与系统配置。模型不可用时明确显示错误，客观评测不受影响。已使用本机真实配置验证工具往返与报告持久化，详见验证记录。启动脚本负责加载 `.env`；直接启动 uvicorn 时须自行导出配置。聊天输出预算为 4096 token（含推理），每次 HTTP 请求超时 60 秒；每轮最多 4 次模型请求、6 次工具调用，最后一次请求保留给无工具总结。报告独立请求三条短反馈：首轮 1200 token，只有 output_limit 可自动重试一次（1800 token），合计上限 3000；单次等待最多 40 秒，总预算 90 秒。对官方 DeepSeek API 的 deepseek-v4-* 报告请求显式设置 thinking.type=disabled；其他供应商不猜测专有参数。每次尝试保存脱敏请求/响应元数据，缺失用量记为未知。报告显示生成中、已生成或失败类别；服务重启会将未完成反馈标记为中断。不会存储模型隐藏推理。

## 使用

1. 选择三道固定版本任务之一。每次开始创建独立工作副本。
2. 阅读症状与约束，查看只读公开 pytest 和固定 JSON 输入；在本地 Monaco 编辑器修改 `solution.py`。
3. 填写诊断说明。未保存状态明确显示，草稿保存在浏览器 localStorage，刷新可恢复；“保存”写入 SQLite / 工作区。
4. “保存并运行公开测试”先保存，然后创建不可变内容寻址快照。运行面板轮询持久化状态，显示检查、错误、超时、退出码、耗时与执行 ID。
5. 向 Agent 描述观察，或点击“请求提示”逐级开放 L1–L3。每次成功获取记录时间和等级；L3 后显示“已获取全部提示”，按钮禁用，接口拒绝追加，不再增加次数。历史报告仍使用提交时的提示记录。
6. “保存并提交评测”重新运行公开与隐藏检查，不复用旧通过结果。报告展示提交时诊断、提示记录、检查与代码快照；可点击查看提交代码、定位执行证据。
7. 点击左上角回任务列表，查看历史；重新打开训练或刷新恢复。

## 验证与清理

```bash
./scripts/test.sh
# Docker 就绪时，这些不会跳过；否则明确 skipped
.venv/bin/python -m pytest tests/test_docker_acceptance.py -v
# 安装并运行真正的浏览器测试
frontend/node_modules/.bin/playwright install chromium
npm --prefix frontend run test:e2e
# 仅清理带 agentlab=true 标签的残留容器，保留所有训练记录
./scripts/clean.sh
```

测试中明确区分基础设施 stub 与真实 Docker 验收；stub 只验证证据关联，不能证明故障修复正确。运行 `tests` 不会将任务代码导入宿主机。

## 范围

没有账号、支付、语音、数字人、任意仓库导入、动态出题、长期课程、多 Agent 或公网部署。没有录用概率、百分位或能力总分。架构、安全边界、任务格式及限制见 [ARCHITECTURE.md](ARCHITECTURE.md)。

完整验收入口为 `./scripts/acceptance.sh`：Docker 不可用时以退出码 2 终止，不把 skipped 包装成通过。浏览器已启动 mock 模式应用时可使用 `AGENTLAB_REUSE_SERVER=1 npm --prefix frontend run test:e2e`；否则测试会启动独立服务，使用 `/tmp/agentlab-playwright` 数据目录。直接运行某题公开测试可使用：

```bash
.venv/bin/python -m pytest tasks/rag/1.0.0/public_test.py --workspace-snapshot /absolute/path/to/snapshot
```

该快照目录必须只有 `solution.py`，目录和文件必须能被容器非 root 用户读取。

真实模型最小联调（先通过 `./scripts/start.sh` 启动真实模式；会新建训练并产生供应商用量）：

```bash
AGENTLAB_REAL_SMOKE=1 AGENTLAB_BROWSER_EXECUTABLE=/path/to/chrome node scripts/real_model_smoke.mjs
```

脚本通过页面编辑、保存、测试、普通聊天、提示、提交和刷新验证；证据写入 `data/model-verification/live.json`。不要把自动化测试中的模型替身计作供应商联调。

本次可靠性联调复现入口（会产生真实模型用量）：

```bash
# 正常真实模式服务启动后；恢复已知失败提交的代码到独立训练再提交
AGENTLAB_REAL_SMOKE=1 node scripts/reliability_smoke.mjs
# 独立两元素重排实验：用户代码仍由现有 Docker 执行器执行
set -a; source .env; set +a
AGENTLAB_REAL_SMOKE=1 .venv/bin/python -m scripts.evidence_model_probe
```

第二个脚本不是新增题目或正式公开测试条目；它保存独立实验的真实执行数据，调用模型检查证据解释。上述同类提交脚本引用本次本地失败报告 ID，移到新数据目录时需替换为待验证的报告。没有新增手动报告重试接口；自动重试只沿用本次提交证据，不重新判分。

源码仓库不包含 `.env`、本地训练数据库、执行快照、验收输出与截图。`VERIFICATION.md` 中指向 `data/` 或截图的链接是原工作区的本地证据引用，在新克隆的仓库中不会存在；可按文档命令重新生成自己的验收记录。版本化任务包（包括服务端隐藏检查与参考修复）属于应用源码，会随仓库提供。
