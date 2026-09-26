#!/usr/bin/env python3
"""Build chapter-organized LaTeX notes from local Obsidian Markdown files.

The Markdown vault remains the source of truth.  Course/chapter membership lives in
notes.config.json so the generated document is organized by textbook chapter rather
than by lecture date.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPOSITORY_ROOT / "notes.config.json"
CALLOUT_NAMES = {
    "abstract": "摘要",
    "bug": "问题",
    "danger": "注意",
    "example": "例",
    "failure": "错误",
    "info": "信息",
    "important": "重要",
    "note": "注",
    "question": "问题",
    "quote": "引文",
    "success": "解答",
    "tip": "提示",
    "todo": "待办",
    "warning": "警告",
}


def run(command: list[str], *, cwd: Path) -> None:
    printable = " ".join(command)
    print(f"[run] {printable}")
    subprocess.run(command, cwd=cwd, check=True)


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not config.get("courses"):
        raise ValueError("notes.config.json 中没有 courses 配置。")
    return config


def resolve_obsidian_root(config: dict[str, Any]) -> Path:
    configured = os.environ.get("OBSIDIAN_NOTES_ROOT", config["obsidian_root"])
    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(
            f"找不到 Obsidian 仓库：{root}\n"
            "可设置 OBSIDIAN_NOTES_ROOT 环境变量覆盖 notes.config.json。"
        )
    return root


def strip_front_matter(lines: list[str]) -> list[str]:
    if not lines or lines[0].strip() != "---":
        return lines
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[index + 1 :]
    raise ValueError("Markdown YAML front matter 缺少结束标记 ---。")


def slice_at_headings(lines: list[str], source: dict[str, Any], path: Path) -> list[str]:
    start = 0
    end = len(lines)
    from_heading = source.get("from_heading")
    until_heading = source.get("until_heading")

    if from_heading:
        matches = [i for i, line in enumerate(lines) if line.strip() == from_heading]
        if len(matches) != 1:
            raise ValueError(f"{path}: from_heading 应唯一匹配，实际匹配 {len(matches)} 次。")
        start = matches[0]
    if until_heading:
        matches = [i for i, line in enumerate(lines) if line.strip() == until_heading]
        if len(matches) != 1:
            raise ValueError(f"{path}: until_heading 应唯一匹配，实际匹配 {len(matches)} 次。")
        end = matches[0]
    if start >= end:
        raise ValueError(f"{path}: Markdown 截取范围为空或顺序错误。")
    return lines[start:end]


def remove_navigation_callout(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    index = 0
    navigation = re.compile(
        r"^>\s*\[!info\][+-]?\s*(课程导航|course navigation)\s*$",
        re.IGNORECASE,
    )
    while index < len(lines):
        if navigation.match(lines[index].strip()):
            index += 1
            while index < len(lines) and (lines[index].lstrip().startswith(">") or not lines[index].strip()):
                index += 1
            continue
        cleaned.append(lines[index])
        index += 1
    return cleaned


def normalize_callouts(line: str) -> str:
    match = re.match(r"^(\s*>\s*)\[!([A-Za-z-]+)\][+-]?\s*(.*)$", line)
    if not match:
        return line
    prefix, kind, title = match.groups()
    label = CALLOUT_NAMES.get(kind.lower(), kind.title())
    heading = f"{label}：{title}" if title else label
    return f"{prefix}**{heading}**"


def copy_embed(
    target: str,
    label: str | None,
    *,
    obsidian_root: Path,
    course_root: Path,
) -> str:
    raw_target = target.split("#", 1)[0].strip().replace("\\", "/")
    source = (obsidian_root / raw_target).resolve()
    try:
        source.relative_to(obsidian_root)
    except ValueError as exc:
        raise ValueError(f"附件路径越过 Obsidian 根目录：{target}") from exc

    image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
    if source.suffix.lower() not in image_extensions or not source.is_file():
        return label or Path(raw_target).stem

    digest = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:10]
    destination_name = f"{digest}-{source.name}"
    destination_dir = course_root / "assets"
    destination_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination_dir / destination_name)
    caption = label or source.stem.replace("-", " ")
    return f"![{caption}](assets/{destination_name})"


def normalize_obsidian_links(
    line: str,
    *,
    obsidian_root: Path,
    course_root: Path,
) -> str:
    embed_pattern = re.compile(r"!\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
    link_pattern = re.compile(r"(?<!!)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

    def embed_replacement(match: re.Match[str]) -> str:
        return copy_embed(
            match.group(1),
            match.group(2),
            obsidian_root=obsidian_root,
            course_root=course_root,
        )

    def link_replacement(match: re.Match[str]) -> str:
        target = match.group(1)
        return match.group(2) or target.split("#", 1)[-1] or target

    line = embed_pattern.sub(embed_replacement, line)
    return link_pattern.sub(link_replacement, line)


def normalize_markdown(
    path: Path,
    source: dict[str, Any],
    *,
    obsidian_root: Path,
    course_root: Path,
) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    lines = strip_front_matter(lines)
    lines = slice_at_headings(lines, source, path)
    lines = remove_navigation_callout(lines)

    normalized: list[str] = []
    for line in lines:
        if re.match(r"^#\s+", line):
            continue
        if re.match(r"^(Ref|Reference):\s*", line, re.IGNORECASE):
            continue
        is_callout_header = bool(
            re.match(r"^\s*>\s*\[![A-Za-z-]+\][+-]?", line)
        )
        line = normalize_callouts(line)
        line = normalize_obsidian_links(
            line,
            obsidian_root=obsidian_root,
            course_root=course_root,
        )
        line = re.sub(r"^(#{2,6})\s+\d+(?:\.\d+)*\.?\s*", r"\1 ", line)
        line = (
            line.replace("✓", "$\\checkmark$")
            .replace("✗", "$\\times$")
            .replace("σ", "$\\sigma$")
        )
        normalized.append(line.rstrip())
        if is_callout_header:
            normalized.append(">")

    while normalized and not normalized[0].strip():
        normalized.pop(0)
    while normalized and not normalized[-1].strip():
        normalized.pop()
    return normalized


def postprocess_latex(text: str) -> str:
    replacements = {
        "\\text{silica} {{1 \\ RMB}\\over} \\text{glass} {{4 \\ RMB}\\over} \\text{automobile} {{100 \\ RMB}\\over}": (
            "\\text{silica }(1\\,\\mathrm{RMB}) \\longrightarrow "
            "\\text{glass }(4\\,\\mathrm{RMB}) \\longrightarrow "
            "\\text{automobile }(100\\,\\mathrm{RMB})"
        ),
        "ouput": "output",
        "automible": "automobile",
        "Captital": "capital",
        "value ot": "value of",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace(
        "&+\\text{Dividends}\n"
        "+\\text{Government Transfers to Individuals}\n"
        "+\\text{Personal Interest Income}.",
        "&+\\text{Dividends}+\\text{Government Transfers to Individuals}\\\\\n"
        "&+\\text{Personal Interest Income}.",
    )
    text = text.replace(
        "\\begin{longtable}[]{@{}lll@{}}",
        "\\begin{longtable}[]{@{}"
        ">{\\raggedright\\arraybackslash}p{0.22\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.34\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.34\\linewidth}@{}}",
    )
    return text


def convert_section(
    section: dict[str, Any],
    *,
    course_root: Path,
    obsidian_root: Path,
    temporary_root: Path,
) -> Path:
    markdown: list[str] = [f"# {section['title']}", ""]
    source_labels: list[str] = []
    for source in section["sources"]:
        source_path = (obsidian_root / source["path"]).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"找不到 Markdown 源文件：{source_path}")
        source_labels.append(source["path"])
        markdown.extend(
            normalize_markdown(
                source_path,
                source,
                obsidian_root=obsidian_root,
                course_root=course_root,
            )
        )
        markdown.extend(["", ""])

    temporary_markdown = temporary_root / f"{course_root.name}-{section['file']}.md"
    temporary_markdown.write_text("\n".join(markdown), encoding="utf-8")
    destination = course_root / "chapters" / section["file"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_tex = temporary_root / f"{course_root.name}-{section['file']}"
    run(
        [
            "pandoc",
            str(temporary_markdown),
            "--from=markdown+yaml_metadata_block+tex_math_dollars+pipe_tables+lists_without_preceding_blankline+raw_tex-auto_identifiers",
            "--to=latex",
            "--top-level-division=section",
            "--wrap=preserve",
            f"--resource-path={course_root}",
            f"--output={temporary_tex}",
        ],
        cwd=course_root,
    )
    generated = postprocess_latex(temporary_tex.read_text(encoding="utf-8"))
    header = "% AUTO-GENERATED. Edit the Markdown sources or notes.config.json.\n"
    header += "% Sources: " + "; ".join(source_labels) + "\n\n"
    destination.write_text(header + generated, encoding="utf-8")
    return destination


def tex_document(course: dict[str, Any], config: dict[str, Any]) -> str:
    chapter_inputs = "\n".join(
        f"\\input{{chapters/{chapter['file']}}}" for chapter in course["chapters"]
    )
    appendix_inputs = ""
    if course.get("appendices"):
        appendix_inputs = "\n\\appendix\n" + "\n".join(
            f"\\input{{chapters/{appendix['file']}}}" for appendix in course["appendices"]
        )
    return f"""% AUTO-GENERATED. Edit notes.config.json instead.
\\documentclass[11pt,a4paper]{{ctexart}}

\\newcommand{{\\CourseName}}{{{course['course_name']}}}
\\newcommand{{\\CourseEnglishTitle}}{{{course['title_en']}}}
\\usepackage{{xcolor}}
\\definecolor{{CourseAccent}}{{HTML}}{{{course['accent_color']}}}
\\definecolor{{CourseAccentDark}}{{HTML}}{{{course['accent_dark']}}}
\\input{{../shared-preamble.tex}}

\\title{{{course['title']}}}
\\author{{{config['author']}}}
\\date{{{course['progress']}}}

\\begin{{document}}

\\maketitle
\\thispagestyle{{empty}}

\\begin{{center}}
\\small\\color{{black!68}} {course['subtitle_tex']}
\\end{{center}}

\\newpage
\\begingroup
\\setstretch{{0.95}}
\\small
\\tableofcontents
\\endgroup
\\newpage

{chapter_inputs}
{appendix_inputs}

\\end{{document}}
"""


def clean_stale_generated(course: dict[str, Any], course_root: Path) -> None:
    expected = {entry["file"] for entry in course["chapters"] + course.get("appendices", [])}
    chapters_root = course_root / "chapters"
    if not chapters_root.exists():
        return
    for tex_file in chapters_root.glob("*.tex"):
        if tex_file.name not in expected and tex_file.read_text(encoding="utf-8").startswith("% AUTO-GENERATED"):
            tex_file.unlink()


def generate_course(
    course: dict[str, Any],
    config: dict[str, Any],
    *,
    obsidian_root: Path,
    temporary_root: Path,
) -> None:
    course_root = REPOSITORY_ROOT / course["directory"]
    course_root.mkdir(parents=True, exist_ok=True)
    (course_root / "assets").mkdir(exist_ok=True)
    shutil.copy2(REPOSITORY_ROOT / "math-shortcuts.sty", course_root / "math-shortcuts.sty")
    clean_stale_generated(course, course_root)
    for section in course["chapters"] + course.get("appendices", []):
        convert_section(
            section,
            course_root=course_root,
            obsidian_root=obsidian_root,
            temporary_root=temporary_root,
        )
    (course_root / "main.tex").write_text(tex_document(course, config), encoding="utf-8")
    print(f"[ok] 已生成 {course['title']} 的 LaTeX 源码。")


def generate(config: dict[str, Any]) -> None:
    obsidian_root = resolve_obsidian_root(config)
    with tempfile.TemporaryDirectory(prefix="latex-notes-") as temporary:
        temporary_root = Path(temporary)
        for course in config["courses"]:
            generate_course(
                course,
                config,
                obsidian_root=obsidian_root,
                temporary_root=temporary_root,
            )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_public_site(config: dict[str, Any], built_pdfs: list[tuple[dict[str, Any], Path]]) -> None:
    public_root = REPOSITORY_ROOT / "public"
    public_root.mkdir(exist_ok=True)
    cards: list[str] = []
    manifest: list[dict[str, Any]] = []
    for course, pdf_path in built_pdfs:
        public_pdf = public_root / course["pdf_name"]
        shutil.copy2(pdf_path, public_pdf)
        pdf_url = quote(course["pdf_name"])
        cards.append(
            f"""<article class="card">
      <p class="eyebrow">{html.escape(config['term'])}</p>
      <h2>{html.escape(course['title'])}</h2>
      <p>{html.escape(course['progress'])}</p>
      <a href="{pdf_url}">阅读或下载 PDF</a>
    </article>"""
        )
        manifest.append(
            {
                "id": course["id"],
                "title": course["title"],
                "progress": course["progress"],
                "file": course["pdf_name"],
                "bytes": public_pdf.stat().st_size,
                "sha256": sha256(public_pdf),
            }
        )

    index = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Raisetsu41 的 2026 秋季课程笔记">
  <title>2026 秋季课程笔记</title>
  <style>
    :root {{ color-scheme: light; --ink:#172033; --muted:#667085; --paper:#f6f7fb; --accent:#3157d5; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font-family:Inter,"Noto Sans SC","Microsoft YaHei",sans-serif; }}
    main {{ width:min(1040px,calc(100% - 32px)); margin:0 auto; padding:72px 0 96px; }}
    header {{ max-width:720px; margin-bottom:36px; }}
    h1 {{ margin:0 0 12px; font-family:"Noto Serif SC","Songti SC",serif; font-size:clamp(2rem,6vw,4.6rem); line-height:1.08; }}
    header p {{ color:var(--muted); font-size:1.05rem; line-height:1.8; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:18px; }}
    .card {{ min-height:230px; padding:28px; background:white; border:1px solid #e4e7ec; border-radius:18px; box-shadow:0 12px 36px rgba(29,41,57,.06); display:flex; flex-direction:column; }}
    .eyebrow {{ margin:0; color:var(--accent); font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
    h2 {{ margin:18px 0 10px; font-size:1.35rem; }}
    .card > p:not(.eyebrow) {{ margin:0; color:var(--muted); }}
    a {{ margin-top:auto; padding-top:28px; color:var(--accent); font-weight:700; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    footer {{ margin-top:34px; color:var(--muted); font-size:.88rem; }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">Raisetsu41 · {html.escape(config['term'])}</p>
      <h1>按章节生长的课程笔记</h1>
      <p>内容来自本地 Obsidian Markdown，由 Pandoc 与 XeLaTeX 自动整理、编译和发布。</p>
    </header>
    <section class="grid">
      {''.join(cards)}
    </section>
    <footer>每次发布均重新读取本地笔记；notes.json 提供文件哈希与构建信息。</footer>
  </main>
</body>
</html>
"""
    (public_root / "index.html").write_text(index, encoding="utf-8")
    metadata = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "courses": manifest,
    }
    (public_root / "notes.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build(config: dict[str, Any]) -> None:
    generate(config)
    build_root = REPOSITORY_ROOT / ".build"
    build_root.mkdir(exist_ok=True)
    built_pdfs: list[tuple[dict[str, Any], Path]] = []

    for course in config["courses"]:
        course_root = REPOSITORY_ROOT / course["directory"]
        course_build = build_root / course["id"]
        if course_build.exists():
            shutil.rmtree(course_build)
        course_build.mkdir(parents=True)
        run(
            [
                "latexmk",
                "-xelatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-outdir={course_build}",
                "main.tex",
            ],
            cwd=course_root,
        )
        compiled = course_build / "main.pdf"
        if not compiled.is_file() or compiled.read_bytes()[:4] != b"%PDF":
            raise RuntimeError(f"PDF 构建结果无效：{compiled}")
        named_pdf = course_root / course["pdf_name"]
        shutil.copy2(compiled, named_pdf)
        built_pdfs.append((course, named_pdf))
        print(f"[ok] {named_pdf}")

    write_public_site(config, built_pdfs)
    print("[ok] public/ 静态站点已更新。")


def check_environment() -> None:
    required = ["python", "pandoc", "xelatex", "latexmk", "git"]
    missing = [tool for tool in required if shutil.which(tool) is None]
    for tool in required:
        location = shutil.which(tool)
        print(f"{tool:10} {location or 'MISSING'}")
    if missing:
        raise RuntimeError("缺少工具：" + ", ".join(missing))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "generate", "build"), nargs="?", default="build")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        check_environment()
        if args.command == "doctor":
            return 0
        config = load_config(args.config.resolve())
        if args.command == "generate":
            generate(config)
        else:
            build(config)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
