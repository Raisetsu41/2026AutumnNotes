# 2026 Autumn LaTeX Notes

- `Financial-Economics/`：金融经济学，当前覆盖 Chapter 1 与 Chapter 2（至课件 p.32）。
- `Macroeconomics/`：宏观经济学，当前覆盖 Chapter 1–2。
- `Probability-Statistics/`：概率论与数理统计，当前覆盖 Chapter 1.1–1.5。

已生成的 PDF：

- [`Financial-Economics/main.pdf`](Financial-Economics/main.pdf)
- [`Macroeconomics/main.pdf`](Macroeconomics/main.pdf)
- [`Probability-Statistics/main.pdf`](Probability-Statistics/main.pdf)

单独编译某门课程时，在对应目录运行：

```powershell
latexmk -xelatex main.tex
```

重新从 Obsidian 课程笔记归并章节并编译全部课程：

```powershell
.\tools\build_all.ps1
```

2026 秋正式课堂笔记。新增课程内容后，只需将新笔记加入该脚本对应课程的文件列表或章节映射。
