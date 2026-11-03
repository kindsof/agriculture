# agriculture 农业水利

农业水利 / 传统与AI / 资源与发展

本仓库收录中国历代农业与水利古籍的全文，供检索、阅读与文本分析使用。

## 古籍库

现收 **33 部**，合计 **754 卷/篇**，约 **644.5 万字**：

- **农业 10 部**：四庫全書子部農家類，自後魏《齊民要術》至清《欽定授時通考》
- **水利 23 部**：四庫全書史部地理類河渠之屬，含《水經注》諸本、農田水利、河工防洪、海塘與水道總志

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

新增书目时，在 `catalog.yaml` 中按现有字段添加条目，再运行脚本即可。

## 许可

古籍底本属于公有领域；Kanripo 转录文本以 [CC BY-SA 4.0](LICENSE) 许可发布，本仓库的整理文本与脚本同样遵循该许可。再分发时请保留 [SOURCES.md](SOURCES.md) 中的署名说明。
