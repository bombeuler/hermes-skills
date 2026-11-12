# hermes-skills

Hermes Agent 技能集合，可直接作为 tap 订阅或单独安装。

## 安装

```bash
# 方式一:整个仓库作为 tap(推荐的长期用法,后续新技能会自动出现在搜索里)
hermes skills tap add bombeuler/hermes-skills
hermes skills search pdf
hermes skills install bombeuler/hermes-skills/skills/pdf-bookmark-and-metadata

# 方式二:不订阅,只装一个
hermes skills install bombeuler/hermes-skills/skills/pdf-bookmark-and-metadata
```

在会话内也可以用斜杠命令:`/skills tap add bombeuler/hermes-skills`、`/skills install ...`。

## 目录

| 技能 | 说明 | 依赖 |
| --- | --- | --- |
| [`pdf-bookmark-and-metadata`](skills/pdf-bookmark-and-metadata/SKILL.md) | 给书籍 PDF 重建多层目录书签、页码标签与元信息(扫描本与原生文字层两类流程) | PyMuPDF, tesseract(+ chi_sim), Pillow, qpdf |

## 布局

```
skills/
└── <skill-name>/
    ├── SKILL.md          # 必需,YAML frontmatter + 正文
    ├── scripts/          # 可选,配套脚本
    ├── references/       # 可选,按主题拆分的细节文档
    └── templates/        # 可选
```

Hermes 通过遍历 tap 的 `skills/` 子目录、探测每个目录下是否有 `SKILL.md` 来发现技能。

## 许可

MIT，见 [LICENSE](LICENSE)。各技能 `SKILL.md` 的 `license` 字段与之一致。
