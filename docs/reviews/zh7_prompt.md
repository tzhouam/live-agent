You are GPT-6 Sol, the INDEPENDENT REVIEWER for the "live-agent" project (AGENTS.md rules: read-only; numbered findings tagged blocking/major/minor). ROUND 7 (zh7) of the review of the owner-directed Chinese rewrite (TaoMate-H3 base + Google agentic suite, D-017). The review log (inlined) records that rounds zh3 and zh5 reviewed text where the author's edits had failed to apply; this round reviews v2.5 after your zh6 finding.
1. State RESOLVED / PARTIALLY / NOT RESOLVED for your zh6 new finding (E2 gating vs the near-real-time fallback), checking §1.2 and §6.4 text.
2. Do a final whole-document pass for any remaining BLOCKING or MAJOR issue. Do not re-raise resolved items unless the text regressed.
3. Verdict: ready / ready with minor fixes (list them exactly) / not ready. Be concise.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/research_proposal_zh.md =====
# 在线智能体导演：基于 TaoMate-H3 的实时个性化直播数字人

**研究提案（中文版 v2.5，2026-09-25）**

*v2.5：已按 GPT-6 Sol 评审（zh1–zh6）修订。本版依据项目负责人的指示重写（决策 D-017）。生成底座由 LingBot-World 2.0 改为 TaoMate-H3，系统架构借鉴 Google 长视频智能体套件（Co-Director / CANVAS / A²RD / VQQA）。英文 v1.0（`docs/research_proposal.md`）保留为上一版。*

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
- **准入控制：** 同时最多有 1 条未执行的指令。更新的指令取代旧指令，被取代的记为「已跳过」。
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
| 指令级成功率（H1a，主） | A2 − A1 ≥ +10 pp，成对 CI 不含 0 |
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

本中文版（v2.0 → v2.5）属于重大架构变更。它提交 GPT-6 Sol（Codex）独立评审，记录见 `docs/codex_reviews.md` 的「中文 v2.0」一节。

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

### zh4: round 4 (v2.3)

> **Correction (added after zh5).** The "Resolution (v2.4)" column below was logged before the edits were verified. The v2.4 edit script aborted on a mismatch in the §8 TVC row: that row still held v2.1 text, because v2.3 had never updated it. The chained shell command committed and ran zh5 anyway, so **zh5 reviewed unchanged text** and correctly reported NOT RESOLVED. **Process fix:** edits are now all-or-nothing scripts, run and grep-verified as a separate step, and logging and review happen only after verification. The resolutions were then applied for real and verified; see zh5 below.

Model gpt-6-sol (rollout verified). zh3 items: all RESOLVED except zh2 #5 and zh3 #3 (PARTIALLY). No new blocking
issue. **Verdict: not ready.**

| # | Sev. | Issue | Disposition | Resolution (v2.4) |
|---|---|---|---|---|
| 1 | major | RQ4 arm 5 (random restatement) vs arm 4 (targeted correction) differs by more than ledger access | **Accepted** | Arms 5 and 7 use the same drift detector, rule and timing; the correction or reset text comes from the static canon only. Arm 4 vs 5 and 6 vs 7 differ **only** in ledger access |
| 2 | major | §8 conditions on "M0-measured Λ", which M0 cannot measure; co-residency cannot be measured on the sequential released path | **Accepted** | Condition moved to M1. Co-residency is measured with a dedicated harness after T2, in M1 |
| 3 | major | No requalification after M2 adds the speech chain, controller, VLM and memory | **Accepted** | Three-step qualification: M0 profiling → M1 generator + playback → end-of-M2 whole-system soak. Only then "real-time live agent", and E2/E5 start. §1.2 and §9.1 updated |
| 4 | minor | RQ3 wording in §8; unlabelled counts; version labels | **Accepted** | Cross-backbone vs within-LTX made explicit; counts labelled 【目标】; title and §12 now v2.3 |

### zh5: round 5 (reviewed unchanged v2.3 text; see the correction above)

Model gpt-6-sol (rollout verified). It correctly reported zh4 #1–#4 NOT RESOLVED and raised no new issues.
**Verdict: not ready.** Resolution: the v2.4 edits were applied with an all-or-nothing script and verified by grep:
- the RQ4 arm-5/7 wording;
- the §8 TVC row: M1 condition, cross-backbone wording, TFMR, and a spoken-audio ASR check;
- the M0 co-residency sentence moved to M1;
- the three-step qualification, with whole-system requalification at the end of M2;
- the §1.2 first-demo gate;
- the M2 row;
- 【目标】 labels;
- v2.4 version labels.

Three residual "M0 measures end-to-end" references were also fixed (§1.1 table, §6.4 heading, §9.3 risk row).

### zh6: round 6 (verified v2.4, commit ee7c7d5)

Model gpt-6-sol (rollout verified). zh4 #1–#4 were all **RESOLVED**. One new major finding: the near-real-time fallback
promises E2 measurements, but E2 was gated on passing real-time requalification. **Verdict: not ready.**
**Resolution (v2.5, verified by grep):** if the end-of-M2 gate fails, E2/E5 still run under the near-real-time service
rule and are labelled "near-real-time". The RQ1/RQ2/RQ4/RQ5 contrasts stay valid (shared substrate). Latency results
are reported as measured, and no §8 real-time target is claimed. §1.2 and §6.4 are consistent.
