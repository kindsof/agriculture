# agriculture 农业水利

农业水利 / 传统与AI / 资源与发展

本仓库收录中国历代农业与水利古籍的全文，供检索、阅读与文本分析使用。

## 古籍库

现收 **42 部**，合计 **838 卷/篇**，约 **783.5 万字**：

- **农业 16 部**：四庫全書子部農家類 10 部，自後魏《齊民要術》至清《欽定授時通考》；另補史部政書類荒政 4 部、史部時令類 2 部
- **水利 26 部**：四庫全書史部地理類河渠之屬 23 部，含《水經注》諸本、農田水利、河工防洪、海塘與水道總志；另補經部書類禹貢 3 部

完整书目、卷数、字数与阅读链接见 **[books/INDEX.md](books/INDEX.md)**；机器可读目录见 **[books/catalog.json](books/catalog.json)**。

各书为 Markdown 全文，卷首保留四庫提要或原序、目錄。文本来自 Kanripo（漢籍リポジトリ）的《四庫全書》等版本转录，未作标点、校勘或繁简转换；来源、处理方式与局限详见 **[SOURCES.md](SOURCES.md)**。

## 使用

直接阅读：

- [古籍目录](books/INDEX.md)
- [農業](books/agriculture/)
- [水利](books/water/)

按关键词检索，例如：

```bash
grep -rn "水車" books/
grep -rn "區田" books/
grep -rn "隄防" books/water/
```

## 知识图谱

[`kg/`](kg/) 把 42 部古籍整理为可查询的知识图谱：**238 个实体（含 27 个消歧辅助实体）、789 条关系**，其中 **603 条关系带原文引文**，全部经脚本校验能在对应古籍全文中找到。

- [图谱索引](kg/INDEX.md)：按书目、主题、实体类型与语义关系浏览
- [图谱说明](kg/README.md)：实体与关系类型、数据格式、整理规则与局限
- [类型示意](kg/schema.svg)：实体类型与关系类型的总体结构
- [书目主题总览](kg/overview.svg)：42 部书按主题的分布
- [机器可读数据](kg/graph.json)：`graph.json`、`entities.jsonl`、`relations.jsonl`、`graph.jsonld`

图谱覆盖 12 类实体：书目、人物、朝代、地域、水道、水利设施、作物、农具、技术、制度、主题与概念；关系包括主题论述、原文提及、作者、成书朝代、注释、相关、分类、水系隶属、地理位置、治理者与技术施用。

```bash
python3 kg/build.py              # 重新构建并校验全部引文
python3 kg/query.py stats        # 查看统计
python3 kg/query.py search 黃河   # 搜索实体
python3 kg/query.py show water:huanghe
python3 kg/query.py books --topic 荒政
```

## 重新生成

脚本依赖 Python 3.9+、PyYAML 与 git：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/fetch_books.py
```

脚本会浅克隆 `catalog.yaml` 中列出的 Kanripo 仓库到 `.cache/kanripo/`，再生成 `books/` 下的文本与索引。已有缓存会直接复用；`--only` 可只处理指定书目，`--jobs` 控制并行克隆数。

```bash
python3 scripts/fetch_books.py --only KR3d0001 KR2k0058
```

新增书目时，在 `catalog.yaml` 中按现有字段添加条目，再运行脚本即可。若书目要进入知识图谱，还需要在 `kg/data/topics.yaml` 登记主题/朝代，并在 `kg/data/entities.yaml`、`kg/data/about.yaml`、`kg/data/relations.yaml` 中补充相应实体、主题与关系，最后运行 `python3 kg/build.py` 校验。

## 许可

古籍底本属于公有领域；Kanripo 转录文本以 [CC BY-SA 4.0](LICENSE) 许可发布，本仓库的整理文本与脚本同样遵循该许可。再分发时请保留 [SOURCES.md](SOURCES.md) 中的署名说明。
