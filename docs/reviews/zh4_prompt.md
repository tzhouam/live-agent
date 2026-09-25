You are GPT-6 Sol, the INDEPENDENT REVIEWER for the "live-agent" project (AGENTS.md rules: read-only; numbered findings tagged blocking/major/minor). ROUND 4 (zh4) of the review of the owner-directed Chinese rewrite (TaoMate-H3 base + Google agentic suite, D-017).
Note: in round 3 you reviewed text where the author's v2.2 edits had silently failed to apply; the review log now records that error. This round reviews v2.3, where the edits were applied and verified.
1. For each item in the zh3 table at the end of the inlined docs/codex_reviews.md (carried zh2 items, zh3 #3, #4, #7, #8, #9), state RESOLVED / PARTIALLY / NOT RESOLVED by checking the proposal text itself.
2. Report any NEW blocking or major issue (internal inconsistency between §1.2, §4, §5.4, §6.4, §7, §8, §9; unlabelled numbers; claims beyond evidence).
3. Verdict: ready / ready with minor fixes (list them exactly) / not ready. Be concise.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/research_proposal_zh.md =====
# 在线智能体导演：基于 TaoMate-H3 的实时个性化直播数字人

**研究提案（中文版 v2.0，2026-09-25）**

*v2.3：已按 GPT-6 Sol 评审（zh1–zh3）修订。本版依据项目负责人的指示重写（决策 D-017）。生成底座由 LingBot-World 2.0 改为 TaoMate-H3，系统架构借鉴 Google 长视频智能体套件（Co-Director / CANVAS / A²RD / VQQA）。英文 v1.0（`docs/research_proposal.md`）保留为上一版。*

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
| 在 8×H20、480×864 上生成 10 秒：DiT 用时 14.81 秒【引用】（约 16.2 FPS，≈0.68× 实时【推导】），首帧可播 17.29 秒（来自单独的基准测试，不是发布的一次性输出路径），首个最终块 6.15 秒。**这几个数字都不含内部音频准备**，而且发布路径的输出要到最后才写出 | 仅看 DiT 就**不是实时**；完整流水线（教师 + 学生 + 编码）更慢，需在 M0 实测 | 【引用】TaoMate-H3 README / 模型卡 |

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

**首个演示的范围。** 只包含 **M1 端到端资格**认定为实时的配置（§6.4）。

**未通过时的「近实时」服务规则。** 如果完整流水线的吞吐达不到每 5 秒一个请求（8×H20 上仅 DiT 就约 7.4 秒 / 请求【推导】），持续的对话会让队列无限增长，所以需要明确的规则：
- **话轮制：** 人设说完一段后进入「倾听」，用户说完才生成下一段。不维持连续的 5 秒节奏，等待时间如实显示。
- **准入控制：** 同时最多有 1 条未执行的指令。更新的指令取代旧指令，被取代的记为「已跳过」。
- **降速播放：** 可选，把播放帧率降到生成速率，但不低于 20 fps，并测量主观质量。
- 反应片段只用来掩饰短暂等待，**不**计入 TFMR。

E2 在持续交互下测量等待时间的增长与 TFMR。

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
| **RQ1 在线导演（主）** | **H1a** 完整在线导演（A2）的**指令级成功率**高于开环（A1：LLM 直接写块提示）。拒绝与降级都算失败。**H1b** 虚假完成声明率更低。**H1c** 消融后下降：去掉清单、去掉质检、去掉前向修正、去掉账本，各自都会下降 | A2−A1 成对差的 95% CI 含 0 或为负；FCR 不降；消融无下降 |
| **RQ2 前向修正** | **H2** 在同一个、事先定义的失败点上，**随机分配**「前向语义梯度修正」或「重复原指令」，比较在**最早可接收修正的请求**（按 §5.4 时间线确定，并如实报告它是第几个请求）中的补救率 | 补救率差的 CI 含 0 |
| **RQ3 时延与粒度（主）** | **H3a** 在 H3 上，TVC 由 §6.4 的单时间线模型预测，中位数误差 ≤ 1 个请求周期。**H3b（有前提）** 先在 TaoMate-LTX 上证实可以逐块（约 1 秒）换提示，再在**同一骨干内**比较 1 秒与 5 秒提示粒度：细粒度的 TVC 中位数更低，且遵循率**非劣**（边际 5 pp，事先做功效计算）。H3 与 LTX 之间的比较只作系统级描述 | 预测误差 > 1 周期；逐块换提示不可行（报告为发现）；TVC 无差异，或遵循率劣于边际 |
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
   - 编译时为每条指令生成 1–3 个可检验问题，例如「这一块中人物是否举杯喝茶？」；
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
- 请求 $k$ 的第 $c$ 块在 $V_k + c\Delta$ 时可见，$\Delta$ 为单块时长，约 1.4 秒。
- 修正链条耗时 $C = v + $ 修正合成 $+$ 编译 $+$ 内容审核 $+$ 文本编码，其中 $v$ 为 VLM 判定时间。
- 修正进入**第一个满足** $P_j \ge V_k + c\Delta + C$ 的请求 $j$。$j$ 可以是 $k+1$、$k+2$ 或更晚，**不设上限**。
- 在即时锁定下，进入 $k+1$ 的条件是 $c\Delta + C \le R - \Lambda - \sigma$。早锁定下，**不可能**进入 $k+1$。
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

- **预渲染反应片段库。** 离线用同一底座、同一人设生成「点头倾听」「思考」「稍等」等 1–3 秒片段，由客户端在打断或等待时切入。它只提供**视觉确认**，不算有意义的回应。
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

### 6.4 时延模型【推导】（数值仅作示意，由 M0 实测替代）

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

**两阶段资格（按实现顺序）。**
1. **M0：组件剖析**（不是资格认定）。在发布路径上分别测教师、学生、编码的耗时与显存。发布路径先准备全部音频，最后写一个 MP4【代码：`cli.py:219-229`、`runner.py:293-330`】，所以 M0 **无法**测端到端的 Λ 与呈现时间。
2. **M1：端到端资格。** T1–T3 完成后，在真实的客户端播放路径上测 Λ、σ、吞吐与抖动，并做 ≥ 3 × 30 分钟浸泡测试，卡顿 ≤ 1 次 / 10 分钟。

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
- 在发布路径上，4 卡与 8 卡各跑 3 次 × 60 秒的 TaoMate-H3 生成【目标】，**分组件**剖析：音频教师、学生每块、VAE 解码、编码各自的耗时，以及教师与学生同时常驻时的显存。这些结果只用于估计 Λ，端到端资格在 M1 认定（§6.4）。
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

**结果规则：**

| 情况 | 处理 |
|---|---|
| 拒绝或降级 | 计为失败 |
| 被用户取代 | 按最终意图计分 |
| 评判「无法判断」 | 主分析计为失败，另做敏感性分析 |
| 从未遵循 | 在截止时间 $D$ 处删失 |

**指标：**
- 指令级成功率；
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
  5. 无账本的文本纠偏（按相同频率随机插入重述，作为对照）；
  6. 账本 + 会话重置；
  7. 无账本、同频率的会话重置。

  这样可以把账本的作用与纠偏、重置的作用分开。TaoMate-LTX 学习型记忆只作描述性对照。会话数按会话级精度计算确定（预试估计方差后，目标 ≥ 10 场 × 30–60 分钟【目标】）。
- 指标：
  - 人脸身份相似度，阈值用人工同一/不同标注校准；
  - **语音保真与内容**：生成语音的 ASR 转写相对台词的 WER；跨会话、跨重启的说话人一致性（嵌入 + 人工同一/不同判断）；讲解类内容的事实正确性（评分细则 + 人工）；
  - 服饰、场景、道具状态探针；
  - 声音一致性（说话人嵌入）；
  - 口型同步 LSE-C/D；
  - 接缝与卡顿。
- **核心假设的检验：** 在 ≥ 3 次会话重启之间（每次都是新上下文）检验记忆与遵循阈值。未包装的端到端系统若有权重，按原样参与；否则检验较弱的消融版本（A2 对去掉记忆服务的 A1），并如实标明其较弱。

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
| 指令级成功率（H1a，主） | A2 − A1 ≥ +10 pp，成对 CI 不含 0 |
| 虚假完成声明率 FCR | A2 ≤ 5% 且低于 A1；声明覆盖率 ≥ 70% |
| 前向修正补救率（H2） | 在最早可接收修正的请求中，补救率高于「重复原指令」，CI 不含 0；同时报告该请求是第几个 |
| TVC（动作类） | H3，L = 0，并且 M0 实测 Λ ≤ 3 秒时：15 秒内截止成功率 ≥ 80%，KM 中位 ≤ 8 秒。L = 1 或 Λ 更大时：M0 后按实测重设。LTX 只作描述 |
| 首个有意义回应 TFMR | 生成的回应语音开始播放的时间：p50 ≤ 8 秒（前提同 TVC） |
| 视觉确认（反应片段或停帧） | p95 ≤ 1 秒；与 TFMR 分开统计 |
| 语音保真 | 生成语音的 ASR-WER 相对台词 ≤ 10%；跨会话说话人一致性 ≥ 80%（人工判断） |
| 讲解正确性与安全 | 事实错误率与不安全内容率单独报告；块脚本在进入生成前先过内容审核 |
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
| M2 | ≈ 3 周 | B0/A1/A2、账本、记忆服务、语音链路、反应片段库 |
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
| 教师与学生同时常驻时显存或算力不足 | 中 | M0 实测；分卡部署；降分辨率 |
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

本中文 v2.0 属于重大架构变更。它提交 GPT-6 Sol（Codex）独立评审，记录见 `docs/codex_reviews.md` 的「中文 v2.0」一节。

===== FILE: docs/notes/taomate_deep_dive.md =====
# TaoMate and TaoMate-H3: a deep dive for building a live persona agent

Compiled on 2026-09-25. This was a read-only study: I ran nothing on a GPU and downloaded no weights. The one hardware query was `nvidia-smi --query-gpu`, and it reports 8× L20X with compute capability 8.9.

This document supersedes and refines `taomate_h3_assessment.md`. Where the two disagree, trust this one, because it is based on reading the code.

## Sources and commit hashes

| Source | Revision |
|---|---|
| Paper, arXiv 2607.24359v1 (27 Jul 2026). HTML at https://arxiv.org/html/2607.24359 and the PDF (9 pages, no supplementary material) | v1 |
| Project page https://taoliveaigc.github.io/TaoMate/ | fetched 2026-09-25 |
| `external/TaoMate-H3` | `6b2f9984acf681e2f387188f5d1f3b26e504315b` (2026-09-23) |
| `external/TaoMate` (the LTX-2.3 paper model and its interactive demo) | `136d89083f13c6d3eceb7cfe8a0ef4ac2ea0bfdd` (2026-09-08) |
| HF `TaoLiveAIGC/TaoMate-H3` (API sha) | `7d7a51f3e63972138882ec2f0e4d1d47728110cf`. `config.json` = `{"rank":128,"alpha":128.0,"weight_source":"generator_ema","optimizer_step":3000}` |
| `external/vllm-omni` | local HEAD `7b4dc7633`; fetched `origin/main` `3bd5ac968` (2026-09-25) |

Paths below are relative to `external/TaoMate-H3/src/taomate_h3/` (**H3:**), to `external/TaoMate/` (**TM:**) or to `external/vllm-omni/` (**VO:**).

**The single most important point.** There are two different systems:
- **TaoMate** (paper and repo) is LTX-2.3-based. It has learned persistent memory, an interactive demo, and claims real-time speed.
- **TaoMate-H3** is a 3-step LoRA plus a streaming runtime on MiniMax H3. It has **none** of the paper's learned memory. It is **not real-time** on the validated hardware, and its audio comes from a separate pre-pass with the base model.

---

## 1. The TaoMate paper (arXiv 2607.24359)

### Architecture
- **Backbone.** "The causal generator is initialized from a distilled LTX-2.3 checkpoint and optimized against a frozen bidirectional teacher using three denoising steps per block" (§4.1). Table 1 lists it at 22.1B parameters (the LTX-2.3 base is 22B).
- **Memory modules.** "Residual memory attention is inserted every four transformer layers, giving 12 memory-enabled layers in the 48-layer backbone. The video branch receives 48 tokens formed by the visual anchor and dynamic video state, while the audio branch receives 64 dynamic-state tokens; together with the modality encoders and video FiLM, these branches add approximately 97.8M trainable parameters" (§4.1).
  - Note that the 48 video tokens are **anchor plus dynamic state together**, not 48 dynamic tokens.
  - In code, pooling gives 24 anchor + 24 EMA tokens at 512×768, which is 48 in total (TM `taomate/runtime_support/learned_memory.py:192-209,550-563`).
- **Memory state.** M_t = (a^v, a^a, m^v_t, m^a_t, κ_t, π_t) (§3.2, Eq. 2). "The visual anchor a^v and audio reference a^a retain canonical evidence from the initial block."
  - The anchor is formed from the **first generated block**. It is not a user image.
- **Update rule.** Anchor-regularized EMA: E(m,a,s;β,λ) = (1−λ)[(1−β)m+βs]+λa (Eq. 4).
  - The video rate is gated by cosine agreement with the anchor (Eq. 5). Audio is ungated.
  - Hyperparameters: (β_v,λ_v)=(0.15,0.20), (β_a,λ_a)=(0.10,0.10), (τ,T_g,g_min)=(0.05,0.10,0.10), appearance (β_c,λ_c)=(0.03,0.60) (§4.1).
- **Conditioning.** h̃ = h + MemAttn(RMSNorm(h), u_{t−1}) for each modality, plus a reference-aware FiLM on video (§3.3, Eq. 6).
  - "Memory K/V remain outside the active cache, so fixed token counts keep the additional cost independent of generated duration."
  - "Both pathways are residual and initialized as identity mappings."
- **Active context.** "At a prompt transition, the active context retains the initial visual reference and at most two recent non-anchor blocks. Only completed blocks update the persistent memory, and local RoPE coordinates restart for each prompt-conditioned segment" (§4.1).
  - The code does not match this. The TM code keeps absolute RoPE on the persistent-cache path (see §3).
- **Training** (§3.4, §4.1):
  - Method: DMD on causal self-rollouts, plus video PCM with weight 0.03 from step 400.
  - Teacher classifier-free guidance: 3.0 for video, 5.0 for audio.
  - Rollout horizons: 5 or 10 blocks, with probability 0.8 / 0.2.
  - Student-prefix substitution happens with probability 0.1. Reused history is re-noised with σ~U(0,0.15). The anchor is kept clean.
  - Data: 6,139 synthetic LTX-2.3 teacher trajectories of up to 241 frames at 768×512, 24 fps.
- **Stage-parallel execution** (§3.5): "every pipeline rank is assigned one denoising stage and maintains an independent video–audio KV cache… Tasks satisfying b+k=d therefore form an anti-diagonal wavefront… the final stage continuously retires clean blocks."
  - With 3 denoising steps this means 3 stages, which gives the 3 GPUs.
  - The text says "the prefix consists of the initial reference sink and up to recent blocks". **The number is missing from both the HTML and the PDF.** §4.1 says "at most two".
- **Block size.** The paper never gives frames per block. The code gives it: 3 latent frames = 24 px frames ≈ 1 s per block (the first block is 4 latents), 5 blocks per ~5 s window (TM `taomate/inference/runtime.py:46-53`).
- **Prompt format.** "every prompt specifies the action, transcript, subject appearance, scene, camera, and voice for one short segment. The subject, scene, camera, and voice descriptions remain consistent across the sequence, while the action and spoken content evolve" (§4.1).
  - Speech is generated jointly from the transcript in the prompt. There is no audio input or TTS (§3.1: "autoregressive audio-video generation from a temporally ordered sequence of text prompts").
- **Throughput and latency:**
  - Single device (RTX PRO 5000 72GB): "130.3±1.3 seconds per 1,441-frame output… 11.1 generated frames per second" (§4.1).
  - DiT FPS: 16.32 (Table 1).
  - Stage-parallel: "TaoMate reaches 35.0 output FPS on three GPUs… the complete 1,441-frame generation pipeline finishes in approximately 41.2 seconds" (§4.3, Table 2).
  - **The GPU type for the 35 FPS result is not stated.** Table 2 is headed "Multi-GPU end-to-end inference throughput". Latency to first frame is not reported.
- **Metrics** (Table 1, 768×512, 60 s Mandarin and English single-presenter scripts):
  - TaoMate: LipSync 5.918, Desync 0.000, Align 5.00, Express 4.00, Long Consistency 0.9755, Color Δ 0.00260, DiT FPS 16.32.
  - Best baselines: LiveAvatar 5.396 / 0.9619 / 0.00541 / 4.529 FPS; OmniForcing 1.590 / 0.3404 / 0.02060 / 8.14.
  - Metrics come from VABench. Color Δ and Long Consistency definitions are "in the supplementary", which is not public.
  - **The project page shows different TaoMate numbers:** LipSync 5.773, Long Consistency 0.9520, Color Δ 0.00483.
- **Ablation** (Table 3; Long Cons. / Color Δ / Face Cons.):

  | Configuration | Long Cons. | Color Δ | Face Cons. |
  |---|---|---|---|
  | No memory | 0.9614 | 0.00380 | 0.9955 |
  | + memory | 0.9653 | 0.00316 | 0.9956 |
  | + FiLM | 0.9620 | 0.00347 | 0.9947 |
  | + gate | 0.9676 | 0.00276 | 0.9962 |

  These are small effects. The memory mostly stabilizes colour, not identity.
- **Longest duration:**
  - Fig. 1: "remains stable over 1,000 seconds".
  - Project page: ">30 min uninterrupted single generation" (a 30-minute narration demo).
  - The evaluation itself uses 60 s.
- **Limitations.** The paper has **no limitations section**. Limitations I infer:
  - The anchor is the first generated block, so there is no user-supplied identity.
  - There is no voice reference.
  - Validation covers single-presenter, static-camera scripts only.
  - The benchmark and the supplementary material are not public.

---

## 2. TaoMate-H3 code (commit 6b2f998)

### Entry point and CLI
- `python -m taomate_h3` → `cli.main`. Arguments, all required unless a default is given:
  - `--prompt` or `--prompt-json`, mutually exclusive (cli.py:29-44)
  - `--duration`, a multiple of 5
  - `--resolution`, default 768x1376; short edge 480, 768 or 1088
  - `--gpus {4,8}` (cli.py:52)
  - `--devices`, `--model-root`, `--adapter`, `--seed` (default 8301), `--output`
- **Prompt JSON schema:** `{"prompts": [str,...], "seeds": [int,...]?}`. You need exactly one prompt per 5 s (config.py:80-134).
- The example prompts follow MiniMax H3's own "integrated_multimodal_description / overall_soundscape / non_diegetic_music" format. Speech goes inline as `<d>[Chinese] …</d>` (examples/prompts_10s.json).
- **Process flow** (cli.py:219-229):
  1. A torchrun job (`taomate_h3.teacher`) generates **audio guidance** for **all** prompts into a directory under `/dev/shm`.
  2. A second torchrun job (`taomate_h3.worker` → `runner.run_direct`) generates the video.

### Block and chunk structure
- A **request** is 5 s (`DirectPolicy.request_seconds=5`, config.py:22). Each request is split into **4 chunks** with `chunk_group_counts=(2,2,2,1)` groups of 17 frames (config.py:23; streaming/geometry.py:173-200).
  - **Request 0:** 39 + 34 + 34 + 17 = 124 native frames. That is 12 + 10 + 10 + 5 = 37 video latents; the first chunk carries a 5-frame / 2-latent prefix.
  - **Later requests:** 119 frames (35 latents) (geometry.py:30-84).
  - Audio latents are 40 Hz (geometry.py:9). A request has 207 audio latents, or 198/199 in steady state.
- **Published timing.** Native frames (124 + 119·(n−1)) are time-compressed to exactly 24 fps × duration by ffmpeg `setpts` and `atempo` (inference/media_timing.py:8-41; runner.py:158-235).
  - For 10 s this means 243 native frames become 240 published frames, a warp of about 1.2%.
- **3-step schedule.** The 50-point shifted ladder is sampled at `DISTILLED_STATE_INDICES=(0,16,33,49)` (denoise_schedule.py:7), with shift 12 for video and 3 for audio (model/pipeline.py:394-403).
  - Computed sigmas: video [1, 0.9612, 0.8533, 0]; audio [1, 0.8609, 0.5926, 0].
  - Each step is a single positive branch with **no CFG** (model/denoise.py:271-351).
  - Each chunk gets 3 noisy forwards plus 1 clean (σ=0) forward that commits KV (streaming/runtime.py:663-702).
  - The README's "24 generation forwards and eight clean-KV updates" for 10 s matches: 2 requests × 4 chunks.

### State that carries across chunks and requests (what is actually implemented)
- **`CleanAVKVCache`** holds dense BF16 K/V for the 50 main layers and **only clean media tokens** (streaming/cache.py:77-204). Text is not cached.
  - The retention rule is `retain_sink_and_recent_commits`: once 3 or more chunks exist, **chunk 0 of the whole session is kept as a video-only sink** and the **2 most recent chunks** keep full A/V (cache.py:206-219; called at runtime.py:714).
  - Policy strings: `video_kv_retention="first_video_sink_plus_recent_2_chunks"` (config.py:27).
- **Audio KV reset.** Audio history is dropped every 12 requests, i.e. every 60 s (config.py:29; runtime.py:584-588).
- **Prefix renormalization.** Each clean chunk's video latents get a per-channel affine fix to the mean/std of the **first chunk** (runtime.py:451-462, 675-678; `prefix_normalization="affine_to_first_stream_chunk"`).
  - This is the only anchor-like statistic. It is parameter-free.
- **Attention hook.**
  - Media queries attend to [current text/condition K/V] + [persistent clean A/V K/V] + [current media K/V].
  - Condition queries attend only to the condition (streaming/attention_hook.py:179-216).
  - It uses dense FA3 with `causal=False`.
- **RoPE is global and absolute.**
  - Video and audio positions continue on one timeline (runtime.py:209-234).
  - The current prompt's text positions are right-aligned just before the request's media origin (runtime.py:155-163).
  - There is no local restart.
  - The sink keeps its original positions. K is cached after RoPE, because RoPE is applied before the hook (model/layers.py:400-430).
- **Not implemented in H3:** anchor/memory tokens, MemAttn, FiLM, the gated EMA, and stage-parallel execution. grep finds no memory module anywhere in `src/`.
  - **TaoMate-H3 is "sink + 2-recent rolling clean KV + first-chunk colour renorm".**

### Audio: it is **not** generated by the streaming student
- `teacher.py` loads **base MiniMax H3 FL2VA in BF16 without the LoRA** (`transformer_load_w8a8_policy=None`, teacher.py:420-427).
- It runs a **10-state, 9-forward audio-only** denoise per 5 s request, with an empty video (teacher.py:352-381).
  - From request 1 onwards it conditions on the **previous request's last 40 audio latents (1 s)** as a frozen prefix (`tail40_rollover`, teacher.py:255-273, 295-300, 333-343).
  - It saves the milestones at states (3, 6, 9) to `request_XX.pt` (teacher.py:461-472).
- The streaming student then **overwrites its audio rows** with those milestones after each of its 3 steps (runtime.py:339-359, 657-673).
  - It **asserts the published audio equals the teacher's clean latent** (runtime.py:739-743).
  - Milestones are validated against the prompt text and seed (inference/base10_teacher.py:158-179).
- **Consequence.** Speech and voice come from base H3 audio-only generation. The 3-step student produces video conditioned on that audio through joint attention. This is the README's "integrated audio guidance".
  - The README says the benchmark "excludes the command's internal audio preparation", so the teacher pass is **not in** the 17.29 s first-playable number.

### Mid-stream prompt injection: none today
- **There is no server, queue, socket or callback.** grep for queue, socket, asyncio and http finds nothing.
- All prompts are fixed up front in three places:
  1. **Text encoding.** `runtime.precompute_text_prompts(config.prompts)` encodes every prompt, then offloads the Qwen3-VL text encoder to CPU (runner.py:293; runtime/direct.py:239-262; model/pipeline.py:101-104).
  2. **Audio teacher.** It is precomputed for all prompts in a separate process before the worker starts (cli.py:223-229).
  3. **The loop where the next prompt is consumed** is `runner.py:299-323`:
     ```python
     for request_index, (text_features, request_seed) in enumerate(zip(precomputed, config.request_seeds, strict=True)):
         ... runtime.generate_latents(..., precomputed_text=text_features, denoise_loop=streaming.run)
     ```
     Inside it, `H3StreamingRuntime.run` (streaming/runtime.py:482-834) builds each chunk's branch from the same `positive` at runtime.py:609-621.
- **Chunk-level prompt swaps are structurally possible,** because the text is not cached in the KV and the branch is rebuilt per chunk. But the audio milestones are per 5 s request, so a **practical** change can only happen at a 5 s request boundary unless the teacher is also chunked.
- **How hard is it to add an injection API? Moderate.** Required changes:
  - (a) Replace the `for` loop with a blocking pop from a rank-0 queue, then `broadcast_object_list` to all 8 ranks. The pattern already exists in `runtime.broadcast`.
  - (b) Keep the text encoder resident, or encode on another device, instead of `_offload_text`. Encode each new prompt when it arrives.
  - (c) Make the audio teacher incremental and resident. It needs its own BF16 base-model copy and the previous 40-latent tail. It must run one request ahead of the student, which is also where the lookahead latency comes from.
  - (d) Drop the assertions that tie prompt, seed and index to a precomputed list (base10_teacher.py:177; runner.py:134-150).
  - (e) Stream output per request or per chunk instead of `_publish` (see below).
  - `H3StreamingRuntime` already holds all cross-request state (`_cache`, offsets, transport rows), so it can be reused unchanged.

### Output
- **Publication is one-shot.** All latents are concatenated, then one video VAE decode, one audio VAE decode on rank 0, one H.264+AAC mux, and a strict ffprobe/decode check (runner.py:124-263, 327-334).
- **There is no chunk streaming output in the repo.**
- The "first playable video" row in the README comes from a "matched first-chunk publication benchmark" that is **not included** in the code.
- **Timing instrumentation that does exist:**
  - CUDA events around each noisy and clean DiT forward (runtime.py:644-653, 696-702; `dit_timing_receipt` 464-480).
  - Wall timers for model load, adapter load, text precompute, stage3 generation, decode and publish.
  - Everything is written to `result.json` and `latent_streaming.json` (runner.py:335-373).

### Parallelism and kernels
- Parallel layout is **TP2 × Ulysses{2,4}** for 4 or 8 GPUs, single node (config.py:151-182; runtime/direct.py:169-189). Both the teacher and the student use the same layout (teacher.py:188-212).
- **Precision:** BF16, plus **INT8 W8A8** on interior `qkv` and `fc1` through vLLM's `cutlass_scaled_mm` / `scaled_int8_quant` (config.py:24; inference/w8a8.py; cli.py:131-146). There is **no fp8**.
- The LoRA stays **unmerged**, as BF16 side buffers with a fused row-reduce (inference/lora_checkpoint.py:172ff, 261-311; acceleration.py:39-40). It targets `qkv_proj`, `out_proj`, `fc1` and `fc2` on 2 refiner blocks + 50 main blocks (lora_checkpoint.py:13-26).
- **Hard SM90 dependency.** FlashAttention-3 (`flash_attn_interface`, built from `flash-attention/hopper`) is used by the streaming hook, which refuses any other backend (attention_hook.py:43-48; layers.py:39-48; cli.py:130,145-146; config.py:25).
- Other kernels: Triton fusions with inline PTX (sm89-compatible PTX ops). The bit-exact video-VAE kernels are gated to capability {90, 100, 103} and fall back on other GPUs (inference/fused_kernels.py:858-870).
- **What fails on sm89 (our L20X)?**
  - FA3 does not run on SM 8.9; vLLM falls back to FA2 there (web sources; not tested here). The FA3 import or kernel launch would fail, and `cli._validate_acceleration_runtime` / `H3StreamingAttentionHook` raise.
  - The fix is small in principle: the hook is plain non-causal dense attention over concatenated K/V, so FA2's `flash_attn_func` or SDPA is a drop-in replacement, applied in both `attention_hook.py` and `layers.py`.
  - vLLM's int8 CUTLASS kernels have sm89 variants (believed; unverified).
  - Performance on L20X is unknown.
  - Memory: peak DiT 31.37 GiB per GPU at 480p (README), and each L20X has 141 GB.

### Inputs
- T2AV only. There is no reference image, first frame or voice reference. The README says "TaoMate-H3 FL2AV … will be released before 26/10/15; Ref2AV TBD".
- Voice is controlled only through prompt text; the example uses "clear, practical, medium-paced Mandarin voice".

### Measured and claimed latency (README; 8×H20, TP2×Ulysses4, 480×864, 10 s, seed 8301)

| Metric | Value |
|---|---|
| Pure DiT time | 14.810 s (vs 169.57 s for base H3) |
| First final chunk latent | 6.148 s |
| First playable (includes VAE decode and H.264 of the first chunk, excludes audio preparation) | 17.287 s |
| Peak DiT memory | 31.37 GiB |

- Derived: 240 frames / 14.81 s = **16.2 DiT FPS, which is 0.68× real time**. The validated setup is **slower than real time** even before VAE, text encoding and the audio teacher.
- 32 forwards in 14.81 s is about 0.46 s per forward.

### License
- TaoMate-H3 is under the **MiniMax H3 Community License**. Its Excluded Territories are the EU, UK, Republic of Korea and USA (LICENSE §I.5).
- A NOTICE file records the modifications.
- TaoMate (LTX) is under **Apache-2.0**, but its weights inherit the LTX-2.3, Gemma and other licenses.

---

## 3. TaoMate (LTX-2.3) repo: useful because it has the only interactive loop

Summarized from a code sweep. The key constants and the RoPE comment were re-checked by hand.

- **Granularity.**
  - A window is 121 frames = 16 latents, split into 5 blocks (4+3+3+3+3). Later windows are 15 latents.
  - A block is 3 latents, which is 24 frames or about 1 s. There are at most 12 windows (TM `taomate/inference/runtime.py:46-53`; `streaming_runtime.py:63-70`).
  - Steps are `DENOISING_STEPS=(1000,757,522,0)` snapped to the LTX2 40-step schedule (`taomate/inference/model.py:11-19`).
- **Memory is implemented** in `taomate/runtime_support/learned_memory.py`, matching the paper:
  - EMA plus anchor tether, and the drift gate (lines 149-166, 231-248).
  - Colour and FiLM statistics (430-505).
  - MemAttn every 4th layer (`ltx_causal/transformer/causal_model.py:341-352`).
  - Updates only after the σ=0 commit (`streaming_runtime.py:3506-3507`).
  - The anchor is block 0 (`learned_memory.py:361-367`).
- **KV.** Sink block 0 + 2 recent clean blocks (`taomate/inference/cache.py:58-67`).
  - The persistent cache commits at absolute runtime positions (`streaming_runtime.py:3535-3541` comment). A restart of the local-window RoPE seems to apply only to the window buffer. **Whether this matches the paper's "local RoPE restart" is unverified.**
- **Parallelism in code is 2-rank tensor parallel.** The demo uses 4 GPUs: DiT TP on 0-1; text encoder and VAE on 2; llama-server and Whisper on 3.
  - **No stage-parallel (3-GPU, 35 FPS) code is in the repo.** It uses flex_attention and SDPA with **no FA3**, so it could run on sm89.
- **Interactive demo** (`apps/interactive_avatar/`): FastAPI + SSE, per-block fragmented MP4 over MSE, playback starting after 2 segments are buffered.
  - Flow: user text → Gemma-4-26B-A4B (llama-server) → JSON `{speech, emotion, action, explicit_action}` → one templated prompt per reply → a `pending/<task>.json` file queue polled by the resident worker (`worker.py:82-176`).
  - Prompts are consumed per window at `streaming_runtime.py:4927-4932` (`conditional_dict = prompt_cache[seg_prompt]`).
  - Whisper-tiny transcribes the **avatar's own audio** to detect end of speech and write `asr_stop_control.json`. It is read after every block and rolls back surplus blocks (4751-4805, 5229-5296).
  - There is **no barge-in**: `cancel.requested` is written (`server.py:5763-5766`) but never read by the worker.
  - Continuity across turns is kept by saving and loading the prefix, KV and memory state (`streaming_runtime.py:4828-4890`).
  - When idle, the UI loops a muted clip. No filler generation runs.
- **This demo is the closest existing template for our agent.** It already shows turn-level (not mid-turn) prompt switching with persistent state across turns.

---

## 4. vLLM-Omni as a host for TaoMate-H3

Sweep result, with parts re-checked. Local HEAD is 7b4dc76; origin/main 3bd5ac9 adds only request-cancellation hooks to minimax_h3.

- **What exists in `vllm_omni/diffusion/models/minimax_h3/`:**
  - `lora.py`: LightX2V Turbo LoRA only. It requires a filename regex and Diffusers-PEFT keys.
  - `fasth3.py`: FastH3, a 4-step DMD2 fused at load.
  - `continuation.py`: Ref2VA windowed continuation that re-encodes a latent tail. It supports per-window prompts fixed ahead of time and has no KV.
  - `temporal_chunks.py` / `chunked_decode.py`: chunked **VAE decode** after full denoise.
  - `pipeline_minimax_h3.py`: pinned `base_schedule` sigma positions and the `audio_mode=lock_source` locked audio rows.
- **What does not exist:**
  - No TaoMate references.
  - No persistent KV in the H3 transformer.
  - No `SupportsInteractionApply` or `SupportsARDiffusionPipeline` implementation for H3. Only LingBot-World, Helios and DreamZero have them (verified by grep).
  - The `/v1/realtime/video` WebSocket (`session.interaction`) and `experimental/ar_diffusion` (sink+window paged KV) exist but cannot drive H3.
- **Missing pieces to serve TaoMate-H3 as a session:**
  1. A loader for TaoMate's native-key LoRA (`blocks.N.attn.qkv_proj.lora_a/b`, rank/alpha from its own config).
  2. A 3-step FL2VA schedule, (0,16,33,49) with shift 12/3.
  3. Persistent clean A/V KV with sink + 2 recent and a σ=0 commit pass, under Ulysses×TP.
  4. Chunk-level streaming with 39/34/34/17-frame chunks. These are off H3's 17n+5 decode grid, so decode needs a streaming VAE cache.
  5. `SupportsInteractionApply`, or the AR tick prompt path, for mid-stream prompts.
  6. A resident base-model audio teacher (a LoRA-off BF16 pass, 10 steps, 40-latent rollover) feeding locked audio rows.
  7. A parity test against the reference runtime.
- **Rough estimate:** porting to vLLM-Omni is much more work than adding a queue to the TaoMate-H3 runtime itself.

---

## 5. Implications for a live persona agent on TaoMate-H3

- **Control granularity.**
  - Effective: 5 s (one request). This is bound by the per-request audio teacher and the prompt/seed contract.
  - Structural minimum: one chunk (0.7–1.6 s), only if the teacher is re-engineered to be per-chunk.
- **Instruction-to-screen latency** is at least the time to finish the current request, plus the audio-teacher pass for the next request, plus the DiT time for its first chunk, plus VAE and mux.
  - On 8×H20 the DiT alone runs at 0.68× real time, so a queue builds without end. Real time needs faster GPUs or fewer tokens.
- **Memory and identity.** Only a first-chunk KV sink + 2-recent + colour renorm, with absolute RoPE.
  - There is no evidence of stability beyond the 60 s example. The audio KV reset every 60 s hints at drift.
  - Long-session identity would need the TaoMate learned-memory design, which is not ported to H3, or the upcoming FL2AV.
- **Barge-in.** Audio for a whole 5 s request is precomputed, so interruption means discarding the request. The TaoMate demo's rollback-after-block pattern could be adapted at chunk granularity.
- **Hardware.** Local L20X (sm89) cannot run the FA3 path as shipped. It needs an FA2/SDPA swap in 2 files and then fresh validation.

---

## Evidence table

| Claim | Evidence | Status |
|---|---|---|
| TaoMate: 22.1B, LTX-2.3 distilled init, 3 steps per block | paper §4.1, Table 1 | verified (paper) |
| 12 memory layers of 48; 48 video tokens (anchor + state), 64 audio; +97.8M params | paper §4.1 | verified (paper) |
| Memory EMA / anchor / gate hyperparameters | paper §4.1; TM learned_memory.py:149-166,231-248 | verified (paper + code sweep) |
| 35.0 FPS on 3 GPUs, 41.2 s for 1,441 frames; GPU type not stated | paper §4.3, Table 2 | verified (paper); GPU type unverified |
| 11.1 FPS single RTX PRO 5000 (130.3 s / 1,441 frames); DiT FPS 16.32 | paper §4.1, Table 1 | verified (paper) |
| Stage-parallel code is in the TaoMate repo | TM sweep: only TP2 code found | **not found** |
| Paper metrics vs project page differ (5.918 vs 5.773 LipSync, etc.) | paper Table 1; project page | verified |
| >30 min single generation | project page | claimed, unverified |
| Prefix size in §3.5 is missing ("up to recent blocks") | arXiv HTML + PDF | verified (typo) |
| Local RoPE restart per segment | paper §4.1; TM code uses absolute positions for the persistent cache | contradicted/unclear |
| TM block = 3 latents ≈ 1 s; window = 5 blocks ≈ 5 s | TM runtime.py:46-53 | verified |
| TM demo: file queue, per-window prompt, no barge-in, MSE fMP4 per block | TM worker.py:82-176; streaming_runtime.py:4927-4932; server.py:5763-5766 | verified (sweep + spot check) |
| H3: one prompt per 5 s; JSON `{"prompts":[..],"seeds":[..]}` | H3 config.py:80-134 | verified |
| H3: 4 chunks per request (2,2,2,1)×17 frames; request 0 = 124 frames | H3 config.py:23; streaming/geometry.py:173-200 | verified |
| H3: 3-step sigmas at indices (0,16,33,49), shift 12/3, no CFG | H3 denoise_schedule.py:7; model/pipeline.py:394-403 | verified |
| H3 KV: first-chunk video sink + 2 recent AV chunks; text not cached | H3 streaming/cache.py:206-219; attention_hook.py:179-216 | verified |
| H3 audio KV dropped every 12 requests | H3 config.py:29; streaming/runtime.py:584-588 | verified |
| H3 has no learned memory / anchor tokens / FiLM | grep of H3 src | verified (absence) |
| H3 audio = base-H3 10-step audio-only teacher, 40-latent rollover; student audio overwritten and asserted equal | H3 teacher.py:255-381; streaming/runtime.py:339-359,739-743 | verified |
| H3 prompts consumed at runner.py:299; text precomputed and encoder offloaded | H3 runner.py:293-323; model/pipeline.py:101-104 | verified |
| No server/queue/socket in H3 | grep | verified (absence) |
| H3 output is one-shot MP4 at end | H3 runner.py:124-263 | verified |
| FA3 required; hook rejects other backends | H3 attention_hook.py:43-48; cli.py:130-146 | verified |
| INT8 W8A8 (not fp8) via vLLM CUTLASS | H3 inference/w8a8.py; acceleration.py | verified |
| FA3 unsupported on SM 8.9 | web (vLLM/FA issue summaries) | unverified locally |
| Local GPUs are L20X, cc 8.9 | `nvidia-smi` | verified |
| DiT 14.81 s, first chunk latent 6.148 s, first playable 17.29 s, 31.37 GiB (8×H20, 480p, 10 s) | H3 README | claimed; not reproduced |
| First-playable excludes audio teacher | H3 README ("excludes the command's internal audio preparation") | verified (text) |
| FL2AV before 2026-10-15; Ref2AV TBD | H3 README | claimed |
| LoRA rank 128 / alpha 128, step 3000 EMA, native (non-PEFT) keys | HF config.json; H3 lora_checkpoint.py:13-26 | verified |
| vLLM-Omni H3: no persistent KV, no interaction or AR-session implementation, LoRA loader incompatible | VO minimax_h3/ (lora.py:38,103); grep of interfaces | verified (sweep + grep) |
| origin/main 3bd5ac9 adds only request cancellation to minimax_h3 | VO git diff (sweep) | verified (sweep) |
| H3 license excludes EU/UK/KR/US | H3 LICENSE §I.5 | verified |

===== FILE: docs/decision_log.md =====
# Decision Log

Material decisions, the alternatives considered, the evidence, and the
assumptions they depend on. IDs are stable. Statuses are *provisional*, *adopted*,
*superseded*, or *open*.

| ID | Date | Decision | Alternatives | Evidence / rationale | Status |
|---|---|---|---|---|---|
| D-001 | 2026-09-25 | The first acceptance scenario is a **1:1 private user**. A **private test livestream** (scripted viewers, no public broadcast) is the second evaluation scenario, with separate memory scopes | Livestream first; both at once | CP1 finding 2. Memory and instruction-following claims are measurable only with a controlled user. Livestream adds unconsented third parties | provisional |
| D-002 | 2026-09-25 | Codex reviews run with `-s read-only` and all evidence inline | Unsandboxed Codex (denied by the permission policy); MCP Codex (server failed to connect) | `max_user_namespaces=0` means bwrap cannot start | adopted |
| D-003 | 2026-09-25 | Pin upstream vLLM-Omni `main` at `7b4dc76` (2026-09-24) as the inspected implementation, in a read-only clone at `external/vllm-omni` | Use one of the user's feature branches under /data/zhoutaichang | Upstream main is the public integration surface. Feature branches hold unrelated or uncommitted work | adopted |
| D-004 | 2026-09-25 | Carry a "no world model" baseline (LLM + TTS + talking-head avatar) through the evaluation | Evaluate only the LingBot-based design | CP1 finding 4 / goal §5 ("simple baseline") | adopted |
| D-005 | 2026-09-25 | Demo = **dual-shot live persona**: a lip-synced avatar close-up (external audio-driven model) plus a LingBot-World world shot of the same persona, chosen by a controller shot track. Voice-over-only explorer rejected | (a) Explorer with voice-over only; (b) avatar composited into the LingBot scene; (c) a native LingBot talking head | CP2 blocking finding 2. The backbone has no native lip, face or audio path (class D), and the owner's goal requires a visible persona. (b) is kept as an ablation | provisional |
| D-006 | 2026-09-25 | Central research claim = capability-grounded closed-loop control with deadline-bounded visual verification. TVC is its measurement protocol | TVC as the headline novelty; memory as the headline | CP2 findings 1 and 6. WorldMark and ABot-World-0 already measure related latencies; SayCan and Inner Monologue are prior art for affordances and feedback | provisional |
| D-007 | 2026-09-25 | No GPU benchmark in this phase. The smallest resolving experiment is specified as M0 | Run the vLLM-Omni LingBot benchmark now | The goal keeps this phase to research. The environment is not turnkey (earlier local run had no FlashAttention and ended in tracebacks). The weights sit in shared `/data/models`, and permission to use them should be confirmed | adopted |
| D-008 | 2026-09-25 | GPU identity recorded as unresolved: NVML "L20X"/Ada/CC 8.9 vs H200-like memory and power | Assume H200 (as an upstream PR says) | Direct `nvidia-smi -q` evidence conflicts with that PR's statement | adopted |
| D-009 | 2026-09-25 | A0, A1 and A2 share LLMs, ASR/TTS, the avatar renderer and the memory service (except in E3). **A1 and A2** also share the generator control substrate (S-cam, plus S-prompt through C1); A0 has no world generator. Between A1 and A2 only the controller differs | Separate stacks per arm | CP3 finding 6: removes confounds for RQ1 and RQ4 | adopted |
| D-010 | 2026-09-25 | A bounded look-ahead gate (C4) is required for real-time TVC. `session.ping` is not flow control. Fallbacks: skip-to-latest, playback-rate adaptation | Rely on the client buffer | Code-read: `serving_video_output_stream.py:148-155` sends chunks as produced; ping only refreshes the stall clock (`:17,79-88,311`). Backlog grows ≈0.2 s/chunk at T=0.549 s and 16 fps [derived] | adopted |
| D-011 | 2026-09-25 | The IR is relative, the wire format is absolute. The compiler tracks a pose estimate and emits absolute `target` poses | Send relative targets | Code-read: `camera.py:44,107,341-352` — target poses are absolute relative to the session-start origin. The API doc's "absolute pose" wording agrees | adopted |
| D-012 | 2026-09-25 | The first demo commits only camera/viewpoint control and a visible host. Locomotion and scene/character events are conditional on C1 and E1 | Promise "walk to the lake" | CP3 finding 5: camera ≠ character; prompts need C1 | adopted |
| D-013 | 2026-09-25 | H-core is tested strictly only against an unwrapped end-to-end system (A3b), if weights become available. Otherwise it is tested as H-core-abl (A2 vs A1−mem, with no cross-session carry-over) | Claim that A1−mem tests "no external layer" | CP4 finding 1: A1−mem still has an external controller | adopted |
| D-014 | 2026-09-25 | The primary E2 outcome is blinded human adjudication, independent of the online monitor. An offline evaluation judge serves the ablations. The evaluation set is locked after E1 and the pilot | Use the online monitor verdicts as the outcome | CP4 finding 2: circularity and condition-dependent judge error | adopted |
| D-015 | 2026-09-25 | The C4 gate fires at *presentation start* of chunk n and starts block n+L+1. TVC ≈ A + U(0,P) + (L+1)P + I. L=0 and L=1 are both measured | Leave the ack edge undefined | CP4 finding 7 | adopted |
| D-016 | 2026-09-25 | **Superseded by D-017.** Should TaoMate-H3 (MiniMax H3 + 3-step streaming LoRA) be used as a base model? Recommendation: use it to render the **presenter shot** (replacing the generic external avatar of D-005) and keep LingBot-World as the world backbone. Adopt it as the *sole* backbone only with explicit owner approval, because that replaces the preferred backbone | (a) sole backbone; (b) presenter shot only; (c) H3 family for both shots via SolarWM-H3 (uncommitted local branch) | `docs/notes/taomate_h3_assessment.md`: native speech and lip sync, per-block action prompts, same family as the reference agent. But only T2AV is released, 5 s blocks, no mid-stream API, slower than real time on 8×H20, SM90 required (local GPUs report CC 8.9), and a territory-restricted license | open |
| D-017 | 2026-09-25 | **Owner directive:** rewrite the whole proposal in Chinese (`docs/research_proposal_zh.md`), with **TaoMate-H3 as the base generator** and an agent architecture modelled on Google's long-form suite (Co-Director / CANVAS / A²RD / VQQA). LingBot-World 2.0 is **repositioned** to an optional world-shot / comparison role; it is not dropped silently. The English v1.0 is kept as the previous version | Keep LingBot-World as the primary backbone (v1.0) | The owner explicitly asked for this. It supersedes D-005 (dual-shot with a generic avatar) and resolves D-016 in favour of TaoMate-H3. Its risks are recorded in `docs/notes/taomate_h3_assessment.md`: only T2AV is released, 5 s blocks, not real-time on 8×H20, SM90 required | adopted (owner) |
| D-018 | 2026-09-25 | *(Amended after zh2: the default is **just-in-time prompt locking**, P_{k+1} = V_k + R − Λ − σ, which respects the presentation slot and KV dependency; early locking and L=1 are contrasts.)* For the TaoMate-H3 base, the default gate is **L = 0**: request k+1's prompt lock → audio teacher → student starts when request k starts presenting, with the requirement Λ = G_a + G_1 + δ ≤ R; L = 1 is the jitter-tolerant contrast. This supersedes D-015 for this backbone. "Re-anchoring" is redefined as three executable interventions: textual correction, session reset, and image re-anchoring (only after FL2AV is released) | L = 1 (it adds one full 5 s request to every instruction) | zh1 findings 1, 2 and 5 | adopted |

## Open questions

See `docs/PROJECT.md` (A*/Q* table). Resolved questions move here with the evidence.

===== FILE: docs/codex_reviews.md =====
# Codex Review Log (GPT-6 Sol)

Auditable record of the mandatory independent reviews (goal.md §7). Raw
artifacts for each run are in `docs/reviews/<tag>_{instructions,prompt,review,events,meta}`.

## Reviewer setup (verified 2026-09-25)

| Item | Value | Evidence |
|---|---|---|
| Tool | Codex CLI `codex-cli 0.156.0` (`/home/zhoutaichang/.local/bin/codex`) | `codex --version` |
| Model requested | `gpt-6-sol` (`-m gpt-6-sol`; also the default in `~/.codex/config.toml`) | command line in each `*_meta.txt` |
| Model actually used | `gpt-6-sol`, provider `openai` | `"model":"gpt-6-sol"` in each session rollout (`~/.codex/sessions/2026/09/25/rollout-*.jsonl`; path recorded in `*_meta.txt`) |
| Available models (cache) | gpt-6-astra, gpt-6-sol, gpt-6-luna, gpt-5.6-*, gpt-5.5, … | `~/.codex/models_cache.json` |
| Codex MCP server | Failed to connect in the Claude Code session (`CONNECTION_CLOSED`). The CLI is used instead | session environment notice |
| Sandbox | The `bwrap` sandbox cannot start: `/proc/sys/user/max_user_namespaces = 0` ("No space left on device"). Running Codex unsandboxed was denied by the Claude Code permission policy. **Mitigation:** run `-s read-only` and inline all evidence through `tools/codex_review.sh`. **Limitation:** the reviewer can check only what is inlined, not browse the repo itself | cp1 attempt 1 output; `unshare` test |

## Summary table

| CP | Tag | Date (UTC) | Reviewed revision | Model (rollout) | Findings | Status |
|---|---|---|---|---|---|---|
| 1 | cp1_attempt1 | 2026-09-24T17:29Z | ef3a0f3 | gpt-6-sol | 6 provisional (reviewer could not read files) | Superseded by cp1 |
| 1 | cp1 | 2026-09-24T17:36Z | ef3a0f3 (+ inlined files) | gpt-6-sol | 7 (1 blocking, 5 major, 1 minor) | Resolved in d68466e. Blocking item #1 is carried into CP3 |
| 2 | cp2 | see `cp2_meta.txt` | 7cce79f | gpt-6-sol | 10 (2 blocking, 7 major, 1 minor) | Resolved in 8eb4d33. CP3 re-reviewed it (no objections) |
| 3 | cp3 | see `cp3_meta.txt` | ecbb880 | gpt-6-sol | 15 (2 blocking, 12 major, 1 minor) | Resolved in c085745. The CP4 re-review found #11, #12 and #15 only partly resolved; fixed in d2e6a36 |
| 4 | cp4 | see `cp4_meta.txt` | b3435bb | gpt-6-sol | 9 (2 blocking, 6 major, 1 minor). Verdict: **not ready** | Addressed in d2e6a36. Re-review → cp4r2 (below) |
| 4 | cp4r2 | 2026-09-24T18:12Z | 3e99d08 | gpt-6-sol | 4 resolved, 5 partial, 1 new major. Verdict: **not ready** | Addressed in e3416a1. Re-review → cp4r3 (below) |
| 4 | cp4r3 | see `cp4r3_meta.txt` | 22c720f | gpt-6-sol | #5, #6, #7 and the substrate fix resolved. 2 major (H3b scope; M0 qualification vs stall target) + 1 minor (log wording). Verdict: **not ready** | Addressed in bacdb22. Re-review → cp4r4 (below) |
| 4 | cp4r4 | see `cp4r4_meta.txt` | 67d8801 | gpt-6-sol | All 3 round-3 items resolved. 1 major (H3b channel operationalization) + 1 minor (table row). Verdict: **not ready** | Addressed in 55016af. Re-review → cp4r5 (below) |
| 4 | cp4r5 | see `cp4r5_meta.txt` | df29f75 | gpt-6-sol | Round-4 items resolved. 2 minor. **Verdict: ready with minor fixes** (no blocking/major) | Both minor fixes applied in d822c32. Confirmation → cp4r6 (below) |
| 4 | cp4r6 | see `cp4r6_meta.txt` | 6f64d21 | gpt-6-sol | Both fixes verified; no regressions. **Final verdict: ready** | Closed |

## Checkpoint 1 — project understanding, requirements, assumptions

**Attempt 1 (invalid).** The reviewer's shell sandbox failed on every file read,
so it reviewed only the prompt text. Its output is kept as
`docs/reviews/cp1_attempt1_review_sandbox_failed.md` but is not counted as a
review of the artifacts.

**Attempt 2 (`cp1`).** The inlined files were goal.md, docs/PROJECT.md v0.1,
CLAUDE.md, AGENTS.md, and AGENT.md, plus the author's initial observations.

| # | Sev. | Issue (abridged) | Disposition | Resolution |
|---|---|---|---|---|
| 1 | blocking | The demo may exceed what the backbone can control. The recipe shows only public camera control: no gestures, expressions, speech, or public mid-session prompt switching | **Accepted** | The backbone is being verified at code level (`docs/backbone_verification.md`). The demo scenario will be chosen after a control→observable-behavior table exists (goal §4/§5). Carried into CP3 for re-review |
| 2 | major | Acceptance scenario and "real-time" are undefined | **Accepted** | PROJECT.md Q3: 1:1 private user is the first acceptance scenario and livestream is the second (D-001). Q6: targets are set in the proposal |
| 3 | major | Feasibility assumptions are stated too confidently (GPU inventory vs. capacity; H3 provenance) | **Accepted** | A1 split into inventory (observed) and capacity (open). Q4 added for H3 provenance/license |
| 4 | major | The hypothesis has no competing account | **Accepted** | Q5: a simple LLM+TTS+talking-head pipeline is carried as a competing baseline that the evaluation can favor |
| 5 | major | The "single source of truth" drops binding requirements from goal.md | **Accepted** | goal.md now takes precedence. A requirement→deliverable checklist was added to PROJECT.md |
| 6 | major | The review log lacks a reproducible evidence trail | **Accepted** | `tools/codex_review.sh` records the prompt with its sha256, output, events, rollout path and model, repo and vLLM-Omni SHAs, dirty state, and exit code. PROJECT.md was updated |
| 7 | minor | CLAUDE.md dropped "where supported" for speech. AGENT.md precedence could override goal.md | **Accepted** | Both fixed |

Remaining disagreements: none.

## Checkpoint 2 — literature synthesis, capability claims, research gap

Tag `cp2`. Reviewed revision 7cce79f. Inlined: related_work.md, backbone_verification.md, the synthesis
sections of the three literature notes, and the reference-agent note. The reviewer followed some primary-source
links (arXiv) on its own.

| # | Sev. | Issue (abridged) | Disposition | Resolution (8eb4d33) and evidence |
|---|---|---|---|---|
| 1 | blocking | G1/TVC overclaims novelty: WorldMark already measures response latency | **Accepted after verification.** Claude read the WorldMark HTML: its latency is counted in *generated-video frames* until motion reaches half the reference speed. A targeted search also found ABot-World-0 (arXiv 2607.19191), which reports *wall-clock action-to-first-frame* time, i.e. when a frame becomes available, with no compliance check | TVC redefined as wall-clock time from instruction arrival to *displayed, judged-compliant* content, with censored failures. Downgraded to a measurement protocol supporting contribution 1. G1 rewritten with both neighbours |
| 2 | blocking | The explorer/voice-over demo undershoots the "digital persona" goal | **Accepted** | Dual-shot live persona (D-005): a lip-synced avatar close-up plus a LingBot world shot of the same persona, with cross-shot coherence measured. Compositing is an ablation |
| 3 | major | "Camera-only" is a code-read conclusion; an ack is not compliance; a real WS prompt test is needed | **Accepted** | Scope stated in backbone_verification.md (CP2 clarifications). A real WS prompt attempt was added to M0 |
| 4 | major | Latency labels are loose (549 ms stack; derived 0.6–1.15 s is not TVC; Wan-Streamer's network is assumed; D vs external avatar; rewind class) | **Accepted** | All relabelled. Rewind/snapshot → "C/D, feasibility unknown". D is limited to native LingBot conditioning |
| 5 | major | The falsification test is loose, and "internal state" mixes generator KV with thinker context | **Accepted** | H-core restated with the two kinds of state separated, a definition of "external state layer", an operational test and a refutation condition |
| 6 | major | Contribution 1's prior art is understated (SayCan, Inner Monologue); "offline only" is too broad | **Accepted after verification.** Claude ran a targeted search (2026-09-25). SPIRAL's critic is iterative/offline; the agentic-visual-generation survey (2609.06758) does not cover runtime verification of streaming generators. Bib entries were added through the arXiv API | Contribution 1 repositioned as a specific combination, with four required comparison arms. G2 reworded to "not found for streaming generators" |
| 7 | major | Novelty varies across G4–G10 (PACE, provenance, WBench) | **Accepted** | Contributions 3–5 downgraded or scoped to their evaluation novelty. G10 now says "no single benchmark found". WBench cited |
| 8 | major | Interruption and TVC need operational definitions; cancel ≠ redirect | **Accepted** | G5 rewritten (cancel exists; redirecting an in-flight chunk does not). The TVC timestamp list and censoring are defined. VLM judges are validated against blinded human labels (proposal §8) |
| 9 | major | Material neighbours were missing from the synthesis (WBench, WorldMark, VideoFDB, MIDAS, StreamingVLM, MemoryArena, LiViBench) | **Accepted** | Added to the matrices and gaps |
| 10 | minor | Matrix fields incomplete (URLs, control interface, latency in §2.4); KV wording; tea observation | **Accepted** | Direct arXiv links in every row. §2.4 rebuilt with control-interface and latency columns ("not stated" per cell). KV sink and window described separately. The tea observation stays a single unaligned sample |

Remaining disagreements: none. The reviewer also noted it could not re-read the pinned checkout. This is an
inherent limitation of inline review (D-002). CP3 inlines the relevant code excerpts.

## Checkpoint 3 — architectures, integration, memory, latency

Tag `cp3`. Reviewed revision ecbb880 (proposal v0.9). Inlined: the proposal, backbone_verification, decision_log,
the 4 figure sources, the vLLM-Omni streaming API doc, the realtime design doc, and **real code excerpts with line
numbers** (`docs/reviews/cp3_ev_code_excerpts.md`) from registry.py, coordinator.py,
serving_video_output_stream.py, pipeline.py and the deploy yaml. CP3 also re-reviewed the CP2 revisions (dual-shot
design, TVC repositioning) and raised no objection to them.

| # | Sev. | Issue (abridged) | Disposition | Resolution (c085745) |
|---|---|---|---|---|
| 1 | blocking | A1's "free-form prompts" cannot execute (prompt handler not registered) | **Accepted** | Shared generator substrate (D-009): S-cam, plus S-prompt only through C1 once it passes M1 tests; without C1, prompt changes are session restarts for both A1 and A2 |
| 2 | blocking | The backlog gate has no mechanism; `session.ping` is not flow control | **Accepted.** Claude had independently confirmed `serving_video_output_stream.py:17,79-88,311` before the review arrived | C4 redefined as a server generation gate (feasibility checked in M1), with skip-to-latest and rate adaptation as fallbacks. M0 measures queue depths and transport backpressure (D-010) |
| 3 | major | C1 is more than registration; stepwise `invalidate=True` safety is unverified | **Accepted** | C1 spec: encode at the boundary, session state, per-rank K/V rebuild under Ulysses head sharding, transition policy, tests. Re-sized to medium |
| 4 | major | Evidence labels (documented / code-read / executed) are conflated | **Accepted** | §6.1 distinguishes the three. M0 WS contract test added |
| 5 | major | Camera commands ≠ "walk slower" / "walk to the lake" | **Accepted** | Demo scoped to committed camera/viewpoint control and a visible host. Locomotion and events are conditional (D-012) |
| 6 | major | Architecture comparison confounded (memory and renderer differ); alternatives missing; A3(b) needs no training | **Accepted** | Shared substrate. Table of feasibility alternatives: SGLang server, tick path, clip scheduling, compositing, different backbone. A3 split into (a) training and (b) none if weights exist |
| 7 | major | IR camera contract undefined; Fig. 2 cancellation inconsistent | **Accepted. While verifying, Claude found an error the reviewer did not name**: `target` poses are *absolute relative to the session origin* (`camera.py:44,107,341-352`), not relative | Contract: frame, units, velocity held until replaced (explicit stop), absolute targets from a compiler pose estimate (D-011). Golden IR→WS example (JSON and quaternions validated). A single cancellation rule; Fig. 2 fixed |
| 8 | major | Monitor underspecified: sparse-flow scale ambiguity, VLM latency ≠ throughput | **Accepted** | Rotation plus translation *direction* only, abstention rules, K=4 frames per chunk, verdict deadline, repair eligibility reported |
| 9 | major | Quarantine leaks: quotations and echoes of persona claims | **Accepted** | Claim-type classification, echo lineage against the generated-event log with confirmation, paraphrase `derived_from`. Probes added to E3 |
| 10 | major | Scope holes through derived media and persona history | **Accepted** | `source_scopes` on every derived artifact. Private-session persona utterances are private. Public sessions start only from canon/public frames. Fresh-public-session probe added |
| 11 | major | Deletion vs append-only log undefined | **Accepted** | Erasure physically deletes records, cascades to 6 artifact classes, keeps a content-free tombstone ledger and bounded backup retention, and is verified after a flush and restart |
| 12 | major | TVC budget mixes paced and unpaced timing; p95 sums invalid | **Accepted** | Regime U (unbounded growth) vs regime G ($W \sim U(0,P)$, $L \cdot P$). Figures are labelled column sums, not quantiles, and will be replaced by a simulation from M0 measurements. 2-GPU/12 fps recomputed |
| 13 | major | Avatar delay omitted from the speech path; ack ≠ presentation | **Accepted** | Shared presentation timeline. Separate first-speech targets for world-shot and presenter-shot starts. Narration aligned to presentation |
| 14 | major | The first-demo boundary and GPU budget are optimistic; C2/C5 under-sized | **Accepted** | First demo = M0-qualified configuration with a presenter-plus-clips fallback. C2 medium–large; C5 seam acknowledged. GPU estimate labelled optimistic; full-machine slots booked |
| 15 | minor | Denominators and censoring | **Accepted** | Instruction-level success is primary (refusals count as failures). Conditional OCR and refusal rate reported. Unconditional p95 only if censoring ≤ 5%, otherwise restricted mean and deadline success |

Remaining disagreements: none.

## Checkpoint 4 — experimental design and complete proposal (round 1)

Tag `cp4`. Reviewed revision b3435bb (proposal v1.0-rc). Inlined: proposal, PROJECT.md, CLAUDE.md, AGENTS.md,
AGENT.md, decision_log, codex_reviews, related_work, and code excerpts (camera handler, ping semantics).
**Verdict: not ready.** The reviewer confirmed that most CP3 resolutions are reflected in the text.

| # | Sev. | Issue (abridged) | Disposition | Resolution (d2e6a36) |
|---|---|---|---|---|
| 1 | blocking | A1−mem does not test "no external layer": it has an external controller and carries history over | **Accepted** | Strict H-core is tested only against an unwrapped A3b-class system. Otherwise H-core-abl, which is explicitly weaker. A1−mem now carries no state across sessions (D-013) |
| 2 | blocking | The primary outcome is judged by the same kind of monitor the system acts on | **Accepted** | Blinded 2-rater human adjudication of every A2-vs-A1 trial. A separate offline evaluation judge for the ablations, with κ per condition. Evaluation set locked after E1 and the pilot (D-014) |
| 3 | major | Time to first *meaningful* response and time to first correctly conditioned visual response are undefined | **Accepted** | TFMR (fillers excluded, rubric, blinded raters) and TFCV (any shot, human-adjudicated, censored at D) defined on the shared timeline. End-to-end p50/p95 over all instructions |
| 4 | major | Power ignores task clustering; rare-leak claims are underpowered | **Accepted** | Pilot ICC → simulation power. 80 committed tasks × 5 seeds (design effect ≈ 2.2). "< 1%" leak claims need ≥ 360 opportunities with 0 leaks (rule of three) |
| 5 | major | FCR denominator, outcome rules and censoring are ambiguous (CP3 #15 partial) | **Accepted** | FCR = contradicted claims / claims, reported with claim coverage. Outcome-rule table (refused, superseded, cannot-tell, never). p95 only if KM reaches 0.95 before D; otherwise restricted mean with horizon D |
| 6 | major | A0 fails scene tasks by construction; H4b has no margin; cross-shot identity uses incomparable embeddings | **Accepted** | RQ4 compares A2 with **A0+clips** on MOS and preference. H4b margin 0.5 MOS (n≈16 needed; N=24 planned). Per-shot thresholds calibrated on human labels; cross-shot identity by human 2AFC; behavioural and scene-state probes added |
| 7 | major | Gate edge undefined; the T ≤ P rule ignores jitter (CP3 #12 partial) | **Accepted** | The gate fires at presentation *start* of chunk n; TVC ≈ A + U(0,P) + (L+1)P + I, with an L=0 vs L=1 trade-off. Qualification needs T+δ ≤ (L+1)P for ≥ 99% of measured chunks, plus a trace-driven queue simulation (D-015) |
| 8 | major | Erasure "cancels" work the API cannot cancel (CP3 #11 partial) | **Accepted** | Distinguishes unsent (dropped), sent (superseded), and live generator state (world session restarted from a canon frame). Presented media cannot be un-presented |
| 9 | minor | §14 claimed completion prematurely; D-001 wording; unlabelled design counts | **Accepted** | §14 reworded. D-001 now says "private test livestream". `[target]` labels added to design counts |

## Checkpoint 4 — round 2 (`cp4r2`)

Reviewed revision 3e99d08. Inlined: proposal, PROJECT.md, the 3 instruction files, decision_log, codex_reviews.
**Verdict: not ready.** CP4 #1, #2, #3 and #8 were RESOLVED. #4, #5, #6, #7 and #9 were PARTIALLY resolved.

| Item | Issue | Disposition | Resolution (e3416a1) |
|---|---|---|---|
| #4 | 360 leak probes from 20 users are not independent; the clustered bound is not < 1% | **Accepted** | The "< 1%" claim is now user-level over ≥ 300 independent simulated users, for text/speech channels. The visual channel gets a rate plus a cluster-robust bound, with no threshold claim |
| #5 | Superseded instructions are excluded while the text says "all instructions" | **Accepted** | Denominator is now "all scored intents" (superseded intermediate intents are replaced by their final intent), consistently in §7.2 and §8 |
| #6 | H4a needs pairwise preference, which §7.5 lacks | **Accepted** | Forced-choice pairwise preference added. Analysed with Bradley–Terry (participant random effects) and an exact sign test |
| #7 | $T+\delta \le (L+1)P$ is insufficient when mean $T > P$ | **Accepted** | Two conditions: throughput (mean $T+\delta < P$; qualification needs < 0.9P) and jitter ($T+\delta \le (L+1)P$ for ≥ 99% of chunks). The 2×H200 / 12 fps case is re-labelled marginal. The M0 go/no-go rule references this |
| #9 | §14 and the log did not record round 2; PROJECT.md status line stale | **Accepted** | This entry. §14 reworded. PROJECT.md status updated |
| new | "A0 shares the generator substrate" contradicts "A0 has no world model" | **Accepted** | §5.1 and D-009: A0 shares LLM, memory, speech and avatar; only A1 and A2 share the generator substrate |

## Checkpoint 4 — round 3 (`cp4r3`)

Reviewed revision 22c720f. Inlined: the same set as cp4r2. **Verdict: not ready.**

| Item | Issue | Disposition | Resolution (bacdb22) |
|---|---|---|---|
| r2#4 | H3b in §4 still states an unqualified "< 1%" | **Accepted** | H3b and its falsification rule are limited to text/speech channels at the user level; the visual channel is descriptive |
| r2#9 | The log said "re-reviewed" without recording a result | **Accepted** | Summary-table wording changed to "Re-review → <tag> (below)". This entry records the cp4r3 verdict |
| new | M0's 99%-jitter qualification conflicts with calling the configuration real-time and with the ≤ 1 stall/10 min target; 120 chunks cannot establish that target | **Accepted** | Two-stage qualification: M0 qualifies throughput (candidates only); an M1 soak test (≥ 3 × 30 min) plus a trace-driven simulation must meet the stall target before anything is called "real-time". §1.3, §6.4, §7.0 and §9.1 updated |

## Checkpoint 4 — round 4 (`cp4r4`)

Reviewed revision 67d8801. **Verdict: not ready.** All round-3 items were RESOLVED.

| Item | Issue | Disposition | Resolution (55016af) |
|---|---|---|---|
| 4 | H3b's "text channel" includes OCR of the displayed stream, which cannot be tested at the 300-user memory+LLM scale | **Accepted** | The statistical claim is limited to the **utterance channel** (response text + ASR of TTS audio), which can be produced at scale. On-screen OCR text and visuals are measured descriptively on ≈ 30 users |
| 5 | The RQ4 table row spans raw line breaks | **Accepted** | Row joined onto one line |

## Checkpoint 4 — round 5 (`cp4r5`)

Reviewed revision df29f75. **Verdict: ready with two minor fixes; no remaining blocking or major issue.**

| Item | Issue | Disposition | Resolution (d822c32) |
|---|---|---|---|
| 3 | The H3b falsification wording assumed exactly 300 users | **Accepted** | Falsification now depends on the exact one-sided Clopper–Pearson 95% upper bound (≥ 1%) |
| 4 | The log lacked a round-5 entry | **Accepted** | This entry |

## Checkpoint 4 — round 6 (`cp4r6`, confirmation)

Reviewed revision 6f64d21 (proposal and review log inlined). The reviewer verified the H3b fix and the round-5 log
entry and found no regression in §4, §7.3 or §8. **Final verdict: ready.**

After this verdict, the only change was the version label "v1.0-rc" → "v1.0". No content changed.

## Completion status of the review requirement (goal.md §7)

| Requirement | Status |
|---|---|
| Actual model verified (not just named in a prompt) | **Met.** Every run's session rollout records `"model":"gpt-6-sol"` (see each `*_meta.txt`) |
| Review at all 4 checkpoints | **Met.** CP1 (plus an invalid first attempt), CP2, CP3, CP4 in rounds 1–6 |
| Critique addressed with evidence or revisions; issues, changes and disagreements recorded | **Met.** Every finding has a disposition. No finding was rejected. Remaining disagreements: none |
| Material changes re-reviewed | **Met.** CP2 changes were re-reviewed in CP3, CP3 changes in CP4, and CP4 changes in rounds 2–6 |
| Limitation | Codex's shell sandbox cannot start on this host, and unsandboxed runs are not permitted. The reviewer therefore saw only inlined files and code excerpts and could not browse the repo on its own; it followed some public arXiv links. Agreement between models is not verification: the key backbone claims were checked independently against code (`docs/backbone_verification.md`, spot-checks) and against primary sources |

## 中文 v2.0/v2.1: owner-directed rewrite (TaoMate-H3 + Google agentic suite)

A material change (D-017), so it is re-reviewed from scratch.

### zh1: review of v2.0 (commit 63734a8)

Inlined: `research_proposal_zh.md`, `taomate_deep_dive.md`, `google_longform_agentic_suite.md`, `decision_log.md`,
and TaoMate-H3 code excerpts with line numbers (`zh1_ev_taomate_code.md`, @6b2f998). Model gpt-6-sol (rollout
verified). **Verdict: not ready.** Before the review, Claude independently checked three code claims: FA3-only
(`attention_hook.py:43-48`), teacher-audio overwrite (`runtime.py:339-359`), and sink + 2 recent (`cache.py:206-219`).

| # | Sev. | Issue (abridged) | Disposition | Resolution (v2.1) |
|---|---|---|---|---|
| 1 | blocking | The §6.4 latency is one request too low under D-015's L=1 gate | **Accepted** | Single timeline (lock → teacher → student → visible). The default gate is now L=0, with Λ ≤ R required (D-018). L=1 is the contrast, with its +R stated. Targets re-set and conditioned on measured Λ |
| 2 | blocking | A displayed failure cannot correct request k+2 under L=1 | **Accepted** | "Earliest correctable request" is defined from the timeline and reported as a distribution. The "within 2 requests" claim was removed |
| 3 | blocking | LTX 1 s control is unsupported (its demo changes the prompt per ~5 s window); H3 vs LTX confounds granularity | **Accepted** | The granularity test now happens only within LTX, after 1 s prompt changes are shown to work. H3 vs LTX is labelled a system comparison. The 2–3 s LTX claim was removed |
| 4 | major | Audio-teacher cost and scheduling are missing; README numbers exclude audio prep | **Accepted** | Throughput condition covers the full pipeline. M0 measures teacher and student co-resident (memory, contention) and runs 30 min continuously |
| 5 | major | "Re-anchoring" means nothing on T2AV without image conditioning | **Accepted** | Three executable interventions (textual correction, session reset, image re-anchoring only after FL2AV), compared with verbatim repetition |
| 6 | major | Interruption can leave the generator continuing from unseen content | **Accepted** | T8 rollback to the last presented chunk (feasibility in M1), else session reset or explicit bridging with measured discontinuity. Visual acknowledgement is measured separately from a meaningful reply |
| 7 | major | Experimental over-claims (RQ2 selection, RQ3 non-inferiority, RQ4 attribution, power) | **Accepted** | RQ2 randomized at a predefined failure point. RQ3 uses a 5 pp non-inferiority margin. RQ4 uses within-H3 ablations, with LTX descriptive only. Preregistered, simulation-based power; no pre-claimed effect size |
| 8 | major | Voice, spoken content and reasoning lack tests; "TTS" label wrong; leak check must cover generated audio | **Accepted** | Speech WER vs script, cross-session speaker identity (human), factual correctness, pre-generation script moderation, leak checks on generated audio (ASR + human spot audit) |
| 9 | minor | Source labels (SM90 from README; CC 8.9 is a local observation; 0.68× is DiT-only; state is not only KV; CANVAS is a storyboard; A²RD-only overhead); source vs new mechanisms | **Accepted** | 【本机观测】 label added; all corrected; paragraph separating source mechanisms from new ones added |

### zh2: re-review of v2.1 (commit dc72ab0)

> **Correction (added after zh3).** The "Resolution (v2.2)" column below was logged before the edits were verified. The v2.2 edit script aborted on one string mismatch, so **none of these resolutions were in the proposal when zh3 reviewed it** (text still v2.1). zh3 correctly reported them as NOT RESOLVED. They were applied and verified by grep in v2.3 (see zh3 below). This was a tooling/process error by the author, not a disagreement with the reviewer.

Model gpt-6-sol (rollout verified). zh1 status: #3, #5 and #6 RESOLVED; #1, #2, #4, #7, #8 and #9 PARTIALLY.
**Verdict: not ready.**

| # | Sev. | Issue | Disposition | Resolution (v2.2) |
|---|---|---|---|---|
| 1 | blocking | The latency model ignores that k+1 cannot present before k's 5 s slot ends, and the KV dependency on k | **Accepted** | ready = max(lock + G_a, done_k) + G_1 + δ; present = max(ready, V_k + R). Just-in-time locking (lock at V_k + R − Λ − σ) is adopted, with early lock and L=1 as contrasts. Targets recomputed (≈7 / 8.5 / 13.5 s illustrative medians) |
| 2 | major | The correction chain omits synthesis, compile, moderation and encode; the "k+2 cap" is wrong | **Accepted** | Chain C is defined in full; the correction enters the first request j with P_j ≥ visible + C, with no cap. The condition for reaching k+1 is stated |
| 3 | major | The H3 prompt contract is not demonstrated (a string per request, `<d>` tags; six-field format is LTX's); voice has no reference; generated speech is unchecked | **Accepted.** Claude read the real H3 format in `examples/prompts_60s.json` | A BlockScript → compiled H3 prompt example is added in the actual `integrated_multimodal_description`/`<d>` format. E1 tests exact spoken content and speaker identity. Generated speech is ASR-checked within σ before presentation, with the added delay measured |
| 4 | major | RQ5 has no matched untyped comparator; ASR spot audit cannot certify zero leaks | **Accepted** | Four memory arms with a matched retrieval budget. All ~900 probe-response audio clips are fully listened to by two raters; ASR sensitivity is validated |
| 5 | major | RQ4 arms confound ledger with correction or reset | **Accepted** | 7-arm factorial with matched prompt budget and reset frequency, including ledger-only and no-ledger controls |
| 6 | major | The bandit is not isolated or frozen; canon risk; the per-axis factorization was misdescribed | **Accepted** | Per-axis updates; canon-preserving arms; trained on separate pilot sessions and frozen during evaluation; a separate randomized ablation |
| 7 | minor | VQQA also runs CogVideoX-5B locally | **Accepted** | Corrected |
| zh1 #9 | residual | The abstract says rolling KV is the "only" state; 0.68× labelled as a citation | **Accepted** | Fixed ("main state" plus the other items; 0.68× is 【推导】) |

### zh3: round 3 (reviewed a revision where the v2.2 edits had silently failed to apply)

Model gpt-6-sol (rollout verified). **Verdict: not ready.** The carried-over findings (zh2 #1, #2 and #4–#7, zh1 #9)
were correct, because the text had not changed. New findings:

| # | Sev. | Issue | Disposition | Resolution (v2.3, verified by grep before commit) |
|---|---|---|---|---|
| carried | blocking/major | zh2 #1–#7 and zh1 #9 not present in the text | **Accepted** | All applied in v2.3: JIT lock with presentation slot + KV dependency; full correction chain C with no cap; compiled H3 prompt example in the real `integrated_multimodal_description`/`<d>` format; four memory comparators + full listening of ~900 probe clips; 7-arm factorial RQ4; per-axis, canon-preserving, frozen bandit; VQQA's local CogVideoX; state/label fixes |
| 3 | blocking | M0 cannot qualify end-to-end timing before T1–T3 exist (the released path precomputes all audio and writes one MP4 at the end) | **Accepted** | M0 is now per-component profiling only. End-to-end qualification (Λ, σ, throughput, jitter, 3 × 30 min soak) moves to M1, after T1–T3. §1.2 first demo requires M1 qualification |
| 4 | major | Speech guarantees overstated; pre-generation moderation cannot catch off-script speech | **Accepted** | "Guarantee scope" paragraph: WER and speaker tests in E1; ASR check of the generated audio inside σ before presentation (the teacher audio is ready at P+G_a), with added delay and false-block rate measured; otherwise the lack of a guarantee is stated |
| 7 | major | No interactive system-level baseline for the backbone decision | **Accepted** | A0 (LLM + streaming TTS + real-time audio-driven avatar, same memory) reinstated as the system baseline. RQ6 now compares A2 vs A0 in both directions |
| 8 | major | The near-real-time fallback lacks a stable service rule | **Accepted** | Turn-based mode, admission control (≤ 1 pending instruction, newer supersedes, skipped logged), optional slowed playback (≥ 20 fps); E2 measures wait growth |
| 9 | minor | Label and source scope | **Accepted** | 17.29 s marked as a separate benchmark; 0.68× 【推导】; VQQA local generator |

===== FILE: docs/reviews/zh1_ev_taomate_code.md =====
# TaoMate-H3 code excerpts @ 6b2f9984acf681e2f387188f5d1f3b26e504315b

## config.py:15-40
```python
   15  class DirectPolicy:
   16      """The validated direct streaming contract.
   17  
   18      These values are deliberately not command-line options. Changing one of
   19      them creates a different inference method and must be evaluated separately.
   20      """
   21  
   22      request_seconds: int = 5
   23      chunk_group_counts: tuple[int, ...] = (2, 2, 2, 1)
   24      precision: str = "bf16_with_interior_fc1_qkv_w8a8"
   25      attention_backend: str = "flash_attn_3"
   26      persistent_kv: str = "clean_audio_video"
   27      video_kv_retention: str = "first_video_sink_plus_recent_2_chunks"
   28      audio_kv_retention: str = "match_video"
   29      audio_kv_reset_window_requests: int = 12
   30      prompt_scope: str = "current_request"
   31      rope: str = "split_temporal_spatial"
   32      audio_guidance: str = "fl2va_tail40_rollover"
   33      audio_guidance_state_numbers: tuple[int, ...] = (3, 6, 9)
   34      stage3_target_state_indices: tuple[int, ...] = (16, 33, 49)
   35      prefix_normalization: str = "affine_to_first_stream_chunk"
   36      canonical_continuation_geometry: bool = True
   37      publication: str = "one_shot_audio_video_vae"
   38  
   39      def to_dict(self) -> dict[str, Any]:
   40          return asdict(self)
```

## config.py:80-134
```python
   80  def load_prompt_json(path: Path) -> tuple[tuple[str, ...], tuple[int, ...] | None]:
   81      try:
   82          payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
   83      except (OSError, UnicodeError, json.JSONDecodeError) as exc:
   84          raise ValueError(f"cannot read prompt JSON: {exc}") from exc
   85      prompts = payload.get("prompts") if isinstance(payload, Mapping) else None
   86      if not isinstance(prompts, list) or not prompts:
   87          raise ValueError('prompt JSON must contain {"prompts": ["...", "..."]}')
   88      normalized: list[str] = []
   89      for index, prompt in enumerate(prompts):
   90          if not isinstance(prompt, str) or not prompt.strip():
   91              raise ValueError(f"prompt JSON item {index} must be a non-empty string")
   92          normalized.append(prompt.strip())
   93      raw_seeds = payload.get("seeds")
   94      if raw_seeds is None:
   95          seeds = None
   96      elif (
   97          not isinstance(raw_seeds, list)
   98          or len(raw_seeds) != len(normalized)
   99          or any(type(seed) is not int or seed < 0 for seed in raw_seeds)
  100      ):
  101          raise ValueError("prompt JSON seeds must be one non-negative integer per prompt")
  102      else:
  103          seeds = tuple(raw_seeds)
  104      return tuple(normalized), seeds
  105  
  106  
  107  def resolve_prompts(
  108      *,
  109      prompt: str | None,
  110      prompt_json: Path | None,
  111      duration_seconds: int | None,
  112  ) -> tuple[tuple[str, ...], int, tuple[int, ...] | None]:
  113      if (prompt is None) == (prompt_json is None):
  114          raise ValueError("choose exactly one of --prompt or --prompt-json")
  115      if prompt_json is not None:
  116          supplied, seeds = load_prompt_json(prompt_json)
  117      else:
  118          supplied, seeds = (str(prompt).strip(),), None
  119      if any(not item for item in supplied):
  120          raise ValueError("prompt must not be empty")
  121      if duration_seconds is None:
  122          duration_seconds = (
  123              len(supplied) * SEGMENT_SECONDS if prompt_json is not None else SEGMENT_SECONDS
  124          )
  125      if duration_seconds <= 0 or duration_seconds % SEGMENT_SECONDS:
  126          raise ValueError("duration must be a positive multiple of 5 seconds")
  127      request_count = duration_seconds // SEGMENT_SECONDS
  128      if prompt_json is not None:
  129          if len(supplied) != request_count:
  130              raise ValueError("prompt JSON count must equal duration divided by 5 seconds")
  131          prompts = supplied
  132      else:
  133          prompts = supplied * request_count
  134      return prompts, duration_seconds, seeds
```

## streaming/geometry.py:170-202
```python
  170          }
  171  
  172  
  173  def direct_5s_plan() -> StreamPlan:
  174      """Return the validated four-chunk plan for one five-second request."""
  175  
  176      native_frame_count = 124
  177      phases: list[StreamPhase] = []
  178      frame_stop = 0
  179      video_stop = 0
  180      for index, groups in enumerate((2, 2, 2, 1)):
  181          frame_start = frame_stop
  182          video_start = video_stop
  183          frame_stop += groups * VIDEO_GROUP_FRAMES
  184          video_stop += groups * VIDEO_GROUP_LATENTS
  185          if index == 0:
  186              frame_stop += VIDEO_PREFIX_FRAMES
  187              video_stop += VIDEO_PREFIX_LATENTS
  188          phases.append(
  189              StreamPhase(
  190                  index=index,
  191                  group_count=groups,
  192                  frame_start=frame_start,
  193                  frame_stop=frame_stop,
  194                  video_latent_start=video_start,
  195                  video_latent_stop=video_stop,
  196                  audio_latent_start=_audio_latent_boundary(frame_start),
  197                  audio_latent_stop=_audio_latent_boundary(frame_stop),
  198              )
  199          )
  200      return StreamPlan(native_frame_count=native_frame_count, phases=tuple(phases))
  201  
  202  
```

## streaming/cache.py:200-222
```python
  200  
  201          self._commit_token_counts.append(token_count)
  202          self._commit_token_tags.append(self._staged_tags)
  203          self._block_index += 1
  204          self._clear_staging()
  205  
  206      def retain_sink_and_recent_commits(self) -> None:
  207          """Keep the first chunk's video sink and the most recent clean chunks."""
  208  
  209          if self.clean_commit_active:
  210              raise RuntimeError("cannot trim persistent KV during an active clean commit")
  211          block_count = len(self._commit_token_counts)
  212          # As soon as three clean chunks exist, age chunk zero to a video-only
  213          # sink and keep chunks one and two as the two complete AV recents.
  214          if block_count <= 2:
  215              return
  216  
  217          recent_start = max(1, block_count - 2)
  218          selection = [(0, True)] + [(index, False) for index in range(recent_start, block_count)]
  219          self._retain_commit_rows(selection)
  220  
  221      def drop_audio_history(self) -> int:
  222          """Remove audio rows while preserving every retained video row."""
```

## streaming/attention_hook.py:38-52
```python
   38  
   39  class H3StreamingAttentionHook:
   40      """Condition current media on text, persistent clean AV KV, and current KV."""
   41  
   42      def __init__(self, cache: CleanAVKVCache, *, backend: str = "flash_attn_3") -> None:
   43          if backend != "flash_attn_3":
   44              raise ValueError("the accelerated direct runtime requires FlashAttention-3")
   45          try:
   46              from flash_attn_interface import flash_attn_func
   47          except ImportError as exc:
   48              raise RuntimeError("FlashAttention-3 kernels are required") from exc
   49          self.cache = cache
   50          self._flash_attention = flash_attn_func
   51          self.kernel_calls = 0
   52          self.query_tokens = 0
```

## streaming/runtime.py:335-362
```python
  335          .view(-1, int(rows.shape[-1]))
  336      )
  337  
  338  
  339  def _base_audio_teacher_step_callback(
  340      teacher: dict[str, Any],
  341      *,
  342      phase: StreamPhase,
  343      total_audio_latents: int,
  344  ) -> Callable[[int, Any, Any], None]:
  345      """Inject the request-wide Base10 milestone used by one Stage3 loop."""
  346  
  347      milestones = teacher["milestones"]
  348  
  349      def on_step(step_index: int, video_rows: Any, audio_rows: Any) -> None:
  350          milestone = milestones.get(step_index)
  351          if milestone is not None:
  352              teacher_rows = _teacher_phase_audio_rows(
  353                  milestone,
  354                  phase=phase,
  355                  total_audio_latents=total_audio_latents,
  356              )
  357              audio_rows.copy_(teacher_rows)
  358  
  359      return on_step
  360  
  361  
  362  @contextmanager
```

## streaming/runtime.py:445-465
```python
  445              self._cache.clear()
  446              self._cache = None
  447          self._canonical_transport_video_rows = None
  448          self._canonical_transport_audio_rows = None
  449          self._prefix_renorm_video_anchor = None
  450  
  451      def _renorm_clean_video_rows(self, rows: Any) -> Any:
  452          """Match generated blocks to persistent block-zero statistics."""
  453  
  454          current = rows.detach().float()
  455          mean = current.mean(dim=0, keepdim=True)
  456          std = current.std(dim=0, keepdim=True, unbiased=False).clamp_min(1e-6)
  457          if self._prefix_renorm_video_anchor is None:
  458              self._prefix_renorm_video_anchor = (mean, std)
  459              return rows
  460          anchor_mean, anchor_std = self._prefix_renorm_video_anchor
  461          normalized = (current - mean).div(std).mul(anchor_std).add(anchor_mean)
  462          return normalized.to(dtype=rows.dtype)
  463  
  464      def dit_timing_receipt(self) -> dict[str, float | int]:
  465          """Return synchronized Transformer-only CUDA time across all ranks."""
```

## streaming/runtime.py:600-625
```python
  600                  request_index=request_index,
  601                  audio_latent_count=total_audio_latents,
  602                  device=cuda_device,
  603              )
  604  
  605              with H3StreamingSession(
  606                  active_plan,
  607                  cache=cache,
  608              ) as session:
  609                  for phase in phases:
  610                      branch = _build_phase_branch(
  611                          positive=positive,
  612                          phase=phase,
  613                          latent_h=latent_h,
  614                          latent_w=latent_w,
  615                          model=model,
  616                          device=cuda_device,
  617                          text_token_tags=text_token_tags,
  618                          media_time_origin=media_time_origin,
  619                          video_latent_offset=self._video_latent_offset,
  620                          audio_latent_offset=self._audio_latent_offset,
  621                      )
  622                      position_capture["phases"].append(
  623                          {
  624                              "phase_index": phase.index,
  625                              **dict(branch._taomate_h3_position_capture),
```

## streaming/runtime.py:735-745
```python
  735              if joined_video.shape != request_video_rows.shape:
  736                  raise RuntimeError("reassembled streaming video rows changed request shape")
  737              if joined_audio.shape != initial_audio.shape:
  738                  raise RuntimeError("reassembled streaming audio rows changed request shape")
  739              final_teacher = audio_teacher["milestones"][2]
  740              if not torch.equal(joined_audio, final_teacher):
  741                  raise RuntimeError(
  742                      "published streaming audio differs from Base teacher clean latent"
  743                  )
  744              audio_teacher_receipt = dict(audio_teacher["receipt"])
  745              audio_teacher_receipt["published_clean_audio_exact_match"] = True
```

## runner.py:285-330
```python
  285          },
  286      )
  287      runtime = H3Runtime(
  288          model_root=config.model_root,
  289          adapter_root=config.adapter,
  290          output_root=config.output_dir,
  291          ulysses_degree=config.ulysses_degree,
  292      )
  293      precomputed = runtime.precompute_text_prompts(config.prompts)
  294      video_segments: list[Any] = []
  295      audio_segments: list[Any] = []
  296      streaming = H3StreamingRuntime(base10_teacher=teacher)
  297      runtime.reset_dit_peak_memory()
  298      noise_contract: list[dict[str, int]] = []
  299      for request_index, (text_features, request_seed) in enumerate(
  300          zip(precomputed, config.request_seeds, strict=True)
  301      ):
  302          video_noise_seed = (
  303              request_seed + request_index * _VIDEO_NOISE_REQUEST_STRIDE
  304          ) % (2**63)
  305          audio_noise_seed = teacher.audio_noise_seed(request_index)
  306          video_latents, audio_latents = runtime.generate_latents(
  307              video_noise_seed=video_noise_seed,
  308              audio_noise_seed=audio_noise_seed,
  309              width=config.width,
  310              height=config.height,
  311              precomputed_text=text_features,
  312              denoise_loop=streaming.run,
  313          )
  314          video_segments.append(video_latents)
  315          audio_segments.append(audio_latents)
  316          noise_contract.append(
  317              {
  318                  "request_index": request_index,
  319                  "authored_seed": request_seed,
  320                  "video_noise_seed": video_noise_seed,
  321                  "audio_noise_seed": audio_noise_seed,
  322              }
  323          )
  324      dit_timing = streaming.dit_timing_receipt()
  325      dit_memory = runtime.dit_peak_memory_receipt()
  326      streaming.release_retained_state()
  327      publication_started = time.perf_counter()
  328      publication = _publish(
  329          runtime=runtime,
  330          config=config,
```

## cli.py:125-150
```python
  125  def _validate_acceleration_runtime() -> None:
  126      """Fail before torchrun when a required GPU acceleration module is absent."""
  127  
  128      try:
  129          vllm_ops = importlib.import_module("vllm._custom_ops")
  130          flash_attn = importlib.import_module("flash_attn_interface")
  131          importlib.import_module("triton")
  132      except ImportError as exc:
  133          raise ValueError(f"accelerated runtime dependency is unavailable: {exc}") from exc
  134      if not all(
  135          callable(getattr(vllm_ops, name, None))
  136          for name in ("scaled_int8_quant", "cutlass_scaled_mm")
  137      ):
  138          raise ValueError("vLLM CUTLASS W8A8 operations are unavailable")
  139      if not callable(getattr(flash_attn, "flash_attn_func", None)):
  140          raise ValueError("FlashAttention-3 interface is unavailable")
  141  
  142  
  143  def _validate_output(output: Path) -> None:
  144      if output.exists():
  145          if not output.is_dir() or any(output.iterdir()):
  146              raise ValueError("--output must be a new or empty directory")
  147  
  148  
  149  def _prepare_output(config: DirectRunConfig) -> Path:
  150      output = config.output_dir
```

## cli.py:215-232
```python
  215          _validate_input_paths(config)
  216      except (OSError, ValueError) as exc:
  217          parser.error(str(exc))
  218      print("Powered by MiniMax H3.", flush=True)
  219      with TemporaryDirectory(prefix="taomate-h3-audio-", dir="/dev/shm") as temporary:
  220          temporary_root = Path(temporary)
  221          audio_guidance_dir = temporary_root / "guidance"
  222          print("Preparing audio guidance...", flush=True)
  223          launch_audio_guidance(
  224              config,
  225              output_dir=audio_guidance_dir,
  226          )
  227          config_path = _prepare_output(config)
  228          print("Generating audio and video...", flush=True)
  229          launch(config, config_path, audio_guidance_dir)
  230      return 0
  231  
  232  
```
