# 来源与许可

## 数据来源

本仓库的古籍文本来自 **Kanripo（漢籍リポジトリ）**：

- 项目主页：<https://www.kanripo.org>
- GitHub 组织：<https://github.com/kanripo>
- 每部书的来源仓库见 `catalog.yaml` 的 `id` 字段，对应
  `https://github.com/kanripo/<id>`，也记录在各书开头的 `source` 字段中。

Kanripo 以《欽定四庫全書》（文淵閣本）等版本为底本制作全文转录。本仓库所收各书的底本如下：

| 底本 | 说明 | 书目 |
|---|---|---|
| 文淵閣四庫全書本 | 清乾隆間纂修《四庫全書》文淵閣抄本 | 除下列两种外的 31 部 |
| 四部叢刊本 | 民國間商務印書館影印《四部叢刊》 | 《齊民要術》《水經注》 |

各书卷首多保留四庫全書提要或原序、目錄；这些内容一并收录，未作删削。

## 处理方式

`scripts/fetch_books.py` 按 `catalog.yaml` 浅克隆 Kanripo 文本仓库，并做以下整理：

1. 删除 Kanripo 转录文件头部的 `#+TITLE`、`#+PROPERTY` 等元数据；
2. 删除 `<pb:...>` 页面标记和行末的 `¶` 符号；
3. 原转录中的替换字符（U+FFFD）统一改为 `□`，以标示底本漫漶或转录缺失；
4. 以 Kanripo 的 `JUAN` 属性作为卷次标题，按文件顺序合并为 Markdown；
5. 生成 `books/INDEX.md` 与机器可读的 `books/catalog.json`。

整理过程**不做**标点、校勘、繁简转换或异体字规范化，以尽量保留底本与转录原貌。因此文本中的用字、行款和分卷一仍其旧，引用和研究时请核对原书或影印本。

## 文本性质与局限

- 本仓库提供的是**全文转录**，不是书影或 PDF 扫描件。
- Kanripo 转录可能存在 OCR 或录入讹误；替换字符以 `□` 标出，但不排除其他错字、漏字。
- 部分书籍的卷次按 Kanripo 文件顺序编排，与原书目录未必完全一致。
- 四庫全書本身对古籍有删改，文淵閣本亦非唯一传本；如需版本校勘，应另取善本。

## 许可

- 古籍底本本身属于公有领域。
- Kanripo 的全文转录以 **Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）** 许可发布。本仓库对转录文本的收录、整理和再分发同样遵循 CC BY-SA 4.0，完整许可文本见 [`LICENSE`](LICENSE)。
- 再分发或引用时，请保留以下署名：

  > 文本来源：Kanripo（漢籍リポジトリ），<https://www.kanripo.org>，CC BY-SA 4.0。

- `scripts/` 下的整理脚本同样以 CC BY-SA 4.0 发布。
