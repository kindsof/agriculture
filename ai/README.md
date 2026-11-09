# 农业 AI 模型与技能跟踪（ai/）

本目录跟踪 Hugging Face 农业相关大模型、GitHub 农业模型项目与农业 Agent Skill，
汇总文档见 [INDEX.md](INDEX.md)。

## 文件

| 文件 | 说明 |
|---|---|
| [INDEX.md](INDEX.md) | 汇总文档（主交付物）：分层收录、趋势观察、方法说明 |
| [catalog.yaml](catalog.yaml) | 机器可读目录源，**人工维护**；新增 / 剔除条目改这里 |
| [stats.json](stats.json) | 实时指标快照（下载量、Stars、最近推送），**脚本生成，勿手改** |

## 日常刷新

```bash
python3 -m pip install -r requirements.txt   # 仅需 PyYAML
python3 scripts/fetch_ai_catalog.py          # 联网采集，刷新 stats.json 与 INDEX.md 快照节
python3 scripts/fetch_ai_catalog.py --check  # 离线校验一致性（CI 用）
```

- Hugging Face API 不可达时脚本自动回退镜像 `hf-mirror.com`；
- 设置 `GITHUB_TOKEN` / `GH_TOKEN` 可提高 GitHub API 限额（定时任务已注入）；
- 定时任务见 [`.github/workflows/ai-catalog.yml`](../.github/workflows/ai-catalog.yml)：
  每日北京时间 10:30 采集，有变化时自动开 PR；也可 `workflow_dispatch` 手动触发。

## 新增条目

1. 在 `ai/catalog.yaml` 的 `entries` 下按现有字段追加（字段说明见文件头注释）；
2. 在 `ai/INDEX.md` 对应章节的表格中补一行叙述性介绍；
3. 运行 `python3 scripts/fetch_ai_catalog.py` 刷新快照，`--check` 与单测通过后提交；
4. 在 `ai/INDEX.md`「更新记录」表中记一行。

筛选口径与检索面见 [INDEX.md「方法与维护」](INDEX.md#九方法与维护)。
