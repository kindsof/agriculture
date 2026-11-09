# 农业 AI 模型与技能信息汇总

> 每日跟踪 **Hugging Face 农业相关大模型**、**GitHub 农业模型相关项目** 与 **农业 Agent Skill**，汇总为本文档。
> 最近更新：**2026-11-09**（首版）。采集与更新方法见文末[「方法与维护」](#九方法与维护)。
>
> 配套文件：[机器可读目录 `ai/catalog.yaml`](catalog.yaml) ｜ [实时数据 `ai/stats.json`](stats.json) ｜ [维护说明 `ai/README.md`](README.md) ｜ 采集脚本 [`scripts/fetch_ai_catalog.py`](../scripts/fetch_ai_catalog.py)

## 目录

1. [概览](#一概览)
2. [农业专用大语言模型](#二农业专用大语言模型)
3. [GitHub 农业模型项目](#三github-农业模型项目)
4. [农业 Agent Skill](#四农业-agent-skill)
5. [农业 MCP 服务器](#五农业-mcp-服务器)
6. [数据集与语料](#六数据集与语料)
7. [实时数据快照](#七实时数据快照每日自动更新)
8. [趋势观察](#八趋势观察)
9. [方法与维护](#九方法与维护)
10. [更新记录](#十更新记录)

## 一、概览

「农业 × 大模型」生态目前分为四个层次，本文档按此分层收录：

| 层次 | 内容 | 代表 |
|---|---|---|
| 领域大模型 | 在开源基座上继续预训练 / 指令微调的农业专用 LLM | 司农 Sinong、后稷 AgriMa、AI4YO、AgriGPT-7B |
| 项目与基准 | 农业 RAG / 智能体系统、评测基准、论文列表 | SeedBench、AgriBench、AgriManager、CDIP-ChatGLM3 |
| 技能（Skills） | 以 `SKILL.md` 形式封装、可被 Claude Code / Codex 等智能体加载的农业知识与工具包 | skills-for-agriculture、academic-skills-food-nutrition、faostat-skills |
| 数据接入 | MCP 服务器与训练语料，为模型和智能体提供农业数据源 | faostat-mcp、agrobr-mcp、KisanVaani 问答语料 |

要点速览（详见各节与[趋势观察](#八趋势观察)）：

- **中文农业大模型在 2024–2026 年密集落地**：后稷 AgriMa（2024，Baichuan 底座）→ 天工开悟 KwooLa（2024–2025，已上线 App 与 API）→ 司农 Sinong（2026-01，南京农业大学，国内首个通用农业开源垂直 LLM，8B/32B 已在魔搭开源）。
- **智能体化是当前最活跃的方向**：从「一个问答模型」转向「模型 + 检索增强 + 工具 / 技能」，欧盟 GARDen、AgriManager（NeurIPS 2026）与各类农场智能体都属于这一类。
- **Agent Skill 生态起步**：2025 年起出现成规模的农业技能包（澳大利亚 skills-for-agriculture、墨尔本大学食品科学技能包、FAOSTAT 技能包等），与 MCP 服务器配套构成智能体的「知识 + 数据」两层。

## 二、农业专用大语言模型

### 2.1 中文模型

| 模型 | 研发方 | 基座 | 规模 / 形态 | 说明 |
|---|---|---|---|---|
| **司农 Sinong 1.0** | 南京农业大学（NAULLM） | Qwen3-8B / 32B（魔搭镜像页标注） | 8B、32B，权重开源 | 2026-01 发布，称**国内首个通用农业领域开源垂直大语言模型**。数据覆盖动物科学、农业经济与管理、农业资源与环境、园艺、植保、作物育种、智慧农业等学科：书籍 8,863 册、论文 243,897 篇、政策标准专利 196,748 份，总量超 40 亿 token；训练含合成数据、CoT 与 in-context 指令、RL，并配套多智能体检索增强框架。权重：[ModelScope NAULLM/Sinong1.0-8B](https://modelscope.cn/models/NAULLM/Sinong1.0-8B)、[Sinong1.0-32B](https://modelscope.cn/models/NAULLM/Sinong1.0-32B)；HF 镜像 [model-scope/Sinong1.0-32B](https://huggingface.co/model-scope/Sinong1.0-32B) 及社区 GGUF；代码与文档见 [njauzzx/Sinong](https://github.com/njauzzx/Sinong) |
| **后稷 AgriMa** | 山西省后稷实验室、山西农业大学、山西大学、武汉大学 | Baichuan | 作物学问答微调版 | 2024-02 发布，称「首个中文开源农业大模型」；仅作物学领域先行开源，指令集需邮件申请，**仅限科研使用**。[仓库](https://github.com/zhiweihu1103/AgriMa) |
| **稷丰 AgriAgent** | 同上 | MiniCPM-Llama3-V-2.5 | 多模态 | 2024-06 发布的中文农业多模态模型。[仓库](https://github.com/zhiweihu1103/AgriAgent)；另有后续体系 [AgriMind](https://github.com/zhiweihu1103/AgriMind) |
| **天工开悟（KwooLa / KwooVa / KwooGr）** | 哈尔滨工业大学等 | 开源基座微调 | 问答 / 多模态 / 生长预测三模型 | KwooLa 为农业问答主线：2025-03 上线 iOS 与 OpenAI 兼容 API，2025-06 加入深度思考，2025-10 发布 2.0（SQL 数据库对话 + 表格分析）。[KwooLa](https://github.com/HIT-Kwoo/KwooLa)、[KwooVa 多模态](https://github.com/HIT-Kwoo/KwooVa)、[KwooGr 生长](https://github.com/HIT-Kwoo/KwooGr) |
| **AgriGPT 系列** | CSTR4019 等（AgriGPTs 社区） | LLaMA-2 / ChatGLM2 | 6B / 7B / 13B | 2023 年启动的中文农业 LLM 研究项目，附 arXiv 论文；HF 上有多个权重仓（[AgriGPT/AgriGPT-7B](https://huggingface.co/AgriGPT/AgriGPT-7B)、[AgriGPTs/AgriGPT-6B](https://huggingface.co/AgriGPTs/AgriGPT-6B) 等），活跃度一般。[项目页](https://github.com/AgriGPTs/AgriGPTs) |
| **DeepSeek-R1-agriculture** | isAsong | DeepSeek-R1（LoRA） | 微调适配器 | 中文农业推理微调实验，有 GGUF。[模型页](https://huggingface.co/isAsong/DeepSeek-R1-agriculture) |
| **农业 mKG-RAG 系统** | hanhuiyang5-web | 大模型 + 多模态知识图谱 | 问答系统 | 支持文本 / 图片三类输入的知农问答。[仓库](https://github.com/hanhuiyang5-web/Agri-mKGraphrag) |

### 2.2 日文模型

| 模型 | 研发方 | 说明 |
|---|---|---|
| **AI4YO** | 日本农业·食品产业技术综合研究机构 NARO（农村工学研究所）等 | 2025 年宣布开发的**日本首个农业专用生成式 AI**，联合业界以日语网页资源与农业知识构建（[NARO 新闻稿](https://www.naro.go.jp/publicity_report/press/laboratory/rcait/166108.html)）。面向设施园艺、病虫害问答等场景，权重与商用条件见官方公告 |

### 2.3 英文与其他语种模型

| 模型 | 语种 | 基座 | 说明 |
|---|---|---|---|
| **Natural Farmer 系列**（llama-3.1-natural-farmer、Gemma2B-NaturalFarmerV1、Mistral7B-NaturalFarmerV4 等） | en | LLaMA-3.1-8B / Gemma-2B / Mistral-7B / Qwen3.5-2B | CopyleftCultivars（OpenAgTech 开源农机社区）组织的**农民可自训**的自然农耕 LLM 族，含 GGUF 量化与 0.6B/1.7B 蒸馏版，配套 RL 训练数据；[组织页](https://huggingface.co/CopyleftCultivars) |
| **AgriManager 微调族** | en | Qwen 系（DSSAT / WOFOST / cycles 多方案） | 农场管理决策的 LLM-RL 微调与泛化基准（NeurIPS 2026 E&D），对接作物模型模拟环境；[仓库](https://github.com/AgriManager-Framework/AgriManager)、[权重](https://huggingface.co/AgriManager-Framework) |
| **agronomYi-hermes-34B** | en | Yi-34B（Hermes 指令版） | 农艺方向微调，有 GGUF；[模型页](https://huggingface.co/gbstox/agronomYi-hermes-34B) |
| **[Qwen3-3.3B-Agricultural-Reasoning](https://huggingface.co/BUAIR/Qwen3.3B-Agricultural-Reasoning)** | en | Qwen3-3.5B LoRA | 乌干达农业场景推理微调（BUAIR）；另有 [Bateesa 的 Qwen2.5/Qwen3 同级系列](https://huggingface.co/Bateesa/Qwen2.5-Agricultural-Reasoning_v4) |
| **dhenu-vision-qwen2.5-7b-grpo-crop-disease** | en | Qwen2.5-VL-7B（GRPO） | 作物病虫害视觉问答的 GRPO 强化学习微调；[模型页](https://huggingface.co/chheplo/dhenu-vision-qwen2.5-7b-grpo-crop-disease) |
| **agriculture-bert-uncased** | en | BERT | 农业语料继续预训练 BERT，HF「agriculture」检索下下载量最高的分类底座之一；[模型页](https://huggingface.co/recobo/agriculture-bert-uncased) |
| **小语种小农模型族** | so / am / ne / ny / ta 等 | LLaMA / MiniCPM / Qwen2.5 / GPT-2 | 地区公益项目产物：[索马里语 tacab/somali-agriculture](https://huggingface.co/tacab/somali-agriculture)、[阿姆哈拉语 BekiTila/Amharic-llama-for-agriculture-chat-bot](https://huggingface.co/BekiTila/Amharic-llama-for-agriculture-chat-bot)、[尼泊尔语 aarajbhattarai/minicpm5-2b-nepali-agriculture](https://huggingface.co/aarajbhattarai/minicpm5-2b-nepali-agriculture)、[马拉维语 PatrickChikuse/qwen25-1.5b-malawi-agriculture](https://huggingface.co/PatrickChikuse/qwen25-1.5b-malawi-agriculture)、[泰米尔语 Kobi-01/mistral_7b_agriculture](https://huggingface.co/Kobi-01/mistral_7b_agriculture) 等 |

> 注：Hugging Face 上尚有大量个人课程 / 黑客松级别的农业微调（phi3、tinyllama、gemma-270m 等），下载量与代码质量参差，未全部收录；完整清单见[每日数据快照](#七实时数据快照每日自动更新)与平台检索。

## 三、GitHub 农业模型项目

### 3.1 评测基准

| 项目 | 发布方 | 年份 | 说明 |
|---|---|---|---|
| [Yutong-Zhou-cv/AgriBench](https://github.com/Yutong-Zhou-cv/AgriBench) | ECCV 2024 Workshop | 2024 | 首个评测多模态大模型的农业基准：8 类农业视觉任务（识别、计数、病害、农业知识问答等） |
| [InternScience/SeedBench](https://github.com/InternScience/SeedBench) | 上海人工智能实验室 InternScience（ACL 2025） | 2025 | 种子科学多任务基准，评测 LLM 在种子科学的事实、推理与安全性 |
| [AgriManager-Framework/AgriManager](https://github.com/AgriManager-Framework/AgriManager) | NeurIPS 2026 E&D | 2026 | LLM 强化学习在农场管理决策中的泛化框架与基准，模拟环境对接 DSSAT、WOFOST、cycles |
| [trust-nlp/PlantXpert](https://github.com/trust-nlp/PlantXpert) | TrustNLP | 2026 | 科研级作物图像 → 农学推理的多模态基准（论文配套，活跃开发中） |
| [sanmay4119/geofm-agriculture-benchmark](https://huggingface.co/datasets/sanmay4119/geofm-agriculture-benchmark) | — | 2026 | 地理空间基础模型（GeoFM）的农业下游基准 |
| [norjordAI/nor_agriculture_bench](https://huggingface.co/datasets/norjordAI/nor_agriculture_bench) | norjordAI | 2026 | 挪威语农业问答基准（另有含模型对比结果的版本） |

### 3.2 论文与资源列表

| 列表 | 说明 |
|---|---|
| [JiajiaLi04/Agriculture-Foundation-Models](https://github.com/JiajiaLi04/Agriculture-Foundation-Models) | 农业基础模型 / LLM 论文列表，持续维护，入门首选 |
| [JiajiaLi04/Multi-Modal-LLMs-in-Agriculture](https://github.com/JiajiaLi04/Multi-Modal-LLMs-in-Agriculture) | 农业多模态 LLM 论文列表 |
| [satellite-image-deep-learning/techniques](https://github.com/satellite-image-deep-learning/techniques) | 卫星 / 航空影像深度学习技术清单（农情遥感部分常用） |

### 3.3 RAG、智能体与系统

| 项目 | 说明 |
|---|---|
| [zlatko-lakisic/agentic-orchestration](https://github.com/zlatko-lakisic/agentic-orchestration) | 欧盟 GARDen 项目的农业多智能体编排框架，配置中接入 HF 托管的 AgriAssist LLM |
| [Rekin226/Agronaut](https://github.com/Rekin226/Agronaut) | 本地运行的开源农艺智能体（Telegram / CLI 接入），2026-10 起活跃 |
| [Shuvam-Banerji-Seal/AgriIR](https://github.com/Shuvam-Banerji-Seal/AgriIR) | 可配置的农业领域 RAG 检索框架，六阶段管线 |
| [SmartAG-Team/CDIP-ChatGLM3](https://github.com/SmartAG-Team/CDIP-ChatGLM3) | CNN 病害识别 + ChatGLM3 处方生成的一体化植保系统 |
| [giri164/krishi-sahayak](https://github.com/giri164/krishi-sahayak) | 印度面向农民的语音 + 多语言 RAG 助手（英语 / 泰卢固语 / 印地语） |
| [DreamRealized/agriculture-chatbot](https://github.com/DreamRealized/agriculture-chatbot) | React 前端 + RAG 后端的农业顾问，2026-11 活跃 |
| [juni2003/Smart-Farming-Agentic-AI](https://github.com/juni2003/Smart-Farming-Agentic-AI) | 全栈 agentic 精准农业：作物推荐 + 病害检测 + 农事建议 |
| [xia-z-x/AgrIculture](https://github.com/xia-z-x/AgrIculture) | 无人机 + 图像识别 + LLM 的智慧农业实践汇总（中文） |

> 本类项目更替很快：多数为近期涌现的开源农场助手，星标不高但更新频繁；筛选口径见[「方法与维护」](#九方法与维护)。

## 四、农业 Agent Skill

以 `SKILL.md` 格式封装、可被 Claude Code / Codex / OpenClaw 等智能体加载的农业技能包：

| 技能包 | 维护方 | 内容 |
|---|---|---|
| [human-avatar/skills-for-agriculture](https://github.com/human-avatar/skills-for-agriculture) | human-avatar | 40+ 个 `s4ag-*` 决策技能：土壤、植保、堆肥、农林业、养蜂、菌菇、果树、牧场、碳汇、认证、市场直销、自然农法（含韩系有机农法）等；Claude Code 插件格式，可经 npm 安装 |
| [PangenomeAI/academic-skills-food-nutrition](https://github.com/PangenomeAI/academic-skills-food-nutrition) | 墨尔本大学食品科学组 | 食品 / 营养 / 农业科研技能（MIT）：多智能体文献综述与系统综述、期刊导向写作与选刊（150+ 期刊作者指南）、同行评审、项目建议书、图表与可编辑 PPTX；适配 Claude Code、Codex、MiniMax Agent、OpenClaw、Grok |
| [berba-q/faostat-skills](https://github.com/berba-q/faostat-skills) | berba-q | 分析联合国 FAOSTAT 数据的技能：国别农业概况、贸易分析、气候评估；配套 [faostat-mcp](https://github.com/berba-q/faostat-mcp) |
| [Adilmunawar/ZD-claude-plugin](https://github.com/Adilmunawar/ZD-claude-plugin) | Adilmunawar | 农业遥感工程 Claude Code 插件：卫星机器学习、PCA 等方向 / 技能 / 护栏 |
| [FrancyJGLisboa/us-crop-monitor-skill](https://github.com/FrancyJGLisboa/us-crop-monitor-skill) | FrancyJGLisboa | 把 Claude Code 变成 USDA NASS 与美国大宗作物市场分析专家 |
| [farmfriend-labs/agent-skills-farming](https://github.com/farmfriend-labs/agent-skills-farming) | farmfriend-labs | AgentSkills.io 开放格式：农场修复、JADAM 自然农法、蚯蚓养殖、发酵、天气监测、农业技术开发 |
| [dungnotnull/*-agent-skill 系列](https://github.com/dungnotnull/smart-agriculture-planting-plan-agent-skill) | dungnotnull | 十余个「生产级」农业规划技能：种植计划评分（土壤 / 气候 / GAP 标准）、产量预测与病害诊断、循环有机农业、城市微型农场设计、农经战略预测、农废造纸、螺旋藻养殖、集装箱垂直农场、宠物农场生物安全等 |
| [CGIAR-Climate-Data-Hub/skills](https://github.com/CGIAR-Climate-Data-Hub/skills) | CGIAR 气候数据枢纽 | 气候数据枢纽官方 LLM 技能：气候数据检索与农业适配分析 |
| [mikeblythe/farm-economics](https://github.com/mikeblythe/farm-economics) | mikeblythe | USDA NASS 真实数据的收支平衡与盈利计算，明确「不编数字」 |
| [borealBytes/my-farm-advisor](https://github.com/borealBytes/my-farm-advisor) | MY Farm, LLC | 农场管理 + 农业数据科学技能，运行于 Cloudflare 开放框架 |
| [RavenClaude precision-agriculture 插件](https://github.com/mcorbett51090/RavenClaude/blob/main/plugins/precision-agriculture/CLAUDE.md) | mcorbett51090 | 精准农业 Claude 插件说明（CLAUDE.md 指南） |

## 五、农业 MCP 服务器

让智能体直接查询农业数据源的 Model Context Protocol 服务：

| 服务器 | 数据范围 |
|---|---|
| [berba-q/faostat-mcp](https://github.com/berba-q/faostat-mcp) | FAOSTAT 完整 API（联合国粮农统计）；另有本地 SQLite 镜像版 [cyanheads/faostat-mcp-server](https://github.com/cyanheads/faostat-mcp-server) |
| [bruno-portfolio/agrobr-mcp](https://github.com/bruno-portfolio/agrobr-mcp) | 巴西农业：价格、作物、贸易、气候、毁林与火灾 |
| [cyanheads/brapi-mcp-server](https://github.com/cyanheads/brapi-mcp-server) | BrAPI v2.1 育种数据：试验、种质、基因型，支持多智能体研究 |
| [rajshivang07/agro-weather-mcp](https://github.com/rajshivang07/agro-weather-mcp) | Open-Meteo 农业气象工具集 |
| [epicpast/nsip](https://github.com/epicpast/nsip) | 绵羊遗传评估：个体检索、育种值比较、配种规划、羊群排名 |
| [MeasureSpace/measure-space-mcp-server](https://github.com/MeasureSpace/measure-space-mcp-server) | 天气、气候、农业、花粉、空气质量、地理编码 |
| [cyanheads/us-drought-monitor-mcp-server](https://github.com/cyanheads/us-drought-monitor-mcp-server) | 美国干旱监测（USDM）严重度、DSCI、持续时长 |

## 六、数据集与语料

训练与评测用农业数据（Hugging Face）：

| 数据集 | 说明 |
|---|---|
| [KisanVaani/agriculture-qa-english-only](https://huggingface.co/datasets/KisanVaani/agriculture-qa-english-only) | 印度农业热线问答（英/印地），农业 LLM 微调最常引用的语料之一 |
| [CopyleftCultivars/Agriculture-Agent-RL-Training-Data](https://huggingface.co/datasets/CopyleftCultivars/Agriculture-Agent-RL-Training-Data) | 农业智能体 RL 训练数据（配合 Natural Farmer 模型族） |
| [BAAI/IndustryCorpus2_agriculture_forestry_animal_husbandry_fishery](https://huggingface.co/datasets/BAAI/IndustryCorpus2_agriculture_forestry_animal_husbandry_fishery) | 智源行业语料库 2 期「农林牧渔」分卷，中文农业继续预训练现成语料 |
| [Mxode/Chinese-QA-Agriculture_Forestry_Animal_Husbandry_Fishery](https://huggingface.co/datasets/Mxode/Chinese-QA-Agriculture_Forestry_Animal_Husbandry_Fishery) | 中文农林牧渔问答对 |
| [Hanzhe1/Chinese-QA-Agriculture_Forestry_Animal_Husbandry_Fishery](https://huggingface.co/datasets/Hanzhe1/Chinese-QA-Agriculture_Forestry_Animal_Husbandry_Fishery) | 同主题的另一中文 QA 版本 |
| [shi-labs/Agriculture-Vision](https://huggingface.co/datasets/shi-labs/Agriculture-Vision) | Agriculture-Vision 农田遥感分割基准的 HF 版 |
| [sanmay4119/geofm-agriculture-benchmark](https://huggingface.co/datasets/sanmay4119/geofm-agriculture-benchmark) | 地理基础模型农业下游基准 |
| [egirma/afrivoice-swahili-agriculture-subset](https://huggingface.co/datasets/egirma/afrivoice-swahili-agriculture-subset) | 斯瓦希里语农业语音（African Voice 子集） |
| [ghanaopenai/twi-agriculture-speech](https://huggingface.co/datasets/ghanaopenai/twi-agriculture-speech) | 契维语农业语音（加纳） |
| [tahsinsoyak/agriculture-qa-turkish-translated](https://huggingface.co/datasets/tahsinsoyak/agriculture-qa-turkish-translated) | KisanVaani 问答的土耳其语翻译版 |
| [electricsheepafrica/africa-synth-agriculture-*](https://huggingface.co/electricsheepafrica) | 非洲农业合成语料系列：气候适应、粮食安全、产后价值链、畜牧健康、小农产量、肥料施用等 |
| [Juancc-ctic/MLLM_agriculture_evaluation](https://huggingface.co/datasets/Juancc-ctic/MLLM_agriculture_evaluation) | 多模态大模型农业评估数据（西班牙语系机构） |
| [YuvrajSingh9886/Agriculture-Soil-QA-Pairs-Dataset](https://huggingface.co/datasets/YuvrajSingh9886/Agriculture-Soil-QA-Pairs-Dataset) | 土壤方向农业 QA 对 |

## 七、实时数据快照（每日自动更新）

以下内容由 [`scripts/fetch_ai_catalog.py`](../scripts/fetch_ai_catalog.py) 从 `ai/catalog.yaml` + `ai/stats.json` 自动生成，请勿手工编辑本小节。

<!-- BEGIN GENERATED SNAPSHOT -->
采集时间：**2026-11-09 17:26**（Asia/Shanghai）；下表数值由脚本从 Hugging Face / GitHub API 自动抓取，未经人工筛选，口径以各平台为准。

### Hugging Face 模型

| 条目 | 模型数 | 下载量 | 点赞 | ModelScope 下载 | 采集状态 |
|---|---|---|---|---|---|
| [agriculture-bert-uncased](https://huggingface.co/recobo/agriculture-bert-uncased) | — | 558 | 26 | — | ✅ |
| [稷丰 AgriAgent（多模态）](https://github.com/zhiweihu1103/AgriAgent) | — | — | — | — | GitHub ★129（指标见下方 GitHub 节） |
| [AgriGPT-7B / 13B](https://huggingface.co/AgriGPT/AgriGPT-7B) | — | 0 | 0 | — | ✅ |
| [后稷 AgriMa](https://github.com/zhiweihu1103/AgriMa) | — | — | — | — | GitHub ★187（指标见下方 GitHub 节） |
| [AgriManager（LLM-RL 农场管理微调族）](https://github.com/AgriManager-Framework/AgriManager) | 99 | 163 | 0 | — | ✅ |
| [agronomYi-hermes-34B](https://huggingface.co/gbstox/agronomYi-hermes-34B) | — | 16 | 2 | — | ✅ |
| [Qwen3-3.3B-Agricultural-Reasoning](https://huggingface.co/BUAIR/Qwen3.3B-Agricultural-Reasoning) | — | 20 | 0 | — | ✅ |
| [DeepSeek-R1-agriculture](https://huggingface.co/isAsong/DeepSeek-R1-agriculture) | — | 9 | 0 | — | ✅ |
| [dhenu-vision-qwen2.5-7b-grpo-crop-disease](https://huggingface.co/chheplo/dhenu-vision-qwen2.5-7b-grpo-crop-disease) | — | 15 | 0 | — | ✅ |
| [天工开悟 KwooLa / KwooVa / KwooGr](https://github.com/HIT-Kwoo/KwooLa) | — | — | — | — | GitHub ★29（指标见下方 GitHub 节） |
| [多语种小农模型族（索马里 / 阿姆哈拉 / 尼泊尔 / 马拉维语等）](https://huggingface.co/tacab/somali-agriculture) | — | 266 | 0 | — | ✅ |
| [Natural Farmer 系列（llama-3.1 / Gemma2B / Mistral7B / qwen3.5-2b 等）](https://huggingface.co/CopyleftCultivars) | 14 | 313 | 24 | — | ✅ |
| [司农 Sinong1.0（8B / 32B）](https://modelscope.cn/models/NAULLM/Sinong1.0-32B) | — | 43 | 2 | 844 | ✅ |

### Hugging Face 数据集

| 条目 | 下载量 | 点赞 | 采集状态 |
|---|---|---|---|
| [electricsheepafrica/africa-synth-agriculture-* 系列](https://huggingface.co/electricsheepafrica) | 40 | 0 | ✅ |
| [CopyleftCultivars/Agriculture-Agent-RL-Training-Data](https://huggingface.co/datasets/CopyleftCultivars/Agriculture-Agent-RL-Training-Data) | 1,292 | 1 | ✅ |
| [shi-labs/Agriculture-Vision](https://huggingface.co/datasets/shi-labs/Agriculture-Vision) | 272 | 6 | ✅ |
| [BAAI/IndustryCorpus2_agriculture_forestry_animal_husbandry_fishery](https://huggingface.co/datasets/BAAI/IndustryCorpus2_agriculture_forestry_animal_husbandry_fishery) | 668 | 2 | ✅ |
| [Mxode/Chinese-QA-Agriculture_Forestry_Animal_Husbandry_Fishery](https://huggingface.co/datasets/Mxode/Chinese-QA-Agriculture_Forestry_Animal_Husbandry_Fishery) | 159 | 14 | ✅ |
| [sanmay4119/geofm-agriculture-benchmark](https://huggingface.co/datasets/sanmay4119/geofm-agriculture-benchmark) | — | — | ⚠️ huggingface api unreachable |
| [KisanVaani/agriculture-qa-english-only](https://huggingface.co/datasets/KisanVaani/agriculture-qa-english-only) | 390 | 26 | ✅ |
| [norjordAI/nor_agriculture_bench](https://huggingface.co/datasets/norjordAI/nor_agriculture_bench) | — | — | ⚠️ huggingface api unreachable |

### GitHub 项目

| 条目 | Stars | 最近推送 | 采集状态 |
|---|---|---|---|
| [zlatko-lakisic/agentic-orchestration（GARDen AgriAssist）](https://github.com/zlatko-lakisic/agentic-orchestration) | 3 | 2026-10-27 | ✅ |
| [Shuvam-Banerji-Seal/AgriIR](https://github.com/Shuvam-Banerji-Seal/AgriIR) | 7 | 2026-04-29 | ✅ |
| [DreamRealized/agriculture-chatbot](https://github.com/DreamRealized/agriculture-chatbot) | 5 | 2026-11-05 | ✅ |
| [Yutong-Zhou-cv/AgriBench](https://github.com/Yutong-Zhou-cv/AgriBench) | 28 | 2025-01-01 | ✅ |
| [zhiweihu1103/AgriMa（仓库）](https://github.com/zhiweihu1103/AgriMa) | 187 | 2026-03-19 | ✅ |
| [Rekin226/Agronaut](https://github.com/Rekin226/Agronaut) | 5 | 2026-11-01 | ✅ |
| [SmartAG-Team/CDIP-ChatGLM3](https://github.com/SmartAG-Team/CDIP-ChatGLM3) | 20 | 2025-02-23 | ✅ |
| [giri164/krishi-sahayak](https://github.com/giri164/krishi-sahayak) | 5 | 2026-10-09 | ✅ |
| [trust-nlp/PlantXpert](https://github.com/trust-nlp/PlantXpert) | 0 | 2026-11-08 | ✅ |
| [InternScience/SeedBench](https://github.com/InternScience/SeedBench) | 25 | 2025-12-19 | ✅ |
| [njauzzx/Sinong（仓库）](https://github.com/njauzzx/Sinong) | 191 | 2026-05-17 | ✅ |
| [juni2003/Smart-Farming-Agentic-AI](https://github.com/juni2003/Smart-Farming-Agentic-AI) | 4 | 2026-10-08 | ✅ |

### 论文 / 资源列表

| 条目 | Stars | 最近推送 | 采集状态 |
|---|---|---|---|
| [JiajiaLi04/Agriculture-Foundation-Models](https://github.com/JiajiaLi04/Agriculture-Foundation-Models) | 67 | 2025-08-02 | ✅ |
| [JiajiaLi04/Multi-Modal-LLMs-in-Agriculture](https://github.com/JiajiaLi04/Multi-Modal-LLMs-in-Agriculture) | 17 | 2025-02-19 | ✅ |

### Agent Skill

| 条目 | Stars | 最近推送 | 采集状态 |
|---|---|---|---|
| [farmfriend-labs/agent-skills-farming](https://github.com/farmfriend-labs/agent-skills-farming) | 3 | 2026-02-21 | ✅ |
| [CGIAR-Climate-Data-Hub/skills](https://github.com/CGIAR-Climate-Data-Hub/skills) | 0 | 2026-11-04 | ✅ |
| [dungnotnull/*-agent-skill（种植计划 / 循环农业 / 城市微型农业 / 产量病害诊断 / 农经预测等）](https://github.com/dungnotnull/smart-agriculture-planting-plan-agent-skill) | 4 | 2026-07-02 | ✅ |
| [berba-q/faostat-skills](https://github.com/berba-q/faostat-skills) | 10 | 2026-04-21 | ✅ |
| [mikeblythe/farm-economics](https://github.com/mikeblythe/farm-economics) | 2 | 2026-07-19 | ✅ |
| [borealBytes/my-farm-advisor](https://github.com/borealBytes/my-farm-advisor) | 7 | 2026-11-06 | ✅ |
| [PangenomeAI/academic-skills-food-nutrition](https://github.com/PangenomeAI/academic-skills-food-nutrition) | 42 | 2026-08-31 | ✅ |
| [human-avatar/skills-for-agriculture](https://github.com/human-avatar/skills-for-agriculture) | 13 | 2026-06-12 | ✅ |
| [FrancyJGLisboa/us-crop-monitor-skill](https://github.com/FrancyJGLisboa/us-crop-monitor-skill) | 6 | 2025-10-18 | ✅ |
| [Adilmunawar/ZD-claude-plugin](https://github.com/Adilmunawar/ZD-claude-plugin) | 10 | 2026-11-01 | ✅ |

### MCP 服务器

| 条目 | Stars | 最近推送 | 采集状态 |
|---|---|---|---|
| [rajshivang07/agro-weather-mcp](https://github.com/rajshivang07/agro-weather-mcp) | 2 | 2026-10-28 | ✅ |
| [bruno-portfolio/agrobr-mcp](https://github.com/bruno-portfolio/agrobr-mcp) | 30 | 2026-10-10 | ✅ |
| [cyanheads/brapi-mcp-server](https://github.com/cyanheads/brapi-mcp-server) | 4 | 2026-10-19 | ✅ |
| [berba-q/faostat-mcp](https://github.com/berba-q/faostat-mcp) | 20 | 2026-10-02 | ✅ |
| [MeasureSpace/measure-space-mcp-server](https://github.com/MeasureSpace/measure-space-mcp-server) | 3 | 2026-02-28 | ✅ |
| [epicpast/nsip](https://github.com/epicpast/nsip) | 3 | 2026-11-02 | ✅ |

<!-- END GENERATED SNAPSHOT -->

## 八、趋势观察

1. **中文赛道从「有没有」进入「好不好」阶段。** 2023–2024 年的 AgriGPT / AgriMa 解决的是中文农业 LLM 从无到有；2026 年的司农把竞争点转向数据规模（40 亿 + token、分学科）、训练配方（CoT / in-context 指令 + RL）与评测，天工开悟则展示了「模型 + App + API」的产品化路径。
2. **智能体与技能成为新战场。** 单纯微调模型的热度下降，「通用大模型 + 检索增强 + 农业工具 / 技能」的架构成为开源项目主流（GARDen、AgriManager、Agronaut、各类 RAG 系统）；AgriManager 把作物模型（DSSAT/WOFOST）当环境做 RL，是模型与农学机理耦合的代表。
3. **Agent Skill 生态从零到一。** Claude Code 等智能体的技能格式公开后（2025），农业技能包在 2025–2026 年集中出现：澳洲面向农场主的决策技能（skills-for-agriculture）、学术科研技能（food-nutrition 技能包）、统计与遥感数据技能（FAOSTAT、USDA NASS、CGIAR），并与 MCP 数据服务器成对出现，形成「技能 = 知识层，MCP = 数据层」的组合。
4. **评测基准进入顶会。** AgriBench（ECCV 2024 Workshop）→ SeedBench（ACL 2025）→ AgriManager（NeurIPS 2026 E&D）→ PlantXpert（2026），农业评测正成为 NLP / CV 顶会的固定题材；领域幻觉评测（agrihallu_bench 等）也开始出现。
5. **小语种与地区普惠明显。** 非洲（斯瓦希里语、契维语、阿姆哈拉语、马拉维语、西非法语语音）与南亚（尼泊尔语、泰米尔语、泰卢固语）的农业语音 / 问答模型持续出现，多由本地 AI 公益组织以「基座 + 农业语料微调」的低成本方式完成。
6. **与本仓库的衔接点。** 本仓库的古籍全文（838 卷 / 783 万字）与知识图谱（238 实体 / 789 关系）可直接作为农业 LLM 的领域语料 / RAG 知识库；农史农文子领域（四库农家类、河渠之属）目前尚无专用模型与基准，是可贡献空间。

## 九、方法与维护

- **检索面**：
  - Hugging Face：以 `agriculture`、`agricultural`、`农业`、`crop disease`、`livestock`、`AgriGPT`、`agronomy`、`FarmLLM`、`sinong` 等关键词检索模型 / 数据集（API `search` + 下载量 / 点赞排序），并抽查 org 主页；
  - GitHub：`gh api search/repositories` 以 `agriculture LLM`、`农业 大模型`、`agriculture skill / agent skill / mcp server`、`agriculture RAG / benchmark` 等词组合检索，按星标排序；
  - Web 搜索：补充新闻性条目（如模型发布会、机构公告）。
- **筛选口径**：收录「有代码 / 有权重 / 有数据、可复核」的条目；一次性黑客松与纯演示项目仅在有代表性时收录；同名营销仓库、空仓库剔除。
- **更新机制**：
  - `ai/catalog.yaml` 为人工维护的目录源（新增 / 剔除条目在这里改）；
  - [`scripts/fetch_ai_catalog.py`](../scripts/fetch_ai_catalog.py) 每日抓取实时指标写入 `ai/stats.json`，并重渲染本文件的[实时数据快照](#七实时数据快照每日自动更新)一节；GitHub Actions 定时任务（`workflow_dispatch` / `schedule`）自动执行并在有变化时提交；
  - 趋势观察与文字描述部分由每日任务人工复核后改写，日期记入[更新记录](#十更新记录)。
- **已知局限**：Hugging Face 下载量口径为平台近 30 天数据，星标数随时间变化；「首个」「最大」等表述为研发方自称；模型可下载性与许可以官方页面为准。

## 十、更新记录

| 日期 | 变更 |
|---|---|
| 2026-11-09 | 首版：建立目录（51 条目）、采集脚本、定时工作流与本文档；覆盖 Hugging Face 模型、GitHub 项目、Skills、MCP、数据集五类 |
