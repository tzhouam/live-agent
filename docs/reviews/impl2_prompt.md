You are the independent reviewer (Codex, GPT-6 Sol) for the live-agent project, Phase 2 checkpoint "impl2":
the **evaluation harness and the memory service** against the Chinese proposal `docs/research_proposal_zh.md`
v2.11 (inlined).

Review goals, in priority order:
1. **Scoring validity:** intent chains (new / revision / withdrawal), effective-chain denominator, deadline table D,
   outcome precedence, capacity skips and refusals as failures, FCR and claim coverage, Kaplan–Meier with censoring,
   Wilson / Clopper–Pearson / clustered bootstrap / Holm. Anything that would bias A2 vs A1 or let the online judge leak
   into the primary outcome.
2. **Runner and converter** (`runner.py`): the orchestrator → SCHEMA mapping (chains by utterance uid, time rescaling,
   verdict fields, speech onset, completion claims), paired seeding, the live-stack mode.
3. **Blinded adjudication** (`adjudicate.py`): blinding, time mapping, merge semantics.
4. **Memory:** provenance typing, scope filtering before ranking, echo detection, bi-temporal correction, erasure
   cascade and verify_erased. Any path where a private fact can reach a public scope or survive erasure.
5. **Honesty of claims** in `docs/implementation.md`.

Output format: a numbered list of findings. For each: severity (blocking / major / minor), file and function, the
concrete failure scenario, and the fix. Then a one-line verdict: "ready for E1/E2 pilot", "ready after fixes", or
"not ready". Do not praise; do not restate the code.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/research_proposal_zh.md =====
# 在线智能体导演：基于 TaoMate-H3 的实时个性化直播数字人

**研究提案（中文版 v2.11，2026-09-25）**

*v2.11：已按 GPT-6 Sol 评审（zh1–zh12）修订。本版依据项目负责人的指示重写（决策 D-017）。生成底座由 LingBot-World 2.0 改为 TaoMate-H3，系统架构借鉴 Google 长视频智能体套件（Co-Director / CANVAS / A²RD / VQQA）。英文 v1.0（`docs/research_proposal.md`）保留为上一版。*

**证据标注。** 每个定量陈述都带一种标注：
- 【引用】：来自具名的一手资料。
- 【代码】：在已检出的源码中核实。只读，未执行。
- 【本机观测】：在本机上用只读命令观测到的结果，例如 `nvidia-smi`。
- 【推导】：基于引用或代码中的数值推算。
- 【目标】：提议的目标，不是结果。
- 【估计】：我们的判断。

**本阶段未运行任何实验、测量或用户研究。**

已检出的代码版本如下（均只读，位于 `external/`）：

| 仓库 | 提交 |
|---|---|
| TaoMate-H3 | `6b2f998` |
| TaoMate（LTX） | `136d890` |
| vLLM-Omni | `7b4dc76`；上游 `3bd5ac9` 仅做了检查 |

支撑材料：
- `docs/notes/taomate_deep_dive.md`
- `docs/notes/google_longform_agentic_suite.md`
- `docs/notes/taomate_h3_assessment.md`
- `docs/related_work.md`
- `docs/backbone_verification.md`（LingBot）

---

## 摘要

我们要构建一个可以直播的数字人。它需要做到：
- 用自己的声音和口型实时说话；
- 在对话中途接受纠正与打断；
- 跨会话记住用户；
- 在数十分钟乃至数小时内保持人设与场景一致。

**生成底座选用 TaoMate-H3。** 它是在 MiniMax H3 上训练的 3 步流式 LoRA，并附带运行时代码【引用】。它有三个优点：音视频在同一时间轴上生成，说话、表情、动作都能用文本提示逐块描述，且与负责人所述的参考主播同属 H3 家族。

**但代码核查发现四个限制，本提案的方法都要围绕它们设计：**
1. **控制粒度粗。** 控制粒度为 **5 秒一个请求**，每个请求内部分为 4 个块。
2. **状态极短。** 生成器的主要状态是「首块视频 sink + 最近 2 个块」的滚动 KV，另有位置偏移、首块归一化统计量与音频教师尾部。论文中的锚点与学习型记忆**不在** H3 代码里【代码】。
3. **语音是离线预算的。** 语音由基座 H3 的「教师」过程**预先**为整份脚本计算，然后覆盖流式模型的音频；运行时**不接受会话中途的新提示**【代码】。
4. **硬件要求高。** 发布的运行路径只接受 FlashAttention-3【代码】，README 要求 Hopper/SM90【引用】，而本机 GPU 报告为计算能力 8.9【本机观测】。在 8×H20 上，**仅 DiT 部分**的速度约为实时的 0.68 倍：10 秒视频用时 14.81 秒【引用】，0.68 倍由此换算【推导】。这个数字不含音频教师与编码。

**Google 的长视频套件为何可借鉴，又为何不能照搬。** 该套件表明：一致性来自包在生成器**外面**的智能体，包括分层导演、持久视觉锚点、分段自回归记忆和基于 VLM 问答的「语义梯度」修正。但这四个系统全部离线，可以反复重生成，每段开销可达数分钟【引用】。

**我们的研究问题是把这套结构「在线化」。** 在线后必须满足四个约束：
- 每个判断都要在截止时间内完成；
- 只能判定用户**实际看到**的画面；
- 已播出的内容不能重生成，修正只能**向前**作用于下一块；
- 用户随时可能打断。

**核心科学贡献：** 在线智能体导演。它由状态账本、校准过的能力清单和截止时间内的「前向语义梯度」修正组成，并通过对照实验衡量它在可观测指令遵循、长时一致性与响应时延上的收益与代价。工程集成不算贡献。

---

## 1. 动机、目标场景与问题定义

### 1.1 为什么「只接一个视频生成器」不够

| 事实 | 对直播智能体的含义 | 证据 |
|---|---|---|
| TaoMate-H3 每个请求 5 秒，分 4 块（首请求为 39/34/34/17 帧，之后共 119 帧），每块 3 步去噪 | 指令最快在下一个 5 秒请求边界生效 | 【代码】`config.py:23,80-134`；`streaming/geometry.py:173-200` |
| KV 只保留首块视频 sink 和最近 2 块音视频；音频历史每 60 秒丢弃。此外还携带位置偏移、首块颜色归一化统计量和音频教师的尾部 | 生成器没有长期的语义记忆。人设与场景一致性主要只能来自外部 | 【代码】`streaming/cache.py:206-219`；`config.py:29`；`streaming/runtime.py:451-462` |
| 音频由基座 H3 教师过程为整份脚本预算，再覆盖流式音频；文本编码器编码完所有提示后被移到 CPU | 语音内容必须提前一个请求写好。运行时不能中途换话题 | 【代码】`streaming/runtime.py:339-359,739-743`；`runner.py:293,299-323`；`cli.py:223-229` |
| 发布路径只接受 FlashAttention-3；权重与激活量化为 INT8（CUTLASS）。README 要求 SM90 | 本机 GPU 为计算能力 8.9，可能无法运行，需移植或换硬件 | 【代码】`streaming/attention_hook.py:43-48`、`cli.py:130-146`；【引用】README；【本机观测】`nvidia-smi` |
| 在 8×H20、480×864 上生成 10 秒：DiT 用时 14.81 秒【引用】（约 16.2 FPS，≈0.68× 实时【推导】），首帧可播 17.29 秒（来自单独的基准测试，不是发布的一次性输出路径），首个最终块 6.15 秒。**这几个数字都不含内部音频准备**，而且发布路径的输出要到最后才写出 | 仅看 DiT 就**不是实时**；完整流水线（教师 + 学生 + 编码）更慢：M0 分组件测，M1 在 T1–T3 完成后测端到端 | 【引用】TaoMate-H3 README / 模型卡 |

**工作假设（可证伪）。** 离开外部状态层与在线导演，仅靠流式生成器无法同时做到三件事：
- (a) 跨会话、可纠正、可删除、可溯源的用户记忆；
- (b) 经过验证的可见指令遵循；
- (c) 小时级的人设与场景一致性。

反例同样存在：X-Streamer、Wan-Streamer 等端到端模型内置了推理【引用】。因此我们只检验上述较窄的命题。检验方法见 §7.4。

### 1.2 目标场景：一对一陪伴主播 + 私有测试直播

**人设。** 一个虚构人设，比如「书房里的汉服读书人」，风格与参考主播相近。人设的**正典档案**由项目方整理，包括外貌、服饰、声音、场景和道具。

**模式 1：主验收场景，一对一私聊。** 用户语音输入。典型指令分四类：

| 类别 | 例子 |
|---|---|
| 动作 | 「喝口茶」「翻一页书」「挥挥手」 |
| 内容 | 「讲讲 CUDA」「唱首歌」 |
| 纠正与打断 | 「不对，换一首」「先停一下」 |
| 记忆 | 「我上次说我妹妹在哪？」「忘掉这件事」 |

**模式 2：第二评测场景，私有测试直播。** 脚本化的测试账号在弹幕里投票、提问，其中部分账号尝试投毒。**本阶段不做公开直播。**

**首个演示的范围。** 只包含 **M2 末整系统再认定**为实时的配置（§6.4）。M1 的认定只覆盖生成器与播放路径。

**未通过时的「近实时」服务规则。** 如果完整流水线的吞吐达不到每 5 秒一个请求（8×H20 上仅 DiT 就约 7.4 秒 / 请求【推导】），持续的对话会让队列无限增长，所以需要明确的规则：
- **话轮制：** 人设说完一段后进入「倾听」，用户说完才生成下一段。不维持连续的 5 秒节奏，等待时间如实显示。
- **准入控制：** 同时最多有 1 条未执行的指令。更新的指令取代旧指令，被取代的记为「**容量跳过**」。它与用户主动撤回或改口（「用户取代」）严格区分。
- **降速播放：** 可选，把播放帧率降到生成速率，但不低于 20 fps，并测量主观质量。
- 反应片段只用来掩饰短暂等待，**不**计入 TFMR。

E2 在持续交互下测量等待时间的增长与 TFMR。只有在 M2 末再认定未通过时，E2 才以「近实时」标签进行（见 §6.4）。

### 1.3 问题定义

- 用户在时间 $t$ 发出指令 $u_t$。
- 智能体为第 $k$ 个请求生成**块脚本** $s_k$。它包含动作、台词、外貌、场景、镜头和声音字段，与 TaoMate 的提示格式一致。
- 生成器以未知概率 $p_c$ 渲染出控制 $c$，从发出到生效的时间服从未知分布 $F_c$。
- 用户在呈现时刻 $\tau$ 看到并听到 $v_{\le\tau}$。

对每条指令，目标是三点：
- 最大化**可观测遵循**：独立评判在截止时间 $D$ 内、在呈现的画面与音频上判定为「已执行」；
- 最小化「指令到可见遵循时间」（TVC）与虚假完成声明；
- 同时保持记忆正确、作用域隔离、可删除，并保持长时一致性。

---

## 2. 相关工作与研究空白

完整矩阵见 `docs/related_work.md`。这里只列出决定本设计的要点。

### 2.1 Google 长视频智能体套件：可借鉴什么、在线后会失效什么

四个系统都**不训练，都不实时，都不交互**【引用】。其中三个是对冻结 API 模型（Gemini、Nano Banana、Veo）的提示编排；VQQA 还在本地通过 Diffusers 运行 CogVideoX-5B 作评估对象。

| 系统 | 机制（原文） | 关键数字【引用】 | 在线化后保留 | 在线化后失效 |
|---|---|---|---|---|
| [Co-Director](https://arxiv.org/abs/2604.24842) | 编排器 → 前期 → 制作 → 后期。UCB1 在「创意策略 3 × 叙事模式 3 × 美学原型 4」三个轴上选择组合，并用 Gemini 3 Pro 的**分因子**评分（每轴 0–100）**按轴分别**更新各轴取值，不是 36 个独立臂 | GenAd-Bench 平均 81.4（随机搜索 75.7，基础流水线 68.5，Veo 3.1 63.6）；换成标量奖励后产品保真度 −5.0 | 分层参数化的人设风格轴；分因子评审；**跨会话**的老虎机 | 一次「拉臂」就要完整跑一遍流水线；奖励在视频结束后才到 |
| [CANVAS](https://arxiv.org/abs/2604.13452) | 全局计划：角色外观状态、地点 id、带「持有者」字段的道具状态（JSON）。锚点记忆：角色规范锚点 + 最近锚点、地点背景锚点、道具锚点。检索规则分三种情况：连续、回到已知地点、新地点 | HardContinuityBench（仅 5 个故事）；去掉规范锚点后角色一致性 4.24 → 2.59 | 状态账本的字段设计；检索规则；**规范锚点永不覆盖** | 生成 N 个候选再选优——已播出的内容无法选；依赖未来剧本的规划 |
| [A²RD](https://arxiv.org/abs/2605.06924) | 分段「检索–合成–精修–更新」。每段记录文本状态：身份、身份变化、动作、空间三元组、镜头。另有全局参考与成功/失败提示库。外推与内插的切换由多模态大模型根据下一段剧情决定 | 1 分钟 VBench-Long：叙事 0.90（基线 0.75），角色 0.74（0.57）。10 分钟时角色/环境/物体一致 90.5/84.0/91.5%。每段额外开销 < 7.2 分钟 | 逐块文本状态；成功/失败提示库作为跨会话程序性记忆；「推进 vs 纠偏」策略（在线版改为三种可执行干预，§5.4） | 重生成和编辑；需要预知下一段；内插需要预定的终止帧 |
| [VQQA](https://arxiv.org/abs/2603.12310) | 问题生成：对齐问题 5–10 个、质量问题 8–10 个 → 问答 → 以低分问答对作「语义梯度」改写提示 → 全局 VLM 按**原始**提示选优 | T2V-CompBench +11.57，VBench2 +8.43；平均 1.245 轮，约 7.23 次 VLM 调用 | 编译时为每条指令生成可检验的问题；语义梯度作用于**下一块**的提示 | 迭代重生成与全局选优 |

**来源机制与我们的新机制要分开看。** 上表「原文」与「关键数字」两列是论文核实过的机制。「在线化后保留」一列是我们**新提出、尚未验证**的机制：跨会话老虎机、前向修正、文本状态账本。另外两点说明：
- CANVAS 的主要产出是**分镜关键帧**，只有附录中才把关键帧交给 Veo 生成约 1.5 分钟视频。
- 「每段数分钟」的开销专指 A²RD。
- Co-Director 的整条流水线拉臂与 VQQA 的候选选优为我们提供了灵感，但**不能**证明在线版本有效。

**空白。** 在我们的检索范围内，没有找到满足以下全部条件的系统：
- 在**截止时间内**判定用户**实际看到**的内容；
- 只做**向前**修正，不重生成；
- 容许用户中途打断；
- 能跨会话保持人设与用户记忆。

这是检索结论，不是「不存在」的证明。

### 2.2 TaoMate 的两个版本：论文 ≠ H3 代码

| | TaoMate（论文，LTX-2.3 初始化） | TaoMate-H3（负责人指定） |
|---|---|---|
| 参数量 | 22.1B（新增记忆模块 97.8M） | H3 约 33B DiT + rank-128 LoRA |
| 记忆 | 不可变视觉锚点 + 固定容量压缩音视频状态 + 分模态残差注意力【引用】；代码中每 4 层一个记忆注意力层【代码：TaoMate `learned_memory.py`】 | **没有**。只有 sink + 最近 2 块的滚动 KV，以及首块颜色重标定【代码】 |
| 块粒度 | 生成块 = 3 个潜帧 ≈ 1 秒，但交互演示**每约 5 秒窗口（5 块）才换一次提示**【代码：TaoMate `runtime.py:46-53`、`streaming_runtime.py:4927`】。1 秒级的提示控制**尚未证实** | 5 秒请求 = 4 块【代码】 |
| 速度 | 3 卡 35 FPS（卡型未说明）；单张 RTX PRO 5000 为 11.1 FPS【引用】 | 8×H20 约 16.2 FPS【引用】 |
| 交互 | 有演示：FastAPI + SSE、本地 Gemma 规划、文件队列、每窗口一个提示；**打断标志写入后从未被读取**【代码】 | 无服务端、无队列、无回调【代码】 |
| 注意力后端 | flex_attention / SDPA（可能可在 CC 8.9 上运行）【代码】 | 必须 FA3（SM90）【代码】 |
| 许可 | 代码 Apache-2.0；权重继承 LTX-2.3 与 Gemma 的许可 | MiniMax H3 社区许可：排除欧盟、英国、韩国、美国地区 |

**设计含义。** TaoMate-H3 是**主底座**（负责人指定）。TaoMate-LTX 只作为**系统级对照**：它与 H3 在骨干、规模、记忆、音频路径、运行时上都不同，所以两者的差异**不能**归因到任何单一因素。LingBot-World 2.0 降为**可选的世界镜头与对照**，其核查结论见 `docs/backbone_verification.md`。

### 2.3 其他相关方向（摘要）

- **流式视频与世界模型。** CausVid、Self Forcing、LongLive、Matrix-Game、LingBot-World。
- **实时数字人。** LiveAvatar、SoulX-FlashTalk、LPM 1.0、X-Streamer。
- **双工语音。** Moshi、Qwen3-Omni。
- **快说慢想的前后端分工。** 已是业界通用做法，我们复用，不作为贡献。
- **与播放对齐的上下文。** PACE（音频）。
- **长期记忆。** MemGPT、Mem0、Zep；其短板是纠错与遗忘：MemoryAgentBench 选择性遗忘 ≤ 28%，K-Bench 删除后仍泄漏 22–86%。

以上均为【引用】，详见 `related_work.md`。

---

## 3. 贡献：科学与工程分开

**科学贡献（待检验）：**

- **S1（核心）在线智能体导演。** 把 Co-Director / CANVAS / A²RD / VQQA 在截止时间、仅可前向修正、可被打断的约束下重新设计：
  - **状态账本**：CANVAS 的全局计划加上 A²RD 的逐块文本状态，用来合成每个块脚本；
  - **能力清单**：离线用 VQQA 式问答和 A²RD 评分细则校准，记录每类动作、表情、台词的实测成功率与生效时间；
  - **在线质检**：编译时生成可检验问题，由 VLM 在截止时间内对呈现内容作答；
  - **前向语义梯度**：失败时把低分问答写进**最早可接收修正的请求**的提示；
  - **推进 vs 纠偏**：检测到漂移时采取三种可执行干预之一（§5.4）。

  我们检验的是这个**组合**相对于开环提示与各消融版本的效果。
- **S2（测量）块粒度下的 TVC 协议。** 以挂钟时间衡量「指令 → 呈现且被判定遵循」的时间，在**同一条时间线**上逐项分解：提示锁定、音频教师、学生生成、编码传输、呈现、视觉惯性。从未遵循的样本按删失处理。粒度的影响只在**同一骨干内**比较（§4 RQ3）。
- **S3（评估）直播人设的类型化记忆。** 按来源区分用户断言、智能体推断、人设生成、观众声称、系统观测，按作用域区分私有、公开、正典。评估虚假记忆、纠错与删除的传播，以及跨语音、屏幕文字、生成画面的泄漏。

**工程集成（必要，但不算贡献）：**

| 编号 | 内容 |
|---|---|
| T1 | TaoMate-H3 **会话中途提示队列**：rank 0 队列广播，文本编码器常驻 GPU，删除「请求必须属于预编译提示列表」的校验（`base10_teacher.py:177`） |
| T2 | **音频教师前瞻一请求**：常驻加载基座 H3 的音频过程，比视频提前一个请求计算 |
| T3 | **逐块 fMP4 输出**，取代结尾一次性写 MP4（`runner.py:124-263`） |
| T4 | **FA3 → FA2/SDPA 移植**，以适配 CC 8.9（`attention_hook.py`、`model/layers.py`）；或改用 H20/H200 级机器 |
| T5 | 客户端呈现时间戳与播放积压控制 |
| T6 | 语音链路（VAD、ASR、话轮） |
| T7 | 可选：LingBot 世界镜头 |
| T8 | 打断回滚：按块快照 KV 与音频教师尾部，回滚到最后一个**已呈现**的块。可行性未知，M1 评估 |

**长期方向（需训练，不属首个演示）：**
- 把 TaoMate 论文的学习型锚点记忆移植到 H3；
- 缩短 H3 的请求粒度（重新蒸馏）；
- 音频教师的逐块化。

---

## 4. 研究问题与可证伪假设

阈值见 §8，均为【目标】。

| RQ | 假设 | 证伪条件 |
|---|---|---|
| **RQ1 在线导演（主）** | **H1a** 完整在线导演（A2）的**指令级成功率**高于开环（A1：LLM 直接写块提示）。以**有效意图链**（最终意图未被撤回，含被容量跳过的链）为分母，每条计分一次；拒绝、降级与容量跳过都算失败（§7.2）。**H1b** 虚假完成声明率更低。**H1c** 消融后下降：去掉清单、去掉质检、去掉前向修正、去掉账本，各自都会下降 | A2−A1 成对差的 95% CI 含 0 或为负；FCR 不降；消融无下降 |
| **RQ2 前向修正** | **H2** 在同一个、事先定义的失败点上，**随机分配**「前向语义梯度修正」或「重复原指令」，比较在**最早可接收修正的请求**（按 §5.4 时间线确定，并如实报告它是第几个请求）中的补救率 | 补救率差的 CI 含 0 |
| **RQ3 时延与粒度（主）** | **H3a** 通过实时认定时，在 H3 上用 §6.4 的单时间线模型（每 R 秒锁定一次）预测 TVC，中位数误差 ≤ 1 个请求周期。近实时运行没有固定节奏，改为检验**排队模型**：TVC ≈ A + 等待准入 + 完整请求处理时间 + I，并用实测的队列时间戳单独做预测与分析，中位数误差 ≤ 1 个请求处理时间。**H3b（有前提）** 先在 TaoMate-LTX 上证实可以逐块（约 1 秒）换提示，再在**同一骨干内**比较 1 秒与 5 秒提示粒度：细粒度的 TVC 中位数更低，且遵循率**非劣**（边际 5 pp，事先做功效计算）。H3 与 LTX 之间的比较只作系统级描述 | 预测误差 > 1 周期；逐块换提示不可行（报告为发现）；TVC 无差异，或遵循率劣于边际 |
| **RQ4 长时一致性** | **H4** 在 H3 **内部**做析因消融（§7.4 的 7 组，提示预算与重置频率匹配）：账本本身，以及它与纠偏、重置的组合，各自提升 30–60 分钟一致性。TaoMate-LTX 的学习型记忆只作描述性对照 | 仅账本与逐字重复无差异；各组合相对其无账本对照无差异 |
| **RQ5 记忆** | 类型化 + 隔离记忆的虚假用户事实率更低，召回非劣（边际 5 pp）。话语通道用户级跨域泄漏的精确（Clopper–Pearson）单侧 95% 上界 < 1%（≥ 300 名模拟用户）。删除后泄漏 < 5% | 未更低或召回劣于边际；上界 ≥ 1%；删除后泄漏 ≥ 5% |
| **RQ6 体验与底座价值** | 混合会话中比较 A2 与交互式语音 + 头像基线 A0：动作与表现类任务上 A2 更受偏好；纯对话任务上 A0 的 TFMR 更低，且 MOS 不劣（边际 0.5）。同时报告 A2 相对 B0 的交互价值与时延容忍度 | A2 对 A0 的偏好 CI 含 0；两个方向的结果都有信息量 |

主问题为 RQ1 与 RQ3。所有结果（包括零结果）都报告。

---

## 5. 方法与系统架构

### 5.1 候选架构比较

| | A0 语音 + 头像（交互式系统基线） | B0 预写脚本 | A1 开环直连 | **A2 在线导演（提出）** | A3 紧耦合（长期） |
|---|---|---|---|---|---|
| 做法 | LLM + 流式 TTS + 实时音频驱动头像（如 SoulX-FlashHead / Ditto 类，M1 选型），同一记忆服务 | TaoMate-H3 原生 JSON 脚本、固定循环，不交互 | LLM 根据对话直接写下一请求的提示 | 分层导演 + 状态账本 + 能力清单 + 在线质检 + 前向修正 + 类型化记忆 | 把学习型记忆移入 H3，重蒸馏为更细粒度，甚至端到端双工 |
| 交互 | 有（话轮级、低时延） | 无 | 有（5 秒粒度） | 有（5 秒粒度，另有即时反应层，§5.5） | 视训练而定 |
| 可观测遵循 | 仅限语音与头部 | – | 未验证 | 测量并修正 | 未知 |
| 训练 | 无 | 无 | 无 | 无（只需校准） | **需要** |
| 可行性【估计】 | 高 | 高 | 高 | 中高 | 低 |

**共享底座（去混杂）。** B0、A1、A2 使用同一 TaoMate-H3 运行时（含 T1–T3）、同一 LLM、ASR 与记忆服务。A1 与 A2 之间只有控制器不同，这一对比回答 RQ1。**A0** 是交互式的「语音 + 头像」系统基线（D-004 保留），用于端到端时延、语音、偏好与成本的系统级比较（RQ6）。它回答「在语音必须跟随 5 秒请求的前提下，TaoMate-H3 是否值得」。TaoMate-LTX 上的 A2 作为粒度与记忆的对照（RQ3、RQ4）。

### 5.2 A2 的五层结构

从上到下依次为：

1. **交互层（快路径）。**
   - VAD/ASR、话轮与打断管理；
   - **应答 LLM**：小而快，产出下一块的台词与动作意图。
2. **导演层（Co-Director 在线化）。**
   - 人设风格轴（策略、叙事模式、美学）在会话开始时固定，在会话内注入每个智能体；
   - **规划 LLM**（慢路径，异步）维护目标栈并拆解多步请求；
   - UCB1 老虎机只在**会话之间**更新。奖励由两部分组成：分因子 MLLM 评审，加上用户显式反馈。
     - 与 Co-Director 一样，奖励**按轴分别**更新三个轴。
     - 所有臂都**保持正典**：只影响表达方式（语气、节奏、景别），不改外貌与声音。
     - 老虎机只在单独的预试会话中训练；E2–E5 评估期间**冻结策略**。它的作用另做一个单独随机化的次要消融。
3. **连续性层（CANVAS + A²RD 在线化）。**
   - **状态账本**：人设外貌状态、地点 id、道具状态（含持有者）、逐块文本状态（身份、动作、空间三元组、镜头）；
   - **块脚本合成器**：把账本中不变的字段（外貌、场景、镜头、声音）**逐字复用**，只让动作与台词演进。这个约定来自 TaoMate（LTX）论文；H3 实际接受的是每个请求一个字符串，所以要经过编译（§5.3），写法与 H3 官方示例相同。
4. **生成层。**
   - TaoMate-H3 流式运行时，加上 T1 提示队列、T2 音频前瞻、T3 逐块输出；
   - 在这一层之上，**编译器**只下发能力清单中实测可靠的动作或表情描述，其余降级（比如改为口头回应）或婉拒。
5. **质检层（VQQA 在线化）。**
   - 编译时为每条指令生成 1–3 个【目标】可检验问题，例如「这一块中人物是否举杯喝茶？」；
   - 在线 VLM 在**呈现**后的截止时间内作答；
   - 失败时生成前向语义梯度（低分问答 → **最早可接收修正的请求**的提示中的修正）；
   - 检测到漂移时触发**纠偏**（定义见 §5.4）；
   - 离线部分：完整的 VQQA 与 A²RD 评分细则只用于校准能力清单，从不用于评估。

**记忆服务**贯穿各层（§5.6）。A²RD 的成功/失败提示库在其中作为跨会话的程序性记忆。

### 5.3 中间表示：块脚本（BlockScript）及其编译后的 H3 提示

块脚本是内部结构。编译器把它编译为 TaoMate-H3 实际接受的**每 5 秒一个字符串**【代码：`config.py:80-134`】，格式与官方示例相同：`integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`，台词写成内联的 `<d>[Chinese] …</d>`（示例文件 `examples/prompts_60s.json`）。

官方 60 秒示例中，每个 5 秒提示都会逐字复述「同一人物、同一服饰、同一场景、镜头与光照保持不变」，只让动作与台词变化。状态账本做的就是把这种写法**自动化、可审计**。

```yaml
# 块脚本（内部）
request_index: 42
plan_version: 17
canon:        # 取自正典与账本，逐字复用，不由 LLM 改写
  subject: "a young East Asian woman (S1) in a green hanfu, hair in a bun with a jade hairpin"
  scene: "classical study, lotus pond outside the window, teapot, pastries and incense burner on the desk"
  camera: "locked eye-level medium shot, soft key light, constant exposure"
  voice: "S1 uses the same gentle, medium-paced Mandarin voice"
evolving:
  action: "she puts the book down and lifts the teacup with both hands to take one sip"   # 须命中能力清单
  transcript: "好，我先喝口茶，再给你讲 CUDA。"
checks: ["人物是否捧起茶杯并喝茶？", "台词是否被完整、准确地说出？"]
provenance: {source_utterance: utt-551, speaker: user}
```

```text
# 编译后交给 TaoMate-H3 的提示（第 42 个请求）
integrated_multimodal_description: [Shot 1] Live-action portrait livestream, one uninterrupted five-second shot.
The same young East Asian woman (S1) in a green hanfu, hair in a bun with a jade hairpin, sits in the same classical
study; the lotus pond, teapot, pastries and incense burner remain unchanged. The locked eye-level medium shot,
soft key light and exposure remain constant. S1 uses the same gentle, medium-paced Mandarin voice. She puts the book
down and lifts the teacup with both hands to take one sip, then says once: <d>[Chinese] 好，我先喝口茶，再给你讲 CUDA。</d>
Her lips close. No other person or human voice appears. No captions or readable text appear anywhere in frame.

overall_soundscape: Clear dry Mandarin speech, quiet room tone, a soft porcelain clink as the cup is set down.

non_diegetic_music: N/A
```

**声音与台词的保证范围。** H3 没有声音参考输入，最终音频来自基座 H3 的纯音频教师【代码：`runtime.py:339-359,739-743`】。所以：
- 声音一致性只能靠文本描述与音频尾部延续；
- 「台词被逐字说出」不能事先保证，E1 要测：在换提示、换种子、会话重置之后，逐字准确率（WER）是多少，说话人是否一致；
- 进入生成前的内容审核只能拦住**脚本**，拦不住模型说出脚本以外的话；
- 在即时锁定的余量 σ 内，对**已生成**的请求音频做 ASR 复核，不合格就不播放该请求，改为反应片段加口头说明。这一步增加的时延与误拦率都单独计量。若 σ 内来不及复核，就如实声明「播放前不保证台词」。

**叙述策略。**
- **意图**可以立即说出，比如「好，我喝口茶」。
- **完成**（例如「刚才那首歌你喜欢吗」这类以「已发生」为前提的话）只有在质检判定遵循之后，才能出现在后续台词里。

### 5.4 关键时序、纠偏与打断

**单一时间线**（请求周期 R = 5 秒，每个请求依次经过以下事件）：
1. **锁定提示** $P_{k}$：块脚本 $s_k$ 定稿；之后到达的指令只能进入 $s_{k+1}$。
2. **音频教师** $A_k$：基座 H3 为 $s_k$ 计算音频里程碑，用时 $G_a$。
3. **学生生成**：从 $S_k$ 开始逐块生成，第一块用时 $G_1$；学生按步骤消费教师里程碑，所以教师必须提前完成，或者与学生并行且在各步骤到来前就绪。
4. **可见**：请求 $k$ 在 $V_k$ 开始呈现，4 个块依次可见。

**提前量** $\Lambda = G_a + G_1 + \delta$，即从锁定提示到第一块生成完毕、可以播放的时间。

**两个硬约束。**
1. **呈现时隙。** 请求 $k+1$ 最早只能在请求 $k$ 的 5 秒时隙结束后呈现，即 $V_{k+1} \ge V_k + R$。
2. **KV 依赖。** 学生生成 $k+1$ 需要 $k$ 的最终 KV 提交；发布代码按请求顺序执行【代码：`runner.py:299-323`】。

所以就绪时间 $\text{ready}_{k+1} = \max(P_{k+1} + G_a,\ \text{done}_k) + G_1 + \delta$，呈现时间 $V_{k+1} = \max(\text{ready}_{k+1},\ V_k + R)$。

**锁定策略：即时锁定（本版采用，记入 D-018）。**
- 在请求 $k$ 呈现期间**尽量晚**锁定 $k+1$：$P_{k+1} = V_k + R - \Lambda - \sigma$，其中 $\sigma$ 为安全余量，也用于生成语音的 ASR 复核。
- 前提有两条：$\text{done}_k \le P_{k+1} + G_a$，即上一请求的学生已完成；以及完整流水线吞吐 < R。
- 这样，锁定到呈现的时间只有 $\Lambda + \sigma$，而不是一整个 R。
- **对照策略：** 早锁定（在 $k$ 开始呈现时锁定 $k+1$）更抗抖动，但锁定到呈现要一个 R；L = 1 还要再加一个 R。

**最早可接收修正的请求。**
- 请求 $k$ 的第 $c$ 块（从 0 起算）在 $V_k + c\Delta$ 时**开始**呈现，$\Delta$ 为单块时长，约 1.4 秒。
- **证据完整时刻** $E$：检验所需的**最后一帧**实际呈现的时刻，取自客户端呈现时间戳。下面的 $E = V_k + (c+1)\Delta$ 假设各块等长、播放不间断，仅作示意；实际块长不等（首请求为 39/34/34/17 帧），且可能降速播放，所以分析一律使用**实测**的最后一帧呈现时间。
- 修正链条耗时 $C = v + $ 修正合成 $+$ 编译 $+$ 内容审核 $+$ 文本编码，其中 $v$ 为 VLM 判定时间。
- 修正进入**第一个满足** $P_j \ge E + C$ 的请求 $j$。$j$ 可以是 $k+1$、$k+2$ 或更晚，**不设上限**。
- 在即时锁定下，整块检验时进入 $k+1$ 的条件是 $(c+1)\Delta + C \le R - \Lambda - \sigma$。例如（示意，假设等长块）$\Lambda + \sigma = 3.5$ 秒时，只有第 0 块、且 $C \le 0.1$ 秒才可能进入 $k+1$【推导】，所以通常是 $k+2$。早锁定下，**不可能**进入 $k+1$。
- E2 实测并报告 $C$ 的各项、$j$ 的分布，以及错过或不具备修正资格的失败。

**纠偏：三种可执行的干预**，都要与「只逐字重复正典字段」对照：
1. **文本纠偏。** 针对漂移的属性加入明确的修正语句，例如「发簪为玉簪，不是金簪」。这是提示内容的**实质改变**，不同于逐字重复。
2. **会话重置。** 用正典文本新开一个生成会话，KV 与 sink 都重新建立。会有可见接缝，接缝需要测量。
3. **图像重锚定。** 仅在 FL2AV（参考帧版本）发布并验证后才有，届时从正典帧启动新会话。

在此之前，本提案不把前两种称为「图像锚定」。

**打断。**
- 客户端立即停止播放（**视觉确认**，目标 ≤ 250 ms），切到最后一个已呈现的帧或反应片段。视觉确认与**有意义的生成回应**分开计量。
- 生成端的问题：正在生成的请求仍可能提交 KV，并推进音频教师的尾部，导致后续内容依赖用户**从未看到**的动作和台词。
- 处置方式，按优先级：
  1. T8 回滚到最后一个已呈现的块（可行性在 M1 评估）；
  2. 会话重置（测量延迟与接缝）；
  3. 接受分叉：账本记录「已生成未呈现」的内容，下一个块脚本显式衔接，并如实计量这种不连续。

### 5.5 即时反应层（弥补 5 秒粒度）

语音由视频模型生成，所以对话延迟至少等于一个请求的延迟（§6.4）。我们引入两项缓解措施：

- **预渲染反应片段库。** 离线用同一底座、同一人设生成「点头倾听」「思考」「稍等」等 1–3 秒【目标】片段，由客户端在打断或等待时切入。它只提供**视觉确认**，不算有意义的回应。
  - 拼接处会有接缝，接缝需要测量；
  - 片段与实时流之间的身份一致性单独评估。
- **缩短请求。** 在 H3 上缩短请求需要重新蒸馏，属于长期方向。短期内，只有在 LTX 上**证实可以逐块换提示**之后，才能在该骨干内检验粒度的影响（RQ3）。

### 5.6 长期记忆设计

五类状态严格区分：

| 类别 | 载体 | 生命周期 | 不可混淆为 |
|---|---|---|---|
| 工作上下文 | 应答与规划提示、近期话轮、**已呈现**内容摘要 | 单次会话 | 长期记忆 |
| 持久用户事实与偏好 | 语义存储：主语、谓语、值、溯源、有效起止、作用域、置信度、derived_from | 跨会话 | 智能体推断 |
| 情景历史 | 只追加日志（时间戳、说话人） | 跨会话 | 摘要 |
| 人设与世界连续性（**状态账本**） | 正典锚点（永不覆盖）、最近状态、地点与道具状态、逐块文本状态；H3 的 FL2AV 发布后再加入参考帧 | 跨会话 | 生成器 KV |
| 模型推理缓存 | TaoMate-H3 的 sink + 最近 2 块 KV、位置偏移、首块归一化统计量、音频教师尾部、LLM KV | 单次生成器会话 | **任何**长期记忆 |

**写入。**
- 事实只从用户话轮抽取，并先判断句子属于哪一类：本人断言、转述人设的话、提问、假设或玩笑。
- 人设说过的话进入**生成事件日志**，永不升级为用户事实。
- 与人设旧输出语义匹配的候选标记为 `echo`，须经用户确认。
- 智能体推断只作为候选信念。
- 弹幕只写入公开作用域，标注 `viewer-claimed`，限速并清洗。

**作用域。**
- 所有派生物都带 `source_scopes` 标签：摘要、人设台词、账本条目、反应片段。
- 直播模式只加载 ⊆ {公开, 正典} 的内容。
- 私聊中人设说的话属于私有。
- 公开会话只能从正典锚点启动。

**纠正。** 双时态更新：旧值记下 `valid_to` 并保留审计。纠正沿 `derived_from` 让所有派生物失效。

**删除（擦除）。** 物理删除，并级联到以下对象：
- 嵌入与索引；
- 摘要（删除后重新生成）；
- 账本条目；
- 缓存提示与 LLM KV（通过重启会话清空）；
- 私有录像；
- 生成器状态：若被删内容仍在未发送的块脚本或当前生成状态中，丢弃未发送的块脚本，并从正典锚点重启生成会话。

已呈现的画面无法撤回。墓碑账本只记录哈希 id、时间和原因。

**冲突优先级。** 用户断言（最新有效）> 系统观测 > 智能体推断 > 观众声称。

---

## 6. 底座集成计划（依据代码核查）

### 6.1 已具备（代码中可见）【代码】

- 3 步去噪的流式 LoRA（rank 128，未合并，以 BF16 旁路存放）；
- 按请求提示（JSON 列表）；
- 滚动 KV，同一全局时间轴、不重置；
- 音视频同步输出；
- 并行方式为 TP2 × Ulysses4，支持 4 或 8 卡；
- 480p / 768p / 1088p。

### 6.2 仅上游报告【引用】

- TaoMate-H3 的速度数字（8×H20），**不含**内部音频准备，且输出到最后才写出；
- TaoMate 论文的 35 FPS、30 分钟以上连续生成、各项质量指标。项目主页与论文的数字不一致，例如 LipSync 5.773 与 5.918。
- 参考帧版本 FL2AV「10/15 前发布」，Ref2AV 待定。

### 6.3 需工程扩展（T1–T7，见 §3）

最小集成点：
- `runner.py:299-323`：取下一个提示的循环；
- `streaming/runtime.py:609-621`：每块输入的构建；
- `cli.py:223-229`：音频教师的预计算。

**vLLM-Omni 在 `7b4dc76` 与 `3bd5ac9` 两个版本上都**无法**直接承载 TaoMate-H3，原因有四：
- LoRA 加载器只认 Turbo 文件名与 PEFT 键；
- H3 模型没有跨请求的持久缓存；
- H3 没有实现实时 WebSocket 或流式会话接口；
- 现有的续写与分块解码都只在单个请求内工作【代码】。

**结论：** 短期直接在 TaoMate-H3 运行时上加队列，比移植到 vLLM-Omni 省事得多。移植到 vLLM-Omni 作为后续上游贡献。

### 6.4 时延模型【推导】（数值仅作示意，由 M1 实测替代）

沿用 §5.4 的单一时间线。$R$ = 5 秒；$\Lambda = G_a + G_1 + \delta$ 为锁定到可见的提前量；$A$ 为端点检测、应答 LLM 与编译的时间；$I$ 为视觉惯性。

锁定每隔 R 发生一次，指令要等 $U(0,R)$ 才赶上下一次锁定。锁定到呈现的时间取决于锁定策略（§5.4），且呈现不能早于上一请求的时隙结束：

| 策略 | TVC | 示意中位（$A = I = 0.5$ 秒） | 示意偏高 |
|---|---|---|---|
| **即时锁定（采用）** | $A + U(0,R) + \Lambda + \sigma + I$ | $\Lambda + \sigma = 3.5$ 秒时 ≈ **7 秒** | ≈ 9.5 秒 |
| 早锁定，L = 0 | $A + U(0,R) + R + I$ | ≈ **8.5 秒** | ≈ 11 秒 |
| 早锁定，L = 1 | $A + U(0,R) + 2R + I$ | ≈ **13.5 秒** | ≈ 16 秒 |

表中数值为各项相加的示意，**不是分位数**【推导·估计】。实现 T1–T3 之后，用实测时间戳重新计算，并做回放仿真。

**吞吐条件（完整流水线，不只是 DiT）。** 平均每个请求的（教师 + 学生 + 编码）时间要小于 R，并且两个模型同时常驻时显存与算力都够用。
- 8×H20 上仅 DiT 就要约 7.4 秒 / 请求【推导】，**不满足**。
- 教师的开销尚未测量：它要跑 9 次前向，且在发布路径中是预先完成的【代码】。
- 「教师与学生重叠执行」是新的工程（T2），能否满足 $\max(G, G_a)$ 形式的并行需要实测。

**TaoMate-LTX。** 其提示粒度同样约为 5 秒窗口【代码】，所以**不预设**它的 TVC 更低，只在 M0 中实测。

**三步资格（按实现顺序）。**
1. **M0：组件剖析**（不是资格认定）。在发布路径上分别测教师、学生、编码的耗时与显存。发布路径先准备全部音频，最后写一个 MP4【代码：`cli.py:219-229`、`runner.py:293-330`】，所以 M0 **无法**测端到端的 Λ 与呈现时间。
2. **M1：端到端资格。** T1–T3 完成后，在真实的客户端播放路径上测 Λ、σ、吞吐与抖动，并做 ≥ 3 × 30 分钟浸泡测试，卡顿 ≤ 1 次 / 10 分钟。这一步只认定「生成器 + 播放路径」的实时性。
3. **M2 末：整系统再认定。** 语音链路、A2 控制器、VLM 质检与记忆服务都会增加时延与 GPU 争用，所以装配完整系统后要再做一次同标准的浸泡测试。通过之后，才能宣称「实时直播智能体」，并以**实时**标签开展 E2 与 E5。**若未通过**，E2 与 E5 仍然进行，但改用 §1.2 的近实时服务规则（话轮制 + 准入控制），所有结果标注为「近实时」：
   - RQ1、RQ2、RQ4、RQ5 的对照仍然有效，因为 A1 与 A2 共享同一底座；
   - 时延类目标（TVC、TFMR）只报告实测值与等待时间的增长，**不**宣称达到 §8 的实时目标。

两阶段都通过后，才称为「实时」；否则按「近实时」如实标注。

### 6.5 需训练或研究

- 把学习型锚点记忆移植到 H3；
- 缩短请求粒度（重新蒸馏）；
- 音频教师的逐块化；
- 端到端双工。

首个演示不依赖这些。

---

## 7. 实验设计

**控制变量：**
- 底座检查点与 LoRA 版本；
- GPU 型号与数量；
- 分辨率 480×864；
- LLM、ASR、VLM 版本；
- 随机种子；
- 脚本化工作负载。

**记录项：**
- 全部挂钟时间戳；
- 块脚本与版本；
- 检验问题与判定；
- 呈现帧哈希。

### 7.0 M0：硬件与底座表征（门槛）

- 在 `gpu run` 预约中执行 `torch.cuda.get_device_capability()`，确认是否为 SM90。
- 在发布路径上，4 卡与 8 卡各跑 3 次 × 60 秒的 TaoMate-H3 生成【目标】，**分组件**剖析：音频教师、学生每块、VAE 解码、编码各自的耗时与显存。发布路径按顺序执行教师与学生，所以**两者同时常驻**的显存与争用在 T2 完成后、于 M1 用专门的测试程序测量。M0 的结果只用于估计 Λ，端到端资格在 M1 认定（§6.4）。
- 若本机 GPU 为 CC 8.9：先做 T4（FA2/SDPA 移植），并做与 FA3 输出的一致性检验（在另一台 H20/H200 上），再测速；否则申请 Hopper 机器。
- 在同一硬件上测 TaoMate-LTX 作为对照。

### 7.1 E1：能力校准（构建能力清单）

在 5 个场景 × 人设上，共 **40 个动作与表情描述**：喝茶、翻书、挥手、点头、起身、笑、皱眉等。另测台词类型（讲解、唱歌、问答）。每项 30 次试验【目标】。

**评判：**
- 离线 VQQA 式问答；
- A²RD 评分细则；
- 20% 分层抽样做人工双盲标注。

**产出：**
- 成功率（Wilson CI）；
- 生效时间分布（KM 曲线）；
- 副作用：身份漂移、口型失配。

**校准数据与评估数据互不相交。**

### 7.2 E2：指令遵循、多步任务、打断与纠正（RQ1、RQ2、RQ3）

**任务。** 80 个任务 × 5 个种子【目标】，由 TTS 模拟用户按脚本发出。分为三类：
- 单步动作或内容；
- 多步任务，如「先喝口茶，再翻到下一页，然后讲一段」；
- 交互动态：中途纠正、改目标、打断、针对呈现内容的指代纠正。

**条件：** B0、A1、A2、A2−清单、A2−质检、A2−前向修正、A2−账本，以及 TaoMate-LTX 上的 A2。

**主结局：** 对每次试验做**双人双盲人工裁定**，第三人仲裁，独立于在线质检。

**计分单位：意图链。** 用户的一条新指令开启一条意图链。之后用户对它的撤回或改口**并入同一条链**，按链的最终意图计分一次。与之无关的新指令开启新链。**有效意图链** = 最终意图未被用户撤回的意图链，包括被系统容量跳过的链。**主分母 = 有效意图链总数**，每条有效意图链恰好计分一次；用户撤回的链不在分母中，只单独报告数量。

**截止时间 D 与计时起点（事先注册，所有条件相同）【目标】。** 计时起点是开启该意图链、或最后一次改口的**用户话语结束时刻**（VAD 端点，在共享呈现时间线上）。

| 任务类型 | D | 判定内容 |
|---|---|---|
| 单步动作 / 表情 | 15 秒 | 首个被判定遵循的呈现帧 |
| 内容类（讲解、唱歌、问答） | **两项都满足才算成功**：(1) 15 秒内开始切题的语音回应；(2) 整段回应在「15 秒 + 预定时长」内完成，预定时长按任务事先注册（问答 ≤ 10 秒，讲解 ≤ 30 秒，唱歌 ≤ 30 秒），并满足事先注册的评分细则：问答答对；讲解覆盖指定的 k 个要点且无事实错误；唱歌唱出指定歌曲或主题的歌词段落且可辨认为歌唱 | 主结局要求 (1) 与 (2) 同时满足。「起始成功率」单独报告，不计入主结局 |
| 多步任务（n 步） | 每一步 15 秒，从上一步被判定遵循的时刻起算；总截止为 15n 秒 | 按顺序全部遵循才算成功 |
| 纠正 / 改口 | 从改口话语结束时重新计时，15 秒 | 按最终意图判定 |

近实时模式使用同样的 D，这样结果可以直接比较。超时即失败，并在 D 处删失。

**结果规则：**

| 情况 | 处理 |
|---|---|
| 拒绝或降级 | 计为失败 |
| 用户改口或撤回 | 并入同一意图链，按最终意图计分一次；撤回的链不计入分母，单独报告 |
| 容量跳过（系统因负载，按准入控制丢弃一条**未被用户改口**的意图链） | 该链属于有效意图链，**计为失败**。容量跳过率 = 被跳过的链数 / 有效意图链总数（不含撤回链），按条件单独报告 |
| 评判「无法判断」 | 主分析计为失败，另做敏感性分析 |
| 从未遵循 | 在截止时间 $D$ 处删失 |

**指标：**
- 指令级成功率（分母为有效意图链总数）；
- 容量跳过率与撤回链数；
- 拒绝与降级率；
- 条件遵循率；
- FCR = 被裁定为未完成的完成声明数 / 完成声明总数，同时报告声明覆盖率；
- 补救率（RQ2）；
- TVC（截止成功率、KM 中位数）；
- 首个有意义回应（TFMR）。

**功效与预注册。** 以任务为聚类单位，事先注册估计量。用预试得到的基线成功率、任务内相关（ICC）与多重比较校正（Holm）做仿真，确定样本量。本提案不预先声称可检出多大的差异。

**RQ2 设计。** 在事先定义的失败点上随机分配「前向修正」或「重复原指令」，避免按处理后的结果挑选样本。

**B0 的定位。** B0 主要检验「交互」对「固定循环」的价值，不承担其他结论。

### 7.3 E3：记忆（RQ5）

- **组件基准：** LongMemEval_S、MemoryAgentBench 选择性遗忘、GateMem 式作用域测试。
- **直播人设协议：** 20 用户 × 6 会话【目标】，覆盖以下情形：
  - 人设生成的干扰信息，例如人设说「我最爱喝龙井」；
  - echo 探针；
  - 纠正与删除；
  - 私聊后立刻开直播；
  - 弹幕投毒（MINJA 式）。
- **对照组（RQ5）：** 在相同工作负载与相同检索预算下比较四种记忆：
  - 全历史上下文；
  - Mem0 式无类型抽取；
  - 去掉作用域隔离的 A2 记忆；
  - 完整的 A2 记忆。
- **泄漏上界：** 在 **≥ 300 名独立模拟用户**上检验话语通道：块脚本的台词文本，以及**底座生成的语音**。
  - 所有对探针问题的**生成语音回答**都由两人完整听审（约 900 段），不依赖 ASR 抽检。
  - ASR 只用于其他场景的筛查，它的检出灵敏度用人工标注校验。
  - 精确上界 < 1% 要求**零**用户级泄漏。
  - 屏幕文字与生成画面只在约 30 名用户上做描述性统计。

### 7.4 E4：长时一致性与核心假设（RQ4）

- 在 H3 内部比较以下几组（提示长度预算与重置频率在组间匹配）：
  1. 纯脚本；
  2. 逐字重复正典字段；
  3. **仅账本**（账本驱动提示合成，不做纠偏）；
  4. 账本 + 文本纠偏；
  5. 无账本的文本纠偏：**同一个**漂移检测器、同一条纠偏规则、同一时机，只是纠偏文本只能取自静态正典档案，拿不到账本记录的当前状态；
  6. 账本 + 会话重置；
  7. 无账本的会话重置：由同一个漂移检测器在同样条件下触发，重置后的提示只来自静态正典档案。

  组 4 对 5、组 6 对 7 之间，**唯一的差别是能否读取账本**，由此把账本的作用与纠偏、重置本身分开。TaoMate-LTX 学习型记忆只作描述性对照。会话数按会话级精度计算确定（预试估计方差后，目标 ≥ 10 场 × 30–60 分钟【目标】）。
- 指标：
  - 人脸身份相似度，阈值用人工同一/不同标注校准；
  - **语音保真与内容**：生成语音的 ASR 转写相对台词的 WER；跨会话、跨重启的说话人一致性（嵌入 + 人工同一/不同判断）；讲解类内容的事实正确性（评分细则 + 人工）；
  - 服饰、场景、道具状态探针；
  - 声音一致性（说话人嵌入）；
  - 口型同步 LSE-C/D；
  - 接缝与卡顿。
- **核心假设的检验：** 在 ≥ 3 次【目标】会话重启之间（每次都是新上下文）检验记忆与遵循阈值。未包装的端到端系统若有权重，按原样参与；否则检验较弱的消融版本（A2 对去掉记忆服务的 A1），并如实标明其较弱。

### 7.5 E5：人工评估（RQ6）

- 被试内设计，平衡顺序。预试 N = 12，正式 N = 24【目标】。
- 条件：A0、B0、A2（A1 视时间而定）。
- 量表：MOS、SUS、Godspeed、社会临场感、时延容忍度、成对强制选择（Bradley–Terry 分析）。
- 流程：预注册；知情同意。

### 7.6 E6：私有测试直播

脚本化观众，2 小时 × 3 场【目标】。测量：
- 弹幕响应时延；
- 投票动作的成功率；
- 投毒与泄漏；
- 卡顿。

**参考主播 sylar_nv 仅作定性参照**，因为其实现未经证实（H3 片段拼接是推测）。只有满足下面全部条件，才做定量对比：VOD 已存档、弹幕与视频时间对齐、使用脚本化测试账号、运营者同意。即便如此，结论也标明为非受控对比。

### 7.7 不确定性报告

- 所有指标都给 95% CI（聚类 bootstrap），并报告 κ。
- 时延给出 p50/p95/p99，每项 ≥ 3 次重复。
- 删失数据用生存曲线分析。
- 遵循率始终与覆盖率一起报告。

---

## 8. 指标与成功标准（均为【目标】，M0 与预试后修订）

| 指标 | 成功标准 |
|---|---|
| 指令级成功率（H1a，主；分母为有效意图链总数，即最终意图未被撤回的链，含被容量跳过的链；拒绝、降级、容量跳过均计为失败） | A2 − A1 ≥ +10 pp，成对 CI 不含 0 |
| 虚假完成声明率 FCR | A2 ≤ 5% 且低于 A1；声明覆盖率 ≥ 70% |
| 前向修正补救率（H2） | 在最早可接收修正的请求中，补救率高于「重复原指令」，CI 不含 0；同时报告该请求是第几个 |
| TVC（动作类） | H3 使用即时锁定，且 **M1** 实测 Λ + σ ≤ 3.5 秒时：15 秒内截止成功率 ≥ 80%，KM 中位 ≤ 8 秒。Λ 更大或改用早锁定时，在 M1 后按回放仿真重设。H3 与 LTX 之间的**跨骨干**比较只作描述；LTX 内部的粒度检验见 RQ3 |
| 首个有意义回应 TFMR | 回应语音开始播放的时间：p50 ≤ 8 秒（前提同 TVC；由实测时间线计算） |
| 视觉确认（反应片段或停帧） | p95 ≤ 1 秒；与 TFMR 分开统计 |
| 语音保真 | 生成语音的 ASR-WER 相对台词 ≤ 10%；跨会话说话人一致性 ≥ 80%（人工判断） |
| 讲解正确性与安全 | 事实错误率与不安全内容率单独报告。块脚本进入生成前先审核；**已生成的语音**在呈现前于 σ 余量内做 ASR 复核，额外时延与误拦率单独计量 |
| 打断停止 | p95 ≤ 250 ms（客户端） |
| 身份一致性（30–60 分钟） | ≥ 80% 的窗口高于人工校准阈值；声音相似度同样标准 |
| 口型同步 | LSE-C/D 不劣于 H3 基座的发布水平 |
| 虚假用户事实率 | ≤ 2% 且低于基线 |
| 删除后泄漏 | ≤ 5% |
| 跨域泄漏（话语通道） | 精确上界 < 1%（≥ 300 名用户） |
| 流稳定性 | ≤ 1 次卡顿 / 10 分钟（通过实时资格的配置） |
| 评判有效性 | κ ≥ 0.6，否则以人工标注为主 |

---

## 9. 里程碑、资源与风险

### 9.1 里程碑（周期为【估计】）

| 里程碑 | 周期 | 内容 |
|---|---|---|
| M0 | ≈ 1 周 | 硬件确认；FA 移植可行性；H3 与 LTX 测速；权重使用许可 |
| M1 | ≈ 3 周 | T1–T3、T5；浸泡测试；E1 校准；质检评判验证 |
| M2 | ≈ 3 周 | A0/B0/A1/A2、账本、记忆服务、语音链路、反应片段库；**结束时对整系统再认定实时性** |
| M3 | ≈ 3 周 | E2–E4 |
| M4 | ≈ 2 周 | E5 预试、E6、撰写报告 |

### 9.2 资源

- **GPU：** H3 需要 4–8 卡，另需 1–2 卡跑 LLM、ASR、VLM。全部通过 canhazgpu 预约并设置超时。这是偏乐观的估计。
- **硬件前提：** 若本机确为 CC 8.9，要么完成 T4，要么使用 Hopper 机器。
- **模型：** 本地共享目录已有 MiniMax H3 快照（272 GB，含 FL2VA/Ref2VA 与文本编码器，完整性未校验）。TaoMate-H3 LoRA 与 TaoMate-LTX 权重需要下载，本阶段未下载。

### 9.3 主要风险

| 风险 | 可能性【估计】 | 对策 |
|---|---|---|
| FA3 无法在本机运行，或移植后精度下降 | 高 | M0 门槛；使用 Hopper 机器；以 TaoMate-LTX 兜底 |
| H3 吞吐达不到实时 | 高（按 H20 数据） | 近实时模式并如实标注；降分辨率；以 LTX 对照 |
| 5 秒粒度导致交互体验差 | 高 | 即时反应层；RQ3 量化；长期重新蒸馏 |
| 提示词无法稳定产生指定动作 | 中 | 能力清单排除；口头替代；作为研究发现报告 |
| 音频教师与中途提示冲突（音频按请求预算） | 中 | T2 前瞻一请求；指令延后一个请求生效并标注 |
| 打断后生成状态与呈现内容分叉 | 高 | T8 回滚 / 会话重置 / 显式衔接，并计量不连续 |
| 教师与学生同时常驻时显存或算力不足 | 中 | M1 在 T2 后实测；分卡部署；降分辨率 |
| 许可（H3 社区许可排除美、欧、英、韩地区） | 确定 | 仅作研究用途，部署地区须合规 |
| GPU 调度冲突 | 中 | 提前预约时段 |

---

## 10. 局限、隐私安全伦理

**局限：**
- 尚无本地测量；
- TaoMate-H3 的关键结论来自代码阅读，未执行；
- 5 秒粒度是底座的硬约束，本提案只做缓解与量化，不解决它；
- 模拟用户无法覆盖自发语音；
- 人评规模小；
- 参考主播不受控。

**隐私与安全：**
- 私有记忆仅在明确同意后存储；用户可查看、纠正、删除，删除会级联；
- 公开与私有物理隔离，泄漏探针作为发布门槛；
- 生成内容永不成为用户事实；
- 弹幕视为不可信输入；
- 人设为虚构，所有直播都标注 AI 生成；不使用真人肖像或声音；
- 对弹幕请求做内容审核（参考主播的弹幕中出现过不当请求）；
- 语音由底座生成，LLM 无法流式控制每个字，所以块脚本要在**进入生成前**审核，生成后再做 ASR 抽检；
- 遵守 MiniMax H3 社区许可与 LTX/Gemma 许可；
- 人评须通过伦理审查。

---

## 11. 参考文献（完整、经核实的 BibTeX 见 `docs/references.bib`）

- **Google 长视频套件：** google2026longformblog，song2026codirector，mondal2026canvas，long2026a2rd，song2026vqqa
- **TaoMate：** gan2026taomate；TaoMate-H3（[GitHub](https://github.com/TaoLiveAIGC/TaoMate-H3)，提交 `6b2f998`；[HF](https://huggingface.co/TaoLiveAIGC/TaoMate-H3)）；TaoMate 代码（提交 `136d890`）
- **MiniMax H3：** minimax2026h3blogvideo
- **LingBot 与流式视频：** gao2026lingbotworld2，yang2025longlive，huang2025selfforcing
- **数字人与双工：** huang2025liveavatar，xie2025xstreamer，huang2026wanstreamer，defossez2024moshi，wang2026pace
- **控制与验证：** ahn2022saycan，huang2022innermonologue，xu2026worldmark，abotworld2026abotworld0
- **记忆与评估：** wu2024longmemeval，hu2025memoryagentbench，ren2026gatemem，yu2026kbench，dong2025minja，ying2026wbench

## 12. 评审状态

本中文版（v2.0 → v2.11）属于重大架构变更。它提交 GPT-6 Sol（Codex）独立评审，记录见 `docs/codex_reviews.md` 的「中文 v2.0」一节。

===== FILE: docs/implementation.md =====
# Implementation (Phase 2)

Status: started 2026-09-26 on the owner's instruction (D-019). This document describes the implementation of
the proposal in `docs/research_proposal_zh.md` v2.11: the architecture as built, how to run it, and what is
verified. Every number is labelled *measured locally*, *cited*, *estimate* or *target*.

## Layout

| Path | Proposal § | What it is |
|---|---|---|
| `live_agent/types.py` | §9, §10 | Shared types: CanonProfile, BlockScript, IntentChain, Chunk, Verdict, TimelineEvent |
| `live_agent/prompt/h3_compiler.py` | §9 | BlockScript → TaoMate-H3 prompt string, in the official `integrated_multimodal_description` / `<d>` format. Canon fields are copied verbatim |
| `live_agent/capability.py` | §8.2 L4, §14.2 | Capability manifest. The compiler emits an action only when it is `executed`/`calibrated` and above the success threshold; otherwise it degrades or refuses (both logged as failures) |
| `live_agent/ledger.py` | §8.2 L3, §10.4 | State ledger (online CANVAS + A²RD): immutable canon, current state, per-request state, textual drift correction, bridging for unshown content |
| `live_agent/timeline.py` | §10, §11 | Single timeline, just-in-time locking (P_{k+1} = V_k + R − Λ − σ; Λ estimated online), earliest correctable request, latency model, JSONL event log |
| `live_agent/director/director.py` | §8.2 L1–2, §9 | Responder (LLM → intent chains + per-request segments), cancellation rule, narration policy ("done" is spoken only after verification), forward-repair queue, A1 open-loop mode |
| `live_agent/qc/judge.py` | §8.2 L5 | VLM judge on presented frames (K=4, may abstain), speech check (ASR character error rate), forward corrector ("semantic gradient"), mock judge |
| `live_agent/orchestrator.py` | §10–§12 | Lock loop, chunk streaming, presentation acks → QC → repair, barge-in (drop unpresented, bridge), erasure (memory cascade + generator reset) |
| `live_agent/memory/` | §12 | Typed, scoped SQLite memory: claim typing, echo detection, source-scope filtering before ranking, bi-temporal correction, erasure cascade with tombstones and `verify_erased` |
| `live_agent/memory_bridge.py` | §12 | Adapter from the memory service to the orchestrator |
| `live_agent/generator/base.py`, `mock.py` | §13 | Generator contract; CPU mock with the TaoMate-H3 chunk layout (39/34/34/17 frames, then 34/34/34/17) |
| `live_agent/generator/taomate_h3.py`, `taomate_worker/` | §13 (T1–T3) | TaoMate-H3 streaming adapter: mid-session prompt queue, audio-teacher lookahead, per-chunk output. Status is tracked in `docs/m0_measurements.md` |
| `live_agent/server/app.py`, `static/index.html` | — | FastAPI WebSocket server and browser client. JPEG frames + PCM16 per chunk; the client's AudioContext is the master clock; chunk start/end acks are stamped with server time |
| `live_agent/asr.py` | — | Qwen3-ASR client (vLLM transcription API) and audio decoding |
| `live_agent/eval/` | §7, §14, §15 | Evaluation: SCHEMA.md log format, scoring (intent chains, D table, outcome rules), stats (Wilson, Clopper–Pearson, KM, clustered bootstrap, Holm, κ, power), 30-task suite, simulated user, runner, report |
| `configs/persona_hanfu/` | §3 | Persona canon and capability manifest (24 actions covering the E2 suite; `documented` until E1 executes them) |
| `live_agent/generator/base.py` `SessionView` | — | One live session on a long-lived shared generator: reset per session, local request numbering, stale chunks dropped (D-022) |
| `live_agent/sim.py` `Recorder` | — | MP4 of the *presented* stream (background-thread encoding), used for adjudication and E1 clips |
| `live_agent/eval/adjudicate.py` | §14, D-014 | Blinded human adjudication: shuffled items, random ids and media names, key kept apart; labels merged back as `source: adjudicated` verdicts with video→session time mapping (D-024) |
| `scripts/e1_calibrate.py` | §14.2 | E1: idle → action → idle per trial; VLM judge; Wilson CI; clips for the 20% human sample. A judge-only pass marks capabilities `executed`, and only human-validated labels make them `calibrated` |
| `scripts/serve_models.sh` | — | vLLM servers for Qwen3-8B (8101), Qwen3-VL-8B (8102), Qwen3-ASR-1.7B (8103) on one GPU (isolated venv `.venvs/serve`, vLLM 0.28.0 + torch cu129) |

## Running

```bash
# helper models (one GPU; always through canhazgpu)
gpu run --gpus 1 --timeout 6h --note "live-agent helper models" -- scripts/serve_models.sh

# server with the mock generator (no video GPU needed)
python3 -m live_agent.server.app --generator mock --dev-allow-uncalibrated --port 8200
# server with TaoMate-H3 (student on 4 GPUs, teacher on 2; started once, shared across sessions)
gpu run --gpus 6 --timeout 4h --note "live-agent server" -- python3 -m live_agent.server.app --generator taomate_h3
# open http://127.0.0.1:8200 (tunnel the port if remote)

# E2 simulation on the mock stack (real LLM responder, mock judge)
python3 -m live_agent.eval.runner --conditions A1 A2 --seeds 0 --speed 4 --out .cache/e2
# E2 / M1 on the real stack (TaoMate-H3 + LLM responder + VLM judge), recording what was presented
gpu run --gpus 6 --timeout 1h --note "live-agent M1" -- env PYTHONPATH=. python3 -m live_agent.eval.runner \
    --generator taomate_h3 --conditions A2 A1 --out .cache/m1 --record [--allow-uncalibrated]
python3 -m live_agent.eval.report .cache/m1/*.jsonl --compare A2:A1 -o .cache/m1/report.md

# blinded adjudication of the primary outcome
python3 -m live_agent.eval.adjudicate prepare .cache/m1/*.jsonl -o .cache/adj/batch1
python3 -m live_agent.eval.adjudicate merge .cache/adj/batch1 labels-batch1.json --annotator <id>

# E1 calibration
gpu run --gpus 6 --timeout 4h --note "live-agent E1" -- env PYTHONPATH=. python3 scripts/e1_calibrate.py \
    --generator taomate_h3 --trials 30 --save-clips --out .cache/e1

# tests (CPU)
python3 -m pytest
```

## Verified so far

- **GPU identity (measured locally, 2026-09-26):** `torch.cuda.get_device_capability()` = (9, 0), 132 SMs,
  139.8 GiB. Hopper, so FA3 is usable (D-020).
- **CPU test suite:** unit and end-to-end tests pass on the mock stack. They cover:
  - the prompt format;
  - JIT lock timing;
  - verified-then-claim ordering;
  - forward repair;
  - refusal of unsupported actions;
  - barge-in drop and bridging;
  - the open-loop baseline;
  - the memory rules;
  - the scoring rules;
  - statistics.
- **Deadlock classes found and fixed by tests:** barge-in or erasure dropping requests that the backlog guard
  was waiting on.

- **M0 (measured locally):** the TaoMate-H3 streaming adapter is real time at 480x864 on 4+2 GPUs. See
  `docs/m0_measurements.md` and D-021.
- **M1 qualification run (measured locally, 2026-09-26; `.cache/m1`, 12 sessions = 6 tasks × A2/A1, seed 0,
  real TaoMate-H3 + Qwen3-8B responder + Qwen3-VL-8B judge, pre-E1 manifest with `--allow-uncalibrated`):**
  - 29–52 chunks per session, **0 playback gaps > 50 ms** in all 12 sessions (after moving the recorder off
    the event loop; the first attempt showed ~0.1 s gaps per chunk caused by the synchronous recorder).
  - A2: every completion claim came after a judge `complied` verdict (0/5 contradicted by the judge). One
    forward repair (M01 step 1) succeeded on the retry, 2 requests after the failure.
  - Judge-sourced chain outcomes: A2 4/6 success (A01, A03, D01, D04), C01 "never" because content rubric
    verdicts come only from adjudication, M01 "never" because of a converter bug (verdicts lacked `step`;
    fixed afterwards, with a test). A1 has no online judge by design, so it scores 0 under judge-only
    scoring. **This is not an A2-vs-A1 result:** the primary outcome is blinded adjudication (D-014), n is
    tiny, and the manifest is not yet calibrated.
  - On-topic speech onset (TFMR) median ≈ 4.2 s in both conditions. The judge-sourced TVC for A2 actions
    uses the start of the verified request as the compliance time (the online judge gives no first
    compliant frame), so it is a lower bound.
  - Spot check (manual, one session): in A2-E2-A01 the persona reaches for the teacup and lifts it toward her
    mouth in the verified request.
- **E2 dry run (simulation):** 54 sessions (A1/A2/A2-repeat × 6 tasks × 3 seeds, mock generator and judge,
  real LLM). The pipeline scores end to end. The repair offset j−k is always 2 with 5 s requests (the
  failure is known only after the full request is presented, and request k+1 is already locked), so most
  repaired chains finish after the 15 s action deadline. This is a structural property to report.

## Not yet verified

- **E1:** a judge-only pilot (5 trials per capability) is the next step. Validated calibration needs the 20%
  human sample.
- **Primary outcome:** nothing has been adjudicated yet. The tool exists; annotators are needed.
- 30-min soak, 768p/1080p, 60 s+ sessions on the TaoMate path, and the browser playback path on a remote
  client (σ, jitter) are not yet measured. The M1 run used the simulated client on the server host.
- None of the simulation outputs are experimental results. The mock judge's success probability is an
  input, not a measurement.

===== FILE: live_agent/eval/SCHEMA.md =====
# E2 session-log schema (v1)

The orchestrator, simulated user, online judge and human adjudication tool all append to
one JSONL file per **session** (= one task × one seed × one condition). Scoring
(`live_agent/eval/scoring.py`) implements proposal v2.11 §7.2 (intent chains, deadline
table D, outcome rules) and §8 metrics. Validation lives in `live_agent/eval/schema.py`
(`SessionLogWriter`, `load_session`). Events may appear in any order; the loader sorts
them by time.

**Times:** all `t*` fields are seconds on the **shared presentation timeline** (the clock
the client uses to timestamp presented frames, `live_agent.types.now`). Do not use wall-clock time.

## Header (line 1)

```json
{"type": "session", "schema_version": 1, "session_id": "A2-E2-D04-s3",
 "condition": "A2", "task_id": "E2-D04", "seed": 3,
 "mode": "realtime|near_realtime", "backbone": "taomate-h3"}
```
Required: `session_id`, `condition`, `task_id`, `seed`. Other keys are free-form metadata.

## Events

| type | required fields | optional fields | emitted by |
|---|---|---|---|
| `utterance` | `uid`, `speaker` (`user`/`persona`/`viewer:<id>`), `text`, `t_start`, `t_end` (VAD endpoint) | `barge_in` (bool) | sim user / ASR |
| `chain_annotation` | `uid` (of the utterance), `action` (`new`/`revision`/`withdrawal`), `chain_id` | `label` (task-local chain label for cross-condition pairing, e.g. `c1`), `kind` (`action`/`content`/`multistep`; `correction` is treated as `action`), `intent`, `content_type` (`qa`/`explain`/`sing`), `prereg_duration_s`, `steps` (list or int) | sim user (script) or annotator |
| `lock` | `t`, `request` | `chain_ids`, `plan_version` | orchestrator (diagnostic; not needed for scoring) |
| `chunk_presented` | `request`, `chunk`, `t_start`, `t_end` | `frame_hash` | client presentation ack |
| `verdict` | `source` (`adjudicated`/`human`/`judge`), `label` (`complied`/`not_complied`/`unknown`), and `chain_id` **or** `claim_id` | `step` (multistep, 0-based), `request`, `chunk`, `t_first_compliant`, `t_evidence`, `revision` (number of revisions the judged intent includes), `qid`, `annotator` | judge / human tool |
| `completion_claim` | `chain_id`, `t` | `step`, `claim_id`, `text` | orchestrator (persona says "done") |
| `refusal` | `chain_id`, `t` | `kind` (`refused` (default) / `degraded`), `reason` | compiler / safety filter |
| `capacity_skip` | `chain_id`, `t` | `reason` | admission control |
| `speech_onset` | `t`, `on_topic` (bool) | `chain_id` (**required for the onset to count toward a chain**), `request` | client audio playback + annotation |
| `visual_ack` | `t`, `uid` (the utterance acknowledged) | `kind` (`reaction_clip`/`freeze`) | client |
| `playback_stop` | `t` | `reason` | client |
| `repair_assignment` | `chain_id`, `arm` (`forward_correction`/`repeat`), `failure_request` (k), `target_request` (j = earliest request with P_j ≥ E + C) | `step`, `E`, `C` | orchestrator (RQ2 randomisation) |

## Time fields on verdicts

* `t_first_compliant`: presentation time of the **first frame judged compliant**. It defines
  TVC and the judged-compliance time of a multistep step. If it is missing, the scorer
  uses the `t_start` of `chunk_presented(request, chunk)`, then `t_evidence`.
* `t_evidence`: presentation time of the **last** frame (or audio) needed for the verdict
  (E in §5.4). For content chains this is the **end of the response**, and it is the
  completion time.
* Verdicts whose compliance time is earlier than the chain's current clock origin are
  ignored, because they judged a superseded intent. When `revision` is present it must
  equal the chain's final revision count.
* Per chain, only the highest-preference source present is used: `adjudicated` >
  `human` > `judge`. Override the order with `ScoringConfig.source_preference`, for
  example `("judge",)` to score the online QC.

## Scoring rules (summary; all *proposed targets*, identical across conditions)

* **Chain.** `new` opens a chain. `revision` merges into it: the intent fields are
  replaced and the clock restarts at the revising utterance's `t_end`. `withdrawal`
  withdraws the chain, and a later `revision` reopens it. Each chain is scored once, on
  its final intent.
* **Effective chains** (primary denominator) are all chains that do not end withdrawn.
  Capacity-skipped chains are included.
* **Precedence:** withdrawn → capacity-skipped (fail) → refused/degraded (fail) →
  deadline rules. A skip or refusal only counts if it happened at or after the final clock
  origin.
* **Deadlines D:**
  * action: first judged-compliant frame ≤ 15 s;
  * content: on-topic `speech_onset` ≤ 15 s **and** a `complied` rubric verdict with
    `t_evidence` ≤ 15 s + preregistered duration (qa 10, explain 30, sing 30, or
    `prereg_duration_s`);
  * multistep: step *i* complied ≤ 15 s after step *i−1*'s compliance (step 0: after the
    origin), with every step in order.
* **Outcomes:** `success`, `late`, `never` (censored at D), `unknown` (a "cannot tell"
  verdict inside the window decided the failure: counted as a failure in the primary
  analysis and excluded in the sensitivity analysis), `onset_fail`, `rubric_fail`,
  `order_fail`, `refused`, `degraded`, `capacity_skipped`, `withdrawn`.
* **FCR:** a claim is contradicted unless a `complied` verdict for that chain (and step,
  if the claim names one) has its compliance time in [origin in force at the claim,
  `t` + `claim_grace_s` (default 0)]. A verdict carrying the claim's `claim_id` settles
  the claim directly, and `unknown` counts as contradicted. **Claim coverage** is the
  share of effective chains with at least one claim; coverage among successful chains is
  also reported.
* **Repair (RQ2):** success means a `complied` verdict on `request == target_request`.
  The offset j−k is reported.
* **TVC** (action chains): first compliant frame − origin, censored at 15 s.
  **TFMR**: first on-topic `speech_onset` − origin, censored at 15 s.
  **Visual-ack latency**: `visual_ack.t` minus the utterance's `t_end`, or its `t_start`
  for a barge-in.
  **Barge-in stop latency**: the first `playback_stop` at or after a barge-in
  utterance's `t_start`, minus that `t_start`.
* **Conditional success** = successes / served chains (effective chains that were not
  refused, degraded or skipped).

## Minimal example

```jsonl
{"type":"session","schema_version":1,"session_id":"s1","condition":"A2","task_id":"E2-A01","seed":0}
{"type":"utterance","uid":"s1:u0","speaker":"user","text":"请喝口茶吧。","t_start":2.0,"t_end":3.1}
{"type":"chain_annotation","uid":"s1:u0","action":"new","chain_id":"s1:c1","label":"c1","kind":"action","intent":"端起茶杯喝一口茶"}
{"type":"visual_ack","t":3.5,"uid":"s1:u0"}
{"type":"chunk_presented","request":2,"chunk":0,"t_start":9.6,"t_end":11.0}
{"type":"verdict","chain_id":"s1:c1","source":"adjudicated","label":"complied","request":2,"chunk":0,"t_evidence":11.0}
{"type":"completion_claim","chain_id":"s1:c1","t":12.0}
```

===== FILE: live_agent/eval/schema.py =====
"""Session-log schema (JSONL) for E2 scoring. Human-readable spec: ``SCHEMA.md``.

One file = one session = one task x one seed x one condition. Line 1 is a ``session``
header; every other line is an event. All times are seconds on the shared presentation
timeline (the same clock as ``live_agent.types.now``), not wall-clock.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# event type -> required fields (besides "type")
REQUIRED: dict[str, tuple[str, ...]] = {
    "session": ("session_id", "condition", "task_id", "seed"),
    "utterance": ("uid", "speaker", "text", "t_start", "t_end"),
    "chain_annotation": ("uid", "action", "chain_id"),
    "lock": ("t", "request"),
    "chunk_presented": ("request", "chunk", "t_start", "t_end"),
    "verdict": ("source", "label"),
    "completion_claim": ("chain_id", "t"),
    "refusal": ("chain_id", "t"),
    "capacity_skip": ("chain_id", "t"),
    "speech_onset": ("t", "on_topic"),
    "visual_ack": ("t", "uid"),
    "playback_stop": ("t",),
    "repair_assignment": ("chain_id", "arm", "failure_request", "target_request"),
}

ANNOTATION_ACTIONS = ("new", "revision", "withdrawal")
VERDICT_LABELS = ("complied", "not_complied", "unknown")
VERDICT_SOURCES = ("adjudicated", "human", "judge")
REFUSAL_KINDS = ("refused", "degraded")
REPAIR_ARMS = ("forward_correction", "repeat")


class SchemaError(ValueError):
    pass


@dataclass
class SessionLog:
    meta: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def session_id(self) -> str:
        return str(self.meta["session_id"])

    @property
    def condition(self) -> str:
        return str(self.meta["condition"])

    @property
    def task_id(self) -> str:
        return str(self.meta["task_id"])

    @property
    def seed(self) -> int:
        return int(self.meta["seed"])

    def of_type(self, *types: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] in types]


def validate_event(ev: dict[str, Any]) -> None:
    typ = ev.get("type")
    if typ not in REQUIRED:
        raise SchemaError(f"unknown event type {typ!r}: {ev}")
    missing = [k for k in REQUIRED[typ] if k not in ev]
    if missing:
        raise SchemaError(f"{typ} event missing {missing}: {ev}")
    if typ == "chain_annotation" and ev["action"] not in ANNOTATION_ACTIONS:
        raise SchemaError(f"bad annotation action {ev['action']!r}")
    if typ == "verdict":
        if ev["label"] not in VERDICT_LABELS:
            raise SchemaError(f"bad verdict label {ev['label']!r}")
        if ev["source"] not in VERDICT_SOURCES:
            raise SchemaError(f"bad verdict source {ev['source']!r}")
        if "claim_id" not in ev and "chain_id" not in ev:
            raise SchemaError(f"verdict needs chain_id or claim_id: {ev}")
    if typ == "refusal" and ev.get("kind", "refused") not in REFUSAL_KINDS:
        raise SchemaError(f"bad refusal kind {ev.get('kind')!r}")
    if typ == "repair_assignment" and ev["arm"] not in REPAIR_ARMS:
        raise SchemaError(f"bad repair arm {ev['arm']!r}")


def _sort_key(ev: dict[str, Any]) -> float:
    for k in ("t", "t_end", "t_evidence", "t_start"):
        if k in ev and ev[k] is not None:
            return float(ev[k])
    return float("-inf")


def parse_session(records: Iterable[dict[str, Any]]) -> SessionLog:
    records = list(records)
    if not records or records[0].get("type") != "session":
        raise SchemaError("first record must be a 'session' header")
    meta = dict(records[0])
    validate_event(meta)
    events = []
    for ev in records[1:]:
        validate_event(ev)
        events.append(dict(ev))
    events.sort(key=_sort_key)  # stable: equal times keep file order
    return SessionLog(meta=meta, events=events)


def load_session(path: str | Path) -> SessionLog:
    with open(path, encoding="utf-8") as f:
        recs = [json.loads(line) for line in f if line.strip()]
    return parse_session(recs)


class SessionLogWriter:
    """Append-only JSONL writer; the orchestrator and the simulated user share one."""

    def __init__(self, path: str | Path, **meta: Any):
        self.path = Path(path)
        header = {"type": "session", "schema_version": SCHEMA_VERSION, **meta}
        validate_event(header)
        self._f = open(self.path, "w", encoding="utf-8")
        self.write(header)

    def write(self, ev: dict[str, Any]) -> None:
        validate_event(ev)
        self._f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> SessionLogWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

===== FILE: live_agent/eval/scoring.py =====
"""E2 scoring: intent chains, per-task deadlines, outcome rules (proposal v2.11 §7.2, §8).

Rules implemented (all *proposed targets*, preregistered, identical across conditions):

* Intent chain: opened by a ``new`` annotation; ``revision`` merges into the same chain,
  replaces its intent fields and restarts the clock; ``withdrawal`` withdraws it (a later
  revision re-opens it). Scored once, on the final intent.
* Clock origin: ``t_end`` (VAD endpoint) of the opening or latest revising utterance.
* Effective chains (primary denominator): final intent not withdrawn; capacity-skipped
  chains are included and count as failures.
* Deadlines D: action 15 s -> first judged-compliant presented frame; content: on-topic
  speech onset <= 15 s AND complete response (rubric pass) <= 15 s + preregistered duration
  (qa 10, explain 30, sing 30); multistep: 15 s per step measured from the previous step's
  judged-compliance time, all steps in order; correction = restart clock at revision.
* Outcomes: refused/degraded -> fail; capacity skip -> fail (in denominator); withdrawn ->
  excluded, counted; "cannot tell" -> fail in primary, excluded in sensitivity analysis;
  never complied -> censored at D.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Any

from live_agent.eval.schema import VERDICT_SOURCES, SessionLog
from live_agent.types import TaskKind

CONTENT_DURATION_S = {"qa": 10.0, "explain": 30.0, "sing": 30.0}  # proposed target (§7.2)


@dataclass(frozen=True)
class ScoringConfig:
    step_deadline_s: float = 15.0  # action / per multistep step / correction (proposed target)
    onset_deadline_s: float = 15.0  # content onset (proposed target)
    content_duration_s: dict[str, float] = field(default_factory=lambda: dict(CONTENT_DURATION_S))
    source_preference: tuple[str, ...] = VERDICT_SOURCES  # adjudicated > human > judge
    claim_grace_s: float = 0.0  # compliance evidence may trail a claim by at most this
    tfmr_horizon_s: float = 15.0  # TFMR censoring horizon


class Outcome(str, enum.Enum):
    SUCCESS = "success"
    LATE = "late"  # complied, but after the deadline
    NEVER = "never"  # no compliant verdict: censored at D
    UNKNOWN = "unknown"  # judge "cannot tell" decided the failure
    ONSET_FAIL = "onset_fail"  # content: no on-topic speech onset within 15 s
    RUBRIC_FAIL = "rubric_fail"  # content: response judged not meeting rubric
    ORDER_FAIL = "order_fail"  # multistep: steps complied out of order
    REFUSED = "refused"
    DEGRADED = "degraded"
    CAPACITY_SKIPPED = "capacity_skipped"
    WITHDRAWN = "withdrawn"


# --------------------------------------------------------------------------- chains


@dataclass
class Chain:
    chain_id: str
    label: str  # task-local label used to pair chains across conditions
    kind: TaskKind
    opened_uid: str
    origins: list[float]  # clock origins in order: opening, then each revision
    intent: str = ""
    content_type: str | None = None
    prereg_duration_s: float | None = None
    n_steps: int = 1
    revisions: list[str] = field(default_factory=list)
    withdrawn: bool = False
    withdrawn_t: float | None = None

    @property
    def clock_origin(self) -> float:
        return self.origins[-1]

    def origin_at(self, t: float) -> float:
        """Clock origin in force at time t (for judging claims made before a revision)."""
        cur = self.origins[0]
        for o in self.origins:
            if o <= t:
                cur = o
        return cur


def _kind(v: Any) -> TaskKind:
    k = TaskKind(v) if v is not None else TaskKind.ACTION
    return TaskKind.ACTION if k == TaskKind.CORRECTION else k


def _apply_intent(ch: Chain, ann: dict[str, Any]) -> None:
    if "kind" in ann:
        ch.kind = _kind(ann["kind"])
    if "intent" in ann:
        ch.intent = ann["intent"]
    if "content_type" in ann:
        ch.content_type = ann["content_type"]
    if "prereg_duration_s" in ann:
        ch.prereg_duration_s = ann["prereg_duration_s"]
    if "steps" in ann:
        ch.n_steps = len(ann["steps"]) if isinstance(ann["steps"], list) else int(ann["steps"])
    elif "kind" in ann and ch.kind != TaskKind.MULTISTEP:
        ch.n_steps = 1


def build_chains(session: SessionLog) -> dict[str, Chain]:
    utts = {e["uid"]: e for e in session.of_type("utterance")}
    anns = sorted(session.of_type("chain_annotation"), key=lambda a: utts[a["uid"]]["t_end"])
    chains: dict[str, Chain] = {}
    for a in anns:
        u = utts.get(a["uid"])
        if u is None:
            raise ValueError(f"annotation refers to unknown utterance {a['uid']}")
        cid = a["chain_id"]
        if a["action"] == "new":
            if cid in chains:
                raise ValueError(f"chain {cid} opened twice")
            ch = Chain(cid, a.get("label", cid), _kind(a.get("kind")), a["uid"], [float(u["t_end"])])
            _apply_intent(ch, a)
            chains[cid] = ch
            continue
        if cid not in chains:
            raise ValueError(f"{a['action']} of unknown chain {cid}")
        ch = chains[cid]
        if a["action"] == "revision":
            ch.revisions.append(a["uid"])
            ch.origins.append(float(u["t_end"]))
            ch.withdrawn, ch.withdrawn_t = False, None
            _apply_intent(ch, a)
        else:  # withdrawal
            ch.withdrawn, ch.withdrawn_t = True, float(u["t_end"])
    return chains


# --------------------------------------------------------------------------- outcomes


@dataclass
class ChainOutcome:
    session_id: str
    condition: str
    task_id: str
    seed: int
    chain_id: str
    label: str
    kind: str
    content_type: str | None
    outcome: Outcome
    clock_origin: float
    n_revisions: int
    deadline_s: float  # D for this chain
    time_to_success: float  # min(time, censor point); for KM
    success_event: bool
    tvc: float | None = None  # action chains: first judged-compliant frame - origin (censored at D)
    tvc_event: bool = False
    onset_s: float | None = None  # content: first on-topic speech onset - origin
    onset_ok: bool | None = None
    tfmr: float | None = None
    tfmr_event: bool = False
    steps_complied: int = 0
    n_claims: int = 0
    n_false_claims: int = 0
    repair_arm: str | None = None
    repair_success: bool | None = None
    repair_offset: int | None = None  # target_request - failure_request

    @property
    def success(self) -> bool:
        return self.outcome == Outcome.SUCCESS

    @property
    def effective(self) -> bool:
        return self.outcome != Outcome.WITHDRAWN

    @property
    def served(self) -> bool:
        """Attempted by the system (not refused, degraded, or capacity-skipped)."""
        return self.effective and self.outcome not in (
            Outcome.REFUSED,
            Outcome.DEGRADED,
            Outcome.CAPACITY_SKIPPED,
        )


@dataclass
class SessionScore:
    session_id: str
    condition: str
    task_id: str
    seed: int
    chains: list[ChainOutcome]
    visual_ack_s: list[float]
    barge_in_stop_s: list[float]
    barge_ins_without_stop: int


def _compliance_time(v: dict[str, Any], chunks: dict[tuple[int, int], dict[str, Any]]) -> float:
    """Presentation time of the first frame judged compliant."""
    if v.get("t_first_compliant") is not None:
        return float(v["t_first_compliant"])
    key = (v.get("request"), v.get("chunk"))
    if key in chunks:
        return float(chunks[key]["t_start"])
    if v.get("t_evidence") is None:
        raise ValueError(f"verdict without any time: {v}")
    return float(v["t_evidence"])


def _pick_source(vs: list[dict[str, Any]], pref: tuple[str, ...]) -> list[dict[str, Any]]:
    for s in pref:
        sel = [v for v in vs if v["source"] == s]
        if sel:
            return sel
    return []


def _score_chain(
    ch: Chain,
    verdicts: list[dict[str, Any]],
    chunks: dict[tuple[int, int], dict[str, Any]],
    onsets: list[dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[Outcome, dict[str, Any]]:
    """Deadline rules for a non-withdrawn, non-skipped, non-refused chain."""
    o = ch.clock_origin
    n_rev = len(ch.revisions)
    vs = [
        v
        for v in verdicts
        if v.get("revision") is None or int(v["revision"]) == n_rev
    ]
    vs = [dict(v, _tc=_compliance_time(v, chunks)) for v in vs]
    vs = [v for v in vs if v["_tc"] >= o]
    info: dict[str, Any] = {}
    D = cfg.step_deadline_s

    if ch.kind == TaskKind.CONTENT:
        dur = ch.prereg_duration_s
        if dur is None:
            dur = cfg.content_duration_s[ch.content_type or "qa"]
        D_c = cfg.onset_deadline_s + dur
        info["deadline"] = D_c
        on = [e["t"] - o for e in onsets if e["on_topic"] and e["t"] >= o]
        onset = min(on) if on else None
        info["onset_s"] = onset
        info["onset_ok"] = onset is not None and onset <= cfg.onset_deadline_s
        # rubric verdicts: t_evidence = presentation time of the end of the response
        rub = sorted(vs, key=lambda v: float(v.get("t_evidence", v["_tc"])))
        done = [float(v.get("t_evidence", v["_tc"])) - o for v in rub if v["label"] == "complied"]
        comp = min(done) if done else None
        info["t_complete"] = comp
        in_time = [v for v in rub if float(v.get("t_evidence", v["_tc"])) - o <= D_c]
        if not info["onset_ok"]:
            return Outcome.ONSET_FAIL, info
        if comp is not None and comp <= D_c:
            return Outcome.SUCCESS, info
        if comp is not None:
            return Outcome.LATE, info
        if any(v["label"] == "unknown" for v in in_time):
            return Outcome.UNKNOWN, info
        if any(v["label"] == "not_complied" for v in in_time):
            return Outcome.RUBRIC_FAIL, info
        return Outcome.NEVER, info

    # action (incl. corrections) and multistep: per-step 15 s from previous compliance
    n = ch.n_steps if ch.kind == TaskKind.MULTISTEP else 1
    prev = o
    done_steps = 0
    for i in range(n):
        step_vs = [v for v in vs if int(v.get("step", 0)) == i]
        ok = sorted(v["_tc"] for v in step_vs if v["label"] == "complied" and v["_tc"] >= prev)
        info["deadline"] = prev - o + D  # censor point if we stop here
        if not ok:
            window = [v for v in step_vs if prev <= v["_tc"] <= prev + D]
            if any(v["label"] == "unknown" for v in window):
                out = Outcome.UNKNOWN
            elif any(v["label"] == "complied" and v["_tc"] < prev for v in step_vs):
                out = Outcome.ORDER_FAIL
            else:
                out = Outcome.NEVER
            info["steps_complied"] = done_steps
            return out, info
        t_ok = ok[0]
        if i == 0 and n == 1:
            info["tvc"] = t_ok - o
        if t_ok - prev > D:
            info["steps_complied"] = done_steps
            info["t_late"] = t_ok - o
            return Outcome.LATE, info
        prev = t_ok
        done_steps += 1
    info["steps_complied"] = done_steps
    info["t_complete"] = prev - o
    info["deadline"] = D * n
    return Outcome.SUCCESS, info


def _claims(
    ch: Chain,
    claims: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    claim_verdicts: dict[str, list[dict[str, Any]]],
    chunks: dict[tuple[int, int], dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[int, int]:
    """Return (n_claims, n_contradicted). A claim is contradicted unless a complied verdict
    for that chain (and step, if the claim names one) has its compliant frame in
    [origin in force at claim time, t_claim + grace]. A verdict that carries the claim's
    ``claim_id`` adjudicates the claim directly and takes precedence ("unknown" = false)."""
    n_false = 0
    for c in claims:
        cid = c.get("claim_id")
        if cid is not None and cid in claim_verdicts:
            direct = _pick_source(claim_verdicts[cid], cfg.source_preference)
            if direct:
                n_false += int(direct[-1]["label"] != "complied")
                continue
        lo = ch.origin_at(float(c["t"]))
        hi = float(c["t"]) + cfg.claim_grace_s
        ok = False
        for v in verdicts:
            if v["label"] != "complied":
                continue
            if "step" in c and int(v.get("step", 0)) != int(c["step"]):
                continue
            if lo <= _compliance_time(v, chunks) <= hi:
                ok = True
                break
        n_false += int(not ok)
    return len(claims), n_false


def score_session(session: SessionLog, cfg: ScoringConfig | None = None) -> SessionScore:
    cfg = cfg or ScoringConfig()
    chains = build_chains(session)
    chunks = {(int(e["request"]), int(e["chunk"])): e for e in session.of_type("chunk_presented")}

    by_chain: dict[str, dict[str, list[dict[str, Any]]]] = {c: {} for c in chains}

    def put(cid: str | None, key: str, ev: dict[str, Any]) -> None:
        if cid in by_chain:
            by_chain[cid].setdefault(key, []).append(ev)

    claim_verdicts: dict[str, list[dict[str, Any]]] = {}
    for e in session.events:
        t = e["type"]
        if t == "verdict":
            if "claim_id" in e:
                claim_verdicts.setdefault(e["claim_id"], []).append(e)
            else:
                put(e["chain_id"], "verdict", e)
        elif t in ("completion_claim", "refusal", "capacity_skip", "repair_assignment") or (
            t == "speech_onset" and e.get("chain_id") is not None
        ):
            put(e["chain_id"], t, e)

    out: list[ChainOutcome] = []
    for cid, ch in chains.items():
        ev = by_chain[cid]
        o = ch.clock_origin
        verdicts = _pick_source(ev.get("verdict", []), cfg.source_preference)
        onsets = ev.get("speech_onset", [])
        skips = [e for e in ev.get("capacity_skip", []) if e["t"] >= o]
        refusals = [e for e in ev.get("refusal", []) if e["t"] >= o]

        info: dict[str, Any] = {}
        if ch.withdrawn:
            outcome = Outcome.WITHDRAWN
        elif skips:
            outcome = Outcome.CAPACITY_SKIPPED
        elif refusals:
            kinds = {e.get("kind", "refused") for e in refusals}
            outcome = Outcome.REFUSED if "refused" in kinds else Outcome.DEGRADED
        else:
            outcome, info = _score_chain(ch, verdicts, chunks, onsets, cfg)

        if ch.kind == TaskKind.CONTENT:
            dur = ch.prereg_duration_s or cfg.content_duration_s[ch.content_type or "qa"]
            D = cfg.onset_deadline_s + dur
        elif ch.kind == TaskKind.MULTISTEP:
            D = cfg.step_deadline_s * ch.n_steps
        else:
            D = cfg.step_deadline_s
        success = outcome == Outcome.SUCCESS
        if success:
            tts = float(info.get("t_complete", info.get("tvc", 0.0)))
        else:
            tts = float(info.get("deadline", D))  # censored where failure became certain

        rec = ChainOutcome(
            session_id=session.session_id,
            condition=session.condition,
            task_id=session.task_id,
            seed=session.seed,
            chain_id=cid,
            label=ch.label,
            kind=ch.kind.value,
            content_type=ch.content_type,
            outcome=outcome,
            clock_origin=o,
            n_revisions=len(ch.revisions),
            deadline_s=D,
            time_to_success=tts,
            success_event=success,
            steps_complied=int(info.get("steps_complied", 0)),
        )
        if ch.kind == TaskKind.ACTION and outcome != Outcome.WITHDRAWN:
            if info.get("tvc") is not None and info["tvc"] <= D:
                rec.tvc, rec.tvc_event = info["tvc"], True
            else:
                rec.tvc, rec.tvc_event = D, False  # censored at D
        if ch.kind == TaskKind.CONTENT and outcome != Outcome.WITHDRAWN:
            rec.onset_s = info.get("onset_s")
            rec.onset_ok = bool(info.get("onset_ok", False))
        if outcome != Outcome.WITHDRAWN:
            on = [e["t"] - o for e in onsets if e["on_topic"] and e["t"] >= o]
            first = min(on) if on else None
            if first is not None and first <= cfg.tfmr_horizon_s:
                rec.tfmr, rec.tfmr_event = first, True
            else:
                rec.tfmr, rec.tfmr_event = cfg.tfmr_horizon_s, False
            rec.n_claims, rec.n_false_claims = _claims(
                ch, ev.get("completion_claim", []), verdicts, claim_verdicts, chunks, cfg
            )
        rep = ev.get("repair_assignment", [])
        if rep:
            r = rep[-1]
            tgt = int(r["target_request"])
            step = r.get("step")
            rec.repair_arm = r["arm"]
            rec.repair_offset = tgt - int(r["failure_request"])
            rec.repair_success = any(
                v["label"] == "complied"
                and v.get("request") is not None
                and int(v["request"]) == tgt
                and (step is None or int(v.get("step", 0)) == int(step))
                for v in verdicts
            )
        out.append(rec)

    # latencies
    utts = {e["uid"]: e for e in session.of_type("utterance")}
    acks = []
    for e in session.of_type("visual_ack"):
        u = utts.get(e["uid"])
        if u is None:
            continue
        ref = u["t_start"] if u.get("barge_in") else u["t_end"]
        acks.append(float(e["t"]) - float(ref))
    stops = sorted(float(e["t"]) for e in session.of_type("playback_stop"))
    barge, missing = [], 0
    for u in utts.values():
        if not u.get("barge_in"):
            continue
        after = [s for s in stops if s >= float(u["t_start"])]
        if after:
            barge.append(after[0] - float(u["t_start"]))
        else:
            missing += 1

    return SessionScore(
        session_id=session.session_id,
        condition=session.condition,
        task_id=session.task_id,
        seed=session.seed,
        chains=out,
        visual_ack_s=acks,
        barge_in_stop_s=barge,
        barge_ins_without_stop=missing,
    )


# --------------------------------------------------------------------------- aggregation


def _rate(k: int, n: int) -> float:
    return k / n if n else math.nan


def summarize(chains: list[ChainOutcome]) -> dict[str, Any]:
    """Point estimates for one condition (CIs are added in report.py)."""
    eff = [c for c in chains if c.effective]
    n = len(eff)
    succ = sum(c.success for c in eff)
    skipped = sum(c.outcome == Outcome.CAPACITY_SKIPPED for c in eff)
    refused = sum(c.outcome in (Outcome.REFUSED, Outcome.DEGRADED) for c in eff)
    unknown = sum(c.outcome == Outcome.UNKNOWN for c in eff)
    served = [c for c in eff if c.served]
    content = [c for c in eff if c.kind == TaskKind.CONTENT.value]
    claims = sum(c.n_claims for c in eff)
    false_claims = sum(c.n_false_claims for c in eff)
    rep = [c for c in eff if c.repair_arm is not None]
    return {
        "n_effective": n,
        "n_success": succ,
        "success_rate": _rate(succ, n),
        "n_withdrawn": sum(not c.effective for c in chains),
        "capacity_skip_rate": _rate(skipped, n),
        "n_capacity_skipped": skipped,
        "refusal_degradation_rate": _rate(refused, n),
        "n_refused_degraded": refused,
        "n_unknown": unknown,
        "success_rate_excl_unknown": _rate(succ, n - unknown),  # sensitivity analysis
        "conditional_success_rate": _rate(sum(c.success for c in served), len(served)),
        "n_served": len(served),
        "content_onset_rate": _rate(sum(bool(c.onset_ok) for c in content), len(content)),
        "n_content": len(content),
        "n_claims": claims,
        "n_false_claims": false_claims,
        "fcr": _rate(false_claims, claims),
        "claim_coverage": _rate(sum(c.n_claims > 0 for c in eff), n),
        "claim_coverage_of_successes": _rate(
            sum(c.n_claims > 0 for c in eff if c.success), succ
        ),
        "repair": {
            arm: {
                "n": sum(c.repair_arm == arm for c in rep),
                "k": sum(bool(c.repair_success) for c in rep if c.repair_arm == arm),
                "offsets": sorted(c.repair_offset for c in rep if c.repair_arm == arm),
            }
            for arm in sorted({c.repair_arm for c in rep})
        },
        "outcomes": {o.value: sum(c.outcome == o for c in chains) for o in Outcome},
    }

===== FILE: live_agent/eval/stats.py =====
"""Statistics for E1-E6 (proposal v2.11 §7.7): binomial intervals, Kaplan-Meier with
right-censoring, clustered bootstrap (cluster = task), Holm, Cohen's kappa,
non-inferiority, and simulation-based power for a paired clustered binary outcome."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import optimize, stats

# --------------------------------------------------------------------------- binomial


def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Two-sided Wilson score interval."""
    if n == 0:
        return (math.nan, math.nan)
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return (float(lo), float(hi))


def wilson_upper(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided upper Wilson bound at level ``conf``."""
    return wilson(k, n, 2 * conf - 1)[1]


def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Exact two-sided Clopper-Pearson interval."""
    if n == 0:
        return (math.nan, math.nan)
    a = 1 - conf
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return (lo, hi)


def clopper_pearson_upper(k: int, n: int, conf: float = 0.95) -> float:
    """Exact one-sided upper bound (RQ5 leakage: 0/300 -> 0.00994)."""
    if n == 0:
        return math.nan
    return 1.0 if k == n else float(stats.beta.ppf(conf, k + 1, n - k))


# --------------------------------------------------------------------------- Kaplan-Meier


@dataclass
class KMResult:
    times: np.ndarray  # distinct event times
    survival: np.ndarray  # S(t) just after each event time
    at_risk: np.ndarray
    events: np.ndarray
    greenwood_var: np.ndarray

    def s_at(self, t: float) -> float:
        idx = np.searchsorted(self.times, t, side="right") - 1
        return 1.0 if idx < 0 else float(self.survival[idx])

    @property
    def median(self) -> float | None:
        """Smallest t with S(t) <= 0.5; None if not reached (report as '> horizon')."""
        hit = np.nonzero(self.survival <= 0.5 + 1e-12)[0]
        return float(self.times[hit[0]]) if hit.size else None

    def quantile(self, q: float) -> float | None:
        """Time by which a fraction q has had the event (e.g. q=0.95 -> p95)."""
        hit = np.nonzero(1 - self.survival >= q - 1e-12)[0]
        return float(self.times[hit[0]]) if hit.size else None

    def rmst(self, horizon: float) -> float:
        """Restricted mean time to event: integral of S(t) over [0, horizon]."""
        grid = np.concatenate([[0.0], self.times[self.times < horizon], [horizon]])
        s = np.concatenate([[1.0], self.survival[self.times < horizon]])
        return float(np.sum(np.diff(grid) * s))


def kaplan_meier(times: Sequence[float], events: Sequence[bool | int]) -> KMResult:
    """Product-limit estimator; ties: events before censorings at the same time."""
    t = np.asarray(times, dtype=float)
    e = np.asarray(events, dtype=bool)
    if t.size == 0:
        z = np.zeros(0)
        return KMResult(z, z, z, z, z)
    ut = np.unique(t[e])
    s, var_sum = 1.0, 0.0
    surv, risk, ev, gw = [], [], [], []
    for u in ut:
        n = int(np.sum(t >= u))
        d = int(np.sum((t == u) & e))
        s *= 1 - d / n
        if n > d:
            var_sum += d / (n * (n - d))
        surv.append(s)
        risk.append(n)
        ev.append(d)
        gw.append(s * s * var_sum)
    return KMResult(ut, np.array(surv), np.array(risk), np.array(ev), np.array(gw))


# --------------------------------------------------------------------------- bootstrap


def _cluster_index(clusters: Sequence[Hashable]) -> tuple[np.ndarray, int]:
    labels = {c: i for i, c in enumerate(dict.fromkeys(clusters))}
    return np.array([labels[c] for c in clusters], dtype=int), len(labels)


def cluster_bootstrap_mean(
    x: Sequence[float],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Percentile CI of a pooled mean, resampling whole clusters with replacement."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "boot": np.zeros(0)}
    idx, C = _cluster_index(clusters)
    sums = np.bincount(idx, weights=x, minlength=C)
    cnts = np.bincount(idx, minlength=C).astype(float)
    rng = np.random.default_rng(rng)
    draw = rng.integers(0, C, size=(n_boot, C))
    boot = sums[draw].sum(1) / cnts[draw].sum(1)
    a = (1 - conf) / 2
    return {
        "estimate": float(x.mean()),
        "lo": float(np.quantile(boot, a)),
        "hi": float(np.quantile(boot, 1 - a)),
        "boot": boot,
    }


def cluster_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Paired difference mean(a - b); units paired by position, clusters resampled whole.
    Also returns a two-sided bootstrap p-value (2 x the smaller tail mass at 0)."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    r = cluster_bootstrap_mean(d, clusters, n_boot=n_boot, conf=conf, rng=rng)
    boot = r["boot"]
    if boot.size:
        p = 2 * min(np.mean(boot <= 0), np.mean(boot >= 0))
        r["p_value"] = float(min(1.0, p))
    else:
        r["p_value"] = math.nan
    return r


def cluster_bootstrap_rate_diff(
    x: Sequence[float],
    in_a: Sequence[bool],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Unpaired difference mean(x | A) - mean(x | not A) with clusters resampled whole
    (e.g. RQ2 forward-correction vs repeat arms randomised within tasks)."""
    x = np.asarray(x, dtype=float)
    g = np.asarray(in_a, dtype=bool)
    idx, C = _cluster_index(clusters)
    sa = np.bincount(idx, weights=x * g, minlength=C)
    na = np.bincount(idx, weights=g.astype(float), minlength=C)
    sb = np.bincount(idx, weights=x * ~g, minlength=C)
    nb = np.bincount(idx, weights=(~g).astype(float), minlength=C)
    est = (x[g].mean() if g.any() else math.nan) - (x[~g].mean() if (~g).any() else math.nan)
    rng = np.random.default_rng(rng)
    draw = rng.integers(0, C, size=(n_boot, C))
    with np.errstate(divide="ignore", invalid="ignore"):
        boot = sa[draw].sum(1) / na[draw].sum(1) - sb[draw].sum(1) / nb[draw].sum(1)
    boot = boot[np.isfinite(boot)]
    a = (1 - conf) / 2
    if boot.size == 0:
        return {"estimate": float(est), "lo": math.nan, "hi": math.nan, "p_value": math.nan}
    p = min(1.0, 2 * min(np.mean(boot <= 0), np.mean(boot >= 0)))
    return {
        "estimate": float(est),
        "lo": float(np.quantile(boot, a)),
        "hi": float(np.quantile(boot, 1 - a)),
        "p_value": float(p),
    }


# --------------------------------------------------------------------------- multiplicity


def holm(pvalues: Sequence[float], alpha: float = 0.05) -> dict[str, list]:
    """Holm step-down; returns adjusted p-values and reject flags in input order."""
    p = np.asarray(pvalues, dtype=float)
    m = p.size
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return {"adjusted": adj.tolist(), "reject": (adj <= alpha).tolist()}


# --------------------------------------------------------------------------- agreement


def cohens_kappa(r1: Sequence[Hashable], r2: Sequence[Hashable], categories=None) -> float:
    if len(r1) != len(r2) or not r1:
        raise ValueError("ratings must be non-empty and equal length")
    cats = list(categories) if categories is not None else sorted(set(r1) | set(r2), key=str)
    ix = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    m = np.zeros((k, k))
    for a, b in zip(r1, r2):
        m[ix[a], ix[b]] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = float(m.sum(1) @ m.sum(0)) / (n * n)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return float((po - pe) / (1 - pe))


# --------------------------------------------------------------------------- non-inferiority


def noninferiority(
    new: Sequence[float],
    ref: Sequence[float],
    clusters: Sequence[Hashable],
    margin: float,
    alpha: float = 0.025,
    n_boot: int = 4000,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, Any]:
    """One-sided non-inferiority of ``new`` vs ``ref`` (higher is better), paired units,
    clustered bootstrap. Non-inferior iff the one-sided (1 - alpha) lower bound of
    mean(new - ref) exceeds -margin. margin > 0, e.g. 0.05 for 5 pp (RQ3 H3b, RQ5)."""
    r = cluster_bootstrap_diff(new, ref, clusters, n_boot=n_boot, conf=1 - 2 * alpha, rng=rng)
    return {
        "estimate": r["estimate"],
        "lower": r["lo"],
        "margin": margin,
        "alpha": alpha,
        "noninferior": bool(r["lo"] > -margin),
    }


# --------------------------------------------------------------------------- power


def _latent_sigma(icc: float) -> float:
    """Logit-scale random-effect SD giving latent-variable ICC (residual var pi^2/3)."""
    if icc <= 0:
        return 0.0
    return math.sqrt(icc / (1 - icc) * math.pi**2 / 3)


_GH_X, _GH_W = np.polynomial.hermite_e.hermegauss(40)
_GH_W = _GH_W / _GH_W.sum()


def _intercept_for_marginal(p: float, sigma: float) -> float:
    """beta such that E[expit(beta + sigma Z)] = p, Z ~ N(0,1)."""
    if sigma == 0:
        return math.log(p / (1 - p))

    def f(b: float) -> float:
        return float(np.sum(_GH_W / (1 + np.exp(-(b + sigma * _GH_X))))) - p

    return float(optimize.brentq(f, -40, 40))


def simulate_power(
    baseline: float,
    effect: float,
    icc: float,
    n_tasks: int,
    n_seeds: int,
    alpha: float = 0.05,
    n_comparisons: int = 1,
    n_sims: int = 2000,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Power for a paired, task-clustered binary outcome (proposal §7.2 power analysis).

    Model: task random intercept u_t ~ N(0, sigma^2) on the logit scale, shared by both
    arms (pairing), sigma from the latent ICC; arm intercepts calibrated so the marginal
    success rates are ``baseline`` and ``baseline + effect``; each (task, seed, arm) trial
    is Bernoulli. Analysis: two-sided one-sample t-test on per-task mean differences
    (the cluster-level analogue of the clustered bootstrap) at alpha / n_comparisons
    (Holm's first, strictest step: conservative). Power counts only rejections in the
    direction of ``effect``."""
    p1 = baseline + effect
    if not (0 < baseline < 1 and 0 < p1 < 1):
        raise ValueError("baseline and baseline+effect must be in (0, 1)")
    if n_tasks < 2:
        raise ValueError("need >= 2 tasks")
    rng = np.random.default_rng(rng)
    sigma = _latent_sigma(icc)
    b0 = _intercept_for_marginal(baseline, sigma)
    b1 = _intercept_for_marginal(p1, sigma)
    u = rng.normal(0.0, sigma, size=(n_sims, n_tasks))
    y0 = rng.binomial(n_seeds, 1 / (1 + np.exp(-(b0 + u))))
    y1 = rng.binomial(n_seeds, 1 / (1 + np.exp(-(b1 + u))))
    d = (y1 - y0) / n_seeds
    mean = d.mean(1)
    sd = d.std(1, ddof=1)
    a = alpha / n_comparisons
    crit = stats.t.ppf(1 - a / 2, n_tasks - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = np.where(sd > 0, mean / (sd / math.sqrt(n_tasks)), np.sign(mean) * np.inf)
    sign = 1.0 if effect >= 0 else -1.0
    reject = (np.abs(tstat) > crit) & (np.sign(tstat) == sign)
    if effect == 0:
        reject = np.abs(tstat) > crit
    power = float(reject.mean())
    return {
        "power": power,
        "mc_se": math.sqrt(power * (1 - power) / n_sims),
        "alpha_per_test": a,
        "sigma_logit": sigma,
        "n_trials_per_arm": n_tasks * n_seeds,
    }


def min_tasks_for_power(
    target: float = 0.8,
    task_grid: Sequence[int] = (10, 20, 30, 40, 60, 80, 100, 120, 160),
    **kw: Any,
) -> dict[str, Any]:
    """Smallest task count in ``task_grid`` reaching ``target`` power (None if none)."""
    curve = {}
    for t in task_grid:
        curve[t] = simulate_power(n_tasks=t, **kw)["power"]
        if curve[t] >= target:
            return {"n_tasks": t, "curve": curve}
    return {"n_tasks": None, "curve": curve}


def percentiles(x: Sequence[float], qs: Sequence[float] = (50, 95, 99)) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {f"p{int(q)}": math.nan for q in qs}
    return {f"p{int(q)}": float(np.percentile(x, q)) for q in qs}


===== FILE: live_agent/eval/tasks.py =====
"""E2 task-suite format (one JSON object per line) and loader/validator.

A task is a scripted user session. Each scripted utterance carries its chain annotation
(``new`` / ``revision`` / ``withdrawal`` / ``none``) and, for ``new`` and ``revision``,
the intent the chain has *after* that utterance; scoring uses the final one.

Task line::

    {"task_id": "E2-A01", "suite": "e2_committed", "kind": "action",
     "persona": "hanfu_scholar_study", "title": "喝茶", "category": "single_action",
     "utterances": [
       {"offset_s": 2.0, "text": "请喝口茶吧。", "annotation": "new", "chain": "c1",
        "barge_in": false,
        "intent": {"kind": "action", "intent": "端起茶杯喝一口茶",
                   "checks": ["人物端起茶杯", "茶杯送到嘴边作饮用动作"]}}],
     "duration_s": 25.0}

Intent fields: ``kind`` (action | content | multistep); content adds ``content_type``
(qa | explain | sing), optional ``prereg_duration_s`` (defaults qa 10 / explain 30 /
sing 30 s) and a ``rubric``; multistep adds ``steps`` = [{"intent", "checks"}, ...].
``offset_s`` is the scripted *start* of the utterance relative to session start.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from live_agent.eval.scoring import CONTENT_DURATION_S

ANNOTATIONS = ("new", "revision", "withdrawal", "none")
TASK_KINDS = ("action", "content", "multistep", "correction")
CATEGORIES = (
    "single_action",
    "content_qa",
    "content_explain",
    "content_sing",
    "multistep",
    "mid_correction",
    "goal_change",
    "barge_in",
    "deictic_correction",
)

# Composition of the full E2 suite (80 tasks x 5 seeds). *Proposed target*; the committed
# 30-task file is the first tranche.
SUITE_TARGETS: dict[str, int] = {
    "single_action": 24,
    "content_qa": 8,
    "content_explain": 6,
    "content_sing": 6,
    "multistep": 16,
    "mid_correction": 5,
    "goal_change": 5,
    "barge_in": 5,
    "deictic_correction": 5,
}


@dataclass
class ScriptedUtterance:
    offset_s: float
    text: str
    annotation: str = "new"
    chain: str | None = None
    intent: dict[str, Any] | None = None
    barge_in: bool = False


@dataclass
class Task:
    task_id: str
    kind: str
    title: str
    category: str
    utterances: list[ScriptedUtterance]
    persona: str = "hanfu_scholar_study"
    suite: str = ""
    duration_s: float | None = None
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def final_intents(self) -> dict[str, dict[str, Any] | None]:
        """chain label -> final intent (None if the chain ends withdrawn)."""
        out: dict[str, dict[str, Any] | None] = {}
        for u in self.utterances:
            if u.annotation in ("new", "revision"):
                out[u.chain] = u.intent
            elif u.annotation == "withdrawal":
                out[u.chain] = None
        return out


class TaskError(ValueError):
    pass


def _check_intent(tid: str, it: dict[str, Any] | None) -> None:
    if not it or it.get("kind") not in ("action", "content", "multistep"):
        raise TaskError(f"{tid}: intent needs kind action|content|multistep: {it}")
    if it["kind"] == "content":
        if it.get("content_type") not in CONTENT_DURATION_S:
            raise TaskError(f"{tid}: content intent needs content_type qa|explain|sing")
        if not it.get("rubric"):
            raise TaskError(f"{tid}: content intent needs a preregistered rubric")
    elif it["kind"] == "multistep":
        steps = it.get("steps") or []
        if len(steps) < 2 or not all(s.get("checks") for s in steps):
            raise TaskError(f"{tid}: multistep needs >= 2 steps, each with checks")
    elif not it.get("checks"):
        raise TaskError(f"{tid}: action intent needs checks")


def validate_task(t: Task) -> None:
    if t.kind not in TASK_KINDS:
        raise TaskError(f"{t.task_id}: bad kind {t.kind}")
    if t.category not in CATEGORIES:
        raise TaskError(f"{t.task_id}: bad category {t.category}")
    if not t.utterances:
        raise TaskError(f"{t.task_id}: no utterances")
    open_: set[str] = set()
    last = -1.0
    for u in t.utterances:
        if u.offset_s < last:
            raise TaskError(f"{t.task_id}: utterance offsets must be non-decreasing")
        last = u.offset_s
        if u.annotation not in ANNOTATIONS:
            raise TaskError(f"{t.task_id}: bad annotation {u.annotation}")
        if u.annotation == "none":
            continue
        if not u.chain:
            raise TaskError(f"{t.task_id}: annotated utterance needs a chain label")
        if u.annotation == "new":
            if u.chain in open_:
                raise TaskError(f"{t.task_id}: chain {u.chain} opened twice")
            open_.add(u.chain)
            _check_intent(t.task_id, u.intent)
        else:
            if u.chain not in open_:
                raise TaskError(f"{t.task_id}: {u.annotation} of unopened chain {u.chain}")
            if u.annotation == "revision":
                _check_intent(t.task_id, u.intent)


def task_from_dict(d: dict[str, Any]) -> Task:
    known = {"task_id", "kind", "title", "category", "utterances", "persona", "suite",
             "duration_s", "notes"}
    t = Task(
        task_id=d["task_id"],
        kind=d["kind"],
        title=d.get("title", ""),
        category=d["category"],
        utterances=[ScriptedUtterance(**u) for u in d["utterances"]],
        persona=d.get("persona", "hanfu_scholar_study"),
        suite=d.get("suite", ""),
        duration_s=d.get("duration_s"),
        notes=d.get("notes", ""),
        extra={k: v for k, v in d.items() if k not in known},
    )
    validate_task(t)
    return t


def load_suite(path: str | Path) -> list[Task]:
    tasks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(task_from_dict(json.loads(line)))
    ids = [t.task_id for t in tasks]
    dup = [i for i, c in Counter(ids).items() if c > 1]
    if dup:
        raise TaskError(f"duplicate task ids: {dup}")
    return tasks


def suite_counts(tasks: list[Task]) -> dict[str, dict[str, int]]:
    """Current vs target count per category (targets are *proposed targets*)."""
    c = Counter(t.category for t in tasks)
    return {k: {"current": c.get(k, 0), "target": v} for k, v in SUITE_TARGETS.items()}

===== FILE: live_agent/eval/sim_user.py =====
"""Simulated user: replays a task's scripted utterances against any agent transport and
emits ``utterance`` + ``chain_annotation`` events in the SCHEMA.md format.

Transport-agnostic: the caller supplies

* ``send_utterance(text, meta) -> Awaitable[dict | None]`` - deliver the utterance (TTS into
  the live session, a websocket message, a direct call...). It may return
  ``{"t_start": ..., "t_end": ...}`` measured on the shared timeline (e.g. from VAD);
  otherwise the clock before/after the await is used.
* ``clock() -> float`` - the shared presentation-timeline clock.
* ``sleep(seconds) -> Awaitable`` - defaults to ``asyncio.sleep``; tests use VirtualClock.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from live_agent.eval.tasks import Task

SendFn = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any] | None]]


class VirtualClock:
    """Deterministic clock for tests and offline replay."""

    def __init__(self, t0: float = 0.0):
        self.t = t0

    def now(self) -> float:
        return self.t

    async def sleep(self, dt: float) -> None:
        self.t += max(0.0, dt)
        await asyncio.sleep(0)

    def advance(self, dt: float) -> None:
        self.t += dt


class SimulatedUser:
    def __init__(
        self,
        task: Task,
        send_utterance: SendFn,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        session_id: str = "",
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.task = task
        self.send = send_utterance
        self.clock = clock
        self.sleep = sleep
        self.session_id = session_id or task.task_id
        self.on_event = on_event
        self.events: list[dict[str, Any]] = []

    def chain_id(self, label: str) -> str:
        return f"{self.session_id}:{label}"

    def _emit(self, ev: dict[str, Any]) -> None:
        self.events.append(ev)
        if self.on_event is not None:
            self.on_event(ev)

    async def run(self) -> list[dict[str, Any]]:
        t0 = self.clock()
        for i, u in enumerate(self.task.utterances):
            wait = t0 + u.offset_s - self.clock()
            if wait > 0:
                await self.sleep(wait)
            uid = f"{self.session_id}:u{i}"
            meta = {"uid": uid, "barge_in": u.barge_in, "task_id": self.task.task_id}
            t_start = self.clock()
            r = await self.send(u.text, meta) or {}
            t_end = float(r.get("t_end", self.clock()))
            t_start = float(r.get("t_start", t_start))
            self._emit(
                {
                    "type": "utterance",
                    "uid": uid,
                    "speaker": "user",
                    "text": u.text,
                    "t_start": t_start,
                    "t_end": t_end,
                    "barge_in": u.barge_in,
                }
            )
            if u.annotation == "none":
                continue
            ann: dict[str, Any] = {
                "type": "chain_annotation",
                "uid": uid,
                "action": u.annotation,
                "chain_id": self.chain_id(u.chain),
                "label": u.chain,
            }
            if u.intent:
                it = u.intent
                ann["kind"] = it["kind"]
                ann["intent"] = it.get("intent", "")
                for k in ("content_type", "prereg_duration_s"):
                    if k in it:
                        ann[k] = it[k]
                if "steps" in it:
                    ann["steps"] = [s.get("intent", "") for s in it["steps"]]
            self._emit(ann)
        if self.task.duration_s is not None:
            rest = t0 + self.task.duration_s - self.clock()
            if rest > 0:
                await self.sleep(rest)
        return self.events

===== FILE: live_agent/eval/runner.py =====
"""E2 runner: execute scripted tasks against the live-agent stack and write SCHEMA.md logs.

Conditions (proposal §7.2): A1 open loop; A2 full; A2-noqc (no online checks);
A2-repeat (RQ2 contrast: repeat instead of forward correction); B0 (scripted, no input).

Time: all orchestrator times are monotonic seconds; with a sped-up mock stack they are
rescaled by ``speed`` so that deadlines (15 s ...) apply in *simulated* seconds.
Chains: the director's chains are mapped to the task's ground-truth chains through the
utterance uid that opened / revised them.

Usage:
    python -m live_agent.eval.runner --suite eval/tasks/e2_committed.jsonl \
        --conditions A1 A2 --seeds 0 1 --out .cache/e2 [--mock --speed 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import zlib
from pathlib import Path
from typing import Any

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.eval.schema import SessionLogWriter
from live_agent.eval.sim_user import SimulatedUser
from live_agent.eval.tasks import Task, load_suite
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.sim import SimClient
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import EventType, Utterance, now

CONDITIONS = {
    "A1": dict(mode=DirectorMode.OPEN_LOOP, qc=False, correction=CorrectionMode.NONE),
    "A2": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.GRADIENT),
    "A2-noqc": dict(mode=DirectorMode.CLOSED_LOOP, qc=False, correction=CorrectionMode.NONE),
    "A2-repeat": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.REPEAT),
}


def convert(orch: Orchestrator, user_events: list[dict], *, t0: float, speed: float) -> list[dict]:
    """Map orchestrator TimelineEvents + sim-user events into SCHEMA.md events."""
    ts = lambda t: (t - t0) * speed  # noqa: E731
    uid_to_chain = {e["uid"]: e["chain_id"] for e in user_events if e["type"] == "chain_annotation"}
    dchain_to_gt: dict[str, str] = {}
    for c in orch.director.chains.values():
        for uid in [c.opened_by, *c.revisions]:
            if uid in uid_to_chain:
                dchain_to_gt[c.chain_id] = uid_to_chain[uid]
    out: list[dict[str, Any]] = []
    for e in user_events:  # already on the shared clock (monotonic) -> rescale
        e = dict(e)
        for k in ("t_start", "t_end", "t"):
            if k in e:
                e[k] = ts(e[k])
        out.append(e)
    script_chains = {k: [dchain_to_gt.get(c) for c in s.chain_ids if dchain_to_gt.get(c)]
                     for k, s in orch.scripts.items()}
    presented_start: dict[int, float] = {}
    for ev in orch.log.events:
        d, k = ev.data, ev.request_index
        if ev.type == EventType.LOCK and k is not None:
            out.append({"type": "lock", "t": ts(ev.t), "request": k, "chain_ids": script_chains.get(k, []),
                        "plan_version": d.get("plan_version")})
        elif ev.type == EventType.CHUNK_PRESENTED:
            out.append({"type": "chunk_presented", "request": k, "chunk": ev.chunk_index,
                        "t_start": ts(ev.t), "t_end": ts(d["t_end"])})
            if ev.chunk_index == 0:
                presented_start[k] = ts(ev.t)
        elif ev.type == EventType.VERDICT and d.get("kind") == "action":
            step = orch.scripts[k].provenance.get("step") if k in orch.scripts else None
            for cid in script_chains.get(k, []):
                v = {"type": "verdict", "source": "judge", "label": d["label"], "chain_id": cid,
                     "request": k, "chunk": 0, "t_evidence": ts(d["t_evidence"]), "qid": d.get("qid")}
                if step is not None:  # multistep: the director's step index (action steps only)
                    v["step"] = step
                out.append(v)
        elif ev.type == EventType.COMPLETION_CLAIM:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "completion_claim", "chain_id": gt, "t": presented_start.get(k, ts(ev.t)),
                            "request": k})
        elif ev.type == EventType.REFUSAL:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "refusal", "chain_id": gt, "t": ts(ev.t),
                            "kind": "degraded" if d.get("degraded") else "refused", "reason": d.get("reason", "")})
        elif ev.type == EventType.PLAYBACK_STOP:
            out.append({"type": "playback_stop", "t": ts(ev.t), "reason": "erasure" if d.get("erasure") else "barge_in"})
        elif ev.type == EventType.REPAIR:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "repair_assignment", "chain_id": gt,
                            "arm": "forward_correction" if d.get("mode") == "gradient" else "repeat",
                            "failure_request": k, "target_request": d.get("earliest_correctable"),
                            "C": d.get("chain_cost_s")})
    # Speech onset: the first presented request carrying a line for a chain.
    for k, s in sorted(orch.scripts.items()):
        if s.transcript and k in presented_start:
            for cid in script_chains.get(k, []):
                out.append({"type": "speech_onset", "t": presented_start[k], "on_topic": True,
                            "chain_id": cid, "request": k})
    return out


async def run_task(task: Task, condition: str, seed: int, *, factory, speed: float, out_dir: Path) -> Path:
    cfg = CONDITIONS[condition]
    # Per-(task, seed) RNG stream, identical across conditions (paired design), different across tasks.
    orch, client = factory(cfg, zlib.crc32(f"{task.task_id}/{seed}".encode()))
    client.orchestrator = orch
    t0 = now()
    user_events: list[dict] = []

    async def send(text: str, meta: dict) -> dict:
        t_start = now()
        if meta.get("barge_in"):
            await orch.on_speech_start(t_start)
        await orch.on_user_utterance(Utterance(meta["uid"], "user", text, now()))
        return {"t_start": t_start, "t_end": now()}

    user = SimulatedUser(task, send, clock=now, sleep=lambda dt: asyncio.sleep(dt / speed),
                         session_id=f"{condition}-{task.task_id}-s{seed}", on_event=user_events.append)
    path = out_dir / f"{condition}-{task.task_id}-s{seed}.jsonl"
    if getattr(client, "recorder", None) is not None:
        client.recorder.path = path.with_suffix(".mp4")  # adjudication looks for <log>.mp4
    client.start()
    await orch.start()
    try:
        await user.run()
        # let the last requests present and be checked
        await asyncio.sleep(15.0 / speed)
    finally:
        await orch.stop()
        client.close()
    with SessionLogWriter(path, session_id=f"{condition}-{task.task_id}-s{seed}", condition=condition,
                          task_id=task.task_id, seed=seed, mode="simulation",
                          backbone=orch.gen.info.name) as w:
        for ev in convert(orch, user_events, t0=t0, speed=speed):
            w.write(ev)
    return path


def mock_factory(config_dir: Path, *, speed: float, llm, p_default: float = 0.7):
    from live_agent.generator.mock import MockGenerator
    from live_agent.qc.judge import ForwardCorrector, MockJudge

    canon = json.loads((config_dir / "canon.json").read_text(encoding="utf-8"))

    def factory(cfg: dict, seed: int):
        manifest = CapabilityManifest.load(config_dir / "capabilities.json")
        manifest.min_status = Status.DOCUMENTED  # simulation: capabilities are not yet executed
        ledger = StateLedger.from_config(config_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"], mode=cfg["mode"])
        gen = MockGenerator(teacher_s=1.0, chunk_s=0.5, speed=speed, seed=seed)
        sched = LockScheduler(SchedulerConfig(request_s=5.0 / speed, sigma_s=0.5 / speed, delta_s=0.01,
                                              lambda_prior_s=3.0 / speed, time_scale=1.0 / speed))
        client = SimClient(speed=speed)
        orch = Orchestrator(gen, director, sched, client, judge=MockJudge(p_default=p_default, seed=seed),
                            corrector=ForwardCorrector(None), log=EventLog(),
                            cfg=OrchestratorConfig(correction_mode=cfg["correction"], qc_enabled=cfg["qc"],
                                                   seed=seed))
        return orch, client

    return factory


def live_factory(config_dir: Path, *, backend, llm, vlm, record_dir: Path | None = None,
                 allow_uncalibrated: bool = False):
    """Real stack: shared generator backend (e.g. TaoMate-H3; one session at a time through
    SessionView), LLM responder, VLM judge, LLM forward corrector. Real time (speed 1)."""
    from live_agent.generator.base import SessionView
    from live_agent.qc.judge import ForwardCorrector, VLMJudge
    from live_agent.sim import Recorder

    canon = json.loads((config_dir / "canon.json").read_text(encoding="utf-8"))
    counter = iter(range(10**9))

    def factory(cfg: dict, seed: int):
        manifest = CapabilityManifest.load(config_dir / "capabilities.json")
        if allow_uncalibrated:
            manifest.min_status = Status.DOCUMENTED  # pre-E1 qualification runs only; never for E2 results
        ledger = StateLedger.from_config(config_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"], mode=cfg["mode"])
        gen = SessionView(backend)
        sched = LockScheduler(SchedulerConfig(request_s=backend.info.request_seconds))
        rec = Recorder(record_dir / f"session-{next(counter):03d}.mp4") if record_dir else None
        client = SimClient(speed=1.0, recorder=rec)
        orch = Orchestrator(gen, director, sched, client, judge=VLMJudge(vlm), corrector=ForwardCorrector(llm),
                            log=EventLog(), cfg=OrchestratorConfig(correction_mode=cfg["correction"],
                                                                   qc_enabled=cfg["qc"], seed=seed))
        return orch, client

    return factory


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", default="eval/tasks/e2_committed.jsonl")
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--conditions", nargs="+", default=["A1", "A2"])
    p.add_argument("--seeds", nargs="+", type=int, default=[0])
    p.add_argument("--tasks", nargs="*", default=None)
    p.add_argument("--out", default=".cache/e2")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--p-default", type=float, default=0.7, help="mock judge success probability")
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3"])
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--allow-uncalibrated", action="store_true",
                   help="live stack: accept 'documented' capabilities (M1 qualification before E1)")
    p.add_argument("--record", action="store_true", help="save the presented stream as MP4 (live stack)")
    args, rest = p.parse_known_args()
    args.extra = rest
    asyncio.run(_main(args))


async def _main(args) -> None:
    from live_agent.llm import OpenAICompatLLM

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in load_suite(args.suite) if not args.tasks or t.task_id in args.tasks]
    llm = OpenAICompatLLM(args.llm_url, args.llm_model)
    backend = None
    if args.generator == "mock":
        speed = args.speed
        factory = mock_factory(Path(args.config), speed=speed, llm=llm, p_default=args.p_default)
    else:
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        speed = 1.0
        backend = TaoMateH3Generator.from_args(args)
        await backend.start()
        factory = live_factory(Path(args.config), backend=backend, llm=llm,
                               vlm=OpenAICompatLLM(args.vlm_url, args.vlm_model),
                               record_dir=out if args.record else None,
                               allow_uncalibrated=args.allow_uncalibrated)
    try:
        for cond in args.conditions:
            for seed in args.seeds:
                for t in tasks:
                    path = await run_task(t, cond, seed, factory=factory, speed=speed, out_dir=out)
                    print(path, flush=True)
    finally:
        if backend is not None:
            await backend.close()


if __name__ == "__main__":
    main()

===== FILE: live_agent/eval/adjudicate.py =====
"""Blinded human adjudication of the primary outcome (proposal §14; SCHEMA.md `verdict`, source
`adjudicated`).

    # 1. build a blinded labelling page from session logs + recorded MP4s (runner --record)
    python -m live_agent.eval.adjudicate prepare .cache/m1/*.jsonl -o .cache/adj/batch1 [--seed 0]
    # 2. open .cache/adj/batch1/index.html in a browser, label, press "Download labels"
    # 3. merge the labels back into the logs as adjudicated verdicts
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labels.json --annotator A1

Blinding: items are shuffled across sessions and conditions, carry random ids, and show only the
user's instruction(s) and the video; the item -> session key stays in ``key.json``.

Time mapping: the recording holds the presented chunks back to back (stalls are not recorded), so
video time v maps to session time through the cumulative chunk durations of the session's
``chunk_presented`` events (``video_to_session``).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import secrets
import shutil
from pathlib import Path
from typing import Any

from live_agent.eval.schema import load_session


def presented_segments(events: list[dict]) -> list[tuple[float, float, float]]:
    """[(video_start, session_start, duration)] for presented chunks in presentation order."""
    chunks = sorted((e for e in events if e["type"] == "chunk_presented"), key=lambda e: e["t_start"])
    out, v = [], 0.0
    for e in chunks:
        d = e["t_end"] - e["t_start"]
        out.append((v, e["t_start"], d))
        v += d
    return out


def video_to_session(segments: list[tuple[float, float, float]], v: float) -> float:
    for v0, s0, d in segments:
        if v < v0 + d:
            return s0 + max(0.0, v - v0)
    if not segments:
        return v
    v0, s0, d = segments[-1]
    return s0 + (v - v0)


def session_to_video(segments: list[tuple[float, float, float]], t: float) -> float:
    for v0, s0, d in segments:
        if t < s0 + d:
            return v0 + max(0.0, t - s0)
    if not segments:
        return t
    v0, s0, d = segments[-1]
    return v0 + d


def chains_for_adjudication(events: list[dict]) -> list[dict[str, Any]]:
    """Final intent of every effective (not finally withdrawn) chain, with its clock origin."""
    utt = {e["uid"]: e for e in events if e["type"] == "utterance"}
    chains: dict[str, dict[str, Any]] = {}
    for e in events:
        if e["type"] != "chain_annotation":
            continue
        c = chains.setdefault(e["chain_id"], {"chain_id": e["chain_id"], "texts": [], "withdrawn": False})
        u = utt.get(e["uid"], {})
        c["texts"].append(u.get("text", ""))
        if e["action"] == "withdrawal":
            c["withdrawn"] = True
            continue
        c["withdrawn"] = False
        c["origin"] = u.get("t_end", 0.0)
        for k in ("kind", "intent", "content_type", "steps", "label"):
            if k in e:
                c[k] = e[k]
    out = []
    for c in chains.values():
        if c["withdrawn"] or "origin" not in c:
            continue
        steps = c.get("steps")
        c["n_steps"] = (len(steps) if isinstance(steps, list) else int(steps)) if c.get("kind") == "multistep" and steps else 1
        c["kind"] = "action" if c.get("kind") == "correction" else c.get("kind", "action")
        out.append(c)
    return out


PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>Adjudication</title>
<style>
:root{{--bg:#fff;--fg:#111;--mut:#666;--line:#ddd;--acc:#1f6feb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--line:#333;--acc:#58a6ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}}
.item{{border:1px solid var(--line);border-radius:8px;padding:12px;margin:16px 0;display:flex;gap:16px;flex-wrap:wrap}}
video{{width:300px;max-width:100%;background:#000}} .meta{{flex:1;min-width:260px}}
.mut{{color:var(--mut);font-size:13px}} button{{margin:2px}} .step{{margin:8px 0;padding:6px;border-top:1px dashed var(--line)}}
.sel{{outline:2px solid var(--acc)}}
</style>
<h1>Blinded adjudication · {n} items</h1>
<p class="mut">For each item: the user's request(s) are shown; the video starts at the request. Decide whether the
persona <b>visibly</b> did the <b>final</b> requested thing. When it did, pause at the <b>first frame that clearly
shows it</b> and press "first compliant = now". For content items, mark the time the answer ends. "Cannot tell" is
allowed. Do not guess the condition.</p>
<div id="items"></div>
<p><button onclick="dl()">Download labels</button> <span class="mut" id="cnt"></span></p>
<script>
const ITEMS = {items};
const L = {{}};
try {{ Object.assign(L, JSON.parse(localStorage.getItem("adj-{batch}") || "{{}}")); }} catch (e) {{}}
function save(){{ try {{ localStorage.setItem("adj-{batch}", JSON.stringify(L)); }} catch (e) {{}}
  document.getElementById("cnt").textContent = Object.keys(L).length + " step labels"; }}
function set(id, step, key, val){{ const k = id + "/" + step; L[k] = Object.assign(L[k] || {{}}, {{[key]: val}}); save(); render(); }}
function now(id, step, key){{ set(id, step, key, +document.getElementById("v-" + id).currentTime.toFixed(2)); }}
function render(){{
  const root = document.getElementById("items"); const keep = {{}};
  document.querySelectorAll("video").forEach(v => keep[v.id] = v);
  root.innerHTML = "";
  ITEMS.forEach(it => {{
    const d = document.createElement("div"); d.className = "item";
    const v = keep["v-" + it.id] || Object.assign(document.createElement("video"),
      {{id: "v-" + it.id, src: it.video + "#t=" + it.v_origin, controls: true, preload: "metadata"}});
    d.appendChild(v);
    const m = document.createElement("div"); m.className = "meta";
    m.innerHTML = "<div class=mut>" + it.id + " · " + it.kind + (it.content_type ? " / " + it.content_type : "") +
      " · request at video " + it.v_origin.toFixed(1) + " s</div>" +
      it.texts.map((t, i) => "<div>" + (i ? "then: " : "user: ") + t + "</div>").join("");
    for (let s = 0; s < it.n_steps; s++) {{
      const k = it.id + "/" + s, cur = L[k] || {{}};
      const st = document.createElement("div"); st.className = "step";
      const lab = it.n_steps > 1 ? "step " + (s + 1) + ": " : "";
      st.innerHTML = lab + ["complied", "not_complied", "unknown"].map(x =>
        `<button class="${{cur.label === x ? "sel" : ""}}" onclick="set('${{it.id}}',${{s}},'label','${{x}}')">${{
          {{complied: "done", not_complied: "not done", unknown: "cannot tell"}}[x]}}</button>`).join("") +
        ` <button onclick="now('${{it.id}}',${{s}},'v_first')">first compliant = now</button>` +
        (it.kind === "content" ? ` <button onclick="now('${{it.id}}',${{s}},'v_end')">answer ends = now</button>` : "") +
        ` <span class=mut>${{cur.v_first != null ? "first " + cur.v_first + " s " : ""}}${{cur.v_end != null ? "end " + cur.v_end + " s" : ""}}</span>`;
      m.appendChild(st);
    }}
    d.appendChild(m); root.appendChild(d);
  }});
}}
function dl(){{ const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(L, null, 1)], {{type: "application/json"}}));
  a.download = "labels-{batch}.json"; a.click(); }}
render(); save();
</script></html>
"""


def prepare(logs: list[Path], out: Path, seed: int = 0) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    items, key = [], {}
    for log in logs:
        s = load_session(log)
        video = log.with_suffix(".mp4")
        if not video.exists():
            print(f"skip {log.name}: no recording {video.name}")
            continue
        segs = presented_segments(s.events)
        media = out / "media" / f"{secrets.token_hex(4)}.mp4"  # random name: the file name would unblind
        media.parent.mkdir(exist_ok=True)
        try:
            media.symlink_to(video.resolve())
        except OSError:
            shutil.copyfile(video, media)
        for c in chains_for_adjudication(s.events):
            iid = secrets.token_hex(3)
            items.append({"id": iid, "video": os.path.relpath(media, out), "kind": c["kind"],
                          "content_type": c.get("content_type"), "texts": [html.escape(t) for t in c["texts"]],
                          "n_steps": c["n_steps"], "v_origin": round(session_to_video(segs, c["origin"]), 2)})
            key[iid] = {"log": str(log.resolve()), "chain_id": c["chain_id"], "segments": segs, "kind": c["kind"]}
    random.Random(seed).shuffle(items)
    batch = out.name
    (out / "index.html").write_text(PAGE.format(n=len(items), items=json.dumps(items, ensure_ascii=False),
                                                batch=batch), encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    return out / "index.html"


def merge(batch_dir: Path, labels_path: Path, annotator: str) -> dict[str, int]:
    key = json.loads((batch_dir / "key.json").read_text(encoding="utf-8"))
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    per_log: dict[str, list[dict]] = {}
    for k, lab in labels.items():
        iid, step = k.split("/")
        if iid not in key or "label" not in lab:
            continue
        info = key[iid]
        segs = [tuple(x) for x in info["segments"]]
        ev: dict[str, Any] = {"type": "verdict", "source": "adjudicated", "label": lab["label"],
                              "chain_id": info["chain_id"], "annotator": annotator}
        if int(step) or info["kind"] == "multistep":
            ev["step"] = int(step)
        if lab.get("v_first") is not None:
            ev["t_first_compliant"] = video_to_session(segs, float(lab["v_first"]))
        if lab.get("v_end") is not None:
            ev["t_evidence"] = video_to_session(segs, float(lab["v_end"]))
        elif "t_first_compliant" in ev:
            ev["t_evidence"] = ev["t_first_compliant"]
        per_log.setdefault(info["log"], []).append(ev)
    counts = {}
    for log, evs in per_log.items():
        with open(log, "a", encoding="utf-8") as f:
            for ev in evs:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        counts[Path(log).name] = len(evs)
    return counts


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("logs", nargs="+", type=Path)
    a.add_argument("-o", "--out", type=Path, required=True)
    a.add_argument("--seed", type=int, default=0)
    b = sub.add_parser("merge")
    b.add_argument("batch_dir", type=Path)
    b.add_argument("labels", type=Path)
    b.add_argument("--annotator", required=True)
    args = p.parse_args()
    if args.cmd == "prepare":
        print(prepare(args.logs, args.out, args.seed))
    else:
        print(merge(args.batch_dir, args.labels, args.annotator))


if __name__ == "__main__":
    main()

===== FILE: live_agent/eval/report.py =====
"""Markdown report from scored E2 sessions, per condition, with CIs (proposal v2.11 §7.7).

Usage::

    python -m live_agent.eval.report logs/*.jsonl --compare A2:A1 --compare A2-QC:A2 -o report.md

Every number in the output is *measured locally* from the given logs; thresholds quoted
from §8 are *proposed targets*.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence

from live_agent.eval import stats
from live_agent.eval.schema import load_session
from live_agent.eval.scoring import (
    ChainOutcome,
    ScoringConfig,
    SessionScore,
    score_session,
    summarize,
)


def _f(x: float | None, pct: bool = False, nd: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.{nd + 1}f}"


def _ci(lo: float, hi: float, pct: bool = True) -> str:
    return f"[{_f(lo, pct)}, {_f(hi, pct)}]"


def _key(c: ChainOutcome) -> tuple[str, int, str]:
    return (c.task_id, c.seed, c.label)


def _rate_line(name: str, k: int, n: int, clusters: Sequence[str] | None = None,
               values: Sequence[float] | None = None, n_boot: int = 4000) -> str:
    if n == 0:
        return f"| {name} | 0/0 | n/a | n/a | n/a |"
    w = stats.wilson(k, n)
    boot = "n/a"
    if clusters is not None and values is not None and len(set(clusters)) > 1:
        b = stats.cluster_bootstrap_mean(values, clusters, n_boot=n_boot)
        boot = _ci(b["lo"], b["hi"])
    return f"| {name} | {k}/{n} | {_f(k / n, True)} | {_ci(*w)} | {boot} |"


def condition_section(cond: str, sessions: list[SessionScore], n_boot: int = 4000) -> list[str]:
    chains = [c for s in sessions for c in s.chains]
    eff = [c for c in chains if c.effective]
    sm = summarize(chains)
    cl = [c.task_id for c in eff]
    L = [f"## Condition `{cond}`", ""]
    L.append(
        f"Sessions: {len(sessions)}; tasks: {len({s.task_id for s in sessions})}; "
        f"effective chains: {sm['n_effective']}; withdrawn chains (excluded): {sm['n_withdrawn']}."
    )
    L += ["", "| Metric | k/n | Estimate | Wilson 95% CI | Task-clustered bootstrap 95% CI |",
          "|---|---|---|---|---|"]
    L.append(_rate_line("Instruction-level success (primary)", sm["n_success"], sm["n_effective"],
                        cl, [float(c.success) for c in eff], n_boot))
    unk = [c for c in eff if c.outcome.value != "unknown"]
    L.append(_rate_line("Success, excluding 'cannot tell' (sensitivity)",
                        sum(c.success for c in unk), len(unk),
                        [c.task_id for c in unk], [float(c.success) for c in unk], n_boot))
    L.append(_rate_line("Capacity-skip rate", sm["n_capacity_skipped"], sm["n_effective"],
                        cl, [float(c.outcome.value == "capacity_skipped") for c in eff], n_boot))
    L.append(_rate_line("Refusal / degradation rate", sm["n_refused_degraded"], sm["n_effective"],
                        cl, [float(c.outcome.value in ("refused", "degraded")) for c in eff], n_boot))
    served = [c for c in eff if c.served]
    L.append(_rate_line("Conditional success (served chains)", sum(c.success for c in served),
                        len(served), [c.task_id for c in served],
                        [float(c.success) for c in served], n_boot))
    content = [c for c in eff if c.kind == "content"]
    L.append(_rate_line("Content onset <= 15 s (reported separately)",
                        sum(bool(c.onset_ok) for c in content), len(content)))
    L.append(_rate_line("FCR (contradicted / completion claims)", sm["n_false_claims"], sm["n_claims"]))
    L.append(_rate_line("Claim coverage (chains with >= 1 claim)",
                        sum(c.n_claims > 0 for c in eff), len(eff)))
    for arm, r in sm["repair"].items():
        L.append(_rate_line(f"Repair rate, arm `{arm}` (RQ2)", r["k"], r["n"]))

    # by kind
    L += ["", "**Success by chain kind**", "", "| Kind | k/n | Estimate | Wilson 95% CI |", "|---|---|---|---|"]
    by_kind: dict[str, list[ChainOutcome]] = defaultdict(list)
    for c in eff:
        by_kind[c.kind].append(c)
    for k, cs in sorted(by_kind.items()):
        kk, nn = sum(c.success for c in cs), len(cs)
        L.append(f"| {k} | {kk}/{nn} | {_f(kk / nn, True)} | {_ci(*stats.wilson(kk, nn))} |")
    L += ["", "Outcome counts: " + ", ".join(f"{k}={v}" for k, v in sm["outcomes"].items() if v)]

    # repair offsets
    for arm, r in sm["repair"].items():
        L.append(f"Repair `{arm}`: earliest eligible request offset j-k = {r['offsets']}")

    # time-to-event
    L += ["", "**Time to event (Kaplan-Meier, right-censored at D)**", "",
          "| Measure | n | events | deadline success | KM median (s) | RMST to horizon (s) |",
          "|---|---|---|---|---|---|"]
    act = [c for c in eff if c.tvc is not None]
    if act:
        km = stats.kaplan_meier([c.tvc for c in act], [c.tvc_event for c in act])
        H = max(c.deadline_s for c in act)
        med = km.median
        L.append(f"| TVC (action chains) | {len(act)} | {sum(c.tvc_event for c in act)} | "
                 f"{_f(sum(c.tvc_event for c in act) / len(act), True)} | "
                 f"{_f(med) if med is not None else f'> {H:g}'} | {_f(km.rmst(H))} (H={H:g}) |")
    tf = [c for c in eff if c.tfmr is not None]
    if tf:
        km = stats.kaplan_meier([c.tfmr for c in tf], [c.tfmr_event for c in tf])
        H = max(c.tfmr for c in tf)
        med = km.median
        L.append(f"| TFMR (on-topic speech onset) | {len(tf)} | {sum(c.tfmr_event for c in tf)} | "
                 f"{_f(sum(c.tfmr_event for c in tf) / len(tf), True)} | "
                 f"{_f(med) if med is not None else f'> {H:g}'} | {_f(km.rmst(H))} (H={H:g}) |")

    # latencies
    va = [x for s in sessions for x in s.visual_ack_s]
    bi = [x for s in sessions for x in s.barge_in_stop_s]
    miss = sum(s.barge_ins_without_stop for s in sessions)
    L += ["", "**Latency (s; p50 / p95 / p99)**", "", "| Measure | n | p50 | p95 | p99 |", "|---|---|---|---|---|"]
    for name, xs in (("Visual acknowledgement", va), ("Barge-in playback stop (client)", bi)):
        p = stats.percentiles(xs)
        L.append(f"| {name} | {len(xs)} | {_f(p['p50'], nd=2)} | {_f(p['p95'], nd=2)} | {_f(p['p99'], nd=2)} |")
    if miss:
        L.append(f"\nBarge-ins with no playback stop: {miss}.")
    if len(sessions) and min(len(xs) for xs in (va, bi)) < 3:
        L.append("\nFewer than 3 latency repetitions in at least one row: treat percentiles as indicative.")
    return L + [""]


def compare(
    by_cond: dict[str, list[SessionScore]],
    pairs: Iterable[tuple[str, str]],
    n_boot: int = 4000,
    alpha: float = 0.05,
) -> list[str]:
    rows = []
    for a, b in pairs:
        if a not in by_cond or b not in by_cond:
            rows.append((a, b, None))
            continue
        ca = {_key(c): c for s in by_cond[a] for c in s.chains if c.effective}
        cb = {_key(c): c for s in by_cond[b] for c in s.chains if c.effective}
        keys = sorted(set(ca) & set(cb))
        if not keys:
            rows.append((a, b, None))
            continue
        r = stats.cluster_bootstrap_diff(
            [float(ca[k].success) for k in keys],
            [float(cb[k].success) for k in keys],
            [k[0] for k in keys],
            n_boot=n_boot,
        )
        r["n"] = len(keys)
        r["unpaired"] = len(set(ca) ^ set(cb))
        rows.append((a, b, r))
    valid = [r for _, _, r in rows if r is not None]
    adj = stats.holm([r["p_value"] for r in valid], alpha)["adjusted"] if valid else []
    L = ["## Paired comparisons (instruction-level success; cluster = task)", "",
         "| Comparison | paired chains | difference | 95% CI | bootstrap p | Holm-adjusted p |",
         "|---|---|---|---|---|---|"]
    i = 0
    for a, b, r in rows:
        if r is None:
            L.append(f"| {a} - {b} | 0 | n/a | n/a | n/a | n/a |")
            continue
        L.append(f"| {a} - {b} | {r['n']} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} | "
                 f"{r['p_value']:.4f} | {adj[i]:.4f} |")
        i += 1
    unp = [f"{a}-{b}: {r['unpaired']}" for a, b, r in rows if r and r["unpaired"]]
    if unp:
        L.append("\nChains present in only one condition (dropped from pairing): " + "; ".join(unp))
    L.append("\nH1a target (*proposed target*, §8): A2 - A1 >= +10 pp with the paired CI excluding 0.")
    return L + [""]


def repair_comparison(by_cond: dict[str, list[SessionScore]], n_boot: int = 4000) -> list[str]:
    L = []
    for cond, ss in by_cond.items():
        rep = [c for s in ss for c in s.chains if c.effective and c.repair_arm is not None]
        arms = {c.repair_arm for c in rep}
        if arms != {"forward_correction", "repeat"}:
            continue
        r = stats.cluster_bootstrap_rate_diff(
            [float(bool(c.repair_success)) for c in rep],
            [c.repair_arm == "forward_correction" for c in rep],
            [c.task_id for c in rep],
            n_boot=n_boot,
        )
        L.append(f"| {cond} | {len(rep)} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} |")
    if not L:
        return []
    return ["## RQ2 repair: forward correction - repeat (earliest eligible request)", "",
            "| Condition | assigned failure points | difference | 95% CI (task-clustered) |",
            "|---|---|---|---|", *L, ""]


def build_report(
    sessions: list[SessionScore],
    pairs: Sequence[tuple[str, str]] = (),
    title: str = "E2 evaluation report",
    n_boot: int = 4000,
) -> str:
    by_cond: dict[str, list[SessionScore]] = defaultdict(list)
    for s in sessions:
        by_cond[s.condition].append(s)
    L = [f"# {title}", "",
         "All values *measured locally* from the session logs below; thresholds are *proposed "
         "targets* (proposal v2.11 §8). Primary denominator = effective intent chains (final "
         "intent not withdrawn, capacity-skipped included). 'Cannot tell' counts as failure "
         "in the primary analysis.", ""]
    L += ["| Condition | sessions | effective chains | success | Wilson 95% CI |", "|---|---|---|---|---|"]
    for cond, ss in sorted(by_cond.items()):
        sm = summarize([c for s in ss for c in s.chains])
        L.append(f"| {cond} | {len(ss)} | {sm['n_effective']} | {_f(sm['success_rate'], True)} | "
                 f"{_ci(*stats.wilson(sm['n_success'], sm['n_effective']))} |")
    L.append("")
    if pairs:
        L += compare(by_cond, pairs, n_boot=n_boot)
    L += repair_comparison(by_cond, n_boot=n_boot)
    for cond, ss in sorted(by_cond.items()):
        L += condition_section(cond, ss, n_boot=n_boot)
    return "\n".join(L)


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--compare", action="append", default=[], help="COND_A:COND_B (A - B)")
    ap.add_argument("--source", action="append", default=None,
                    help="verdict source preference order (default adjudicated, human, judge)")
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args(argv)
    cfg = ScoringConfig(source_preference=tuple(args.source)) if args.source else ScoringConfig()
    scores = [score_session(load_session(p), cfg) for p in args.logs]
    pairs = [tuple(p.split(":", 1)) for p in args.compare]
    md = build_report(scores, pairs, n_boot=args.n_boot)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md + "\n")
    else:
        print(md)


if __name__ == "__main__":
    main()

===== FILE: live_agent/memory/schema.py =====
"""Record model for long-term memory (proposal §5.6).

Working context (prompt, recent turns, presented-content summary) and inference caches
(TaoMate-H3 KV, LLM KV) are deliberately *not* modelled here: they live and die with a
session and must never be confused with long-term memory.

Scopes
------
``private:<user_id>``  one user's private conversation data.
``public:<stream_id>`` data from one public livestream (viewer chat, public persona lines).
``canon``              persona canon anchors; the only thing a public session may boot from.

Every record carries ``source_scopes``: the union of its own scope and the
``source_scopes`` of everything it was derived from. Retrieval filters on
``source_scopes`` (never on ``scope`` alone), so a "public" ledger entry that was
derived from a private conversation can never be read in public mode.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


class Kind(str, enum.Enum):
    USER_FACT = "user_fact"  # semantic: subject, predicate, value, valid_from/to, confidence
    EPISODE = "episode"  # append-only turn log (user / viewer turns)
    LEDGER = "ledger"  # persona / world continuity; canonical anchors are immutable
    GENERATED_EVENT = "generated_event"  # everything the persona said or showed; never promoted
    CANDIDATE_BELIEF = "candidate_belief"  # agent inference pending confirmation
    PROCEDURAL = "procedural"  # A²RD-style success / failure prompt-library entry
    SUMMARY = "summary"  # sleep-time consolidation output (derived artifact)


class ClaimType(str, enum.Enum):
    OWN_ASSERTION = "own_assertion"
    QUOTE_OF_PERSONA = "quote_of_persona"
    QUESTION = "question"
    HYPOTHETICAL = "hypothetical"  # includes jokes / role-play
    AGENT_INFERENCE = "agent_inference"
    VIEWER_CLAIM = "viewer_claim"
    SYSTEM_OBSERVATION = "system_observation"  # also used for persona output (speaker="persona")


class Status(str, enum.Enum):
    ACTIVE = "active"  # usable
    PENDING = "pending"  # needs explicit user confirmation (echo, conflict, candidate belief)
    SUPERSEDED = "superseded"  # bi-temporal history: valid_to is set, kept for audit
    STALE = "stale"  # derived artifact whose source was corrected; must be regenerated
    REJECTED = "rejected"  # user declined a pending candidate


# Conflict-resolution priority (higher wins): user-asserted > system-observed >
# agent-inferred > viewer-claimed. Anything else never resolves a fact.
CLAIM_PRIORITY: dict[ClaimType, int] = {
    ClaimType.OWN_ASSERTION: 4,
    ClaimType.SYSTEM_OBSERVATION: 3,
    ClaimType.AGENT_INFERENCE: 2,
    ClaimType.VIEWER_CLAIM: 1,
}

# Predicates that hold one value at a time; a new value is a correction or a conflict.
SINGLE_VALUED = {"lives_in", "name", "works_at", "age", "birthday"}


def is_single_valued(predicate: str | None) -> bool:
    return bool(predicate) and (predicate in SINGLE_VALUED or predicate.startswith("favorite"))


CANON = "canon"


def private_scope(user_id: str) -> str:
    return f"private:{user_id}"


def public_scope(stream_id: str) -> str:
    return f"public:{stream_id}"


def validate_scope(scope: str) -> str:
    if scope == CANON:
        return scope
    head, sep, tail = scope.partition(":")
    if sep and tail and head in ("private", "public"):
        return scope
    raise ValueError(f"invalid scope {scope!r}; expected private:<user>, public:<stream> or canon")


def is_private(scope: str) -> bool:
    return scope.startswith("private:")


@dataclass
class Provenance:
    source_id: str = ""  # utterance / frame / request id that produced the record
    speaker: str = ""  # "user" | "persona" | "viewer:<id>" | "agent" | "system"
    session_id: str = ""
    timestamp: float = 0.0  # wall-clock seconds of the source event
    extractor_version: str = ""
    user_id: str = ""  # owning user (for erasure), "" if none

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> Provenance:
        return cls(**json.loads(s)) if s else cls()


@dataclass
class Record:
    id: str
    kind: Kind
    scope: str
    source_scopes: frozenset[str]
    claim_type: ClaimType
    text: str
    provenance: Provenance
    derived_from: tuple[str, ...] = ()
    created_at: float = 0.0
    # semantic fields (user_fact / candidate_belief; optional elsewhere)
    subject: str | None = None
    predicate: str | None = None
    value: str | None = None
    valid_from: float | None = None
    valid_to: float | None = None
    confidence: float = 1.0
    status: Status = Status.ACTIVE
    echo: bool = False
    importance: float = 0.5
    immutable: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def tags(self) -> dict[str, Any]:
        """Compact provenance / claim-type tags for prompt rendering."""
        return {
            "kind": self.kind.value,
            "claim_type": self.claim_type.value,
            "scope": self.scope,
            "speaker": self.provenance.speaker,
            "status": self.status.value,
            "echo": self.echo,
            "source_id": self.provenance.source_id,
        }

    def is_valid_at(self, t: float) -> bool:
        start_ok = self.valid_from is None or self.valid_from <= t
        return start_ok and (self.valid_to is None or t < self.valid_to)


def union_scopes(own: str, parents: Iterable[Record]) -> frozenset[str]:
    out = {own}
    for p in parents:
        out |= p.source_scopes
    return frozenset(out)

===== FILE: live_agent/memory/extract.py =====
"""Pluggable fact extraction, claim-type classification and viewer-chat sanitisation.

The write policy (proposal §5.6) first decides *what kind of sentence* an utterance is
(own assertion, quote of the persona, question, hypothetical/joke) and only then extracts
facts. Only ``own_assertion`` candidates may become user facts; the classification of
everything else is still recorded on the episode for audit.

:class:`RuleExtractor` is a small deterministic default for tests and offline use
(simple Chinese/English patterns). An LLM extractor can implement :class:`Extractor`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .schema import ClaimType


@dataclass
class CandidateFact:
    text: str  # the sentence the fact came from
    claim_type: ClaimType
    subject: str | None = None  # relative: "user" or "user/sister"; the store makes it absolute
    predicate: str | None = None
    value: str | None = None
    confidence: float = 0.8
    correction: bool = False  # explicit correction cue ("actually", "不对", "moved to" ...)


@runtime_checkable
class Extractor(Protocol):
    version: str

    def classify(self, text: str) -> ClaimType:
        """Utterance-level claim type (used to tag the episode)."""
        ...

    def extract(self, text: str) -> list[CandidateFact]:
        """Candidate facts, each tagged with the claim type of its sentence."""
        ...


# --------------------------------------------------------------------------- rules

_SENT = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]*")

_QUOTE = re.compile(
    r"(你(刚才|之前|上次|以前)?(说过|说|讲过|告诉过?我|提到过?)|听你说|you (told|said|mentioned)|"
    r"you'?ve (told|said)|as you said|according to you)",
    re.IGNORECASE,
)
_HYPO = re.compile(
    r"(如果|假如|假设|要是|万一|开玩笑|逗你|\bif\b|\bsuppose\b|\bimagine\b|\bpretend\b|"
    r"\bjust kidding\b|\bjk\b|\bwhat if\b|\bhypothetically\b)",
    re.IGNORECASE,
)
_QMARK = re.compile(r"[?？]\s*$|[吗嘛呢]\s*[。.]?\s*$")
_QWORD_EN = re.compile(
    r"^\s*(do|does|did|is|are|was|were|can|could|will|would|should|have|has|what|where|who|when|why|how)\b",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"(不对|其实|更正|纠正|说错了|搬到|搬去|现在|改成|\bactually\b|\bno longer\b|\banymore\b|"
    r"\bmoved to\b|\bcorrection\b|\bnot anymore\b|\bi meant\b|\bnow\b)",
    re.IGNORECASE,
)

_REL_ZH = {
    "妹妹": "sister", "姐姐": "sister", "哥哥": "brother", "弟弟": "brother",
    "妈妈": "mother", "母亲": "mother", "爸爸": "father", "父亲": "father",
    "老婆": "wife", "妻子": "wife", "老公": "husband", "丈夫": "husband",
    "儿子": "son", "女儿": "daughter", "男朋友": "boyfriend", "女朋友": "girlfriend", "朋友": "friend",
}
_REL_EN = {
    "sister": "sister", "brother": "brother", "mother": "mother", "mom": "mother", "mum": "mother",
    "father": "father", "dad": "father", "wife": "wife", "husband": "husband", "son": "son",
    "daughter": "daughter", "friend": "friend", "boyfriend": "boyfriend", "girlfriend": "girlfriend",
}
_OBJ_ZH = {"喝": "drink", "吃": "food", "看": "watch", "听": "music", "玩": "game"}

_ZH_REL = "|".join(sorted(_REL_ZH, key=len, reverse=True))
_EN_REL = "|".join(sorted(_REL_EN, key=len, reverse=True))
_ZV = r"(?P<val>[^，。！？；,.!?;\s的]{1,20})"
_EV = r"(?P<val>[^,.!?;]{1,40}?)(?=\s+(?:and|but|now|too|already)\b|[,.!?;]|$)"

# (pattern, predicate or None if derived from groups)
_ZH_RULES: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(rf"我(?:的)?(?P<rel>{_ZH_REL})?(?:现在|目前|其实|也|已经)?(?:住在|搬到了?|搬去了?)" + _ZV), "lives_in"),
    (re.compile(r"(?:我的名字是|我叫)" + _ZV), "name"),
    (re.compile(r"我最(?:喜欢|爱)(?P<obj>喝|吃|看|听|玩)?" + _ZV), "favorite"),
    (re.compile(r"我(?:不喜欢|讨厌|不爱)(?P<obj>喝|吃|看|听|玩)?" + _ZV), "dislikes"),
    (re.compile(r"我(?:很|也|非常|特别)?(?:喜欢|爱)(?P<obj>喝|吃|看|听|玩)?" + _ZV), "likes"),
    (re.compile(r"我在(?P<val>[^，。！？；,.!?;\s]{1,20}?)(?:工作|上班)"), "works_at"),
]
_EN_RULES: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(rf"\bmy (?P<rel>{_EN_REL}) (?:now |still |actually |also )?(?:lives|is living|has moved|moved) (?:in|to) " + _EV, re.IGNORECASE), "lives_in"),
    (re.compile(r"\bI (?:now |still |actually |also )?(?:live|am living|have moved|'ve moved|moved) (?:in|to) " + _EV, re.IGNORECASE), "lives_in"),
    (re.compile(r"\b(?:my name is|call me) " + _EV, re.IGNORECASE), "name"),
    (re.compile(r"\bmy favou?rite (?P<obj>\w+) is " + _EV, re.IGNORECASE), "favorite"),
    (re.compile(r"\bI (?:don't|do not|really don't) (?:like|love) " + _EV + r"|\bI hate " + _EV.replace("val", "val2"), re.IGNORECASE), "dislikes"),
    (re.compile(r"\bI (?:really |also )?(?:like|love|enjoy) " + _EV, re.IGNORECASE), "likes"),
    (re.compile(r"\bI work (?:at|for) " + _EV, re.IGNORECASE), "works_at"),
]
_TRAIL_ZH = re.compile(r"[了呢啊呀吧哦嘛吗]+$")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.findall(text) if s.strip()]


class RuleExtractor:
    """Deterministic pattern extractor (Chinese + English). Version is stored in provenance."""

    version = "rule-v1"

    def classify(self, text: str) -> ClaimType:
        # An utterance counts as an assertion if any sentence is one; otherwise it takes the
        # type of its first sentence. Facts are still classified per sentence in extract().
        types = [self._classify_sentence(s) for s in split_sentences(text)] or [ClaimType.OWN_ASSERTION]
        return ClaimType.OWN_ASSERTION if ClaimType.OWN_ASSERTION in types else types[0]

    def _classify_sentence(self, s: str) -> ClaimType:
        if _QUOTE.search(s):
            return ClaimType.QUESTION if _QMARK.search(s) else ClaimType.QUOTE_OF_PERSONA
        if _QMARK.search(s) or _QWORD_EN.search(s):
            return ClaimType.QUESTION
        if _HYPO.search(s):
            return ClaimType.HYPOTHETICAL
        return ClaimType.OWN_ASSERTION

    def extract(self, text: str) -> list[CandidateFact]:
        out: list[CandidateFact] = []
        for sent in split_sentences(text):
            ct = self._classify_sentence(sent)
            corr = bool(_CORRECTION.search(sent))
            taken: list[tuple[int, int]] = []
            for pat, pred in _ZH_RULES + _EN_RULES:
                for m in pat.finditer(sent):
                    if any(a < m.end() and m.start() < b for a, b in taken):
                        continue  # a more specific rule already consumed this span
                    fact = self._build(m, pred or "", sent, ct, corr)
                    if fact is not None:
                        taken.append((m.start(), m.end()))
                        out.append(fact)
        return out

    @staticmethod
    def _build(m: re.Match[str], pred: str, sent: str, ct: ClaimType, corr: bool) -> CandidateFact | None:
        gd = m.groupdict()
        val = (gd.get("val") or gd.get("val2") or "").strip()
        val = _TRAIL_ZH.sub("", val).strip(" '\"“”")
        if not val:
            return None
        rel = gd.get("rel")
        subject = "user"
        if rel:
            subject = "user/" + (_REL_ZH.get(rel) or _REL_EN.get(rel.lower(), rel.lower()))
        obj = gd.get("obj")
        if pred == "favorite":
            if obj:
                pred = "favorite_" + (_OBJ_ZH.get(obj) or obj.lower())
        return CandidateFact(
            text=sent, claim_type=ct, subject=subject, predicate=pred, value=val,
            confidence=0.8, correction=corr,
        )


# --------------------------------------------------------------------------- sanitising

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
        r"disregard (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
        r"forget (all |your )?(previous |prior )?(instructions|rules)",
        r"you are now\b",
        r"\bsystem prompt\b",
        r"\bnew instructions?:",
        r"\b(remember|memori[sz]e) (that|this)\b",
        r"<\|[^|>]*\|>",
        r"\[/?(INST|SYS)\]",
        r"^\s*#{2,}",
        r"(?:^|\s)(system|assistant)\s*:",
        r"忽略(之前|以上|前面|上面|先前)?的?(所有)?(指令|指示|提示|规则|设定)",
        r"无视(之前|以上|前面)?的?(所有)?(指令|指示|提示|规则)",
        r"(系统提示|系统指令|你现在是|请记住|记住[:：])",
    )
]


@dataclass
class SanitizedText:
    text: str
    injection: bool
    truncated: bool


def sanitize(text: str, max_len: int = 200) -> SanitizedText:
    """Strip control/format characters, drop prompt-injection markers, cap length."""
    cleaned = "".join(
        " " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in text
    )
    injection = False
    for pat in INJECTION_PATTERNS:
        cleaned, n = pat.subn(" ", cleaned)
        injection = injection or n > 0
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    truncated = len(cleaned) > max_len
    return SanitizedText(cleaned[:max_len], injection, truncated)

===== FILE: live_agent/memory/store.py =====
"""SQLite-backed long-term memory service (proposal §5.6, evaluated by E3 §7.3).

One DB file per deployment. Tables:

``records``        every stored record (all kinds), bi-temporal fields for facts.
``record_scopes``  one row per element of a record's ``source_scopes`` (the SQL filter key).
``derivations``    ``derived_from`` edges (child -> parent) for invalidation / erasure cascades.
``embeddings``     one vector per record (pluggable :class:`Embedder`).
``tombstones``     erasure ledger: only (sha256 of id, time, reason code).
``generated_event_log`` (VIEW) everything the persona said / showed.

Invariants enforced here (not by callers):

* Persona output is only ever a ``generated_event``; it is never promoted to a user fact.
* Only ``own_assertion`` sentences from the user become facts; candidates that echo an
  earlier generated event are held ``pending`` until :meth:`MemoryStore.confirm`.
* Retrieval filters on ``source_scopes`` *before* ranking; public mode can never read a
  record with any private source scope.
* Canon records may only derive from canon and are immutable (SQL triggers).
* Episodes are append-only (text cannot be updated); erasure physically deletes rows
  with ``PRAGMA secure_delete=ON`` so the bytes are overwritten in the file.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..types import Utterance, new_id
from .embed import Embedder, HashingEmbedder
from .extract import CandidateFact, Extractor, RuleExtractor, sanitize
from .schema import (
    CANON,
    CLAIM_PRIORITY,
    ClaimType,
    Kind,
    Provenance,
    Record,
    Status,
    is_private,
    is_single_valued,
    private_scope,
    public_scope,
    union_scopes,
    validate_scope,
)
from .summarize import ExtractiveSummarizer, Summarizer

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    text TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    t REAL NOT NULL,
    created_at REAL NOT NULL,
    subject TEXT, predicate TEXT, value TEXT,
    valid_from REAL, valid_to REAL,
    confidence REAL NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL,
    echo INTEGER NOT NULL DEFAULT 0,
    importance REAL NOT NULL DEFAULT 0.5,
    immutable INTEGER NOT NULL DEFAULT 0,
    provenance TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS records_kind ON records(kind, status);
CREATE INDEX IF NOT EXISTS records_sp ON records(subject, predicate);
CREATE INDEX IF NOT EXISTS records_session ON records(session_id);
CREATE INDEX IF NOT EXISTS records_owner ON records(owner);
CREATE INDEX IF NOT EXISTS records_t ON records(t);
CREATE TABLE IF NOT EXISTS record_scopes (
    record_id TEXT NOT NULL, scope TEXT NOT NULL, PRIMARY KEY (record_id, scope)
);
CREATE INDEX IF NOT EXISTS record_scopes_scope ON record_scopes(scope);
CREATE TABLE IF NOT EXISTS derivations (
    child_id TEXT NOT NULL, parent_id TEXT NOT NULL, PRIMARY KEY (child_id, parent_id)
);
CREATE INDEX IF NOT EXISTS derivations_parent ON derivations(parent_id);
CREATE TABLE IF NOT EXISTS embeddings (
    record_id TEXT PRIMARY KEY, model TEXT NOT NULL, vec BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS tombstones (
    id_hash TEXT NOT NULL, t REAL NOT NULL, reason TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS generated_event_log AS
    SELECT id, text, scope, session_id, t, provenance FROM records WHERE kind = 'generated_event';
CREATE TRIGGER IF NOT EXISTS immutable_no_update BEFORE UPDATE ON records
    WHEN OLD.immutable = 1 BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS immutable_no_delete BEFORE DELETE ON records
    WHEN OLD.immutable = 1 BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS log_append_only BEFORE UPDATE OF text, scope, provenance ON records
    WHEN OLD.kind IN ('episode', 'generated_event') BEGIN SELECT RAISE(ABORT, 'append-only'); END;
"""

_DEFAULT_IMPORTANCE = {
    Kind.USER_FACT: 0.8,
    Kind.LEDGER: 0.7,
    Kind.SUMMARY: 0.6,
    Kind.PROCEDURAL: 0.5,
    Kind.EPISODE: 0.4,
    Kind.GENERATED_EVENT: 0.3,
    Kind.CANDIDATE_BELIEF: 0.2,
}
_KIND_PREFIX = {
    Kind.USER_FACT: "fact", Kind.EPISODE: "ep", Kind.LEDGER: "led", Kind.GENERATED_EVENT: "gen",
    Kind.CANDIDATE_BELIEF: "bel", Kind.PROCEDURAL: "proc", Kind.SUMMARY: "sum",
}


class ImmutableRecordError(RuntimeError):
    pass


@dataclass
class IngestResult:
    episode: Record | None
    facts: list[Record] = field(default_factory=list)  # stored (active or pending) fact records
    skipped: list[tuple[CandidateFact, str]] = field(default_factory=list)  # (candidate, reason)
    generated_event: Record | None = None  # set when a persona utterance was routed here


@dataclass
class Hit:
    record: Record
    score: float
    relevance: float
    recency: float
    importance: float

    @property
    def tags(self) -> dict[str, Any]:
        return self.record.tags


@dataclass
class RetrievalResult:
    hits: list[Hit]
    elapsed_ms: float
    scanned: int
    truncated: bool  # budget exhausted before all eligible candidates were scored

    def __iter__(self):
        return iter(self.hits)

    def __len__(self) -> int:
        return len(self.hits)

    @property
    def records(self) -> list[Record]:
        return [h.record for h in self.hits]


@dataclass
class Resolution:
    subject: str
    predicate: str
    value: str | None
    record: Record | None
    alternatives: list[Record]  # lower-priority / older active claims
    pending: list[Record]  # echo or conflicting candidates awaiting confirmation

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.pending)


@dataclass
class ErasureReport:
    """Passed to erasure hooks so the orchestrator can purge external caches.

    ``terms`` are held in memory only (never persisted) so hooks can scrub LLM prompt
    caches, unsent BlockScripts and recordings; ``sessions`` tells which generator / LLM
    sessions to restart from canon anchors.
    """

    user_id: str
    reason: str
    t: float
    deleted_ids: list[str]
    kinds: dict[str, int]
    sessions: set[str]
    terms: set[str]
    regenerated: list[str] = field(default_factory=list)  # new summary ids
    hook_errors: list[str] = field(default_factory=list)


class _RateLimiter:
    def __init__(self, max_events: int, window_s: float, clock: Callable[[], float]) -> None:
        self.max_events, self.window_s, self.clock = max_events, window_s, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        q = self._events[key]
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if len(q) >= self.max_events:
            return False
        q.append(now)
        return True


class MemoryStore:
    """Long-term memory for one deployment. Not thread-safe; use one instance per process."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        embedder: Embedder | None = None,
        extractor: Extractor | None = None,
        clock: Callable[[], float] = time.time,
        echo_threshold: float = 0.5,
        echo_lexical_floor: float = 0.4,
        viewer_rate: tuple[int, float] = (5, 10.0),
        viewer_max_len: int = 200,
        recency_tau_s: float = 3 * 86400.0,
        weights: tuple[float, float, float] = (0.6, 0.2, 0.2),
    ) -> None:
        self.path = str(path)
        self.embedder: Embedder = embedder or HashingEmbedder()
        self.extractor: Extractor = extractor or RuleExtractor()
        self.clock = clock
        self.echo_threshold = echo_threshold
        self.echo_lexical_floor = echo_lexical_floor
        self.viewer_max_len = viewer_max_len
        self.recency_tau_s = recency_tau_s
        self.weights = weights
        self._viewer_limiter = _RateLimiter(viewer_rate[0], viewer_rate[1], clock)
        self.stats: dict[str, int] = defaultdict(int)
        # hooks: erasure -> external caches; stale -> summary regeneration etc.
        self.erasure_hooks: list[Callable[[ErasureReport], None]] = []
        self.stale_hooks: list[Callable[[list[Record]], None]] = []
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA secure_delete = ON")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ low level

    def add_record(
        self,
        kind: Kind,
        scope: str,
        text: str,
        claim_type: ClaimType,
        provenance: Provenance,
        *,
        derived_from: Sequence[str] = (),
        subject: str | None = None,
        predicate: str | None = None,
        value: str | None = None,
        valid_from: float | None = None,
        confidence: float = 1.0,
        status: Status = Status.ACTIVE,
        echo: bool = False,
        importance: float | None = None,
        immutable: bool = False,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Record:
        """Insert one record; computes ``source_scopes`` from its parents and embeds it."""
        validate_scope(scope)
        parents = [self._require(pid) for pid in dict.fromkeys(derived_from)]
        source_scopes = union_scopes(scope, parents)
        if scope == CANON and source_scopes != {CANON}:
            raise ValueError("canon records may only derive from canon records")
        if kind == Kind.GENERATED_EVENT and claim_type == ClaimType.OWN_ASSERTION:
            raise ValueError("generated events are never user assertions")
        now = self.clock()
        owner = provenance.user_id or next((p.provenance.user_id for p in parents if p.provenance.user_id), "")
        provenance.user_id = owner
        if not provenance.timestamp:
            provenance.timestamp = now
        if kind == Kind.USER_FACT and valid_from is None:
            valid_from = provenance.timestamp
        rec = Record(
            id=new_id(_KIND_PREFIX[kind]), kind=kind, scope=scope, source_scopes=source_scopes,
            claim_type=claim_type, text=text, provenance=provenance,
            derived_from=tuple(p.id for p in parents), created_at=now, subject=subject,
            predicate=predicate, value=value, valid_from=valid_from, valid_to=None,
            confidence=confidence, status=status, echo=echo,
            importance=_DEFAULT_IMPORTANCE[kind] if importance is None else importance,
            immutable=immutable, meta=dict(meta or {}),
        )
        self.db.execute(
            "INSERT INTO records (id, kind, scope, claim_type, text, owner, session_id, t, created_at,"
            " subject, predicate, value, valid_from, valid_to, confidence, status, echo, importance,"
            " immutable, provenance, meta) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec.id, kind.value, scope, claim_type.value, text, owner, provenance.session_id,
                provenance.timestamp, now, subject, predicate, value, valid_from, None, confidence,
                status.value, int(echo), rec.importance, int(immutable), provenance.to_json(),
                json.dumps(rec.meta, ensure_ascii=False),
            ),
        )
        self.db.executemany(
            "INSERT INTO record_scopes (record_id, scope) VALUES (?, ?)",
            [(rec.id, s) for s in sorted(source_scopes)],
        )
        self.db.executemany(
            "INSERT INTO derivations (child_id, parent_id) VALUES (?, ?)",
            [(rec.id, p.id) for p in parents],
        )
        vec = self.embedder.embed([self._embed_text(rec)])[0].astype(np.float32)
        self.db.execute(
            "INSERT INTO embeddings (record_id, model, vec) VALUES (?, ?, ?)",
            (rec.id, self.embedder.name, vec.tobytes()),
        )
        if commit:
            self.db.commit()
        return rec

    @staticmethod
    def _embed_text(rec: Record) -> str:
        if rec.subject and rec.predicate and rec.value:
            return f"{rec.text} {rec.value}"
        return rec.text

    def get(self, record_id: str) -> Record | None:
        recs = self._load([record_id])
        return recs[0] if recs else None

    def _require(self, record_id: str) -> Record:
        rec = self.get(record_id)
        if rec is None:
            raise KeyError(record_id)
        return rec

    def _load(self, ids: Sequence[str]) -> list[Record]:
        if not ids:
            return []
        out: dict[str, Record] = {}
        for chunk_start in range(0, len(ids), 500):
            chunk = list(ids[chunk_start:chunk_start + 500])
            q = ",".join("?" * len(chunk))
            rows = self.db.execute(f"SELECT * FROM records WHERE id IN ({q})", chunk).fetchall()
            scopes: dict[str, set[str]] = defaultdict(set)
            for r in self.db.execute(f"SELECT record_id, scope FROM record_scopes WHERE record_id IN ({q})", chunk):
                scopes[r[0]].add(r[1])
            parents: dict[str, list[str]] = defaultdict(list)
            for r in self.db.execute(
                f"SELECT child_id, parent_id FROM derivations WHERE child_id IN ({q}) ORDER BY rowid", chunk
            ):
                parents[r[0]].append(r[1])
            for row in rows:
                out[row["id"]] = self._row_to_record(row, scopes[row["id"]], parents[row["id"]])
        return [out[i] for i in ids if i in out]

    @staticmethod
    def _row_to_record(row: sqlite3.Row, scopes: set[str], parents: list[str]) -> Record:
        return Record(
            id=row["id"], kind=Kind(row["kind"]), scope=row["scope"], source_scopes=frozenset(scopes),
            claim_type=ClaimType(row["claim_type"]), text=row["text"],
            provenance=Provenance.from_json(row["provenance"]), derived_from=tuple(parents),
            created_at=row["created_at"], subject=row["subject"], predicate=row["predicate"],
            value=row["value"], valid_from=row["valid_from"], valid_to=row["valid_to"],
            confidence=row["confidence"], status=Status(row["status"]), echo=bool(row["echo"]),
            importance=row["importance"], immutable=bool(row["immutable"]), meta=json.loads(row["meta"]),
        )

    def _ids(self, sql: str, params: Sequence[Any] = ()) -> list[str]:
        return [r[0] for r in self.db.execute(sql, params)]

    def _set_status(self, record_id: str, status: Status, **cols: Any) -> None:
        sets = ["status = ?"] + [f"{c} = ?" for c in cols]
        try:
            self.db.execute(
                f"UPDATE records SET {', '.join(sets)} WHERE id = ?", [status.value, *cols.values(), record_id]
            )
        except sqlite3.IntegrityError as e:
            raise ImmutableRecordError(record_id) from e

    def _update_meta(self, record_id: str, **kv: Any) -> None:
        rec = self._require(record_id)
        rec.meta.update(kv)
        self.db.execute("UPDATE records SET meta = ? WHERE id = ?", (json.dumps(rec.meta, ensure_ascii=False), record_id))

    # ------------------------------------------------------------------ scope helpers

    @staticmethod
    def _scope_filter_sql(mode: str, user_id: str | None, stream_id: str | None) -> tuple[str, list[Any]]:
        """SQL predicate over ``rs.scope`` that is TRUE for readable scopes."""
        if mode == "private":
            if not user_id:
                raise ValueError("private mode requires user_id")
            return "(rs.scope = 'canon' OR rs.scope = ? OR rs.scope LIKE 'public:%')", [private_scope(user_id)]
        if mode == "public":
            if stream_id:
                return "(rs.scope = 'canon' OR rs.scope = ?)", [public_scope(stream_id)]
            return "(rs.scope = 'canon' OR rs.scope LIKE 'public:%')", []
        raise ValueError(f"unknown mode {mode!r}; expected 'private' or 'public'")

    @staticmethod
    def scope_readable(scopes: Iterable[str], mode: str, user_id: str | None, stream_id: str | None) -> bool:
        """Python mirror of the SQL filter (defence in depth)."""
        for s in scopes:
            if s == CANON:
                continue
            if mode == "private" and (s == private_scope(user_id or "") or s.startswith("public:")):
                continue
            if mode == "public" and (s == public_scope(stream_id) if stream_id else s.startswith("public:")):
                continue
            return False
        return True

    def _utterance_scope(self, utt: Utterance, user_id: str, stream_id: str | None) -> str:
        if ":" in utt.scope or utt.scope == CANON:
            return validate_scope(utt.scope)
        if utt.scope == "public":
            if not stream_id:
                raise ValueError("public utterance requires stream_id")
            return public_scope(stream_id)
        return private_scope(user_id)

    # ------------------------------------------------------------------ write policy

    def ingest_user_utterance(
        self,
        utt: Utterance,
        extractor: Extractor | None = None,
        *,
        user_id: str,
        stream_id: str | None = None,
    ) -> IngestResult:
        """Append the turn to the episode log and store candidate facts per the write policy.

        Persona utterances are routed to the generated-event log; viewer utterances to
        :meth:`ingest_viewer_chat`. Only ``own_assertion`` sentences produce facts.
        """
        ex = extractor or self.extractor
        scope = self._utterance_scope(utt, user_id, stream_id)
        if utt.speaker == "persona":
            gen = self.record_generated_event(utt.text, utt.session_id, scope, source_id=utt.uid, user_id=user_id)
            return IngestResult(episode=None, generated_event=gen)
        if utt.speaker.startswith("viewer:"):
            if not stream_id:
                raise ValueError("viewer chat requires stream_id")
            ep = self.ingest_viewer_chat(utt.text, utt.speaker.split(":", 1)[1], stream_id,
                                         session_id=utt.session_id, source_id=utt.uid)
            return IngestResult(episode=ep)

        prov = lambda: Provenance(
            source_id=utt.uid, speaker="user", session_id=utt.session_id, timestamp=self.clock(),
            extractor_version=ex.version, user_id=user_id,
        )
        episode = self.add_record(
            Kind.EPISODE, scope, utt.text, ex.classify(utt.text), prov(),
            meta={"t_end": utt.t_end}, commit=False,
        )
        result = IngestResult(episode=episode)
        for cand in ex.extract(utt.text):
            if cand.claim_type != ClaimType.OWN_ASSERTION:
                result.skipped.append((cand, cand.claim_type.value))
                continue
            if not (cand.subject and cand.predicate and cand.value):
                result.skipped.append((cand, "incomplete"))
                continue
            rec = self._store_user_fact(cand, scope, user_id, episode, prov())
            if rec is None:
                result.skipped.append((cand, "duplicate"))
            else:
                result.facts.append(rec)
        self.db.commit()
        return result

    def _abs_subject(self, subject: str, user_id: str) -> str:
        if subject.startswith(("user:", "viewer:", "persona")):
            return subject
        if subject == "user":
            return f"user:{user_id}"
        if subject.startswith("user/"):
            return f"user:{user_id}/{subject[5:]}"
        return subject

    def _store_user_fact(
        self, cand: CandidateFact, scope: str, user_id: str, episode: Record, prov: Provenance
    ) -> Record | None:
        subject = self._abs_subject(cand.subject or "user", user_id)
        echo_ids = self._echo_matches(cand.text, cand.value or "", user_id)
        derived = [episode.id, *echo_ids]
        meta: dict[str, Any] = {}
        status = Status.ACTIVE
        current = self._current_facts(subject, cand.predicate or "", user_id, claim=ClaimType.OWN_ASSERTION)
        same = [r for r in current if _norm(r.value) == _norm(cand.value)]
        if same:
            return None  # already asserted by the user: no duplicate
        if echo_ids:
            status = Status.PENDING
            meta["echo_of"] = echo_ids
        different = [r for r in current if _norm(r.value) != _norm(cand.value)]
        if status == Status.ACTIVE and different and is_single_valued(cand.predicate):
            if cand.correction:
                meta["supersedes"] = [r.id for r in different]
                self._supersede(different)
            else:
                status = Status.PENDING
                meta["conflict_with"] = [r.id for r in different]
        elif echo_ids and different and is_single_valued(cand.predicate):
            meta["conflict_with"] = [r.id for r in different]
        return self.add_record(
            Kind.USER_FACT, scope, cand.text, ClaimType.OWN_ASSERTION, prov, derived_from=derived,
            subject=subject, predicate=cand.predicate, value=cand.value, confidence=cand.confidence,
            status=status, echo=bool(echo_ids), meta=meta, commit=False,
        )

    def _echo_matches(self, text: str, value: str, user_id: str) -> list[str]:
        """Generated events readable by this user that the candidate semantically echoes."""
        filt, params = self._scope_filter_sql("private", user_id, None)
        rows = self.db.execute(
            "SELECT r.id, r.text, e.vec FROM records r JOIN embeddings e ON e.record_id = r.id"
            " WHERE r.kind = 'generated_event' AND NOT EXISTS (SELECT 1 FROM record_scopes rs"
            f" WHERE rs.record_id = r.id AND NOT {filt})",
            params,
        ).fetchall()
        if not rows:
            return []
        q = self.embedder.embed([f"{text} {value}"])[0]
        mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        sims = mat @ q
        nv = _norm(value)
        hits = []
        for r, s in zip(rows, sims):
            lexical = len(nv) >= 2 and nv in _norm(r["text"])
            if s >= self.echo_threshold or (lexical and s >= self.echo_lexical_floor):
                hits.append(r["id"])
        return hits

    def record_generated_event(
        self,
        text: str,
        session_id: str,
        scope: str,
        *,
        source_id: str = "",
        user_id: str = "",
        derived_from: Sequence[str] = (),
        request_index: int | None = None,
    ) -> Record:
        """Log persona output (speech / shown content). Never promoted to a user fact.

        Persona lines in a private conversation are private (pass ``private:<user>``);
        ``derived_from`` should list the memory records the line was conditioned on so the
        line inherits their ``source_scopes``.
        """
        validate_scope(scope)
        if not user_id and is_private(scope):
            user_id = scope.split(":", 1)[1]
        prov = Provenance(source_id=source_id, speaker="persona", session_id=session_id,
                          timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.GENERATED_EVENT, scope, text, ClaimType.SYSTEM_OBSERVATION, prov,
            derived_from=derived_from, meta={"request_index": request_index} if request_index is not None else None,
        )

    def ingest_viewer_chat(
        self, text: str, viewer_id: str, stream_id: str, *, session_id: str = "", source_id: str = ""
    ) -> Record | None:
        """Public-scope, ``viewer_claim``, rate-limited and sanitised. Returns None if dropped."""
        if not self._viewer_limiter.allow(viewer_id):
            self.stats["viewer_rate_limited"] += 1
            return None
        clean = sanitize(text, self.viewer_max_len)
        if not clean.text:
            self.stats["viewer_empty"] += 1
            return None
        scope = public_scope(stream_id)
        prov = Provenance(source_id=source_id, speaker=f"viewer:{viewer_id}", session_id=session_id,
                          timestamp=self.clock(), extractor_version=self.extractor.version)
        ep = self.add_record(
            Kind.EPISODE, scope, clean.text, ClaimType.VIEWER_CLAIM, prov, importance=0.1,
            meta={"injection": clean.injection, "truncated": clean.truncated}, commit=False,
        )
        if clean.injection:
            self.stats["viewer_injection"] += 1
        else:
            for cand in self.extractor.extract(clean.text):
                if cand.claim_type != ClaimType.OWN_ASSERTION or not (cand.predicate and cand.value):
                    continue
                subj = f"viewer:{viewer_id}" + ((cand.subject or "user")[4:])  # "user/sister" -> "/sister"
                self.add_record(
                    Kind.USER_FACT, scope, cand.text, ClaimType.VIEWER_CLAIM,
                    Provenance(source_id=source_id, speaker=f"viewer:{viewer_id}", session_id=session_id,
                               timestamp=self.clock(), extractor_version=self.extractor.version),
                    derived_from=[ep.id], subject=subj, predicate=cand.predicate, value=cand.value,
                    confidence=0.3, importance=0.1, commit=False,
                )
        self.db.commit()
        return ep

    def record_inference(
        self,
        text: str,
        *,
        user_id: str,
        derived_from: Sequence[str],
        subject: str | None = None,
        predicate: str | None = None,
        value: str | None = None,
        confidence: float = 0.5,
        session_id: str = "",
        scope: str | None = None,
    ) -> Record:
        """Agent inference -> ``candidate_belief`` (pending; never a user fact until confirmed)."""
        prov = Provenance(speaker="agent", session_id=session_id, timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.CANDIDATE_BELIEF, scope or private_scope(user_id), text, ClaimType.AGENT_INFERENCE, prov,
            derived_from=derived_from, subject=self._abs_subject(subject, user_id) if subject else None,
            predicate=predicate, value=value, confidence=confidence, status=Status.PENDING,
        )

    def record_observation(
        self,
        text: str,
        *,
        user_id: str,
        subject: str,
        predicate: str,
        value: str,
        confidence: float = 0.9,
        session_id: str = "",
        source_id: str = "",
        derived_from: Sequence[str] = (),
    ) -> Record:
        """System observation (e.g. from a sensor / platform metadata) as a user fact."""
        prov = Provenance(source_id=source_id, speaker="system", session_id=session_id,
                          timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.USER_FACT, private_scope(user_id), text, ClaimType.SYSTEM_OBSERVATION, prov,
            derived_from=derived_from, subject=self._abs_subject(subject, user_id), predicate=predicate,
            value=value, confidence=confidence,
        )

    def add_ledger(
        self,
        text: str,
        scope: str,
        *,
        canonical: bool = False,
        key: str | None = None,
        derived_from: Sequence[str] = (),
        session_id: str = "",
        user_id: str = "",
    ) -> Record:
        """Persona / world continuity entry. Canonical anchors are immutable and canon-only.

        A non-canonical entry with a ``key`` supersedes the previous entry with the same key
        in the same scope (bi-temporal: old one keeps ``valid_to``).
        """
        if canonical and scope != CANON:
            raise ValueError("canonical anchors must have scope 'canon'")
        if not canonical and scope == CANON:
            raise ValueError("only canonical anchors live in scope 'canon'")
        if key and not canonical:
            old = self._load(self._ids(
                "SELECT id FROM records WHERE kind = 'ledger' AND scope = ? AND status = 'active'"
                " AND json_extract(meta, '$.key') = ?", (scope, key)))
            self._supersede(old)
        prov = Provenance(speaker="system", session_id=session_id, timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.LEDGER, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=derived_from,
            immutable=canonical, meta={"key": key, "canonical": canonical},
        )

    def add_procedure(
        self,
        text: str,
        outcome: str,
        *,
        scope: str = CANON,
        tags: Sequence[str] = (),
        derived_from: Sequence[str] = (),
    ) -> Record:
        """A²RD-style prompt-library entry: what worked (``success``) or failed (``failure``)."""
        if outcome not in ("success", "failure"):
            raise ValueError("outcome must be 'success' or 'failure'")
        prov = Provenance(speaker="system", timestamp=self.clock())
        return self.add_record(
            Kind.PROCEDURAL, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=derived_from,
            meta={"outcome": outcome, "tags": list(tags)},
        )

    # ------------------------------------------------------------------ confirmation / correction

    def confirm(self, record_id: str) -> Record:
        """User explicitly confirms a pending echo / conflicting fact or a candidate belief."""
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending (status={rec.status.value})")
        now = self.clock()
        if rec.subject and rec.predicate and is_single_valued(rec.predicate):
            owner = rec.provenance.user_id
            others = [r for r in self._current_facts(rec.subject, rec.predicate, owner, claim=None)
                      if r.id != rec.id and r.kind == Kind.USER_FACT
                      and r.claim_type in (ClaimType.OWN_ASSERTION, ClaimType.SYSTEM_OBSERVATION)
                      and _norm(r.value) != _norm(rec.value)]
            self._supersede(others)
            if others:
                self._update_meta(rec.id, supersedes=[r.id for r in others])
        cols: dict[str, Any] = {"valid_from": now}
        if rec.kind == Kind.CANDIDATE_BELIEF:
            cols.update(kind=Kind.USER_FACT.value, claim_type=ClaimType.OWN_ASSERTION.value)
            self._update_meta(rec.id, confirmed_from=ClaimType.AGENT_INFERENCE.value)
        self._set_status(rec.id, Status.ACTIVE, **cols)
        self._update_meta(rec.id, confirmed_at=now)
        self.db.commit()
        return self._require(rec.id)

    def reject(self, record_id: str) -> Record:
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending")
        self._set_status(rec.id, Status.REJECTED)
        self.db.commit()
        return self._require(rec.id)

    def correct(self, record_id: str, new_value: str, *, text: str | None = None,
                source_id: str = "", session_id: str = "") -> Record:
        """Bi-temporal correction: old value gets ``valid_to`` (kept for audit), new value is
        inserted, and every artifact reachable through ``derived_from`` is marked stale."""
        old = self._require(record_id)
        if old.kind != Kind.USER_FACT or old.status not in (Status.ACTIVE, Status.PENDING):
            raise ValueError("only current user facts can be corrected")
        self._supersede([old])
        prov = Provenance(source_id=source_id, speaker="user", session_id=session_id or old.provenance.session_id,
                          timestamp=self.clock(), user_id=old.provenance.user_id)
        new = self.add_record(
            Kind.USER_FACT, old.scope, text or f"{old.subject} {old.predicate} {new_value}",
            ClaimType.OWN_ASSERTION, prov, subject=old.subject, predicate=old.predicate, value=new_value,
            meta={"supersedes": [old.id]},
        )
        return new

    def _supersede(self, records: Sequence[Record]) -> list[Record]:
        now = self.clock()
        for r in records:
            if r.immutable:
                raise ImmutableRecordError(r.id)
            self._set_status(r.id, Status.SUPERSEDED, valid_to=now)
        stale = self.invalidate_derivatives([r.id for r in records]) if records else []
        self.db.commit()
        return stale

    def invalidate_derivatives(self, root_ids: Sequence[str]) -> list[Record]:
        """Mark every artifact reachable through ``derived_from`` as stale; fire stale hooks."""
        ids = self._descendants(root_ids) - set(root_ids)
        stale: list[Record] = []
        for rec in self._load(sorted(ids)):
            if rec.immutable or rec.status in (Status.SUPERSEDED, Status.STALE, Status.REJECTED):
                continue
            self._set_status(rec.id, Status.STALE)
            rec.status = Status.STALE
            stale.append(rec)
        self.db.commit()
        if stale:
            for hook in list(self.stale_hooks):
                hook(stale)
        return stale

    def regenerate_stale(self, summarizer: Summarizer | None = None) -> list[Record]:
        """Hook helper: rebuild every stale summary from its session's current records."""
        sessions = {r["session_id"] for r in self.db.execute(
            "SELECT session_id FROM records WHERE kind = 'summary' AND status = 'stale'")}
        out = []
        for s in sorted(sessions):
            rec = self.consolidate(s, summarizer)
            if rec is not None:
                out.append(rec)
        return out

    def _descendants(self, root_ids: Iterable[str]) -> set[str]:
        seen = set(root_ids)
        frontier = list(seen)
        while frontier:
            q = ",".join("?" * len(frontier))
            children = self._ids(f"SELECT child_id FROM derivations WHERE parent_id IN ({q})", frontier)
            frontier = [c for c in children if c not in seen]
            seen.update(frontier)
        return seen

    # ------------------------------------------------------------------ read paths

    def _current_facts(self, subject: str, predicate: str, user_id: str, claim: ClaimType | None) -> list[Record]:
        filt, params = self._scope_filter_sql("private", user_id, None)
        sql = ("SELECT r.id FROM records r WHERE r.kind = 'user_fact' AND r.status = 'active'"
               " AND r.subject = ? AND r.predicate = ? AND (r.valid_to IS NULL OR r.valid_to > ?)"
               f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})")
        args: list[Any] = [subject, predicate, self.clock(), *params]
        if claim is not None:
            sql += " AND r.claim_type = ?"
            args.append(claim.value)
        return self._load(self._ids(sql + " ORDER BY r.valid_from", args))

    def retrieve(
        self,
        query: str,
        mode: str,
        user_id: str | None = None,
        stream_id: str | None = None,
        k: int = 8,
        budget_ms: float = 50.0,
        *,
        kinds: Sequence[Kind] | None = None,
        include_pending: bool = False,
        batch: int = 512,
    ) -> RetrievalResult:
        """Scope-filter first (in SQL, on ``source_scopes``), then rank by
        relevance + recency + importance. Pending / stale / superseded records are excluded
        unless ``include_pending`` (which adds pending only)."""
        t0 = time.perf_counter()
        now = self.clock()
        filt, params = self._scope_filter_sql(mode, user_id, stream_id)
        statuses = ["active"] + (["pending"] if include_pending else [])
        sql = (
            "SELECT r.id, r.t, r.importance, e.vec FROM records r JOIN embeddings e ON e.record_id = r.id"
            f" WHERE r.status IN ({','.join('?' * len(statuses))})"
            " AND (r.valid_to IS NULL OR r.valid_to > ?)"
            f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})"
        )
        args: list[Any] = [*statuses, now, *params]
        if kinds:
            sql += f" AND r.kind IN ({','.join('?' * len(kinds))})"
            args += [Kind(x).value for x in kinds]
        sql += " ORDER BY r.t DESC LIMIT ? OFFSET ?"
        qv = self.embedder.embed([query])[0]
        w_rel, w_rec, w_imp = self.weights
        scored: list[tuple[float, float, float, float, str]] = []
        offset, scanned, truncated = 0, 0, False
        while True:
            rows = self.db.execute(sql, [*args, batch, offset]).fetchall()
            if not rows:
                break
            mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
            rel = np.clip(mat @ qv, 0.0, 1.0)
            for r, rv in zip(rows, rel):
                rec_s = math.exp(-max(0.0, now - r["t"]) / self.recency_tau_s)
                imp = float(r["importance"])
                scored.append((w_rel * float(rv) + w_rec * rec_s + w_imp * imp, float(rv), rec_s, imp, r["id"]))
            scanned += len(rows)
            offset += batch
            if len(rows) < batch:
                break
            if (time.perf_counter() - t0) * 1000.0 > budget_ms:
                truncated = True
                break
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]
        recs = {r.id: r for r in self._load([x[4] for x in top])}
        hits = []
        for score, rv, rs, imp, rid in top:
            rec = recs.get(rid)
            if rec is None or not self.scope_readable(rec.source_scopes, mode, user_id, stream_id):
                continue  # defence in depth; the SQL filter should already have excluded it
            hits.append(Hit(rec, score, rv, rs, imp))
        return RetrievalResult(hits, (time.perf_counter() - t0) * 1000.0, scanned, truncated)

    def resolve(self, user_id: str, subject: str, predicate: str) -> Resolution:
        """Conflict resolution: user-asserted (latest valid) > system-observed >
        agent-inferred > viewer-claimed. Echo / conflicting candidates never count until confirmed."""
        subj = self._abs_subject(subject, user_id)
        filt, params = self._scope_filter_sql("private", user_id, None)
        ids = self._ids(
            "SELECT r.id FROM records r WHERE r.kind IN ('user_fact', 'candidate_belief')"
            " AND r.subject = ? AND r.predicate = ? AND r.status IN ('active', 'pending')"
            " AND (r.valid_to IS NULL OR r.valid_to > ?)"
            f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})",
            [subj, predicate, self.clock(), *params],
        )
        recs = self._load(ids)
        active = [r for r in recs if r.status == Status.ACTIVE and r.claim_type in CLAIM_PRIORITY]
        pending = [r for r in recs if r.status == Status.PENDING]
        active.sort(key=lambda r: (CLAIM_PRIORITY[r.claim_type], r.valid_from or 0.0, r.created_at), reverse=True)
        best = active[0] if active else None
        return Resolution(subj, predicate, best.value if best else None, best, active[1:], pending)

    def profile(self, user_id: str) -> list[Record]:
        """Session preload: current valid user facts (user-asserted or system-observed) from
        the user's private scope; single-valued predicates collapsed to the resolved winner."""
        ids = self._ids(
            "SELECT id FROM records WHERE kind = 'user_fact' AND status = 'active' AND scope = ?"
            " AND claim_type IN ('own_assertion', 'system_observation')"
            " AND (valid_to IS NULL OR valid_to > ?) ORDER BY valid_from",
            [private_scope(user_id), self.clock()],
        )
        out: dict[tuple[str, str], Record] = {}
        multi: list[Record] = []
        for r in self._load(ids):
            if not self.scope_readable(r.source_scopes, "private", user_id, None):
                continue
            if is_single_valued(r.predicate):
                key = (r.subject or "", r.predicate or "")
                prev = out.get(key)
                if prev is None or (CLAIM_PRIORITY[r.claim_type], r.valid_from or 0) >= (
                        CLAIM_PRIORITY[prev.claim_type], prev.valid_from or 0):
                    out[key] = r
            else:
                multi.append(r)
        return list(out.values()) + multi

    def canon_anchors(self) -> list[Record]:
        return self._load(self._ids(
            "SELECT id FROM records WHERE kind = 'ledger' AND scope = 'canon' AND immutable = 1 ORDER BY t"))

    def boot_context(self, mode: str, user_id: str | None = None) -> list[Record]:
        """Records a new session may start from. Public sessions boot from canon anchors only."""
        anchors = self.canon_anchors()
        if mode == "public":
            return anchors
        if mode == "private":
            if not user_id:
                raise ValueError("private mode requires user_id")
            return anchors + self.profile(user_id)
        raise ValueError(mode)

    # ------------------------------------------------------------------ consolidation

    def consolidate(self, session_id: str, summarizer: Summarizer | None = None) -> Record | None:
        """Sleep-time summary of one session. Writes a ``summary`` record whose
        ``derived_from`` lists every input and whose ``source_scopes`` is their union.
        Supersedes any previous summary of the same session."""
        summ = summarizer or ExtractiveSummarizer()
        now = self.clock()
        ids = self._ids(
            "SELECT id FROM records WHERE session_id = ? AND ("
            " (kind IN ('episode', 'generated_event'))"
            " OR (kind = 'user_fact' AND status = 'active' AND (valid_to IS NULL OR valid_to > ?)))"
            " ORDER BY t", [session_id, now])
        recs = self._load(ids)
        # drop turns whose extracted facts were all corrected away (history stays in the episode log)
        retired = set(self._ids(
            "SELECT d.parent_id FROM derivations d JOIN records c ON c.id = d.child_id"
            " WHERE c.kind = 'user_fact' AND c.status IN ('superseded', 'stale', 'rejected')"))
        live = set(self._ids(
            "SELECT d.parent_id FROM derivations d JOIN records c ON c.id = d.child_id"
            " WHERE c.kind = 'user_fact' AND c.status IN ('active', 'pending')"))
        recs = [r for r in recs if not (r.kind == Kind.EPISODE and r.id in retired and r.id not in live)]
        old = self._load(self._ids(
            "SELECT id FROM records WHERE kind = 'summary' AND session_id = ? AND status IN ('active', 'stale')",
            [session_id]))
        for r in old:
            self._set_status(r.id, Status.SUPERSEDED, valid_to=now)
        if not recs:
            self.db.commit()
            return None
        scopes = frozenset().union(*(r.source_scopes for r in recs))
        privs = sorted(s for s in scopes if is_private(s))
        if len(privs) > 1:
            raise ValueError("refusing to summarise across several users' private scopes")
        scope = privs[0] if privs else next((s for s in sorted(scopes) if s.startswith("public:")), CANON)
        if scope == CANON:
            raise ValueError("summaries are never canon")
        text = summ.summarize(recs)
        prov = Provenance(speaker="system", session_id=session_id, timestamp=now,
                          extractor_version=summ.version, user_id=privs[0].split(":", 1)[1] if privs else "")
        return self.add_record(Kind.SUMMARY, scope, text, ClaimType.SYSTEM_OBSERVATION, prov,
                               derived_from=[r.id for r in recs], meta={"session": session_id})

    # ------------------------------------------------------------------ erasure

    def _user_records_sql(self) -> str:
        return ("(r.owner = ? OR EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id"
                " AND rs.scope = ?))")

    def forget(
        self,
        target: str | Record,
        user_id: str,
        reason: str = "user_request",
        *,
        regenerate: bool | Summarizer = True,
    ) -> ErasureReport:
        """Physically erase a fact (by record id / Record) or everything matching a query term.

        Cascade: matched records -> source episodes (id link) -> every record of this user
        mentioning the value/term (content match: episodes, persona lines, summaries,
        ledger ...) -> all descendants through ``derived_from``; plus their embeddings,
        scope rows and derivation edges. A tombstone keeps only sha256(id), time and
        reason. Affected session summaries are regenerated from what remains, then
        erasure hooks fire so the orchestrator can reset LLM KV / generator sessions and
        delete recordings. Over-deletion (e.g. another fact from the same turn) is
        accepted as the safe side.
        """
        priv = private_scope(user_id)
        mine = self._user_records_sql()
        seeds: list[Record] = []
        terms: set[str] = set()
        rid = target.id if isinstance(target, Record) else target
        rec = self.get(rid)
        if rec is not None:
            if rec.provenance.user_id != user_id and priv not in rec.source_scopes:
                raise PermissionError("record does not belong to this user")
            seeds = [rec]
        else:
            term = str(target).strip()
            if not term:
                raise ValueError("empty erasure target")
            terms.add(term)
            seeds = self._load(self._ids(
                f"SELECT r.id FROM records r WHERE {mine} AND r.immutable = 0 AND ("
                " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0)",
                [user_id, priv, term, term]))
        terms |= {s.value for s in seeds if s.value and len(s.value.strip()) >= 2}
        erase: set[str] = {s.id for s in seeds}
        # id link: the episodes the seed facts were extracted from (facts only: a summary's
        # parents are whole sessions and are handled by content match instead)
        for s in seeds:
            if s.kind not in (Kind.USER_FACT, Kind.CANDIDATE_BELIEF):
                continue
            for p in self._load(list(s.derived_from)):
                if p.kind == Kind.EPISODE and (p.provenance.user_id == user_id or priv in p.source_scopes):
                    erase.add(p.id)
        # content match over all of this user's records (any kind)
        for term in terms:
            erase |= set(self._ids(
                f"SELECT r.id FROM records r WHERE {mine} AND r.immutable = 0 AND ("
                " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0)",
                [user_id, priv, term, term]))
        erase = self._descendants(erase)
        doomed = self._load(sorted(erase))
        if any(r.immutable for r in doomed):
            raise ImmutableRecordError("erasure cascade reached a canon anchor; canon must not derive from user data")
        now = self.clock()
        sessions = {r.provenance.session_id for r in doomed if r.provenance.session_id}
        kinds: dict[str, int] = defaultdict(int)
        for r in doomed:
            kinds[r.kind.value] += 1
        ids = [r.id for r in doomed]
        with self.db:
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                q = ",".join("?" * len(chunk))
                self.db.execute(f"DELETE FROM embeddings WHERE record_id IN ({q})", chunk)
                self.db.execute(f"DELETE FROM record_scopes WHERE record_id IN ({q})", chunk)
                self.db.execute(f"DELETE FROM derivations WHERE child_id IN ({q}) OR parent_id IN ({q})", chunk + chunk)
                self.db.execute(f"DELETE FROM records WHERE id IN ({q})", chunk)
            self.db.executemany(
                "INSERT INTO tombstones (id_hash, t, reason) VALUES (?, ?, ?)",
                [(hashlib.sha256(i.encode()).hexdigest(), now, reason) for i in ids],
            )
        report = ErasureReport(user_id=user_id, reason=reason, t=now, deleted_ids=ids, kinds=dict(kinds),
                               sessions=sessions, terms=terms)
        if regenerate and kinds.get(Kind.SUMMARY.value):
            summ = regenerate if not isinstance(regenerate, bool) else None
            for s in sorted(sessions):
                new = self.consolidate(s, summ)
                if new is not None:
                    report.regenerated.append(new.id)
        for hook in list(self.erasure_hooks):
            try:
                hook(report)
            except Exception as e:  # a failing cache hook must not undo the erasure
                report.hook_errors.append(f"{getattr(hook, '__name__', hook)}: {e!r}")
        return report

    def verify_erased(self, term: str, user_id: str, *, raw_file: bool = False) -> list[str]:
        """Search every table for residue of ``term`` belonging to ``user_id``; returns hits
        (must be empty after :meth:`forget`). ``raw_file`` additionally greps the DB file
        bytes (only meaningful if no other user legitimately stores the term)."""
        priv = private_scope(user_id)
        hits: list[str] = []
        like = [term, term, term, term, term]
        for r in self.db.execute(
            f"SELECT r.id FROM records r WHERE {self._user_records_sql()} AND ("
            " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0"
            " OR instr(lower(coalesce(r.subject, '')), lower(?)) > 0 OR instr(lower(r.provenance), lower(?)) > 0"
            " OR instr(lower(r.meta), lower(?)) > 0)", [user_id, priv, *like]):
            hits.append(f"records:{r[0]}")
        for r in self.db.execute("SELECT rowid FROM tombstones WHERE instr(lower(reason), lower(?)) > 0", [term]):
            hits.append(f"tombstones:{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM embeddings WHERE record_id NOT IN (SELECT id FROM records)"):
            hits.append(f"embeddings(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM record_scopes WHERE record_id NOT IN (SELECT id FROM records)"):
            hits.append(f"record_scopes(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT child_id, parent_id FROM derivations WHERE child_id NOT IN (SELECT id FROM records)"
                " OR parent_id NOT IN (SELECT id FROM records)"):
            hits.append(f"derivations(orphan):{r[0]}->{r[1]}")
        if raw_file and self.path != ":memory:":
            needle = term.encode("utf-8")
            for p in (Path(self.path), Path(self.path + "-journal"), Path(self.path + "-wal")):
                if p.exists() and needle in p.read_bytes():
                    hits.append(f"file:{p.name}")
        return hits


def _norm(v: str | None) -> str:
    return "".join((v or "").lower().split()).strip("。.!！'\"")

===== FILE: live_agent/memory_bridge.py =====
"""Adapter from live_agent.memory.MemoryStore to the orchestrator's MemoryPort."""

from __future__ import annotations

from collections.abc import Callable

from live_agent.memory.store import ErasureReport, MemoryStore
from live_agent.types import Utterance


class MemoryBridge:
    def __init__(self, db_path: str, *, user_id: str, stream_id: str, session_id: str,
                 store: MemoryStore | None = None):
        self.store = store or MemoryStore(db_path)
        self.user_id = user_id
        self.stream_id = stream_id
        self.session_id = session_id
        self.on_erasure: list[Callable[[ErasureReport], None]] = []
        self.store.erasure_hooks.append(self._erasure_hook)

    def _scope(self, mode: str) -> str:
        return f"private:{self.user_id}" if mode == "private" else f"public:{self.stream_id}"

    def recall(self, text: str, *, mode: str) -> list[str]:
        res = self.store.retrieve(text, mode, user_id=self.user_id if mode == "private" else None,
                                  stream_id=self.stream_id, k=6)
        out = []
        for h in res.hits:
            t = h.tags
            out.append(f"[{t.get('kind')}/{t.get('claim_type')}/{t.get('status', 'active')}] {h.record.text}")
        return out

    def on_user_utterance(self, utt: Utterance) -> None:
        self.store.ingest_user_utterance(utt, user_id=self.user_id, stream_id=self.stream_id)

    def on_persona_line(self, text: str, *, session_id: str, scope: str) -> None:
        self.store.record_generated_event(text, session_id, self._scope(scope), user_id=self.user_id)

    def forget(self, term: str) -> ErasureReport:
        return self.store.forget(term, self.user_id, reason="user_request")

    def _erasure_hook(self, report: ErasureReport) -> None:
        for cb in self.on_erasure:
            cb(report)
