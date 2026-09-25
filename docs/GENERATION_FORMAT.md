# 生成资产协议 V0.2

协议标识：`agentlab-generated-json-v1`；权威程序校验见 `backend/generation_schema.py`。

## 旧记录协议与上下文

需求包含必填自然语言、可选分钟数、难度和偏好。设计输出 assessment（generatable / clarify / simulation / unsupported）、理由、澄清问题、公开 Contract、私有故障要求。公开契约包含标题、能力、症状、输入输出 JSON schema、行为 ID、约束、输入域、排除范围、业务文件、模拟范围。行为 ID 使用小写字母开头的字母数字下划线。

JSON schema 是受限子集：type/properties/required/additionalProperties/items/enum/description；不支持的关键字拒绝而非忽略。单次场景不得依赖其他容器状态，持久化场景在一次调用内执行完整动作序列。契约确认记录版本、哈希、模拟范围确认时间。

构建输出 normal / faulty / reference 文件映射、2–3 个规避版本与说明。文件必须与契约相同，2–5 个扁平 Python 模块，必须有 app.py；平台生成只读 solution.py 调用 app.scenario。禁止越界路径与保留模块名，每文件24KiB、单个项目60KiB，只允许固定环境标准库。语法检查不执行生成代码。

独立评测输出4–10个 case：id、group（target/regression）、visibility（public/hidden）、covers、input、expected，目标可含 faulty_expected。必须覆盖契约行为、包含公开和隐藏目标及正常回归；故障指纹与正确期望不同。判分比较完整结构化 JSON，不采信用户打印的通过状态。评测不接受 Python 源码。

评测自身错误可由作者明确分类并给出公开契约依据后重做；保存旧评测引用、理由及次数，不传实现，审计标记为审核指导而非完全盲测。仍受每阶段与总预算限制。

教学输出题面、恰好三级提示、追问、契约一致性说明。完整解法不得写入公开题面；自动检查不能替代人工审核语义。

## 审计与冻结

`data/generation/<id>/call-*/` 保存阶段输入、可见原始响应和通过校验的输出；SQLite 保存引用、哈希、模型标识/usage（缺失为未知）、尝试和状态。矩阵记录每个版本/检查的执行 ID、快照、耗时、结果、环境 ID；作者可看完整证据，普通界面只有筛选摘要。

发布目录包含 manifest.json、initial、public_cases.json、只读入口；private 下有正常版、参考、隐藏检查、提示、作者资产和 freeze.json。冻结清单包含文件哈希、协议、契约摘要、Docker 镜像 ID、矩阵和审核记录。训练只读 manifest 白名单，不向 Agent 提供 private。后续版本另建目录，旧会话继续关联原版本。

MOCK 是固定工程测试资产，与真实需求生成严格区分。自动验证仅证明本次列出的行为，不证明整个领域或模型质量。

## roles-v1 批次与修复资产

新 generation 对象包含 `policy_version=roles-v1`、`batch_id`、可选 `parent_job`、单调 `revision`、`budget`、`checkpoint`、`coordinator_token`、`attempts`、`failure_history`、`diagnoses`、`asset_revisions`、`validation_history`。旧对象无此字段，仍走原策略，不迁移旧证据。

每次调用写入独立 `call-<id>/input.json`、可见供应商 `response.txt`（没有隐藏推理）和校验后的 `output.json`。尝试记录角色、资产/输入哈希、契约版本、输出预留及记账、usage与结束原因、成功/失败/用量未知。解析失败不提升候选。diagnosis 的模型结构经程序补充 matrix_id、contract_hash、必须保留的资产哈希及指导来源。

修复是指定版本的完整文件映射，不能删换其他版本。`evaluation_action` 仅允许 none/add_coverage/classification/fingerprint；expectation 表示需作者确认，不自动更改正确期望。每次修改后重跑完整矩阵。文件、JSON与运行协议仍采用既有 `agentlab-generated-json-v1`，不引入生成 Python 评测器。

`POST /api/generation/jobs/{id}/regenerate` 请求包含 `expected_revision`、8–80字符 `idempotency_key`、可选 `repair_note`、`new_batch`；新批次必须明确提供 `budget`。同键同内容返回同记录；同键不同内容拒绝。原批次状态和计数不被重置。新状态：diagnosing、repairing_build、waiting_backoff、waiting_provider、waiting_environment、awaiting_contract_review、budget_exhausted；评测修复沿用 evaluating，通过尝试审计区分。

## 局部契约修订协议

新增角色 `contract_review`（最多4000输出Token）和 `contract_check`（最多3000），共享原批次预算。Proposal绑定contract_hash，decision为correction/need_user/clear；补丁包含JSON Pointer path、op(add/replace)、before/after、source、quote、reason；需求问题包含id、text、2–3个options及impact。Check绑定proposal_hash，verdict为approve/revise。所有可见输出保存于独立call目录，不保存隐藏推理。

generation对象增加contract_candidate、contract_decision、contract_reviews、contract_clarity、contract_issue、contract_origin_plan、requirement_question和requirement_answers。旧契约历史包含origin_job，便于定位不可变资产来源。GET进度公开局部补丁与需求问题，不提供私有故障材料；作者接口可查看完整契约历史。训练Agent的工具和冻结发布资产权限不变。

POST `/api/generation/jobs/{id}/requirement-answer`：`expected_revision`、`question_id`、`answers`（当前全部问题ID到文本的映射，每条最多2000字）。原需求与答案分别保存。修订通过后旧资产只归档、不删除；新矩阵必须绑定新contract_hash。已发布实例不能自动原地修订。

## 前五项回退后的兼容性

- 新任务沿用roles-v1，不再启用reliability-v1控制策略。
- RepairPlan恢复原协议：category、failure_ids、contract_behavior_ids、target_variants、observed_facts、hypothesis、change_request、evaluation_action、target_cases、requires_contract_confirmation。不要求证据充分性扩展字段。
- 契约Check恢复proposal_hash/verdict/reason，不要求impact_checks；旧已完成检查点中的扩展可读取，原记录不重写。
- 新矩阵仅保留原六项门禁，不新增反例门禁，不复用相同资产的历史矩阵代替新执行。
- no_progress仅为历史状态，显式恢复后回到diagnosis；不会再生成此终止状态。旧progress_history与语义影响审计只读展示，不参与控制。
- usage_summary与作者专用summary保留。作者variant_results是实际检查的分组展示，不计算新门禁。
- 已有本地失败档案继续保存，自动归档机制和CLI已撤回。冻结实例摘要与历史会话关联不变。

## separated-evidence-v2 生成扩展

只有新创建的角色流程记录带generation_protocol=separated-evidence-v2；发布训练运行仍兼容原JSON协议。旧记录没有标记时保留Evaluation及faulty_expected的原语义。

- BehaviorEvaluation：cases保留id/group/visibility/covers/input/expected，faulty_expected必须为null，增加必填classification_reason。公开、隐藏均有target，至少一个保留行为regression。
- fingerprint资产：`{checks:[{case_id,design_quote,reason,assertions:[{path:["字段","0"],equals:值}]}]}`。空path表示根。最多10个检查，每检查最多8断言、路径8层，资产24KiB；不含Python代码或任意执行表达式。引用必须来自冻结private_fault_requirements，必须针对target且不命中正确expected。语义仍由模型和作者核对。
- EvaluationPatch：`{evaluation_hash,action,changes:[{case_id,field,before,after,reason}],additions:[]}`。修改动作和字段一一对应，动作混用、越权、旧值不符、重复字段、无变化均拒绝。add_coverage只能有additions。正确expected修改还须当前契约已独立确认。
- 指纹执行前冻结，矩阵保存fingerprint_hash；审核摘要将fingerprint与build/evaluation/teaching一起哈希绑定。训练与公共生成API不返回私有指纹。
- 调用failure_kind区分response_format、diagnosis_rejected、patch_rejected、asset_invalid及供应商错误类别；completed只代表该调用资产校验完成。


## 新记录 direct-build-v1

应用API新建任务自动选择此流程；内部兼容工具不传direct_build仍可创建旧协议测试记录。内部Contract保留为公开项目规范，移除新任务单独设计和用户确认阶段。

- project_build：Bundle包含assessment、rationale、questions、contract、private_fault_requirements、project。可生成/模拟必须同时有完整规范与全部版本；有歧义只返回问题，不构建不完整项目。
- spec_review：contract_hash、decision（approve/revise/need_user/unsupported）、reason、issues、questions、output_rules。approve逐字段引用公开规则；revise用受限JSON路径授权补齐；need_user只用于用户目标歧义。审查不接收实现。
- 公开规范补齐生成新版本，归档原资产和矩阵；只允许更改issues指定字段。下游评测、指纹、教学与验证必须重建，禁止沿用旧批准。
- evaluation初次仍完全独立；修复响应为decision（patch/specification_issue/reject_plan）、reason、patch、issues。patch沿用受限字段补丁校验；另外两种保存审计并转回规范审查/诊断，不覆盖已存评测。
- 确认字段为程序兼容保留：confirmation.source=independent_specification_review、not_user_approval=true；人工发布审核仍独立，摘要绑定Bundle、审查、测试、故障指纹、教学和实际矩阵。

项目路径/大小、固定Docker环境、行为判分与已有预算上限不变。输出字段引用检查只约束来源和完整性，不能当作语义正确的形式证明。

执行前纠错补充：evaluation_candidate保存失败候选asset及contract_hash，rejected.json仅原评测阶段可读取。规范审查收到缺失行为、覆盖caseID和公开/隐藏目标缺口，不读取候选输入/期望。它不是已通过评测资产，不能用于发布。连续两次首次评测校验失败复用spec_review，仍受同一请求/Token/时间预算限制。direct-build-v1发布检查新增平台控制的repeat_count=2；生成矩阵保存repeat_actual及repeat_consistent，训练评测执行同样的两次独立调用。此字段不由模型选择；历史冻结检查不迁移。

角色归属协议consolidated-v1：新任务增加role_policy，阶段attempt增加role_id（builder/evaluator/teacher）和role_policy。stage标识、资产格式、输入哈希、预算和矩阵保持原协议。角色名用于显示，角色归属和共享职责由程序注册表确定；各阶段依旧重新构造权限不同的上下文。历史attempt不回写，新批次延续源记录策略；新建任务启用合并。审核私有资产保存该策略信息，训练视图不注入作者角色材料。

执行诊断补充（2026-09-20）：生成矩阵检查新增可选 `diagnostic` 和 `execution_attempt`（第一次或重复执行）。诊断包含 `category`、`stage`，按类别提供 schema 路径、期望/实际类型、容器退出码或超时秒数；不记录原始 Docker stderr 和异常消息。schema 路径使用 `$` 根及 JSON Pointer 转义的后续段。仅记录首个 schema/行为差异位置，完整 actual/expected 仍遵循原作者侧权限。运行器返回的异常类型标记为不可信输出，源码位置未知；容器退出码只能提示启动失败的可能性，不能独立证明环境根因。作者审核与失败分析读取诊断；构建修复仅获得公开检查的诊断；公开矩阵/训练工具不新增私有详情。历史矩阵不回写。

入口协议统一为：`scenario(data)` 直接返回契约对应的 Python 值，平台执行一次 JSON 序列化。对象/数组不得预先 `json.dumps`；契约为字符串时仍允许返回字符串。执行器不进行递归解码，schema 错误仍阻止故障命中和发布。此次不改变诊断调度、重试次数、预算或门禁。

规范审查纠错补充（2026-09-20）：引用校验失败使用 `ReviewEvidenceError`，将 `validation_feedback` 同时保存于 attempt.error、failure_history.error 和仅同阶段使用的 format_error。反馈绑定 contract_hash，包含 output_rules 的字段位置、对应输出路径、原引用、最多两个候选公开来源路径/原文片段以及文本差异；一次最多8条并显式报告遗漏数。下一次 spec_review 的实际输入携带完整结构化反馈，不受错误摘要1500/1800字符截断影响。旧契约反馈不注入新契约；不传给构建或独立测试阶段。候选文本相似度只用于定位，不替代逐字连续引用校验，不证明语义充分，缺少公开规则仍应返回 revise。历史失败资产不重写。

程序修复范围（2026-09-20）：`repair_scope` 根据当前执行矩阵生成 failed_gates、allowed_code_variants、protected_code_variants、unverified_code_variants，以及逐版本 unmet_requirements/must_preserve。fault_trigger 与 fault_regression 为独立义务；规避候选只有目标失败、至少一个回归通过且无运行错误才合格，合格表示禁止继续修改，不表示实现正确。无证据不标记合格。该清单进入失败分析上下文，并随已校验诊断提案保存；构建修复仅获得授权版本的义务摘要，不传隐藏检查ID或输入。服务器校验诊断目标和返回资产，拒绝当前合格版本及过期矩阵；已有无gates的旧记录沿用历史校验兼容路径，新执行矩阵始终具备gates。评测/契约异议仍使用原审核流程，范围许可不等于实现根因已确定，也不允许自动改期望。本轮不改变修复优先级、无进展处理或预算。

`repair-handoff-v1` 新字段：
- `handoff_version`：新任务/新预算批次启用，不回写历史实例。
- 诊断 `work_order`：互斥 `action`，执行检查与公开行为引用 `evidence`，对当前冲突的 `resolutions`。分类动作必须带 case_id/before/after/design_quote/rationale；不能夹带代码目标或修改 expected。
- 构建返回 `BuildDecision.result`：modified 含文件映射；constraint_conflict 含两项真实义务引用；insufficient_evidence 含缺项与建议验证。模块提示必须属于契约文件，明确标记为诊断推断。
- `handoff_conflicts`、`open_conflict`：矩阵ID、语义证据摘要、冲突双方、时间与稳定签名；`handoff_rejections` 保存拒绝原因。自由文本不作为语义正确性证明。
- `candidate_assets`、`candidate_history`：候选资产引用和 pending/rejected/passed/accepted 状态，绑定验证矩阵。`assets` 保留接受前版本；晋升须校验完整通过矩阵的摘要，不接受旧结果证明新资产。
- `needs_manual_review`：非运行状态，界面说明停止原因；作者入口显示私有冲突和候选，公开任务与训练上下文不暴露它们。`evidence_request` 保存尚缺证据及建议验证。

工单权限与语义校验各有边界：程序能阻止动作混写、过期引用、越权文件/版本及未验证候选发布，不能自动证明模型的因果解释。冲突能被正确路由、候选能实际通过本轮检查，也不代表整个训练题设计已经符合用户意图，发布仍需人工审核。

need_evidence动作现在要求requests（1–3项），每项包含question及以下一种结构：file/variant/path、check/check_id、scenario/variant/case_id。额外命令、路径和输入字段由Strict模型拒绝。诊断补充仅支持已存在的独立评测输入，未知场景明确不支持。WorkOrder增加evidence_responses对象，键必须正好对应当前资产的补充记录ID，值为说明。diagnostic_evidence保存binding(matrix_id/contract_hash/build_hash/evaluation_hash)、请求、完整结果、状态及时间；新实验另存execution_id、snapshot、environment、duration、actual或error。已有矩阵仍是唯一评分依据，补充记录不产生通过门禁。完整材料只在作者接口及失败分析上下文返回。

evidence_responses协议补充：无当前补充记录时省略或{}；有记录时键必须恰好为evidence_response_contract.allowed_ids。矩阵检查ID只属于evidence[].check_ids。动态输出Schema与服务端校验均使用相同response_contract；错误反馈分别列出误用矩阵ID、过期补充ID、未知ID、遗漏和说明过短项，不把所有引用错误称作旧资产。

2026-09-22：新诊断的edit_code动作不再使用宽泛approach/suspected_files，改为variants与edits。每条edit必须有variant、path、location、current_behavior、intended_behavior、must_preserve；版本集合须恰好覆盖variants，path限契约业务文件，当前与预期行为文本不能完全相同。缺字段及旧动作字段按结构错误退回，不用关键词自动改派。旧持久化工单保留原样，构建上下文仍兼容读取旧suspected_files。完整诊断文字可能包含隐藏检查内容，不直接转发构建；构建仅接收推断文件集合、现有程序义务与授权目标。字段完整和文本不同不证明语义正确，仍需执行门禁。

## 可执行故障影响模型 v1

新 API 记录 `fault_model_version: fault-model-v1`，构建 Bundle 增加私有 `fault_model`：

```json
{
  "trigger": {"any_of": [[
    {"path": ["ready_after"], "quantifier": "value", "operator": "gt", "value": 1}
  ]]},
  "affected_paths": [["attempts"], ["status"], ["registered_tools"]],
  "preservation": "首次已就绪的输入保持完整正确行为；其他输出字段不受影响。"
}
```

`path` 是字面 JSON 对象键/数组下标，空路径为根；不支持 shell、代码、通配表达式。`quantifier` 为 value/any/all，any/all 只作用于输入数组；operator 为 eq/ne/lt/le/gt/ge，顺序比较仅数字，不把 true 隐式当作 1。缺失路径、非法类型和超限规则报错，不默认为不触发。构建时检查路径属于公开 JSON 接口。输出影响可指定合法子树（如整个工具数组）。

故障审核资产在原 `checks` 外增加 `review: agree|conflict`、`review_reason`、`impacts`。每个 impact 含 case_id、triggers、affected_paths、rationale，必须覆盖全部检查且不重复。独立审核冲突暂停作者复核。正文、规则及 impacts 都是作者资产，不进入学习者文件或训练 Agent；正常题库检查仅使用冻结正确行为期望。

新矩阵增加 `fault_model_hash` 和 `fault_preserved_fields` 门禁。修复候选仍绑定原 build/evaluation/contract 摘要；分类修正不能改输入或期望。原协议不迁移。`tests/fixtures/fault_classification_regressions.json` 保存历史失败的最小分类投影，不是原项目完整执行证明；实际原记录继续保留在本地忽略的数据目录。

### Amendment：冻结项目后的公开规范补齐

仅用于同时具有 fault-model、installed_bundle、spec_review_feedback 的记录。模型返回：`contract_hash`、有效 Bundle 的 `bundle_hash`、`decision=patch|conflict`、`changes`、`conflict_evidence`、`explanation`。patch 最多8项，每项 path/before/after/reason，path 必须精确等于审查授权字段；不允许同时报告冲突。conflict 不得携带修改，必须引用至少两个不同 Bundle JSON 路径及连续原文。

调用私有目录保存原 response、patch.json、合并后的 output.json 及输入/输出摘要。output.json 保持 Bundle 兼容性；项目取当前 build，不取旧初始代码。程序保留 private_fault_requirements/fault_model/project，模型不得重写它们。错误类别 spec_patch_invalid 附具体路径和当前期望；specification_conflict/spec_patch_exhausted 进入作者复核。此流程不新增学习者接口权限。

### 构建请求 repair_handoff（输入字段，非响应协议变更）

包含matrix/contract/build/evaluation/fingerprint摘要，edits（授权variant/path及代码中可核对symbols）、public_requirements（检查ID、公开input、objective、逐字段observed/required_value/matches）、omitted_public_checks及response_files。字段缺失与JSON null分开；故障断言和正确期望分开；规避检查不被要求修成正确实现。原私有工单留在作者审计，禁止整段转发隐藏诊断。构建响应仍必须返回完整版本文件集合。该输入随实际模型请求落盘，不是仅供UI展示的摘要。
