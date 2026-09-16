# AgentLab Interview V0.1 实施计划
1. 空目录采用 React/TypeScript/Vite/Monaco + FastAPI/Pydantic + SQLite。
2. 完成版本任务包、独立会话、代码快照、Docker 执行与报告闭环，再扩展三题。
3. 单 Agent 使用兼容 Chat Completions 的真实 HTTP 工具循环与显式 mock；提示由服务端递增授权。
4. 完成中文工作区、持久化恢复、历史和证据链接。
5. 运行后端测试、前端构建与验收，记录未执行部分。

重要假设：本地单用户、仅监听回环地址；隐藏检查仅正常应用隔离。用户代码仅在 Docker 内运行。宿主只执行可信 pytest 行为断言，通过 Docker JSON 协议调用用户代码，不采信用户打印的测试结论。当前环境无 Docker，禁止宿主降级。
