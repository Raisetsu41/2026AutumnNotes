# 2026 Autumn LaTeX Notes

本仓库把本地 Obsidian Markdown 按课程与教材章节整理为 LaTeX/PDF，不按上课日期拆分最终文档。

当前输出：

- [`金融经济学.pdf`](Financial-Economics/金融经济学.pdf)：Chapter 1、2、4；
- [`宏观经济学.pdf`](Macroeconomics/宏观经济学.pdf)：Chapter 1–3；
- [`概率论与数理统计.pdf`](Probability-Statistics/概率论与数理统计.pdf)：Chapter 1–2、Problem Set 1 与第一次习题课。

内容从本地 Obsidian Markdown 源仓库生成，排版沿用
[`Latex-Notes-Template`](https://github.com/Raisetsu41/Latex-Notes-Template) 的页面、数学快捷命令和页眉页脚风格。

## 工作流

```text
Obsidian Markdown
    → 清理 YAML、课程导航、Wiki 链接和 callout
    → 按 notes.config.json 合并为章节
    → Pandoc 生成章节 .tex
    → XeLaTeX 编译学科名称.pdf
    → 复制到 public/ 静态站点
    → Git commit + push
    → Vercel 自动部署
```

Markdown 是内容的唯一来源。`main.tex` 和 `chapters/*.tex` 会自动生成，不应手工修改。

## 环境要求

- Python 3.10+
- Pandoc
- TeX Live（含 XeLaTeX 和 latexmk）
- Git
- 可选：Node.js/npx，用于 Vercel CLI 直接部署

检查环境：

```powershell
python .\tools\build_notes.py doctor
```

构建前可用环境变量指定 Obsidian 仓库：

```powershell
$env:OBSIDIAN_NOTES_ROOT = 'C:\path\to\your\vault'
```

也可以在仓库根目录创建不会提交到 Git 的 `.notes.local.json`：

```json
{
  "obsidian_root": "C:/path/to/your/vault"
}
```

## 生成与编译

只重新生成 LaTeX：

```powershell
python .\tools\build_notes.py generate
```

生成 LaTeX、编译全部 PDF 并刷新 `public/`：

```powershell
.\tools\build_all.ps1
```

构建中间文件统一写入 `.build/`；课程目录中只保留以学科命名的发布 PDF，不再使用 `main.pdf`。

## 添加新笔记

编辑 [`notes.config.json`](notes.config.json)：

1. 同一章新增课程笔记时，把 Markdown 相对路径加入对应 `sources`；
2. 新开一章时，在 `chapters` 中增加 `file`、`title` 和 `sources`；
3. 习题课、Problem Set 等补充材料放入 `appendices`；
4. 如果一个 Markdown 同时包含两章，可用 `from_heading` 和 `until_heading` 精确切分。

这样章节判断是显式、可审阅的，不会因日期或标题猜测而把内容归错章。

## 一键发布到 GitHub

首次提交本套脚本后，日常发布只需在干净工作区运行：

```powershell
.\tools\publish.ps1
```

脚本会先完整构建；只有三份 PDF 全部成功后，才会暂存生成文件、创建提交并执行 `git push origin HEAD`。如果构建失败，不会上传旧或残缺的 PDF。

常用选项：

```powershell
# 只构建并提交，不推送
.\tools\publish.ps1 -NoPush

# 自定义提交信息
.\tools\publish.ps1 -Message 'docs: update week 4 notes'

# 明确允许仓库中已有修改
.\tools\publish.ps1 -AllowDirty
```

## 部署到 Vercel

推荐让 Vercel 与 GitHub 仓库 `Raisetsu41/2026AutumnNotes` 建立 Git Integration：

1. 在 Vercel 导入该 GitHub 仓库；
2. Framework Preset 选择 `Other`；
3. Root Directory 保持仓库根目录；
4. Output Directory 使用 `public`（仓库中的 `vercel.json` 已声明）；
5. 完成首次部署。

以后 `publish.ps1` 推送 GitHub 后，Vercel 会自动部署，无需在脚本中保存 Token。

如需绕过 Git Integration 直接部署，先完成一次登录和项目关联：

```powershell
npx vercel login
npx vercel link
```

随后运行：

```powershell
.\tools\publish.ps1 -DirectVercel
```

脚本会调用已安装的 `vercel`，未安装时则通过 `npx vercel@latest` 运行。
