You are the independent reviewer (Codex, GPT-6 Sol) for the live-agent project, Phase 2 checkpoint "impl1":
the **implementation of the A2 control path** against the Chinese proposal `docs/research_proposal_zh.md` v2.11
(inlined), plus the TaoMate-H3 generator adapter and its local measurements.

Review goals, in priority order:
1. **Correctness bugs** in the control path: the single timeline (lock → teacher → student → presented),
   just-in-time locking (P_{k+1} = V_k + R − Λ − σ), KV/order constraints, barge-in and erasure (drop unpresented,
   bridging, generator reset), deadlocks and races in the asyncio orchestration, QC → repair → earliest correctable
   request, "done" spoken only after verification, capability gating (emit/degrade/refuse), prompt compilation.
2. **Fidelity to the proposal:** anything the proposal specifies as mandatory for A2 that is missing, or behaves
   differently, or places where the implementation would make a later E2 result invalid (confounds between A1 and A2,
   leakage between the online judge and the primary outcome, mis-timed events).
3. **Adapter** (`taomate_h3.py`, `SessionView`): session isolation, request numbering, stale chunks, error paths,
   resource leaks on shutdown or cancellation.
4. **Honesty of claims** in `docs/implementation.md` and `docs/m0_measurements.md`: is each claim supported by the
   code and the numbers described, are the number labels right, and is anything overstated?

Output format: a numbered list of findings. For each: severity (blocking / major / minor), file and line or function,
the concrete failure scenario, and the fix. Then a one-line verdict: "ready for E1/E2 pilot", "ready after fixes",
or "not ready". Do not praise; do not restate the code. If you find nothing in a category, say so briefly.

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

===== FILE: docs/m0_measurements.md =====
# M0 measurements: TaoMate-H3 on the local GPUs (2026-09-26)

Status: first local measurements (Phase 2, D-019). Every number in this file is **[measured
locally]** unless it carries another label. Raw data (events, logs, JSON, MP4s) is under
`.cache/m0/` (git-ignored). Scripts are in `scripts/m0/`.

## Setup

| Item | Value |
|---|---|
| Date | 2026-09-26, 05:00-05:55 CST |
| Hardware | GPUs reported by torch as compute capability (9, 0), 139.8 GiB, 132 SMs (nvidia-smi name "NVIDIA L20X"). So they are Hopper/SM90 and the FA3 path runs natively; no FA2/SDPA port (T4) was needed. Driver 570.133.20 |
| GPUs used | canhazgpu IDs 0,1,2,3 (4-GPU runs) and 0-5 (one 6-GPU run). GPU 6 was reserved by the lead for helper models and GPU 7 was held by another user's process, so **no 8-GPU run was possible** |
| TaoMate-H3 | `external/TaoMate-H3` at `6b2f9984acf681e2f387188f5d1f3b26e504315b` (read-only, unmodified; integrated by import, subclassing and runtime wrapping) |
| LoRA | HF `TaoLiveAIGC/TaoMate-H3` sha `7d7a51f3e63972138882ec2f0e4d1d47728110cf` (rank 128, step-3000 EMA) in `.cache/models/TaoMate-H3` |
| Base weights | shared `/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe` (= `refs/main`), read-only. FL2VA complete: 13 transformer shards (62 GB), text_encoder (63 GB), video_vae (9.8 GB), audio_vae (0.6 GB). Four other snapshots also carry a complete FL2VA |
| Environment | `.venvs/taomate-h3` (`scripts/m0/setup_env.sh`): Python 3.11.15, torch 2.9.0+cu128 (vllm 0.11.1 pins it; the README says torch 2.8), vllm 0.11.1, triton 3.5.0, diffusers 0.35.2, transformers 4.57.6 |
| FA3 | Prebuilt Hopper FA3 from HF `kernels-community/flash-attn3` rev `7cb368cf` (kernel `8a730d9`, `torch-stable-abi29-cu128`), exposed as `flash_attn_interface` by a shim. Only a CUDA 13 toolkit exists on the host, so the README's source build of `flash-attention/hopper` was not attempted. A smoke test against SDPA gave max abs diff 0.002 (bf16) |
| ffmpeg | `/usr/local/bin/ffmpeg` has no libx264, which the released CLI rejects. `/usr/bin/ffmpeg` 4.4.2 has it and is used through a PATH shim |
| Canvas / length | 480x864 (portrait, the README benchmark canvas), 10 s (2 requests) for the released path, and 8 requests (39.7 s native) for streaming |

Live-agent HEAD moved during the session because others were committing (`987de17` to `3cd2de1`). The new files in this work are uncommitted.

## Problems hit and fixes (all in our code; the clone is untouched)

1. **ffmpeg without libx264.** `cli._validate_media_tools` failed. Fix: use `/usr/bin/ffmpeg`.
2. **Triton cache race.** On the first 4-GPU worker run, `OSError: [Errno 116] Stale file handle` came from
   `triton/compiler/compiler.py` (4 ranks sharing `~/.triton` on CPFS). Fix: a per-role, per-rank
   `TRITON_CACHE_DIR` under `.cache/triton/`.
3. **Spinning NCCL waits slowed the colocated student about 2.5×.** In the first streaming run, idle ranks waited for
   commands in `broadcast_object_list` on NCCL. A waiting NCCL kernel occupies SMs, so the colocated
   teacher's idle ranks slowed every student chunk. Chunk denoise took 1.1 s instead of 0.44 s, and a request took 9.6 s.
   Fix: send control traffic over a gloo (CPU) group. The next run gave 5.05 s/request.
4. **Chunk transport.** Pickling about 42 MB of frames per chunk through the socket took 0.27 s per chunk and
   competed for the GIL with the rank-0 launch thread. Fix: hand frames over through `/dev/shm` (0.017 s) and make them
   contiguous before saving. The request time fell to 4.0-4.4 s.

## 1. Released path, component profile (4 GPUs, TP2 × Ulysses2)

Command (3 repetitions in one reservation):

```bash
gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "live-agent M0: TaoMate-H3 released baseline 4GPU 480p 10s x3" -- \
  bash scripts/m0/run_baseline_reps.sh r4_480p 3
python3 scripts/m0/summarize_released.py .cache/m0/runs/r4_480p_rep*
```

`profile_released.py` runs the same two torchrun stages as `python -m taomate_h3` (cli.py:219-229),
with `examples/prompts_10s.json` and seed 8301. It adds synchronized timestamp hooks through
`profile_entry.py`. rep1 is the first run in fresh Triton caches, so it includes JIT compilation.

| Component | rep1 | rep2 | rep3 | Note |
|---|---|---|---|---|
| Teacher process, spawn → exit (s) | 75.7 | 74.5 | 77.5 | whole stage 1 |
| Teacher model load: text encoder + BF16 DiT (s) | 36.3 | 36.3 | 38.9 | one-time |
| Teacher text encode, request 0 / 1 (s) | 5.25 / 0.060 | 3.63 / 0.058 | 2.97 / 0.059 | request 0 includes warm-up |
| Teacher text-encoder offload to CPU (s) | 13.4 | 12.2 | 10.9 | removed in the streaming adapter |
| **Audio teacher, request 0 / 1 (s)** (10-state, 9 forwards) | 2.80 / **0.653** | 4.07 / **0.684** | 6.51 / **0.677** | |
| Student process, spawn → exit (s) | 154.8 | 136.3 | 139.1 | whole stage 2 |
| Student model load + LoRA + acceleration (s) | 47.0 | 50.8 | 49.5 | of which LoRA 0.8-1.3 |
| Student text encode, request 0 / 1 (s) | 1.72 / 0.057 | 0.77 / 0.061 | 1.69 / 0.060 | |
| Student text offload (s) | 12.7 | 12.4 | 13.6 | |
| **Student request 0 / 1, 4 chunks (s)** | 12.71 / **2.49** | 7.45 / **2.96** | 8.10 / **2.50** | request 0 = cold (JIT, allocator) |
| First final chunk latent (from request start) (s) | 10.12 | 4.78 | 5.45 | README, 8×H20: 6.148 s [cited] |
| Pure DiT CUDA time, 24 noisy + 8 clean forwards (s) | 10.26 | 6.82 | 7.12 | README, 8×H20: 14.81 s [cited] |
| VAE load and setup before the first decode (s) | 45.1 | 33.1 | 33.6 | one-time |
| Video VAE decode, 243 frames, one-shot (wall / CUDA-active s) | 9.36 / 4.90 | 6.42 / 2.55 | 6.04 / 2.42 | temporal-window DP |
| H.264 encode, video only (s) | 1.72 | 1.84 | 1.83 | |
| Audio VAE decode, 10 s (s) | 2.19 | 1.87 | 3.10 | includes the host→GPU move |
| AAC mux (s) / strict validate (s) | 1.23 / 1.93 | 1.26 / 2.07 | 1.19 / 2.03 | |
| Peak allocated per GPU: student / its DiT interval (GiB) | 42.4 / 36.6 | same | same | README DiT peak: 31.37 GiB [cited] |
| Peak allocated per GPU, teacher (GiB) | 55.3 | 55.3 | 55.3 | |
| nvidia-smi peak used per GPU (GiB) | 57.1 | 57.1 | 57.1 | all 4 GPUs |

Per-chunk timing in the warm request 1 (mean of 3 runs):
- Denoise, 3 noisy forwards: 0.44 s for a 10-latent chunk and 0.34 s for the 5-latent chunk.
- Clean-KV commit: usually 0.15-0.19 s, with occasional outliers of 0.64-0.87 s.

Across the 3 runs, the released video latents of the same seed are **not reproducible**: relative L2 difference 0.31-0.37 between runs. Teacher milestones do not have this problem.

## 2. Streaming adapter (T1 + T2 + T3), 8 mid-session requests

Command:

```bash
gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "live-agent M0: ..." -- \
  .venvs/taomate-h3/bin/python scripts/m0/validate_streaming.py --tag s4_coloc_v3 --colocate --student-devices 0,1,2,3
gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "..." -- bash scripts/m0/run_stream_reps.sh   # rep2, rep3, sequential
gpu run --gpu-ids 0,1,2,3,4,5 --timeout 1h --note "..." -- .venvs/taomate-h3/bin/python \
  scripts/m0/validate_streaming.py --tag s6_dedicated --student-devices 0,1,2,3 --teacher-devices 4,5
python3 scripts/m0/summarize_streaming.py .cache/m0/stream/<runs>
```

**Workload.** 8 different prompts (`scripts/m0/prompts_session_40s.json`: same presenter, a new action and line each
time), submitted one at a time.

**Warm-up.** One throw-away request runs before the session, followed by `reset()`.

**Lock policy.**
- Requests 1-5 are pipelined: request k+1 is locked when request k's first chunk arrives.
- Requests 6-7 are idle: each is locked 0.5 s after the previous request finishes, which measures Λ_idle.

**Topology.**
- Colocated: the teacher is a second torchrun group on the student's 4 GPUs (TP2×U2).
- Dedicated: the teacher runs on GPUs 4-5 with TP2 × Ulysses 1. This was not a validated upstream topology, but it ran.

| Run | Teacher | Teacher s/req | Student s/req, pipelined 1-5 (mean / max) | Period s/req | Lock→first chunk, pipelined (s) | **Λ_idle** (lock→first chunk) (s) | Student start→first chunk (s) | Idle chunk denoise / decode / transport (s) | Min startup buffer, no stall (s) |
|---|---|---|---|---|---|---|---|---|---|
| s4_coloc_v1 (NCCL waits, pickled frames) | colocated, lookahead | 2.06 | 9.62 / 10.42 | 9.62 | 9.87 | 4.03, 5.09 | 2.34 | 1.11 / 0.51 / 0.277 | 39.8 |
| s4_coloc_v2 (gloo control) | colocated, lookahead | 1.22 | 5.05 / 5.57 | 5.06 | 5.42 | 1.85, 1.80 | 1.10 | 0.42 / 0.25 / 0.265 | 3.56 |
| **s4_coloc_v3** (+ /dev/shm) | colocated, lookahead | 1.21 | **4.22 / 4.55** | 4.10* | 4.38 | **1.54, 1.56** | 0.82 | 0.41 / 0.26 / 0.018 | 0.69 |
| s4_coloc_rep2 | colocated, lookahead | 1.25 | 4.41 / 4.98 | 4.35* | 4.54 | 1.53, 1.51 | 0.79 | 0.42 / 0.24 / 0.017 | 0.03 |
| s4_coloc_rep3 | colocated, lookahead | 1.12 | 4.03 / 4.39 | 3.80* | 4.13 | 1.55, 1.54 | 0.79 | 0.41 / 0.24 / 0.016 | 0.57 |
| s4_coloc_seq | colocated, **sequential** | 0.73 | 3.56 / 3.84 | 4.31* | 4.47 | 1.51, 1.51 | 0.80 | 0.42 / 0.24 / 0.015 | 0.19 |
| **s6_dedicated** | GPUs 4-5, lookahead | 0.69 | **3.55 / 3.82** | **3.55** | 3.62 | **1.53, 1.50** | 0.82 | 0.42 / 0.26 / 0.017 | **0.00** |

`*` marks a period reconstructed from lock policy and per-request deltas; ±0.1 s [estimate]. The s6 run has exact absolute timestamps.

**Definitions.**
- **Period.** The mean time between completions of pipelined requests, teacher included. Real time needs a period below 119/24 = **4.958 s**, the native media per request. Frames are native 24 fps without the released 124+119n→120n time warp.
- **Min startup buffer.** The smallest playback delay after the first chunk that avoids any stall, given where each chunk sits on the playback timeline.

**Common to all runs.**
- Chunks: 34/34/34/17 frames per request.
- `audio == teacher`: True in every request. This is the runtime's own check `torch.equal(published audio, teacher clean latent)` (streaming/runtime.py:739-743).
- Streamed audio compared with a one-shot audio VAE decode of the same latents: SNR 62-63 dB, max abs diff ≤ 0.007.
- Frames emitted: 952, plus 5 held back until `flush()`.
- Startup cost:
  - Processes → both ready: 128-141 s. Student load 95-102 s, with the VAE on the GPU; teacher load 37-39 s.
  - Warm-up request: 16-19 s after the first run (31 s in v1).
- Memory: student peak 51.1 GiB per GPU, including the resident video VAE; teacher 55.2 GiB per GPU. Colocated this is about 106 GiB of 139.8 GiB.
- Sample MP4s:
  - `.cache/m0/stream/s4_coloc_v3-20260926T053444/session.mp4`
  - `.cache/m0/stream/s6_dedicated-20260926T054734/session.mp4`
  - Both are 39.67 s, 480x864 h264 + AAC 32 kHz. A frame check shows a consistent presenter, with the prompted actions such as a raised palm and a wave visible.

**Composition of Λ_idle ≈ 1.5 s.**
- Teacher: text 0.06 s + audio teacher 0.63 s ≈ 0.70 s.
- Dispatch: < 0.03 s.
- Student chunk 0: denoise 0.44 s + VAE decode 0.28 s + transport 0.02 s + branch build about 0.08 s ≈ 0.82 s.

**Parity with the released path** (`scripts/m0/parity_check.py`, prompts_10s, same seed):
- Teacher milestones (states 3/6/9) and the student's published audio latents are **bitwise identical** to the released run for both requests.
- Video latents differ with relative L2 0.39-0.42. This is in the same range as the run-to-run variation of the released path itself (0.31-0.37). So there is no bitwise video parity, and no evidence of a systematic deviation.

## 3. What this decides (proposal §6.4 / §11)

- **Generator throughput is real time at 480p on 4 local Hopper GPUs** with the streaming adapter.
  - With a dedicated 2-GPU teacher: period 3.55 s against 4.958 s of media, about 1.40× real time, and no startup buffer needed.
  - Colocated on the same 4 GPUs: period 3.8-4.35 s (about 1.14-1.30×). The worst single request was 4.98 s (rep2), so the colocated margin is thin.
- **Teacher lookahead (T2).**
  - Dedicated GPUs: the lookahead hides the teacher completely (period = student time).
  - Colocated: lookahead overlaps the teacher with the student's chunk 1. That chunk's denoise rises from 0.44 s to about 1.0-1.3 s, so the gain over the sequential teacher is small (period 3.8-4.35 s vs 4.31 s).
- **Λ_idle (lock → first chunk ready at the adapter) ≈ 1.5 s** in every warm configuration. Under pipelined just-in-time locking, lock → first chunk is 3.6-4.5 s, because request k+1 waits for request k to finish (KV dependency).
- **Scope of the claim.** These results qualify only the *generator + adapter* part of M1. They do not cover:
  - a client playback path, where σ and jitter are unmeasured;
  - 30-minute soak tests;
  - GPU contention from the LLM/ASR/VLM services;
  - 768p or 1080p.
- **Comparison with the README.** The README's H20 numbers (DiT 14.8 s per 10 s) [cited] are about 2× slower than local runs. The earlier proposal inference "not real time" [estimate, based on H20] does not hold for this hardware.

## 4. Open gaps

- No 8-GPU run: GPUs 6 and 7 were unavailable. The 4-vs-8 comparison is open.
- No repetition at 768p or 1080p, and no 60 s run on the released path. The audio-KV reset every 12 requests (60 s) has not been exercised in streaming (8 requests max).
- The released path's video latents are not deterministic for a fixed seed (cause not investigated; candidates are FA3/NCCL/atomic nondeterminism amplified by the 3-step sampler). This limits exact parity testing.
- Request 0 of a process costs 7-13 s without warm-up. The adapter's `warmup_prompt` hides this behind start-up.
- Colocated chunk-1 contention (teacher k+1 overlapping student k) is the main source of variance. A dedicated teacher or a lower-priority CUDA stream for the teacher are the options.
- fMP4 per-chunk encoding (`Chunk.encoded`) is not implemented. Chunks carry raw uint8 frames and float32 audio.
- VAE windows: each chunk emits exactly its own 34/34/34/17 final frames (VAE windows [5i, 5i+7) complete inside each chunk). Only the 5-frame blend tail of the newest window is held, and it is emitted by `flush()` at session end. At the last chunk of a request, the audio decode has only about 8 latents (0.2 s) of right context. The 62-63 dB SNR against the one-shot decode includes this effect.

===== FILE: live_agent/types.py =====
"""Core data types shared by every component.

The names follow docs/research_proposal_zh.md (v2.11): a *request* is one 5-second
TaoMate-H3 generation unit (4 chunks); a *BlockScript* is our internal description of
one request; an *intent chain* is the scoring unit for instruction following.
All times are monotonic seconds on the shared presentation timeline unless noted.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def now() -> float:
    return time.monotonic()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------- persona


@dataclass(frozen=True)
class CanonProfile:
    """Persona canon: fields repeated verbatim in every request; never rewritten by an LLM."""

    persona_id: str
    subject: str  # e.g. "a young East Asian woman (S1) in a green hanfu, ..."
    scene: str
    camera: str
    voice: str
    language: str = "Chinese"  # tag inside <d>[...]</d>
    speech_language: str = "Mandarin"  # used in the soundscape description
    negative: str = (
        "No other person or human voice appears. "
        "No captions or readable text appear anywhere in frame."
    )


# --------------------------------------------------------------------------- scripts


@dataclass
class CheckQuestion:
    """A verifiable yes/no question generated at compile time (online VQQA)."""

    qid: str
    text: str
    kind: str = "action"  # action | speech | identity | scene
    deadline_s: float = 15.0


@dataclass
class BlockScript:
    """Internal description of one 5-second request (see proposal §9)."""

    request_index: int
    plan_version: int
    canon: CanonProfile
    action: str  # must match a capability-manifest entry (or "" for idle)
    transcript: str  # spoken line; "" for silence
    soundscape: str = "Quiet room tone."
    corrections: list[str] = field(default_factory=list)  # forward corrections / textual drift fixes
    checks: list[CheckQuestion] = field(default_factory=list)
    chain_ids: list[str] = field(default_factory=list)  # intent chains this request serves
    provenance: dict[str, Any] = field(default_factory=dict)
    capability_ids: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- instructions


class ChainStatus(str, enum.Enum):
    OPEN = "open"
    COMPLIED = "complied"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"  # user withdrew: excluded from the primary denominator
    CAPACITY_SKIPPED = "capacity_skipped"  # dropped by admission control: counts as failure
    REFUSED = "refused"  # compiler refused / degraded: counts as failure


class TaskKind(str, enum.Enum):
    ACTION = "action"
    CONTENT = "content"
    MULTISTEP = "multistep"
    CORRECTION = "correction"
    MEMORY = "memory"
    CHAT = "chat"


@dataclass
class Utterance:
    uid: str
    speaker: str  # "user" | "persona" | "viewer:<id>"
    text: str
    t_end: float  # VAD endpoint on the shared timeline
    session_id: str = ""
    scope: str = "private"


@dataclass
class IntentChain:
    """Scoring unit: one instruction plus the user's later revisions (proposal §14.3)."""

    chain_id: str
    kind: TaskKind
    opened_by: str  # utterance id
    final_intent: str
    clock_origin: float  # end of the opening or latest revising utterance
    revisions: list[str] = field(default_factory=list)
    status: ChainStatus = ChainStatus.OPEN
    steps: list[str] = field(default_factory=list)  # for multistep
    step_index: int = 0
    first_compliant_t: float | None = None
    requests: list[int] = field(default_factory=list)


# --------------------------------------------------------------------------- timeline


class EventType(str, enum.Enum):
    UTTERANCE_END = "utterance_end"
    LOCK = "lock"  # P_k: script frozen
    TEACHER_START = "teacher_start"
    TEACHER_DONE = "teacher_done"
    STUDENT_START = "student_start"
    CHUNK_READY = "chunk_ready"
    CHUNK_PRESENTED = "chunk_presented"  # client presentation ack (start of chunk)
    CHUNK_PRESENTED_END = "chunk_presented_end"
    REQUEST_DONE = "request_done"
    VERDICT = "verdict"
    INTERRUPT = "interrupt"
    PLAYBACK_STOP = "playback_stop"
    COMPLETION_CLAIM = "completion_claim"
    REFUSAL = "refusal"
    CAPACITY_SKIP = "capacity_skip"
    REPAIR = "repair"
    SPEECH_ONSET = "speech_onset"


@dataclass
class TimelineEvent:
    type: EventType
    t: float
    request_index: int | None = None
    chunk_index: int | None = None
    data: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- generation


@dataclass
class Chunk:
    """One generated chunk (audio+video) of a request."""

    request_index: int
    chunk_index: int  # 0..3 within the request
    n_frames: int
    fps: float
    video: Any = None  # np.ndarray [T,H,W,3] uint8, or None for mock
    audio: Any = None  # np.ndarray [S, C] float32
    sample_rate: int = 32000
    encoded: bytes | None = None  # fMP4 fragment, if the generator encodes
    t_ready: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)  # e.g. prompt, session id

    @property
    def duration_s(self) -> float:
        return self.n_frames / self.fps


# --------------------------------------------------------------------------- QC


class VerdictLabel(str, enum.Enum):
    COMPLIED = "complied"
    NOT_COMPLIED = "not_complied"
    UNKNOWN = "unknown"


@dataclass
class Verdict:
    qid: str
    request_index: int
    label: VerdictLabel
    confidence: float
    rationale: str = ""
    t_evidence: float = 0.0  # E: presentation time of the last frame needed
    t_verdict: float = 0.0

===== FILE: live_agent/prompt/h3_compiler.py =====
"""Compile a BlockScript into the one-string-per-request prompt TaoMate-H3 accepts.

Format follows the official examples (external/TaoMate-H3/examples/prompts_60s.json):

    integrated_multimodal_description: [Shot 1] <style>, one uninterrupted five-second shot.
    The same <subject> ... <scene> remain unchanged. <camera> remain constant. <voice>.
    <action>, then says once: <d>[Chinese] <line></d> Her lips close. <negative>

    overall_soundscape: <soundscape>

    non_diegetic_music: N/A

The canon fields are copied verbatim (never paraphrased) so that every request restates
the persona identically -- this is the state-ledger convention of proposal §9.
"""

from __future__ import annotations

import re

from live_agent.types import BlockScript

STYLE = "Live-action portrait livestream"

# Characters that would break the <d>...</d> dialogue tag or the section headers.
_FORBIDDEN = re.compile(r"</?d>|integrated_multimodal_description:|overall_soundscape:|non_diegetic_music:", re.I)


class PromptError(ValueError):
    pass


def _clean(text: str, *, field: str, max_len: int = 400) -> str:
    text = " ".join(text.split())
    if _FORBIDDEN.search(text):
        raise PromptError(f"{field} contains a reserved prompt token")
    if len(text) > max_len:
        raise PromptError(f"{field} too long ({len(text)} > {max_len})")
    return text


def _sentence(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?。！？":
        text += "."
    return text


def compile_prompt(script: BlockScript, *, first_request: bool = False) -> str:
    """Return the TaoMate-H3 prompt string for one 5-second request."""
    c = script.canon
    subject = _clean(c.subject, field="subject")
    scene = _clean(c.scene, field="scene")
    camera = _clean(c.camera, field="camera")
    voice = _clean(c.voice, field="voice")
    action = _clean(script.action, field="action", max_len=300) if script.action else ""
    line = _clean(script.transcript, field="transcript", max_len=120) if script.transcript else ""

    same = "" if first_request else "The same "
    parts: list[str] = [f"[Shot 1] {STYLE}, one uninterrupted five-second shot."]
    if first_request:
        parts.append(_sentence(f"{subject[0].upper()}{subject[1:]} is in {scene}"))
    else:
        parts.append(_sentence(f"{same}{subject} stays in the same setting; {scene} remain unchanged"))
    parts.append(_sentence(f"{camera}, all remaining constant"))
    parts.append(_sentence(voice))
    for fix in script.corrections:
        parts.append(_sentence(_clean(fix, field="correction", max_len=200)))

    if action and line:
        parts.append(f"{_sentence(action)[:-1]}, then says once: <d>[{c.language}] {line}</d> Her lips close.")
    elif line:
        parts.append(f"S1 looks into the lens and says once: <d>[{c.language}] {line}</d> Her lips close.")
    elif action:
        parts.append(_sentence(action) + " She does not speak.")
    else:
        parts.append("S1 continues quietly with small natural movements and does not speak.")
    parts.append(_sentence(c.negative))

    description = " ".join(parts)
    soundscape = _sentence(_clean(script.soundscape, field="soundscape", max_len=200))
    if line:
        soundscape = f"Clear dry {c.speech_language} speech, {soundscape[0].lower()}{soundscape[1:]}"
    return (
        f"integrated_multimodal_description: {description}\n\n"
        f"overall_soundscape: {soundscape}\n\n"
        f"non_diegetic_music: N/A"
    )


def extract_dialogue(prompt: str) -> str:
    """Return the spoken line inside <d>[...] ...</d> (for ASR fidelity checks)."""
    m = re.search(r"<d>\[[^\]]*\]\s*(.*?)</d>", prompt, re.S)
    return m.group(1).strip() if m else ""

===== FILE: live_agent/capability.py =====
"""Capability manifest: what the generator is *measured* to render reliably (proposal §8, §14.2).

Each entry maps an intent (e.g. "drink_tea") to the exact English action phrase that
goes into the H3 prompt, plus calibrated statistics from experiment E1. The compiler
only emits entries whose status is at least ``executed`` and whose success rate is
above threshold; everything else is degraded (e.g. to a verbal reply) or refused.
Refusals and degradations are logged and count as failures in scoring.
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


class Status(str, enum.Enum):
    DOCUMENTED = "documented"
    CODE_READ = "code_read"
    EXECUTED = "executed"  # rendered at least once in M0/M1
    CALIBRATED = "calibrated"  # E1 statistics available

    @property
    def rank(self) -> int:
        return ["documented", "code_read", "executed", "calibrated"].index(self.value)


@dataclass
class Capability:
    cap_id: str
    intent: str  # canonical intent key, e.g. "drink_tea"
    phrase: str  # exact action phrase used in the prompt
    aliases: list[str] = field(default_factory=list)  # user-language triggers (中文/English)
    status: Status = Status.DOCUMENTED
    p_success: float | None = None  # E1: fraction judged compliant within deadline
    p_ci: tuple[float, float] | None = None
    tvc_median_s: float | None = None
    side_effects: list[str] = field(default_factory=list)
    check_question: str = ""  # default QC question for this action
    degrade_to: str = ""  # verbal fallback line when refused/degraded

    def usable(self, min_status: Status, min_p: float) -> bool:
        if self.status.rank < min_status.rank:
            return False
        if self.status == Status.CALIBRATED and (self.p_success or 0.0) < min_p:
            return False
        if self.p_success is not None and self.p_success < min_p:  # measured (e.g. judge-only E1) below threshold
            return False
        return True


class Decision(str, enum.Enum):
    EMIT = "emit"
    DEGRADE = "degrade"
    REFUSE = "refuse"


@dataclass
class CompileResult:
    decision: Decision
    capability: Capability | None
    reason: str


class CapabilityManifest:
    def __init__(self, caps: list[Capability], *, min_status: Status = Status.EXECUTED, min_p: float = 0.6):
        self.caps = {c.cap_id: c for c in caps}
        self.min_status = min_status
        self.min_p = min_p

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: str | Path, **kw) -> CapabilityManifest:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        caps = []
        for d in data["capabilities"]:
            d = dict(d)
            d["status"] = Status(d.get("status", "documented"))
            if d.get("p_ci") is not None:
                d["p_ci"] = tuple(d["p_ci"])
            caps.append(Capability(**d))
        return cls(caps, min_status=Status(data.get("min_status", kw.get("min_status", "executed"))),
                   min_p=data.get("min_p", kw.get("min_p", 0.6)))

    def save(self, path: str | Path) -> None:
        out = {
            "min_status": self.min_status.value,
            "min_p": self.min_p,
            "capabilities": [
                {**asdict(c), "status": c.status.value} for c in self.caps.values()
            ],
        }
        Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ lookup
    def match(self, text: str) -> Capability | None:
        """Find the capability whose intent or alias occurs in ``text`` (longest alias wins)."""
        best: tuple[int, Capability] | None = None
        low = text.lower()
        for c in self.caps.values():
            for a in [c.intent, *c.aliases]:
                if a and a.lower() in low and (best is None or len(a) > best[0]):
                    best = (len(a), c)
        return best[1] if best else None

    def by_intent(self, intent: str) -> Capability | None:
        for c in self.caps.values():
            if c.intent == intent:
                return c
        return None

    def decide(self, intent: str) -> CompileResult:
        cap = self.by_intent(intent)
        if cap is None:
            return CompileResult(Decision.REFUSE, None, f"no capability for intent {intent!r}")
        if cap.usable(self.min_status, self.min_p):
            return CompileResult(Decision.EMIT, cap, "ok")
        if cap.degrade_to:
            return CompileResult(Decision.DEGRADE, cap, f"status={cap.status.value} p={cap.p_success}")
        return CompileResult(Decision.REFUSE, cap, f"status={cap.status.value} p={cap.p_success}")

    def update_from_calibration(self, cap_id: str, *, successes: int, trials: int,
                                ci: tuple[float, float], tvc_median_s: float | None,
                                validated: bool = False) -> None:
        """Record an E1 estimate. Only human-validated labels (judge agreement checked on the 20%
        sample) make a capability ``calibrated``; a judge-only pass marks it ``executed``."""
        c = self.caps[cap_id]
        c.status = Status.CALIBRATED if validated else Status.EXECUTED
        c.p_success = successes / trials if trials else 0.0
        c.p_ci = ci
        c.tvc_median_s = tvc_median_s

===== FILE: live_agent/ledger.py =====
"""State ledger: online CANVAS + A²RD continuity layer (proposal §8.2 layer 3, §10.4).

The ledger keeps
- the immutable canon (persona appearance, scene, camera, voice) -- never overwritten;
- the *current* state that may legitimately change (props and who holds them, pose,
  whether the book is open, what was last done/said) -- updated only from events that
  were *presented* (and, for claimed completions, verified);
- per-request textual state (A²RD style) for audit and for composing the next request.

It produces the canon block for each BlockScript and the textual drift corrections
("the hairpin is jade, not gold") used by the text-correction intervention.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from live_agent.types import CanonProfile


@dataclass
class PropState:
    name: str
    location: str  # e.g. "on the desk"
    carrier: str | None = None  # "S1" when held


@dataclass
class RequestState:
    request_index: int
    action: str
    transcript: str
    presented: bool = False
    verified: dict[str, str] = field(default_factory=dict)  # qid -> verdict label
    identity_score: float | None = None
    notes: str = ""


class StateLedger:
    def __init__(self, canon: CanonProfile, props: list[PropState] | None = None):
        self._canon = canon
        self.props: dict[str, PropState] = {p.name: p for p in (props or [])}
        self.pose: str = "seated at the desk"
        self.history: list[RequestState] = []
        self.generated_not_presented: list[int] = []  # requests generated but never shown

    # ---------------------------------------------------------------- canon
    @property
    def canon(self) -> CanonProfile:
        return self._canon  # frozen dataclass: cannot be mutated

    @classmethod
    def from_config(cls, path: str | Path) -> StateLedger:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        canon = CanonProfile(
            persona_id=d["persona_id"], subject=d["subject"], scene=d["scene"],
            camera=d["camera"], voice=d["voice"], language=d.get("language", "Chinese"),
            speech_language=d.get("speech_language", "Mandarin"),
            negative=d.get("negative", CanonProfile.__dataclass_fields__["negative"].default),
        )
        props = [PropState("book", "open on the desk"), PropState("teacup", "on the desk"),
                 PropState("teapot", "on the desk")]
        return cls(canon, props)

    # ---------------------------------------------------------------- updates
    def record_request(self, request_index: int, action: str, transcript: str) -> None:
        self.history.append(RequestState(request_index, action, transcript))

    def mark_presented(self, request_index: int) -> None:
        for r in self.history:
            if r.request_index == request_index:
                r.presented = True
        if request_index in self.generated_not_presented:
            self.generated_not_presented.remove(request_index)

    def mark_generated_not_presented(self, request_index: int) -> None:
        """Interrupt case (proposal §10.5, option 3): content exists in generator state but was not shown."""
        if request_index not in self.generated_not_presented:
            self.generated_not_presented.append(request_index)

    def apply_verified_action(self, intent: str) -> None:
        """Update prop/pose state after an action was *verified* on presented frames."""
        if intent == "stand_up":
            self.pose = "standing beside the desk"
        elif intent in ("put_down_book",):
            self.props.setdefault("book", PropState("book", "on the desk")).location = "closed on the desk"
            self.props["book"].carrier = None
        elif intent == "pick_up_book":
            self.props.setdefault("book", PropState("book", "")).carrier = "S1"
            self.props["book"].location = "held open in her hands"
        elif intent == "drink_tea":
            self.props.setdefault("teacup", PropState("teacup", "on the desk")).location = "on the desk"

    def record_verdict(self, request_index: int, qid: str, label: str) -> None:
        for r in self.history:
            if r.request_index == request_index:
                r.verified[qid] = label

    # ---------------------------------------------------------------- prompt helpers
    def continuity_sentence(self) -> str:
        """Current (non-canon) state restated each request, e.g. pose and held props."""
        held = [p.name for p in self.props.values() if p.carrier == "S1"]
        parts = [f"S1 is {self.pose}"]
        if held:
            parts.append("holding the " + " and the ".join(held))
        return ", ".join(parts)

    def bridging_note(self) -> str | None:
        """If generated-but-unshown content exists, return an explicit bridging instruction."""
        if not self.generated_not_presented:
            return None
        return "S1 calmly returns to her previous posture and looks into the lens"

    @staticmethod
    def drift_correction(attribute: str, correct: str, wrong: str | None = None) -> str:
        """Textual drift correction (intervention 1 in proposal §10.4)."""
        if wrong:
            return f"Her {attribute} is {correct}, not {wrong}"
        return f"Her {attribute} is {correct}"

    def snapshot(self) -> dict:
        return {
            "canon": asdict(self._canon),
            "pose": self.pose,
            "props": {k: asdict(v) for k, v in self.props.items()},
            "history": [asdict(h) for h in self.history[-20:]],
            "generated_not_presented": list(self.generated_not_presented),
        }

===== FILE: live_agent/timeline.py =====
"""Single timeline, just-in-time locking and correction eligibility (proposal §10, §11).

Events per request k: lock P_k -> teacher (G_a) -> student (first chunk G_1) -> ready
-> presented V_k (4 chunks, ~R seconds). Hard constraints:

    ready_{k+1} = max(P_{k+1} + G_a, done_k) + G_1 + delta
    V_{k+1}     = max(ready_{k+1}, V_k + R)

Just-in-time lock (D-018):  P_{k+1} = V_k + R - Lambda - sigma, Lambda = G_a + G_1 + delta,
estimated online from measured request timings (a high quantile, for safety).
"Early" lock (contrast): P_{k+1} = V_k.
"""

from __future__ import annotations

import enum
import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO

from live_agent.generator.base import RequestTiming
from live_agent.types import EventType, TimelineEvent, now


class LockMode(str, enum.Enum):
    JIT = "jit"
    EARLY = "early"


@dataclass
class SchedulerConfig:
    request_s: float = 5.0
    sigma_s: float = 0.5  # safety margin (also used for the spoken-audio ASR check)
    delta_s: float = 0.15  # mux + transport estimate until measured
    lambda_prior_s: float = 3.0  # used until enough timings are observed
    lambda_quantile: float = 0.9
    min_observations: int = 3
    mode: LockMode = LockMode.JIT
    time_scale: float = 1.0  # simulation: wall seconds per content second (1/speed)


class LockScheduler:
    def __init__(self, cfg: SchedulerConfig | None = None):
        self.cfg = cfg or SchedulerConfig()
        self._timings: list[RequestTiming] = []
        self.presented_start: dict[int, float] = {}  # V_k
        self.locks: dict[int, float] = {}  # P_k
        self.durations: dict[int, float] = {}  # playback duration of request k (sum of its chunks)

    # ------------------------------------------------------------ observations
    def observe_timing(self, t: RequestTiming) -> None:
        self._timings = [x for x in self._timings if x.request_index != t.request_index] + [t]
        self._timings = self._timings[-50:]

    def on_lock(self, k: int, t: float) -> None:
        self.locks[k] = t

    def on_presented(self, k: int, t: float) -> None:
        self.presented_start.setdefault(k, t)

    def on_duration(self, k: int, seconds: float) -> None:
        """Playback length of request k (e.g. 124 frames for the first request, 119 later)."""
        self.durations[k] = seconds * self.cfg.time_scale

    # ------------------------------------------------------------ estimates
    def lambda_estimate(self) -> float:
        leads = [x.lead_s for x in self._timings if x.lead_s is not None]
        if len(leads) < self.cfg.min_observations:
            return self.cfg.lambda_prior_s
        leads.sort()
        idx = min(len(leads) - 1, int(round(self.cfg.lambda_quantile * (len(leads) - 1))))
        return leads[idx] + self.cfg.delta_s

    def mean_request_time(self) -> float | None:
        vals = [x.t_done - x.t_lock for x in self._timings if x.t_done is not None]
        return statistics.fmean(vals) if vals else None

    def keeps_up(self) -> bool | None:
        """Throughput condition: mean full-pipeline time per request < R (with 10% margin)."""
        m = self.mean_request_time()
        return None if m is None else m < 0.9 * self.cfg.request_s

    # ------------------------------------------------------------ locking
    def expected_presentation(self, k: int) -> float | None:
        """V_k if known, else extrapolated from the latest known presentation start."""
        if k in self.presented_start:
            return self.presented_start[k]
        known = [i for i in self.presented_start if i < k]
        if not known:
            return None
        j = max(known)
        return self.presented_start[j] + sum(self.durations.get(i, self.cfg.request_s) for i in range(j, k))

    def lock_time(self, k_next: int) -> float | None:
        """Wall-clock time at which request ``k_next`` should be locked.

        Returns None while the time is not yet determined (start-up: request k_next-1 has
        not started presenting, so V_{k_next-1} is unknown). The caller waits and asks again;
        locking early would commit content far ahead of playback and delay every instruction.
        """
        if k_next == 0:
            return now()
        v_prev = self.expected_presentation(k_next - 1)
        if v_prev is None:
            return None
        if self.cfg.mode == LockMode.EARLY:
            return v_prev
        return v_prev + self.cfg.request_s - self.lambda_estimate() - self.cfg.sigma_s

    # ------------------------------------------------------------ corrections
    def planned_lock(self, j: int) -> float | None:
        """P_j: actual lock time if already locked, else the planned one (None if unknown)."""
        if j in self.locks:
            return self.locks[j]
        v_prev = self.expected_presentation(j - 1)
        if v_prev is None:
            return None
        if self.cfg.mode == LockMode.EARLY:
            return v_prev
        return v_prev + self.cfg.request_s - self.lambda_estimate() - self.cfg.sigma_s

    def earliest_correctable(self, t_evidence: float, chain_cost_s: float, next_unlocked: int) -> int:
        """First request j >= next_unlocked with P_j >= E + C (no upper bound; proposal §10.3)."""
        t_ready = t_evidence + chain_cost_s
        j = next_unlocked
        for _ in range(10_000):
            pj = self.planned_lock(j)
            if pj is None or pj >= t_ready:
                return j
            j += 1
        return j


def tvc_model(A: float, wait: float, lam: float, sigma: float, inertia: float, R: float,
              mode: LockMode = LockMode.JIT, lookahead: int = 0) -> float:
    """Illustrative latency model (proposal §11): returns predicted TVC for one instruction."""
    if mode == LockMode.JIT:
        return A + wait + lam + sigma + inertia
    return A + wait + (lookahead + 1) * R + inertia


# ---------------------------------------------------------------------- event log


class EventLog:
    """Append-only JSONL log of timeline events (consumed by live_agent.eval)."""

    def __init__(self, path: str | Path | None = None):
        self.events: list[TimelineEvent] = []
        self._fh: IO[str] | None = open(path, "a", encoding="utf-8") if path else None

    def emit(self, type_: EventType, t: float | None = None, **kw) -> TimelineEvent:
        ev = TimelineEvent(type=type_, t=now() if t is None else t,
                           request_index=kw.pop("request_index", None),
                           chunk_index=kw.pop("chunk_index", None), data=kw)
        self.events.append(ev)
        if self._fh:
            d = asdict(ev)
            d["type"] = ev.type.value
            self._fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            self._fh.flush()
        return ev

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

===== FILE: live_agent/director/director.py =====
"""Online director (proposal §8.2 layers 1-2, §9, §10).

Responsibilities
- Interpret each user utterance with the responder LLM: new intent chain, revision of
  an open chain, or withdrawal; the plan is a queue of *segments* (one per 5-s request:
  an action intent and at most ~5 s of speech).
- On a new plan version, drop *unsent* segments of older versions (cancellation rule).
- At each lock, build the BlockScript for the next request: canon from the ledger
  (verbatim), action via the capability manifest (emit / degrade / refuse), pending
  forward corrections, and compile-time check questions.
- Narration policy: the LLM never claims completion; the director appends a completion
  remark only after QC verified the action on presented frames (FCR control).

Modes: ``closed_loop`` (A2) and ``open_loop`` (A1 baseline: the LLM writes the action
phrase freely, no manifest, no QC-driven corrections, no narration guard).
"""

from __future__ import annotations

import enum
import re
from collections import deque
from dataclasses import dataclass, field

from live_agent.capability import CapabilityManifest, Decision
from live_agent.ledger import StateLedger
from live_agent.llm import ChatLLM, parse_json
from live_agent.types import (BlockScript, ChainStatus, CheckQuestion, IntentChain, TaskKind,
                              Utterance, new_id)

CHARS_PER_REQUEST = 22  # ~4.5 Chinese characters/s x 5 s [estimate; calibrate in E1]


class DirectorMode(str, enum.Enum):
    CLOSED_LOOP = "closed_loop"  # A2
    OPEN_LOOP = "open_loop"  # A1


@dataclass
class Segment:
    chain_id: str | None
    plan_version: int
    intent: str = ""  # capability intent (closed loop) or free phrase (open loop)
    line: str = ""
    step: int | None = None
    is_completion_remark: bool = False
    correction: str = ""  # forward correction attached to a retried action
    retry_of: int | None = None  # request index whose check failed


@dataclass
class DirectorEvents:
    """Things the orchestrator must log (consumed by the eval schema)."""

    refusals: list[tuple[str, str]] = field(default_factory=list)  # (chain_id, reason)
    degradations: list[tuple[str, str]] = field(default_factory=list)
    completion_claims: list[tuple[str, int]] = field(default_factory=list)  # (chain_id, request)
    capacity_skips: list[str] = field(default_factory=list)


RESPONDER_SYSTEM = """你是直播数字人「{name}」的应答大脑。人设：{bio}
人设能做的动作只有这些 intent：{intents}。
输出一个 JSON 对象（不要输出任何其他文字），字段：
- "relation": "new"（用户提出新的要求）| "revision"（用户改口、纠正尚未完成的要求）| "withdrawal"（用户取消尚未完成的要求）| "chat"（闲聊、提问、陈述）
- "target_chain": relation 为 revision/withdrawal 时，被修改的链 id（从下面的未完成链中选）；否则 null
- "kind": "action"（要求做一个动作）| "multistep"（按顺序做多个动作）| "content"（讲解、唱歌、回答知识问题）| "memory"（要求记住或忘记某事）| "chat"
- "steps": [{{"intent": ..., "line": ...}}]，按顺序执行
- "memory_note": 用户陈述了关于**他自己**的事实时，用第三人称写成一句（如「用户的妹妹住在杭州」）；否则 null
- "forget_term": 用户要求忘记某事时，写出关键词；否则 null
规则：
1. 只有当用户**明确要求人设做动作**时（kind 为 action 或 multistep），steps 里才写动作 intent；其他情况 intent 一律写 ""。
2. 用户要求的动作不在上面的列表里时，intent 写 ""，并在 line 里礼貌说明做不到。
3. 每个 line 不超过 {chars} 个汉字；长回答拆成多个 step。
4. 只说意图（「好，我喝口茶」），不说已经完成（不说「我喝完了」）。
5. 称呼用户用「你」。绝不把用户说的关于他自己的事说成是人设自己的事。
示例：
用户：喝口茶吧 → {{"relation":"new","target_chain":null,"kind":"action","steps":[{{"intent":"drink_tea","line":"好，我喝口茶。"}}],"memory_note":null,"forget_term":null}}
用户：你能飞起来吗 → {{"relation":"chat","target_chain":null,"kind":"chat","steps":[{{"intent":"","line":"我可飞不起来，不过可以给你讲讲飞行的原理。"}}],"memory_note":null,"forget_term":null}}
用户：我妹妹住在杭州 → {{"relation":"chat","target_chain":null,"kind":"chat","steps":[{{"intent":"","line":"原来你妹妹住在杭州，那里很美。"}}],"memory_note":"用户的妹妹住在杭州","forget_term":null}}
用户：忘掉我妹妹的事 → {{"relation":"chat","target_chain":null,"kind":"memory","steps":[{{"intent":"","line":"好的，关于你妹妹的事我已经忘掉了。"}}],"memory_note":null,"forget_term":"妹妹"}}
用户（有未完成链 chain-1：翻书）：不对，先挥挥手 → {{"relation":"revision","target_chain":"chain-1","kind":"action","steps":[{{"intent":"wave","line":"好，先挥挥手。"}}],"memory_note":null,"forget_term":null}}
当前未完成的指令链：{open_chains}
人设当前状态：{state}
相关记忆（带来源标签，只作参考）：{memories}"""


class Director:
    def __init__(self, llm: ChatLLM, manifest: CapabilityManifest, ledger: StateLedger, *,
                 persona_name: str, persona_bio: str, mode: DirectorMode = DirectorMode.CLOSED_LOOP,
                 idle_intent: str = "idle_read", listen_intent: str = "listen"):
        self.llm = llm
        self.manifest = manifest
        self.ledger = ledger
        self.mode = mode
        self.persona_name = persona_name
        self.persona_bio = persona_bio
        self.idle_intent = idle_intent
        self.listen_intent = listen_intent
        self.plan_version = 0
        self.queue: deque[Segment] = deque()
        self.chains: dict[str, IntentChain] = {}
        self.pending_corrections: dict[int, list[str]] = {}  # request index -> correction sentences
        self.events = DirectorEvents()
        self.listening = False
        self.memory_notes: list[tuple[str, str]] = []  # (utterance id, note)

    # ------------------------------------------------------------ utterances
    def _open_chains(self) -> list[IntentChain]:
        return [c for c in self.chains.values() if c.status == ChainStatus.OPEN]

    async def on_user_utterance(self, utt: Utterance, memories: list[str] | None = None) -> dict:
        """Interpret an utterance and replace the unsent plan. Returns the parsed decision."""
        intents = ", ".join(sorted({c.intent for c in self.manifest.caps.values()
                                    if self.mode == DirectorMode.OPEN_LOOP
                                    or c.usable(self.manifest.min_status, self.manifest.min_p)})) or "（暂无）"
        open_chains = [{"chain_id": c.chain_id, "intent": c.final_intent} for c in self._open_chains()]
        sys = RESPONDER_SYSTEM.format(
            name=self.persona_name, bio=self.persona_bio, intents=intents, chars=CHARS_PER_REQUEST,
            open_chains=open_chains or "无", state=self.ledger.continuity_sentence(),
            memories=memories or "无")
        raw = await self.llm.chat([{"role": "system", "content": sys},
                                   {"role": "user", "content": utt.text}], json_mode=True)
        try:
            d = parse_json(raw)
        except ValueError:
            d = {"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "抱歉，我没听清，可以再说一次吗？"}]}
        self._apply_decision(utt, d)
        return d

    def _apply_decision(self, utt: Utterance, d: dict) -> None:
        relation = d.get("relation", "new")
        kind = TaskKind(d.get("kind", "chat")) if d.get("kind") in TaskKind._value2member_map_ else TaskKind.CHAT
        steps = [s for s in d.get("steps", []) if isinstance(s, dict)]
        # Enforce the contract in code, not only in the prompt: actions only for action/multistep
        # chains and only from the manifest; lines must not be empty punctuation.
        allowed = {c.intent for c in self.manifest.caps.values()}
        for st in steps:
            if kind not in (TaskKind.ACTION, TaskKind.MULTISTEP) or st.get("intent") not in allowed:
                if kind in (TaskKind.ACTION, TaskKind.MULTISTEP) and st.get("intent"):
                    st["unsupported_intent"] = st["intent"]  # keep: the compiler will refuse it
                    continue
                st["intent"] = ""
        target = self.chains.get(d.get("target_chain") or "")
        if d.get("memory_note"):
            self.memory_notes.append((utt.uid, d["memory_note"]))

        # New plan version: drop unsent segments of older versions (sent ones can only be superseded).
        self.plan_version += 1
        self.queue.clear()

        if relation == "withdrawal" and target:
            target.status = ChainStatus.WITHDRAWN
            chain_id = None
        elif relation == "revision" and target:
            target.revisions.append(utt.uid)
            target.final_intent = utt.text
            target.clock_origin = utt.t_end
            target.steps = [s.get("intent", "") for s in steps]
            target.step_index = 0
            chain_id = target.chain_id
        elif relation == "chat" and kind == TaskKind.CHAT:
            chain_id = None
        else:
            chain = IntentChain(chain_id=new_id("chain"), kind=kind, opened_by=utt.uid,
                                final_intent=utt.text, clock_origin=utt.t_end,
                                steps=[s.get("intent", "") for s in steps])
            self.chains[chain.chain_id] = chain
            chain_id = chain.chain_id

        for i, s in enumerate(steps):
            for j, line in enumerate(_split_line(s.get("line", "")) or [""]):
                self.queue.append(Segment(chain_id=chain_id, plan_version=self.plan_version,
                                          intent=(s.get("intent") or "") if j == 0 else "",
                                          line=line, step=i if len(steps) > 1 else None))
        self.listening = False

    def on_barge_in(self) -> None:
        """User started speaking: stop planning ahead; next requests show the persona listening."""
        self.plan_version += 1
        self.queue.clear()
        self.listening = True

    # ------------------------------------------------------------ verdict feedback
    def on_verified(self, chain_id: str, intent: str, request_index: int, t: float) -> None:
        chain = self.chains.get(chain_id)
        if not chain or chain.status != ChainStatus.OPEN:
            return
        self.ledger.apply_verified_action(intent)
        chain.step_index += 1
        if chain.first_compliant_t is None:
            chain.first_compliant_t = t
        if chain.step_index >= max(1, len([s for s in chain.steps if s])):
            chain.status = ChainStatus.COMPLIED
            if self.mode == DirectorMode.CLOSED_LOOP:
                # Narration policy: completion is voiced only after verification.
                self.queue.appendleft(Segment(chain_id=chain_id, plan_version=self.plan_version,
                                              intent="", line="好了。", is_completion_remark=True))

    def schedule_correction(self, request_index: int, sentence: str) -> None:
        self.pending_corrections.setdefault(request_index, []).append(sentence)

    def queue_retry(self, chain_id: str, intent: str, *, correction: str, failed_request: int,
                    plan_version: int) -> bool:
        """Forward repair: retry the action in the next request to be locked.

        Dropped if the chain is no longer open or a newer plan superseded the one that
        produced the failed request (the user changed their mind meanwhile).
        """
        chain = self.chains.get(chain_id)
        if chain is None or chain.status != ChainStatus.OPEN or plan_version != self.plan_version:
            return False
        self.queue.appendleft(Segment(chain_id=chain_id, plan_version=self.plan_version, intent=intent,
                                      line="", correction=correction, retry_of=failed_request))
        return True

    # ------------------------------------------------------------ script building
    def next_script(self, request_index: int) -> BlockScript:
        seg = self.queue.popleft() if self.queue else None
        if seg is None:
            intent = self.listen_intent if self.listening else self.idle_intent
            seg = Segment(chain_id=None, plan_version=self.plan_version, intent=intent, line="")

        action_phrase, cap_ids, checks = "", [], []
        line = seg.line
        if seg.intent:
            if self.mode == DirectorMode.OPEN_LOOP:
                cap = self.manifest.by_intent(seg.intent)
                action_phrase = cap.phrase if cap else seg.intent
            else:
                res = self.manifest.decide(seg.intent)
                if res.decision == Decision.EMIT and res.capability:
                    action_phrase = res.capability.phrase
                    cap_ids.append(res.capability.cap_id)
                    if seg.chain_id and res.capability.check_question:
                        checks.append(CheckQuestion(qid=new_id("q"), text=res.capability.check_question,
                                                    kind="action"))
                elif res.decision == Decision.DEGRADE and res.capability:
                    self.events.degradations.append((seg.chain_id or "", res.reason))
                    line = line or res.capability.degrade_to
                    self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
                else:
                    self.events.refusals.append((seg.chain_id or "", res.reason))
                    line = line or "这个我现在做不到，不过我们可以聊聊别的。"
                    self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
        if line and self.mode == DirectorMode.CLOSED_LOOP:
            checks.append(CheckQuestion(qid=new_id("q"), text="台词是否被完整、准确地说出？", kind="speech"))
        if seg.is_completion_remark and seg.chain_id:
            self.events.completion_claims.append((seg.chain_id, request_index))
        elif self.mode == DirectorMode.OPEN_LOOP and seg.chain_id and _claims_completion(line):
            self.events.completion_claims.append((seg.chain_id, request_index))

        corrections = list(self.pending_corrections.pop(request_index, []))
        if seg.correction:
            corrections.append(seg.correction)
        if self.mode == DirectorMode.CLOSED_LOOP:
            bridge = self.ledger.bridging_note()
            if bridge:
                corrections.append(bridge)
                self.ledger.generated_not_presented.clear()  # bridge once, then continue normally
        script = BlockScript(request_index=request_index, plan_version=seg.plan_version,
                             canon=self.ledger.canon, action=action_phrase, transcript=line,
                             corrections=corrections, checks=checks,
                             chain_ids=[seg.chain_id] if seg.chain_id else [],
                             capability_ids=cap_ids,
                             provenance={"intent": seg.intent, "step": seg.step, "retry_of": seg.retry_of})
        if seg.chain_id and seg.chain_id in self.chains:
            self.chains[seg.chain_id].requests.append(request_index)
        self.ledger.record_request(request_index, action_phrase, line)
        return script

    def _fail_chain(self, chain_id: str | None, status: ChainStatus) -> None:
        if chain_id and chain_id in self.chains and self.chains[chain_id].status == ChainStatus.OPEN:
            self.chains[chain_id].status = status


def _split_line(line: str, n: int = CHARS_PER_REQUEST) -> list[str]:
    """Split a spoken line into <= n-character pieces at punctuation where possible."""
    line = line.strip()
    if not line:
        return []
    out, cur = [], ""
    for piece in re.split(r"(?<=[。！？!?；;，,])", line):
        if len(cur) + len(piece) <= n:
            cur += piece
        else:
            if cur:
                out.append(cur)
            while len(piece) > n:
                out.append(piece[:n])
                piece = piece[n:]
            cur = piece
    if cur:
        out.append(cur)
    return [x for x in out if re.search(r"[\w\u4e00-\u9fff]", x)]


_COMPLETION = re.compile(r"(完了|好了|做完|喝完|已经|done|finished)")


def _claims_completion(line: str) -> bool:
    return bool(_COMPLETION.search(line or ""))

===== FILE: live_agent/qc/judge.py =====
"""Online QC (proposal §8.2 layer 5): deadline-bounded checks on *presented* content.

- ``VLMJudge``: asks a VLM a yes/no question about K frames sampled from the presented
  chunks of a request; may abstain (UNKNOWN).
- ``SpeechCheck``: ASR of the generated audio vs the scripted line (character error rate).
- ``ForwardCorrector``: VQQA-style "semantic gradient": turns failed Q/A into a correction
  sentence for the earliest correctable request (never regenerates presented content).
- ``MockJudge``: for tests/simulation; decides compliance from the prompt with a
  per-capability success probability.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from live_agent.llm import ChatLLM, frame_to_data_url, parse_json
from live_agent.types import CheckQuestion, Chunk, Verdict, VerdictLabel, now

JUDGE_PROMPT = """你是严格的视频质检员。下面是直播画面中按时间顺序抽取的 {k} 帧。
问题：{question}
只根据画面回答，只输出 JSON：{{"answer": "yes" | "no" | "unsure", "confidence": 0到1之间的小数, "reason": "一句话"}}"""


def sample_frames(chunks: Sequence[Chunk], k: int = 4) -> list[np.ndarray]:
    frames = [f for c in chunks if c.video is not None for f in c.video]
    if not frames:
        return []
    idx = np.linspace(0, len(frames) - 1, num=min(k, len(frames))).round().astype(int)
    return [frames[i] for i in idx]


@dataclass
class VLMJudge:
    vlm: ChatLLM
    k: int = 4
    min_confidence: float = 0.6

    async def judge(self, q: CheckQuestion, chunks: Sequence[Chunk], request_index: int,
                    t_evidence: float) -> Verdict:
        frames = sample_frames(chunks, self.k)
        if not frames:
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, "no frames", t_evidence, now())
        content = [{"type": "text", "text": JUDGE_PROMPT.format(k=len(frames), question=q.text)}]
        content += [{"type": "image_url", "image_url": {"url": frame_to_data_url(f)}} for f in frames]
        try:
            d = parse_json(await self.vlm.chat([{"role": "user", "content": content}], max_tokens=128,
                                               temperature=0.0, json_mode=True))
            ans, conf = str(d.get("answer", "unsure")).lower(), float(d.get("confidence", 0.0))
            reason = str(d.get("reason", ""))
        except Exception as e:  # abstain on any judge failure
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, f"judge error: {e}", t_evidence, now())
        if conf < self.min_confidence or ans not in ("yes", "no"):
            label = VerdictLabel.UNKNOWN
        else:
            label = VerdictLabel.COMPLIED if ans == "yes" else VerdictLabel.NOT_COMPLIED
        return Verdict(q.qid, request_index, label, conf, reason, t_evidence, now())


def char_error_rate(ref: str, hyp: str) -> float:
    """Levenshtein distance / len(ref) on characters, ignoring punctuation and spaces."""
    norm = lambda s: re.sub(r"[\s\W_]+", "", s.lower())  # noqa: E731
    r, h = norm(ref), norm(hyp)
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hc in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return prev[-1] / len(r)


@dataclass
class SpeechCheck:
    """Compare ASR of generated speech with the scripted line (used within sigma before playback)."""

    asr: Callable[[np.ndarray, int], str]  # (audio [S,C] float32, sample_rate) -> text
    max_cer: float = 0.10

    def check(self, q: CheckQuestion, script_line: str, chunks: Sequence[Chunk], request_index: int,
              t_evidence: float) -> Verdict:
        audio = [c.audio for c in chunks if c.audio is not None and len(c.audio)]
        if not audio:
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, "no audio", t_evidence, now())
        sr = chunks[0].sample_rate
        text = self.asr(np.concatenate(audio, axis=0), sr)
        cer = char_error_rate(script_line, text)
        label = VerdictLabel.COMPLIED if cer <= self.max_cer else VerdictLabel.NOT_COMPLIED
        return Verdict(q.qid, request_index, label, 1.0 - min(cer, 1.0), f"asr={text!r} cer={cer:.2f}",
                       t_evidence, now())


CORRECTION_PROMPT = """视频生成模型没有执行下面的动作。请把动作描述改写成更明确、更容易被画出来的英文短句（一句，不超过 30 个词），
只描述人物 S1 的可见动作，不要改变人物外貌、场景或镜头。
原动作：{action}
失败的检查问答：{qa}
只输出 JSON：{{"correction": "..."}}"""


@dataclass
class ForwardCorrector:
    llm: ChatLLM | None = None

    async def correction(self, action_phrase: str, failed: Sequence[Verdict], questions: dict[str, str]) -> str:
        qa = "; ".join(f"Q: {questions.get(v.qid, v.qid)} A: {v.label.value} ({v.rationale})" for v in failed)
        if self.llm is not None:
            try:
                d = parse_json(await self.llm.chat(
                    [{"role": "user", "content": CORRECTION_PROMPT.format(action=action_phrase, qa=qa)}],
                    max_tokens=96, temperature=0.2, json_mode=True))
                text = str(d.get("correction", "")).strip()
                if text:
                    return text
            except Exception:
                pass
        # Template fallback: emphasise visibility and timing.
        return f"This time S1 clearly and visibly does it: {action_phrase}, facing the lens, within the first two seconds"


class MockJudge:
    """Simulated judge: an action 'renders' with probability p (per phrase), boosted by corrections."""

    def __init__(self, p_default: float = 0.7, p_by_phrase: dict[str, float] | None = None,
                 correction_boost: float = 0.2, seed: int = 0):
        self.p_default = p_default
        self.p_by_phrase = p_by_phrase or {}
        self.boost = correction_boost
        self._rng = random.Random(seed)

    async def judge(self, q: CheckQuestion, chunks: Sequence[Chunk], request_index: int,
                    t_evidence: float) -> Verdict:
        prompt = chunks[0].meta.get("prompt", "") if chunks else ""
        p = self.p_default
        for phrase, pp in self.p_by_phrase.items():
            if phrase in prompt:
                p = pp
        if "clearly and visibly" in prompt:
            p = min(1.0, p + self.boost)
        ok = self._rng.random() < p
        return Verdict(q.qid, request_index, VerdictLabel.COMPLIED if ok else VerdictLabel.NOT_COMPLIED,
                       0.9, "mock", t_evidence, now())

===== FILE: live_agent/orchestrator.py =====
"""Orchestrator: runs the live agent on the single timeline (proposal §10, §11).

Concurrent loops
- lock loop     : at each just-in-time lock time, ask the director for the next BlockScript,
                  compile it to an H3 prompt and submit it to the generator (event LOCK).
- chunk loop    : forward generated chunks to the client transport (event CHUNK_READY).
- presentation  : client acks (start/end of each chunk) drive V_k and the evidence time E;
                  when a request's last chunk has been presented, run its QC checks.
- input         : user utterances (after ASR) go to memory + director; speech onset = barge-in.

Everything that the evaluation needs is written to the EventLog as JSONL.
"""

from __future__ import annotations

import asyncio
import enum
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import Generator
from live_agent.prompt.h3_compiler import compile_prompt
from live_agent.qc.judge import ForwardCorrector
from live_agent.timeline import EventLog, LockScheduler
from live_agent.types import (BlockScript, ChainStatus, Chunk, EventType, Utterance, Verdict,
                              VerdictLabel, now)


class Transport(Protocol):
    """Client side: plays chunks and reports presentation times via Orchestrator.on_presented."""

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None: ...

    async def stop_playback(self) -> None: ...


class MemoryPort(Protocol):
    """Minimal memory interface used by the orchestrator (adapter over live_agent.memory)."""

    def recall(self, text: str, *, mode: str) -> list[str]: ...

    def on_user_utterance(self, utt: Utterance) -> None: ...

    def on_persona_line(self, text: str, *, session_id: str, scope: str) -> None: ...


class Judge(Protocol):
    async def judge(self, q, chunks, request_index: int, t_evidence: float) -> Verdict: ...


class CorrectionMode(str, enum.Enum):
    GRADIENT = "gradient"  # forward semantic gradient (A2)
    REPEAT = "repeat"  # RQ2 contrast: repeat the instruction unchanged
    NONE = "none"  # ablation / open loop


@dataclass
class OrchestratorConfig:
    session_id: str = "session-0"
    scope: str = "private"  # "private" (1:1) | "public" (test livestream)
    correction_mode: CorrectionMode = CorrectionMode.GRADIENT
    qc_enabled: bool = True
    max_requests: int | None = None  # stop after N requests (tests / batch runs)
    correction_chain_prior_s: float = 1.0  # C estimate until measured
    seed: int = 0


class Orchestrator:
    def __init__(self, generator: Generator, director: Director, scheduler: LockScheduler,
                 transport: Transport, *, judge: Judge | None = None,
                 corrector: ForwardCorrector | None = None, speech_check=None,
                 memory: MemoryPort | None = None, log: EventLog | None = None,
                 cfg: OrchestratorConfig | None = None):
        self.gen = generator
        self.director = director
        self.sched = scheduler
        self.transport = transport
        self.judge = judge
        self.corrector = corrector or ForwardCorrector()
        self.speech_check = speech_check
        self.memory = memory
        self.log = log or EventLog()
        self.cfg = cfg or OrchestratorConfig()
        self.scripts: dict[int, BlockScript] = {}
        self.prompts: dict[int, str] = {}
        self.chunks: dict[int, list[Chunk]] = defaultdict(list)
        self.presented: dict[int, set[int]] = defaultdict(set)
        self.next_lock = 0
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._rng = random.Random(self.cfg.seed)
        self._chain_costs: list[float] = []
        self.dropped: set[int] = set()  # requests discarded by a barge-in (never presented in full)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        await self.gen.start()
        self._tasks = [asyncio.create_task(self._lock_loop()), asyncio.create_task(self._chunk_loop())]

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await self.gen.close()
        self.log.close()

    async def wait_done(self) -> None:
        await self._stop.wait()

    # ------------------------------------------------------------------ lock loop
    async def _lock_loop(self) -> None:
        while not self._stop.is_set():
            k = self.next_lock
            if self.cfg.max_requests is not None and k >= self.cfg.max_requests:
                return
            # Re-evaluate while waiting: V_{k-1} becomes known (or better extrapolated) meanwhile.
            while not self._stop.is_set():
                tl = self.sched.lock_time(k)
                if tl is not None and tl <= now():
                    break
                await asyncio.sleep(0.01 if tl is None else min(0.05, tl - now()))
            # Never run more than two requests ahead of presentation (bounded backlog).
            while k >= 2 and not self._resolved(k - 2) and not self._stop.is_set():
                await asyncio.sleep(0.01)
            script = self.director.next_script(k)
            prompt = compile_prompt(script, first_request=(k == 0))
            self.scripts[k], self.prompts[k] = script, prompt
            t = now()
            await self.gen.submit(k, prompt)
            self.sched.on_lock(k, t)
            self.next_lock = k + 1
            self.log.emit(EventType.LOCK, t, request_index=k, plan_version=script.plan_version,
                          lambda_est=self.sched.lambda_estimate(), planned_lock=tl,
                          action=script.action, transcript=script.transcript,
                          chain_ids=script.chain_ids, corrections=script.corrections,
                          capability_ids=script.capability_ids, prompt=prompt,
                          checks=[{"qid": q.qid, "text": q.text, "kind": q.kind} for q in script.checks])
            if script.transcript and self.memory:
                self.memory.on_persona_line(script.transcript, session_id=self.cfg.session_id,
                                            scope=self.cfg.scope)
            for chain_id, rid in self.director.events.completion_claims:
                if rid == k:
                    self.log.emit(EventType.COMPLETION_CLAIM, t, request_index=k, chain_id=chain_id)
            for chain_id, reason in self._drain(self.director.events.refusals):
                self.log.emit(EventType.REFUSAL, t, request_index=k, chain_id=chain_id, reason=reason)
            for chain_id, reason in self._drain(self.director.events.degradations):
                self.log.emit(EventType.REFUSAL, t, request_index=k, chain_id=chain_id, reason=reason,
                              degraded=True)

    def _resolved(self, k: int) -> bool:
        return k in self.sched.presented_start or k in self.dropped

    @staticmethod
    def _drain(items: list) -> list:
        out = list(items)
        items.clear()
        return out

    # ------------------------------------------------------------------ chunk loop
    async def _chunk_loop(self) -> None:
        async for ch in self.gen.chunks():
            self.chunks[ch.request_index].append(ch)
            self.log.emit(EventType.CHUNK_READY, ch.t_ready, request_index=ch.request_index,
                          chunk_index=ch.chunk_index, n_frames=ch.n_frames)
            if ch.chunk_index == 3:
                self.sched.on_duration(ch.request_index,
                                       sum(c.duration_s for c in self.chunks[ch.request_index]))
                for tm in self.gen.timings:
                    if tm.request_index == ch.request_index:
                        self.sched.observe_timing(tm)
                        self.log.emit(EventType.REQUEST_DONE, now(), request_index=ch.request_index,
                                      lead_s=tm.lead_s, teacher_s=tm.teacher_s,
                                      total_s=(tm.t_done - tm.t_lock) if tm.t_done else None)
            if ch.request_index in self.dropped:
                continue  # generated before a barge-in: never shown
            script = self.scripts.get(ch.request_index)
            if script is not None:
                await self.transport.send_chunk(ch, script)

    # ------------------------------------------------------------------ presentation acks
    def on_presented(self, request_index: int, chunk_index: int, t_start: float, t_end: float) -> None:
        """Called by the transport when a chunk *finished* presenting (with its start/end times)."""
        if chunk_index == 0:
            self.sched.on_presented(request_index, t_start)
            self.director.ledger.mark_presented(request_index)
        self.presented[request_index].add(chunk_index)
        self.log.emit(EventType.CHUNK_PRESENTED, t_start, request_index=request_index,
                      chunk_index=chunk_index, t_end=t_end)
        n = len(self.chunks.get(request_index, [])) or 4
        if len(self.presented[request_index]) == n and self.cfg.qc_enabled:
            asyncio.ensure_future(self._run_checks(request_index, t_evidence=t_end))
        self._maybe_finish()

    def _maybe_finish(self) -> None:
        m = self.cfg.max_requests
        if m is None:
            return
        last = m - 1
        done = last in self.dropped or len(self.presented.get(last, ())) == (len(self.chunks.get(last, [])) or 4)
        if done and all(self._resolved(k) for k in range(m)):
            self._stop.set()

    # ------------------------------------------------------------------ QC
    async def _run_checks(self, k: int, t_evidence: float) -> None:
        script = self.scripts.get(k)
        if script is None or not script.checks or self.director.mode == DirectorMode.OPEN_LOOP:
            return
        chunks = self.chunks[k]
        action_verdicts: list[Verdict] = []
        for q in script.checks:
            if q.kind == "speech":
                if self.speech_check is None:
                    continue
                v = self.speech_check.check(q, script.transcript, chunks, k, t_evidence)
            elif self.judge is not None:
                v = await self.judge.judge(q, chunks, k, t_evidence)
            else:
                continue
            if q.kind == "action":
                action_verdicts.append(v)
            self.log.emit(EventType.VERDICT, v.t_verdict, request_index=k, qid=v.qid, kind=q.kind,
                          label=v.label.value, confidence=v.confidence, rationale=v.rationale,
                          t_evidence=t_evidence, source="online_monitor")
            self.director.ledger.record_verdict(k, v.qid, v.label.value)
        intent = script.provenance.get("intent", "")
        for chain_id in script.chain_ids:
            if action_verdicts and all(v.label == VerdictLabel.COMPLIED for v in action_verdicts):
                self.director.on_verified(chain_id, intent, k, t_evidence)
            elif any(v.label == VerdictLabel.NOT_COMPLIED for v in action_verdicts):
                await self._repair(chain_id, intent, script, action_verdicts, t_evidence)

    async def _repair(self, chain_id: str, intent: str, script: BlockScript, failed: list[Verdict],
                      t_evidence: float) -> None:
        mode = self.cfg.correction_mode
        if mode == CorrectionMode.NONE:
            return
        t0 = now()
        if mode == CorrectionMode.GRADIENT:
            qtext = {q.qid: q.text for q in script.checks}
            sentence = await self.corrector.correction(script.action, failed, qtext)
        else:
            sentence = ""
        cost = now() - t0
        self._chain_costs.append(cost)
        j_planned = self.sched.earliest_correctable(t_evidence, cost, self.next_lock)
        queued = self.director.queue_retry(chain_id, intent, correction=sentence,
                                           failed_request=script.request_index,
                                           plan_version=script.plan_version)
        self.log.emit(EventType.REPAIR, now(), request_index=script.request_index,
                      chain_id=chain_id, mode=mode.value, correction=sentence, queued=queued,
                      earliest_correctable=j_planned, next_unlocked=self.next_lock, chain_cost_s=cost)

    # ------------------------------------------------------------------ user input
    async def on_speech_start(self, t: float | None = None) -> None:
        """Barge-in: stop playback now; stop planning ahead; mark unshown generated content."""
        t = now() if t is None else t
        await self._drop_unpresented()
        self.log.emit(EventType.PLAYBACK_STOP, now(), t_speech_onset=t, dropped=sorted(self.dropped))
        self.director.on_barge_in()
        self._maybe_finish()

    async def _drop_unpresented(self) -> None:
        """Stop playback and discard everything locked but not (fully) presented."""
        await self.transport.stop_playback()
        for k in range(self.next_lock):
            n = len(self.chunks.get(k, [])) or 4
            if len(self.presented.get(k, ())) < n:
                self.dropped.add(k)
                self.director.ledger.mark_generated_not_presented(k)

    async def on_user_utterance(self, utt: Utterance) -> dict[str, Any]:
        self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text)
        memories = self.memory.recall(utt.text, mode=self.cfg.scope) if self.memory else None
        if self.memory:
            self.memory.on_user_utterance(utt)
        decision = await self.director.on_user_utterance(utt, memories)
        term = (decision or {}).get("forget_term")
        if term and self.memory is not None and hasattr(self.memory, "forget"):
            await self._erase(term)
        self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
                      chains={c.chain_id: c.status.value for c in self.director.chains.values()})
        return decision

    async def _erase(self, term: str) -> None:
        """Erasure (proposal §12): memory cascade + drop unsent scripts + restart generator state."""
        report = self.memory.forget(term)
        # Unsent plan segments that mention the term are dropped.
        self.director.queue = type(self.director.queue)(
            s for s in self.director.queue if term not in (s.line or ""))
        # The generator's KV / teacher tail may hold the erased content: restart from canon.
        await self._drop_unpresented()
        self.director.ledger.generated_not_presented.clear()  # erased content must not be bridged to
        await self.gen.reset()
        self._maybe_finish()
        self.log.emit(EventType.PLAYBACK_STOP, now(), erasure=True, deleted=len(report.deleted_ids),
                      kinds=report.kinds, generator_reset=True)

    def open_chains(self) -> list[str]:
        return [c.chain_id for c in self.director.chains.values() if c.status == ChainStatus.OPEN]

===== FILE: live_agent/generator/base.py =====
"""Generator interface.

A generator consumes one compiled prompt per request (5 s for TaoMate-H3) and yields
the request's chunks as they become ready. Implementations:

- ``MockGenerator``   : deterministic, CPU-only, configurable latencies (tests / sim).
- ``TaoMateH3Generator``: wraps the TaoMate-H3 streaming runtime with the T1 prompt
  queue, T2 audio-teacher lookahead and T3 per-chunk output (see proposal §6.2).

Contract (mirrors the single timeline of proposal §10):
- ``submit(request_index, prompt)`` *locks* the prompt for that request (event LOCK).
  Requests must be submitted in order; request k+1 may only start generating after
  request k's final KV commit (KV dependency).
- ``chunks()`` is an async iterator over ``Chunk`` objects in generation order.
- ``reset(prompt)`` starts a new generation session (fresh KV/sink); used for
  session-reset drift correction and erasure.
- ``timings`` exposes the measured G_a (teacher) and G_1 (first chunk) of recent
  requests so the scheduler can estimate Lambda.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from live_agent.types import Chunk


@dataclass
class RequestTiming:
    request_index: int
    t_lock: float
    t_teacher_start: float | None = None
    t_teacher_done: float | None = None
    t_student_start: float | None = None
    t_first_chunk: float | None = None
    t_done: float | None = None

    @property
    def teacher_s(self) -> float | None:
        if self.t_teacher_start is None or self.t_teacher_done is None:
            return None
        return self.t_teacher_done - self.t_teacher_start

    @property
    def lead_s(self) -> float | None:
        """Lock -> first chunk ready (Lambda without transport)."""
        if self.t_first_chunk is None:
            return None
        return self.t_first_chunk - self.t_lock


@dataclass
class GeneratorInfo:
    name: str
    request_seconds: float = 5.0
    chunks_per_request: int = 4
    fps: float = 24.0
    width: int = 864
    height: int = 480
    sample_rate: int = 32000
    extra: dict = field(default_factory=dict)


class Generator(abc.ABC):
    info: GeneratorInfo

    @abc.abstractmethod
    async def start(self) -> None:
        """Load models / spawn workers."""

    @abc.abstractmethod
    async def submit(self, request_index: int, prompt: str) -> None:
        """Lock the prompt for ``request_index`` (must be the next index)."""

    @abc.abstractmethod
    def chunks(self) -> AsyncIterator[Chunk]:
        """Async iterator over generated chunks, in order."""

    @abc.abstractmethod
    async def reset(self) -> None:
        """Drop all generator state (KV, sink, teacher tail); next submit starts a new session."""

    @abc.abstractmethod
    async def close(self) -> None: ...

    @property
    @abc.abstractmethod
    def timings(self) -> list[RequestTiming]: ...

    @property
    def next_request_index(self) -> int:
        raise NotImplementedError


class SessionView(Generator):
    """One live session on a long-lived shared generator (TaoMate-H3 workers take ~130 s to start).

    ``start`` resets the backend (fresh KV/sink/teacher tail) and numbers this session's requests
    from 0; ``close`` resets again instead of shutting the workers down. Chunks and timings of
    earlier sessions are dropped. Only one view may be active at a time (the caller serialises).
    """

    def __init__(self, backend: Generator) -> None:
        self.backend = backend
        self.info = backend.info
        self._offset = 0

    async def start(self) -> None:
        await self.backend.reset()
        self._offset = self.backend.next_request_index

    async def submit(self, request_index: int, prompt: str) -> None:
        await self.backend.submit(request_index + self._offset, prompt)

    async def chunks(self) -> AsyncIterator[Chunk]:
        from dataclasses import replace

        async for ch in self.backend.chunks():
            if ch.request_index < self._offset:
                continue  # stale chunk from an earlier session
            yield replace(ch, request_index=ch.request_index - self._offset)

    async def reset(self) -> None:
        await self.backend.reset()  # indices stay monotonic within the session

    async def close(self) -> None:
        await self.backend.reset()

    @property
    def timings(self) -> list[RequestTiming]:
        from dataclasses import replace

        return [replace(t, request_index=t.request_index - self._offset)
                for t in self.backend.timings if t.request_index >= self._offset]

    @property
    def next_request_index(self) -> int:
        return self.backend.next_request_index - self._offset

===== FILE: live_agent/generator/mock.py =====
"""CPU-only mock generator with TaoMate-H3-shaped timing (for tests and simulation).

Timings are parameters, not measurements. Frames are tiny solid-colour arrays whose
colour encodes the request index; audio is silence. ``chunk.meta['prompt']`` carries
the locked prompt so a mock judge can decide compliance.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator

import numpy as np

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.types import Chunk, now

# TaoMate-H3 chunk layout (frames): first request 39/34/34/17, later requests 119 split 34/34/34/17.
FIRST_LAYOUT = (39, 34, 34, 17)
LATER_LAYOUT = (34, 34, 34, 17)


class MockGenerator(Generator):
    def __init__(self, *, teacher_s: float = 1.0, chunk_s: float = 0.6, jitter: float = 0.0,
                 fps: float = 24.0, size: tuple[int, int] = (48, 86), speed: float = 1.0, seed: int = 0):
        self.info = GeneratorInfo(name="mock", fps=fps, width=size[1], height=size[0])
        self.teacher_s = teacher_s
        self.chunk_s = chunk_s
        self.jitter = jitter
        self.speed = speed  # divide all sleeps (tests use large speed-ups)
        self._rng = random.Random(seed)
        self._queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
        self._out: asyncio.Queue[Chunk | None] = asyncio.Queue()
        self._timings: dict[int, RequestTiming] = {}
        self._next = 0
        self._session = 0
        self._first_in_session = True
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _sleep(self, s: float) -> None:
        s = max(0.0, s + (self._rng.uniform(-self.jitter, self.jitter) if self.jitter else 0.0))
        await asyncio.sleep(s / self.speed)

    async def _run(self) -> None:
        while True:
            k, prompt = await self._queue.get()
            session = self._session
            tm = self._timings[k]
            tm.t_teacher_start = now()
            await self._sleep(self.teacher_s)
            tm.t_teacher_done = now()
            tm.t_student_start = now()
            layout = FIRST_LAYOUT if self._first_in_session else LATER_LAYOUT
            self._first_in_session = False
            for ci, n in enumerate(layout):
                await self._sleep(self.chunk_s * n / 34)
                if session != self._session:  # reset happened mid-request
                    break
                shade = (k * 37) % 255
                video = np.full((1, self.info.height, self.info.width, 3), shade, dtype=np.uint8)
                audio = np.zeros((int(n / self.info.fps * self.info.sample_rate), 2), dtype=np.float32)
                ch = Chunk(k, ci, n, self.info.fps, video=video, audio=audio,
                           sample_rate=self.info.sample_rate, t_ready=now(),
                           meta={"prompt": prompt, "session": session})
                if ci == 0:
                    tm.t_first_chunk = ch.t_ready
                await self._out.put(ch)
            tm.t_done = now()

    async def submit(self, request_index: int, prompt: str) -> None:
        if request_index != self._next:
            raise ValueError(f"expected request {self._next}, got {request_index}")
        self._next += 1
        self._timings[request_index] = RequestTiming(request_index, t_lock=now())
        await self._queue.put((request_index, prompt))

    async def chunks(self) -> AsyncIterator[Chunk]:
        while True:
            ch = await self._out.get()
            if ch is None:
                return
            yield ch

    async def reset(self) -> None:
        self._session += 1
        self._first_in_session = True
        while not self._queue.empty():
            self._queue.get_nowait()

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        await self._out.put(None)

    @property
    def timings(self) -> list[RequestTiming]:
        return [self._timings[k] for k in sorted(self._timings)]

    @property
    def next_request_index(self) -> int:
        return self._next

===== FILE: live_agent/generator/taomate_h3.py =====
"""TaoMate-H3 streaming generator adapter (``TaoMateH3Generator``).

Implements ``live_agent.generator.base.Generator`` on top of two torchrun worker groups
(see ``live_agent/generator/taomate_worker/protocol.py`` for the wire protocol):

* T1 mid-session prompt queue: ``submit(k, prompt)`` locks one 5-second request at a time;
  nothing is precompiled. The text encoder stays resident in the teacher group.
* T2 audio-teacher lookahead: the base-H3 audio teacher for request k starts as soon as k is
  locked (``lookahead=True``), overlapping the student's generation of k-1 when the teacher
  has its own GPUs, and carries the 1 s (40-latent) audio tail across requests.
* T3 per-chunk output: every chunk (34/34/34/17 native 24 fps frames + aligned 32 kHz
  stereo audio) is yielded by ``chunks()`` as soon as its VAE decode finishes.

This module only needs the standard library and numpy; torch lives in the worker
environment (``.venvs/taomate-h3``). The caller must hold a canhazgpu reservation for the
devices it passes (e.g. run the whole program under ``gpu run ...``).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import subprocess
import threading
import time
from collections.abc import AsyncIterator
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Any

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.generator.taomate_worker import protocol as P
from live_agent.types import Chunk, now

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PYTHON = REPO / ".venvs" / "taomate-h3" / "bin" / "python"
DEFAULT_MODEL_ROOT = Path(
    "/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe"
)
DEFAULT_ADAPTER = REPO / ".cache" / "models" / "TaoMate-H3"


class WorkerError(RuntimeError):
    pass


def split_devices(visible: str | None) -> tuple[str, str | None]:
    """Default placement: first 4 (or 8) devices for the student, 2+ leftovers for the teacher."""

    ids = [d for d in (visible or "").split(",") if d.strip()]
    if len(ids) >= 8:
        student, rest = ids[:8], ids[8:]
    elif len(ids) >= 4:
        student, rest = ids[:4], ids[4:]
    else:
        raise ValueError("TaoMate-H3 needs at least 4 visible GPUs for the student")
    teacher = ",".join(rest[: 2 * (len(rest) // 2)]) if len(rest) >= 2 else None
    return ",".join(student), teacher


class TaoMateH3Generator(Generator):
    def __init__(
        self,
        *,
        student_devices: str | None = None,
        teacher_devices: str | None = None,
        colocate_teacher: bool | None = None,
        model_root: Path = DEFAULT_MODEL_ROOT,
        adapter_dir: Path = DEFAULT_ADAPTER,
        python: Path = DEFAULT_PYTHON,
        width: int = 480,  # portrait 480x864, the README's benchmark canvas
        height: int = 864,
        seed: int = 8301,
        lookahead: bool = True,
        launch: bool = True,
        log_dir: Path | None = None,
        start_timeout: float = 1800.0,
        return_latents: bool = False,
        warmup_prompt: str | None = None,
    ) -> None:
        self.info = GeneratorInfo(name="taomate-h3", width=width, height=height,
                                  request_seconds=119 / 24,
                                  extra={"native_frames_per_request": 119, "lookahead": lookahead})
        if launch and student_devices is None:
            student_devices, auto_teacher = split_devices(os.environ.get("CUDA_VISIBLE_DEVICES"))
            if teacher_devices is None and not colocate_teacher:
                teacher_devices = auto_teacher
        self.student_devices = student_devices
        self.teacher_devices = teacher_devices or student_devices  # None -> colocated
        self.model_root = Path(model_root)
        self.adapter_dir = Path(adapter_dir)
        self.python = Path(python)
        self.seed = seed
        self.lookahead = lookahead
        self.launch = launch
        self.log_dir = Path(log_dir) if log_dir else REPO / ".cache" / "taomate_worker_logs"
        self.start_timeout = start_timeout
        self.return_latents = return_latents
        self.warmup_prompt = warmup_prompt
        self.warmup_s: float | None = None
        self.authkey = secrets.token_bytes(16)
        self.address: tuple[str, int] | None = None
        self.worker_info: dict[str, dict[str, Any]] = {}
        self.request_extras: dict[int, dict[str, Any]] = {}
        self.errors: list[dict[str, Any]] = []
        self._listener: Listener | None = None
        self._channels: dict[str, P.Channel] = {}
        self._procs: dict[str, subprocess.Popen] = {}
        self._ready: dict[str, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._out: asyncio.Queue[Chunk | Exception | None] = asyncio.Queue()
        self._timings: dict[int, RequestTiming] = {}
        self._prompts: dict[int, str] = {}
        self._teacher_done: dict[int, dict[str, Any]] = {}
        self._next = 0
        self._session = 0
        self._session_base = 0  # global index of local request 0 in this session
        self._taught = -1  # highest request index sent to the teacher
        self._generated = -1  # highest request index sent to the student
        self._student_done = -1  # highest request index the student finished
        self._clock_offset = time.monotonic() - time.time()
        self._futures: dict[str, asyncio.Future] = {}

    @classmethod
    def add_args(cls, p) -> None:
        p.add_argument("--taomate-student-devices", default=None,
                       help="comma list; default: split CUDA_VISIBLE_DEVICES (see split_devices)")
        p.add_argument("--taomate-teacher-devices", default=None)
        p.add_argument("--taomate-colocate-teacher", action="store_true")
        p.add_argument("--taomate-model-root", default=str(DEFAULT_MODEL_ROOT))
        p.add_argument("--taomate-adapter-dir", default=str(DEFAULT_ADAPTER))
        p.add_argument("--taomate-python", default=str(DEFAULT_PYTHON))
        p.add_argument("--taomate-width", type=int, default=480)
        p.add_argument("--taomate-height", type=int, default=864)
        p.add_argument("--taomate-seed", type=int, default=8301)
        p.add_argument("--taomate-no-warmup", action="store_true")

    @classmethod
    def from_args(cls, args) -> "TaoMateH3Generator":
        """Build from the unparsed ``--taomate-*`` options a CLI left in ``args.extra``."""
        import argparse

        p = argparse.ArgumentParser(add_help=False)
        cls.add_args(p)
        o, _ = p.parse_known_args(getattr(args, "extra", []) or [])
        warmup = None
        if not o.taomate_no_warmup:
            warmup = ("integrated_multimodal_description: [Shot 1] A person sits quietly at a desk, "
                      "reading a book in soft daylight.\n\noverall_soundscape: Quiet room tone.\n\n"
                      "non_diegetic_music: N/A")
        return cls(student_devices=o.taomate_student_devices, teacher_devices=o.taomate_teacher_devices,
                   colocate_teacher=o.taomate_colocate_teacher, model_root=Path(o.taomate_model_root),
                   adapter_dir=Path(o.taomate_adapter_dir), python=Path(o.taomate_python),
                   width=o.taomate_width, height=o.taomate_height, seed=o.taomate_seed,
                   warmup_prompt=warmup)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._listener = Listener(("127.0.0.1", 0), authkey=self.authkey)
        self.address = self._listener.address
        self._ready = {P.ROLE_TEACHER: asyncio.Event(), P.ROLE_STUDENT: asyncio.Event()}
        threading.Thread(target=self._accept_loop, daemon=True).start()
        if self.launch:
            self._spawn()
        waiter = asyncio.gather(*(event.wait() for event in self._ready.values()))
        deadline = time.monotonic() + self.start_timeout
        while not waiter.done():
            await asyncio.wait({waiter}, timeout=1.0)
            self._check_processes()
            if self.errors and not waiter.done():
                waiter.cancel()
                raise WorkerError(f"worker failed during start: {self.errors[-1]['message']}")
            if time.monotonic() > deadline:
                waiter.cancel()
                raise WorkerError("TaoMate-H3 workers did not become ready in time")
        if self.warmup_prompt:
            await self._warmup(self.warmup_prompt)

    async def _warmup(self, prompt: str) -> None:
        """Run one throw-away request (Triton JIT, CUDA graphs/allocator, VAE fusions), then
        reset so the caller's session starts at request 0 with a fresh KV/sink/teacher tail."""

        started = now()
        await self.submit(0, prompt)
        received = 0
        async for _chunk in self.chunks():
            received += 1
            if received == 4:
                break
        while self._student_done < 0:
            await asyncio.sleep(0.05)
        self.warmup_s = now() - started
        self.warmup_record = {"timing": self._timings.get(0), "extras": self.request_extras.get(0)}
        await self.reset()
        self._next = self._session_base = 0
        self._taught = self._generated = self._student_done = -1
        self._timings.clear()
        self._prompts.clear()
        self.request_extras.clear()

    def _worker_env(self, role: str, devices: str) -> dict[str, str]:
        env = os.environ.copy()
        assert self.address is not None
        env.update({
            P.ENV_ADDRESS: f"{self.address[0]}:{self.address[1]}",
            P.ENV_AUTHKEY: self.authkey.hex(),
            P.ENV_ROLE: role,
            "CUDA_VISIBLE_DEVICES": devices,
            "OMP_NUM_THREADS": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(REPO), str(REPO / "external" / "TaoMate-H3" / "src"),
                              env.get("PYTHONPATH")])
            ),
        })
        return env

    def _spawn(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        common = ["--width", str(self.info.width), "--height", str(self.info.height),
                  "--model-root", str(self.model_root)]
        plan = {
            P.ROLE_TEACHER: (self.teacher_devices, "teacher_service", common),
            P.ROLE_STUDENT: (self.student_devices, "student_service",
                             [*common, "--adapter", str(self.adapter_dir)]),
        }
        stamp = time.strftime("%Y%m%dT%H%M%S")
        for role, (devices, module, args) in plan.items():
            count = len(devices.split(","))
            command = [
                str(self.python), "-m", "torch.distributed.run", "--standalone",
                f"--nproc-per-node={count}", "--module",
                f"live_agent.generator.taomate_worker.{module}", *args,
            ]
            log = open(self.log_dir / f"{stamp}-{role}.log", "w")
            self._procs[role] = subprocess.Popen(
                command, env=self._worker_env(role, devices), stdout=log,
                stderr=subprocess.STDOUT, cwd=str(REPO),
            )

    def _check_processes(self) -> None:
        for role, proc in self._procs.items():
            code = proc.poll()
            if code is not None and not any(e.get("role") == role and e.get("exit") for e in self.errors):
                self.errors.append({"role": role, "exit": code,
                                    "message": f"{role} worker exited with code {code}"})

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while len(self._channels) < 2:
            try:
                conn = self._listener.accept()
            except (OSError, EOFError):
                return
            channel = P.Channel(conn)
            try:
                hello = channel.recv()
            except (EOFError, OSError):
                continue
            role = hello.get("role")
            if role not in (P.ROLE_TEACHER, P.ROLE_STUDENT) or role in self._channels:
                channel.close()
                continue
            self._channels[role] = channel
            self._post(role, hello)
            threading.Thread(target=self._reader, args=(role, channel), daemon=True).start()

    def _reader(self, role: str, channel: P.Channel) -> None:
        while True:
            try:
                message = channel.recv()
            except (EOFError, OSError, TypeError):  # TypeError: connection closed under us
                self._post(role, {"type": "disconnected"})
                return
            self._post(role, message)

    def _post(self, role: str, message: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(self._on_message, role, message)
        except RuntimeError:  # loop closed between the check and the call
            pass

    def _send(self, role: str, message: dict[str, Any]) -> None:
        channel = self._channels.get(role)
        if channel is None:
            raise WorkerError(f"{role} worker is not connected")
        channel.send(message)

    def _mono(self, t: float | None) -> float | None:
        return None if t is None else t + self._clock_offset

    # ------------------------------------------------------------------ message handling
    def _on_message(self, role: str, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == P.HELLO:
            self.worker_info.setdefault(role, {})["hello"] = message
            return
        if kind == P.READY:
            self.worker_info.setdefault(role, {})["ready"] = message
            self._ready[role].set()
            return
        if kind == "disconnected":
            if not getattr(self, "_closing", False):
                self._fail({"role": role, "message": f"{role} worker disconnected"})
            return
        if kind in ("flushed", "full_audio"):
            future = self._futures.pop(kind, None)
            if future is not None and not future.done():
                future.set_result(message)
            return
        session = int(message.get("session", -1))
        if kind == P.ERROR:
            if session == self._session:
                self._fail({"role": role, **message})
            return
        if session != self._session:
            return  # stale reply from a reset session
        k = int(message.get("request_index", -1))
        timing = self._timings.get(k)
        extras = self.request_extras.setdefault(k, {})
        if kind == P.TEACHER_DONE:
            if timing is not None:
                timing.t_teacher_start = self._mono(message["t_start"])
                timing.t_teacher_done = self._mono(message["t_done"])
            extras.update({
                "teacher_text_s": message["t_text_done"] - message["t_start"],
                "teacher_s": message["t_done"] - message["t_start"],
                "teacher_done_received": now(),
                "audio_latent_count": message.get("audio_latent_count"),
                "teacher_peak_allocated_gib": message.get("peak_allocated_gib"),
            })
            if self.return_latents:  # debug/parity: keep the opaque teacher payload
                extras["teacher_blob"] = message["blob"]
            self._teacher_done[k] = message
            self._dispatch()
        elif kind == P.REQUEST_START:
            if timing is not None:
                timing.t_student_start = self._mono(message["t"])
        elif kind == P.CHUNK:
            t_ready = now()
            chunk = Chunk(
                request_index=k,
                chunk_index=int(message["chunk_index"]),
                n_frames=int(message["n_frames"]),
                fps=float(message["fps"]),
                video=P.from_shm(message.get("video")),
                audio=P.from_shm(message.get("audio")),
                sample_rate=int(message.get("sample_rate", 32000)),
                t_ready=t_ready,
                meta={
                    "prompt": self._prompts.get(k, ""),
                    "session": session,
                    "local_index": message.get("local_index"),
                    "frame_start": message.get("frame_start"),
                    "audio_sample_start": message.get("audio_sample_start"),
                    "latent_count": message.get("latent_count"),
                    "audio_context": message.get("audio_context"),
                    "t_phase_start": self._mono(message.get("t_phase_start")),
                    "t_denoised": self._mono(message.get("t_denoised")),
                    "t_decoded": self._mono(message.get("t_decoded")),
                    "t_worker_ready": self._mono(message.get("t_ready")),
                },
            )
            if chunk.chunk_index == 0 and timing is not None:
                timing.t_first_chunk = t_ready
            extras.setdefault("chunks", []).append(
                {key: chunk.meta[key] for key in ("t_phase_start", "t_denoised", "t_decoded",
                                                  "t_worker_ready")} | {"t_ready": t_ready,
                                                                        "n_frames": chunk.n_frames})
            self._out.put_nowait(chunk)
        elif kind == P.REQUEST_DONE:
            if timing is not None:
                timing.t_done = self._mono(message["t"])
            extras.update({
                "audio_teacher_exact_match": message.get("audio_teacher_exact_match"),
                "frames_emitted": message.get("frames_emitted"),
                "student_peak_allocated_gib": message.get("peak_allocated_gib"),
                "latents": message.get("latents"),
            })
            self._student_done = max(self._student_done, k)
            self._dispatch()

    def _fail(self, error: dict[str, Any]) -> None:
        self.errors.append(error)
        self._out.put_nowait(WorkerError(f"{error.get('role')}: {error.get('message')}"))

    def _dispatch(self) -> None:
        """Send teacher and student work that has become eligible, in request order."""

        # teacher: all locked requests (lookahead) or only the one after the student's last
        limit = self._next - 1 if self.lookahead else min(self._next - 1, self._student_done + 1)
        while self._taught < limit:
            k = self._taught + 1
            if not self.lookahead and k > self._session_base and k - 1 > self._student_done:
                break
            self._send(P.ROLE_TEACHER, {
                "type": P.TEACH, "session": self._session, "request_index": k,
                "local_index": k - self._session_base, "prompt": self._prompts[k],
                "seed": self.seed,
            })
            self._taught = k
        # student: next request once its teacher output is available (student queues FIFO)
        while self._generated + 1 in self._teacher_done:
            k = self._generated + 1
            done = self._teacher_done.pop(k)
            self._send(P.ROLE_STUDENT, {
                "type": P.GENERATE, "session": self._session, "request_index": k,
                "local_index": k - self._session_base, "prompt": self._prompts[k],
                "seed": self.seed, "blob": done["blob"], "return_latents": self.return_latents,
            })
            self._generated = k

    # ------------------------------------------------------------------ Generator API
    async def submit(self, request_index: int, prompt: str) -> None:
        if request_index != self._next:
            raise ValueError(f"expected request {self._next}, got {request_index}")
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        self._timings[request_index] = RequestTiming(request_index, t_lock=now())
        self._prompts[request_index] = prompt
        self._next += 1
        self._dispatch()

    async def chunks(self) -> AsyncIterator[Chunk]:
        while True:
            item = await self._out.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    async def reset(self) -> None:
        self._session += 1
        self._session_base = self._next
        self._taught = self._generated = self._student_done = self._next - 1
        self._teacher_done.clear()
        for role in (P.ROLE_TEACHER, P.ROLE_STUDENT):
            self._send(role, {"type": P.RESET, "session": self._session})

    async def flush(self, timeout: float = 120.0) -> dict[str, Any]:
        """Ask the student for the held 5-frame video overlap (end of a session)."""

        return await self._request_reply("flushed", {"type": "flush"}, timeout)

    async def full_audio(self, timeout: float = 120.0) -> dict[str, Any]:
        """One-shot audio decode of the whole session (parity check against streaming)."""

        return await self._request_reply("full_audio", {"type": "full_audio"}, timeout)

    async def _request_reply(self, key: str, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert self._loop is not None
        future = self._loop.create_future()
        self._futures[key] = future
        self._send(P.ROLE_STUDENT, message)
        return await asyncio.wait_for(future, timeout)

    async def close(self) -> None:
        self._closing = True
        for role in list(self._channels):
            try:
                self._send(role, {"type": P.SHUTDOWN})
            except (WorkerError, OSError):
                pass
        for proc in self._procs.values():
            try:
                await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=120)
            except asyncio.TimeoutError:
                proc.terminate()
                try:
                    await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=30)
                except asyncio.TimeoutError:
                    proc.kill()
        for channel in self._channels.values():
            channel.close()
        if self._listener is not None:
            self._listener.close()
        self._out.put_nowait(None)

    @property
    def timings(self) -> list[RequestTiming]:
        return [self._timings[k] for k in sorted(self._timings)]

    @property
    def next_request_index(self) -> int:
        return self._next


__all__ = ["TaoMateH3Generator", "WorkerError", "split_devices"]

===== FILE: live_agent/sim.py =====
"""Simulated playback client (transport) for CPU tests and offline simulation.

Plays chunks in real time (optionally sped up), reports presentation start/end times to
the orchestrator, records stalls (gaps between chunks), and implements stop_playback()
(drops everything queued). Time scale: one simulated second = 1/speed wall seconds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from live_agent.types import BlockScript, Chunk, now


@dataclass
class Stall:
    t_start: float
    t_end: float


@dataclass
class SimClient:
    speed: float = 1.0
    orchestrator: object | None = None  # set after construction
    presented: list[tuple[int, int, float, float]] = field(default_factory=list)
    stalls: list[Stall] = field(default_factory=list)
    dropped: list[tuple[int, int]] = field(default_factory=list)
    recorder: object | None = None  # optional Recorder of the presented stream

    def __post_init__(self) -> None:
        self._q: asyncio.Queue[tuple[Chunk, BlockScript]] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._last_end: float | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._play())

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        await self._q.put((chunk, script))

    async def stop_playback(self) -> None:
        while not self._q.empty():
            ch, _ = self._q.get_nowait()
            self.dropped.append((ch.request_index, ch.chunk_index))

    async def _play(self) -> None:
        while True:
            ch, _script = await self._q.get()
            t0 = now()
            if self._last_end is not None and t0 - self._last_end > 0.05 / self.speed:
                self.stalls.append(Stall(self._last_end, t0))
            await asyncio.sleep(ch.duration_s / self.speed)
            t1 = now()
            self._last_end = t1
            self.presented.append((ch.request_index, ch.chunk_index, t0, t1))
            if self.recorder is not None:
                self.recorder.write(ch)
            if self.orchestrator is not None:
                self.orchestrator.on_presented(ch.request_index, ch.chunk_index, t0, t1)

    def close(self) -> None:
        if self._task:
            self._task.cancel()
        if self.recorder is not None:
            self.recorder.close()


class Recorder:
    """Writes the *presented* stream (what a viewer saw) to MP4: raw frames are piped to ffmpeg,
    audio is buffered and muxed on close. Needs an ffmpeg with libx264 (``/usr/bin/ffmpeg`` here)."""

    def __init__(self, path, ffmpeg: str = "/usr/bin/ffmpeg") -> None:
        from pathlib import Path

        self.path = Path(path)
        self.ffmpeg = ffmpeg
        self._proc = None
        self._audio: list = []
        self._sr = 32000

    def write(self, chunk: Chunk) -> None:
        """Non-blocking: frames are encoded on a background thread (the caller is the playback loop)."""
        import queue
        import threading

        if not hasattr(self, "_q"):
            self._q = queue.Queue()
            self._thread = threading.Thread(target=self._drain, daemon=True)
            self._thread.start()
        self._q.put(chunk)

    def _drain(self) -> None:
        while True:
            chunk = self._q.get()
            if chunk is None:
                return
            self._write(chunk)

    def _write(self, chunk: Chunk) -> None:
        import subprocess

        import numpy as np

        if chunk.video is None:
            return
        v = np.ascontiguousarray(chunk.video, dtype=np.uint8)
        if self._proc is None:
            _, h, w, _ = v.shape
            self._tmp = self.path.with_suffix(".video.mp4")
            self._proc = subprocess.Popen(
                [self.ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{w}x{h}", "-r", str(chunk.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt",
                 "yuv420p", "-preset", "veryfast", str(self._tmp)], stdin=subprocess.PIPE)
        self._proc.stdin.write(v.tobytes())
        if chunk.audio is not None:
            self._audio.append(np.asarray(chunk.audio, dtype=np.float32))
            self._sr = chunk.sample_rate

    def close(self) -> None:
        import subprocess
        import wave

        import numpy as np

        if hasattr(self, "_q"):
            self._q.put(None)
            self._thread.join()
        if self._proc is None:
            return
        self._proc.stdin.close()
        self._proc.wait()
        if not self._audio:
            self._tmp.replace(self.path)
            return
        a = np.concatenate(self._audio)
        a = a if a.ndim == 2 else a[:, None]
        wav = self.path.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(a.shape[1])
            w.setsampwidth(2)
            w.setframerate(self._sr)
            w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
        subprocess.run([self.ffmpeg, "-y", "-loglevel", "error", "-i", str(self._tmp), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-shortest", str(self.path)], check=True)
        self._tmp.unlink()
        wav.unlink()

===== FILE: live_agent/server/app.py =====
"""Live-agent server: FastAPI + WebSocket, one session per connection.

Wire protocol (WS /ws), JSON text frames unless noted:
  client -> server
    {"type":"hello","mode":"private"|"public","user_id":"u1"}
    {"type":"speech_start"}                        barge-in (push-to-talk pressed)
    binary frame                                   recorded speech (webm/opus or wav) -> ASR
    {"type":"text","text":"..."}                   typed utterance (fallback / tests)
    {"type":"chunk_start","request":k,"chunk":c}   presentation start (server stamps arrival)
    {"type":"chunk_end","request":k,"chunk":c}     presentation end
    {"type":"ping","t":...}
  server -> client
    {"type":"chunk","request":k,"chunk":c,"n_frames":n,"fps":24,"sample_rate":sr,
     "width":w,"height":h,"transcript":"..."}      followed by n binary JPEG frames and one binary PCM16 frame
    {"type":"stop"}                                 drop everything queued (barge-in)
    {"type":"transcript","text":"..."}             ASR result of the user's speech
    {"type":"status", ...}

Presentation times are stamped with the *server* monotonic clock on arrival of the
client's chunk_start / chunk_end messages (network delay is logged via ping RTT).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import SessionView
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import BlockScript, Chunk, Utterance, new_id, now

log = logging.getLogger("live_agent.server")
STATIC = Path(__file__).parent / "static"


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def to_pcm16(audio: np.ndarray | None, n_samples: int) -> bytes:
    if audio is None or len(audio) == 0:
        return np.zeros(n_samples, dtype=np.int16).tobytes()
    a = audio.mean(axis=1) if audio.ndim == 2 else audio
    return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()


class WSTransport:
    """Orchestrator transport over one WebSocket connection."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.orchestrator: Orchestrator | None = None
        self._send_lock = asyncio.Lock()
        self._starts: dict[tuple[int, int], float] = {}
        self._epoch = 0  # incremented on stop; stale sends are skipped

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        epoch = self._epoch
        frames = chunk.video if chunk.video is not None else np.zeros((chunk.n_frames, 8, 8, 3), np.uint8)
        # Encode off the event loop.
        loop = asyncio.get_running_loop()
        jpegs = await loop.run_in_executor(None, lambda: [encode_jpeg(f) for f in frames])
        pcm = to_pcm16(chunk.audio, int(chunk.duration_s * chunk.sample_rate))
        async with self._send_lock:
            if epoch != self._epoch:
                return
            h, w = frames.shape[1:3]
            await self.ws.send_text(json.dumps({
                "type": "chunk", "request": chunk.request_index, "chunk": chunk.chunk_index,
                "n_frames": len(jpegs), "fps": chunk.fps, "sample_rate": chunk.sample_rate,
                "width": int(w), "height": int(h), "transcript": script.transcript}))
            for j in jpegs:
                await self.ws.send_bytes(j)
            await self.ws.send_bytes(pcm)

    async def stop_playback(self) -> None:
        self._epoch += 1
        async with self._send_lock:
            await self.ws.send_text(json.dumps({"type": "stop"}))

    def on_client_message(self, msg: dict) -> None:
        t = now()
        key = (int(msg.get("request", -1)), int(msg.get("chunk", -1)))
        if msg["type"] == "chunk_start":
            self._starts[key] = t
        elif msg["type"] == "chunk_end" and self.orchestrator is not None:
            self.orchestrator.on_presented(key[0], key[1], self._starts.pop(key, t), t)


def build_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI()
    cfg_dir = Path(args.config)
    canon = json.loads((cfg_dir / "canon.json").read_text(encoding="utf-8"))

    app.state.shared_gen = None
    app.state.session_lock = asyncio.Lock()

    @app.on_event("startup")
    async def _startup() -> None:
        # Heavy generators are started once and shared (reset per session); the mock is per session.
        if args.generator != "mock":
            gen = make_generator(args)
            await gen.start()
            app.state.shared_gen = gen

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.shared_gen is not None:
            await app.state.shared_gen.close()

    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hello = json.loads(await ws.receive_text())
        mode = hello.get("mode", "private")
        session_id = new_id("sess")
        transport = WSTransport(ws)

        from live_agent.llm import OpenAICompatLLM

        llm = OpenAICompatLLM(args.llm_url, args.llm_model)
        manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
        if args.dev_allow_uncalibrated:
            manifest.min_status = Status.DOCUMENTED
        ledger = StateLedger.from_config(cfg_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"],
                            mode=DirectorMode(args.director_mode))
        if app.state.shared_gen is not None:
            if app.state.session_lock.locked():
                await ws.send_text(json.dumps({"type": "error", "error": "generator busy (one live session at a time)"}))
                await ws.close()
                return
            await app.state.session_lock.acquire()
            generator = SessionView(app.state.shared_gen)
        else:
            generator = make_generator(args)
        sched = LockScheduler(SchedulerConfig(request_s=generator.info.request_seconds,
                                              lambda_prior_s=args.lambda_prior))
        judge = speech = corrector = None
        if args.vlm_url:
            from live_agent.qc.judge import VLMJudge

            judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model))
        asr = None
        if args.asr_url:
            from live_agent.asr import OpenAIASR
            from live_agent.qc.judge import SpeechCheck

            asr = OpenAIASR(args.asr_url, args.asr_model)
            speech = SpeechCheck(asr.transcribe_sync)
        from live_agent.qc.judge import ForwardCorrector

        corrector = ForwardCorrector(llm)
        log_dir = Path(args.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        orch = Orchestrator(generator, director, sched, transport, judge=judge, corrector=corrector,
                            speech_check=speech, memory=make_memory(args, hello, session_id),
                            log=EventLog(log_dir / f"{session_id}.jsonl"),
                            cfg=OrchestratorConfig(session_id=session_id, scope=mode,
                                                   correction_mode=CorrectionMode(args.correction_mode)))
        transport.orchestrator = orch
        await orch.start()
        await ws.send_text(json.dumps({"type": "status", "session": session_id, "mode": mode,
                                       "generator": generator.info.name}))
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    if asr is None:
                        continue
                    from live_agent.asr import decode_audio_bytes

                    audio = decode_audio_bytes(msg["bytes"], 16000)
                    text = await asr.transcribe(audio, 16000)
                    await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                    if text:
                        await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, now(),
                                                               session_id=session_id, scope=mode))
                    continue
                data = json.loads(msg["text"])
                t = data.get("type")
                if t in ("chunk_start", "chunk_end"):
                    transport.on_client_message(data)
                elif t == "speech_start":
                    await orch.on_speech_start()
                elif t == "text" and data.get("text", "").strip():
                    await orch.on_user_utterance(Utterance(new_id("utt"), "user", data["text"].strip(),
                                                           now(), session_id=session_id, scope=mode))
                elif t == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": data.get("t")}))
        except WebSocketDisconnect:
            pass
        finally:
            await orch.stop()
            if app.state.shared_gen is not None:
                app.state.session_lock.release()

    return app


def make_generator(args: argparse.Namespace):
    if args.generator == "mock":
        from live_agent.generator.mock import MockGenerator

        return MockGenerator(size=(480, 864))
    if args.generator == "taomate_h3":
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        return TaoMateH3Generator.from_args(args)
    raise ValueError(args.generator)


def make_memory(args: argparse.Namespace, hello: dict, session_id: str):
    if not args.memory_db:
        return None
    from live_agent.memory_bridge import MemoryBridge

    return MemoryBridge(args.memory_db, user_id=hello.get("user_id", "anon"),
                        stream_id=hello.get("stream_id", "stream-0"), session_id=session_id)


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3"])
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--asr-url", default="http://127.0.0.1:8103/v1")
    p.add_argument("--asr-model", default="qwen3-asr")
    p.add_argument("--memory-db", default=".cache/memory.sqlite")
    p.add_argument("--log-dir", default=".cache/sessions")
    p.add_argument("--director-mode", default="closed_loop", choices=["closed_loop", "open_loop"])
    p.add_argument("--correction-mode", default="gradient", choices=["gradient", "repeat", "none"])
    p.add_argument("--lambda-prior", type=float, default=3.0)
    p.add_argument("--dev-allow-uncalibrated", action="store_true",
                   help="allow capabilities that were never executed (development only)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8200)
    # TaoMate-H3 generator options are parsed by the adapter (see taomate_h3.py).
    args, rest = p.parse_known_args()
    args.extra = rest
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
