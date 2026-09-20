# 版本化任务包

旧三题保持 `tasks/{rag,retry,resume}/1.0.0` 原样。未指定多文件权限时默认读取/编辑 `solution.py`，参考与基线分别为 `private/reference.py`、`private/normal.py`。新任务不修改旧版本、历史报告或旧快照摘要。

进阶任务位于 `tasks/rag_versioning/1.0.0/`：

- `manifest.json`：题面、公开接口、版本、能力标签、设计估计时长、环境；明确 `readable`、`editable`、`runtime`、`private_assets`。
- `initial/`：只读 `solution.py`，可编辑 `pipeline.py`、`ingestion.py`、`index_store.py`、`retrieval.py`、`context_builder.py`。
- `public_cases.json`、`public_test.py`：初次导入、更新查询、无关文档保留三个公开行为；直接运行公开 pytest 也必须通过 Docker fixture。
- `private/hidden_cases.json`：11 个行为检查，覆盖旧片段清除、片段缩减、旧关键词、文档隔离、重复导入、延迟低版本、空正文、重开持久化及不同数据组合。
- `private/normal/`、`private/reference/`：各自完整六文件正常基线与参考实现；实现写法不同，不以代码相等判分。
- `private/hints.json`、`private/rubric.json`：沿用三级授权提示和无精确能力总分的评价规则。

权限字段是可信任务包配置，不能由 API、用户代码或模型修改。只允许扁平文件名；读取集合必须等于可编辑集合与固定运行资产集合之并集。私有资产不进入公开任务索引、文件接口、Agent 或容器挂载。公开测试入口由独立只读 API 提供，不属于可编辑代码集合。

`scenario({"actions": [...]})` 支持：

```json
{"actions": [
  {"op":"import", "document_id":"refund", "version":1, "body":"退款 旧规则 7天"},
  {"op":"import", "document_id":"refund", "version":2, "body":"退款 新规则 30天"},
  {"op":"reopen"},
  {"op":"query", "query":"退款", "limit":1}
]}
```

正文按非空行切分，词项匹配计分。输出 `result` 包括 `queries`、`versions` 和 `chunks`；另有 `trace` 记录导入版本、前后数量、候选 ID/文档/版本/分数和最终上下文。轨迹可被用户代码修改，不是可信通过证明。`contract: versioned_index` 让服务端评测器仅比较结构化行为 `result`，忽略轨迹作为判分依据。公开失败显示期望与实际，隐藏失败只显示筛选后的类别、行为覆盖和状态。聊天工具对隐藏覆盖保持未知，不读取隐藏用例文件。

整数版本可跳跃。高版本完整替换同文档正文；重复相同版本/内容幂等，低版本忽略，空正文保留版本但无片段。其他文档不受影响，重开后保持一致。同版本不同内容、非法输入、并发、崩溃事务恢复与生产级分布式一致性不在输入域。固定 SQLite 表和公开函数接口是题面协议；接受所有满足协议的实现，不要求匹配参考代码。

任务运行仅 Python 标准库，依赖固定 Dockerfile 基础镜像。每个检查单独容器/临时 SQLite，不共享可写索引，不使用 embedding、模型或网络。故障仅为更新时追加片段而未清除同文档旧片段，其他模块按契约工作。

测试命令：

```bash
docker build -t agentlab-runner:0.1 -f backend/Dockerfile .
.venv/bin/python -m pytest tests/test_versioning_docker.py -v
./scripts/acceptance.sh
```

Docker 不可用时直接测试会明确 skipped，完整验收会失败阻塞；不允许宿主运行用户代码。本机项目所有者可阅读私有资产，隔离仅针对正常应用流程，不是防本机所有者的秘密机制。

## V0.2 生成任务

生成任务位于 `data/published/gen_<id>/<version>`，manifest 标记 `source=generated` 和 `generation_mode`，包含固定契约及协议标识。训练仍使用同一 readable/editable/runtime 权限与多文件快照。评测资产为 JSON，而不是生成的宿主 pytest；详见 [生成资产格式](GENERATION_FORMAT.md)。冻结环境使用已验证镜像的本地 digest，旧会话按原版本读取。
