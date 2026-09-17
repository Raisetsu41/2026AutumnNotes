$ErrorActionPreference = 'Stop'

$obsidianRoot = 'D:\Obsidian\Notes'
$outputRoot = 'D:\2026Autumn\Notes'
$temporaryRoot = Join-Path $env:TEMP 'latex-notes-chapter-build-20260917'

New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null

function Get-MarkdownBody {
    param([Parameter(Mandatory)][string]$Path)

    $lines = Get-Content -LiteralPath $Path -Encoding UTF8
    if ($lines.Count -gt 0 -and $lines[0] -eq '---') {
        $closing = -1
        for ($i = 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -eq '---') {
                $closing = $i
                break
            }
        }
        if ($closing -ge 0) {
            $lines = $lines[($closing + 1)..($lines.Count - 1)]
        }
    }

    return $lines
}

function Remove-CommonMetadata {
    param([Parameter(Mandatory)][AllowEmptyString()][string[]]$Lines)

    return ($Lines | Where-Object {
        $_ -notmatch '^# ' -and
        $_ -notmatch '^Ref:' -and
        $_ -notmatch '^!\[\[' -and
        $_ -ne '---'
    })
}

function Convert-MarkdownFragment {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string[]]$Lines,
        [Parameter(Mandatory)][string]$MarkdownPath,
        [Parameter(Mandatory)][string]$TexPath
    )

    $parent = Split-Path -Parent $TexPath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $normalizedLines = $Lines | ForEach-Object {
        $line = $_ -replace '^(#{2,6})\s+\d+(?:\.\d+)*\.?\s*', '$1 '
        $line.Replace('✓', '$\checkmark$').Replace('✗', '$\times$').Replace('σ', '$\sigma$').Replace('ouput', 'output').Replace('automible', 'automobile').Replace('Captital', 'capital').Replace('value ot', 'value of')
    }
    Set-Content -LiteralPath $MarkdownPath -Value $normalizedLines -Encoding UTF8
    & pandoc $MarkdownPath `
        --from='markdown+yaml_metadata_block+tex_math_dollars+pipe_tables+lists_without_preceding_blankline' `
        --to=latex `
        --top-level-division=section `
        --wrap=preserve `
        --output=$TexPath
    if ($LASTEXITCODE -ne 0) {
        throw "Pandoc conversion failed: $MarkdownPath"
    }
}

# 金融经济学：课堂进度为 Chapter 1 与 Chapter 2 pp.1--32。
$financeSource = Join-Path $obsidianRoot '02-Economics\2026-Financial-Economics\2026-09-17-Note.md'
$financeLines = Remove-CommonMetadata (Get-MarkdownBody $financeSource)
$financeChapter2Start = [Array]::FindIndex(
    [string[]]$financeLines,
    [Predicate[string]] { param($line) $line -match '^## 7\. The Financial System' }
)
if ($financeChapter2Start -lt 0) {
    throw 'Cannot locate the Chapter 2 boundary in the financial-economics note.'
}
$financeChapter1 = @('# 金融与财务决策') + $financeLines[0..($financeChapter2Start - 1)]
$financeChapter2 = @('# 金融体系、激励与市场价格') + $financeLines[$financeChapter2Start..($financeLines.Count - 1)]
Convert-MarkdownFragment $financeChapter1 (Join-Path $temporaryRoot 'finance-ch01.md') (Join-Path $outputRoot 'Financial-Economics\chapters\ch01.tex')
Convert-MarkdownFragment $financeChapter2 (Join-Path $temporaryRoot 'finance-ch02.md') (Join-Path $outputRoot 'Financial-Economics\chapters\ch02.tex')

# 宏观经济学：按 Chapter 1--2 归并正式课堂笔记。
$macroChapter1Source = Join-Path $obsidianRoot '02-Economics\2026-Macroeconomics\2026-09-07-Note.md'
$macroChapter1Lines = Remove-CommonMetadata (Get-MarkdownBody $macroChapter1Source)
$macroChapter1 = @('# 宏观经济学科学') + $macroChapter1Lines
Convert-MarkdownFragment $macroChapter1 (Join-Path $temporaryRoot 'macro-ch01.md') (Join-Path $outputRoot 'Macroeconomics\chapters\ch01.tex')

$macroChapter2Files = @(
    '2026-09-09-Note.md',
    '2026-09-14-Note.md',
    '2026-09-16-Note.md'
)
$macroChapter2Lines = @()
foreach ($fileName in $macroChapter2Files) {
    $lines = Remove-CommonMetadata (
        Get-MarkdownBody (Join-Path $obsidianRoot "02-Economics\2026-Macroeconomics\$fileName")
    )
    if ($fileName -eq '2026-09-14-Note.md') {
        $lines = $lines | Where-Object { $_ -notmatch '^## 7\. Review' }
    }
    if ($fileName -eq '2026-09-16-Note.md') {
        $lines = $lines | Where-Object { $_ -notmatch '^## 1\. Chain-Weighted Real GDP' }
    }
    $macroChapter2Lines += $lines
}
$macroChapter2 = @('# 宏观经济数据') + $macroChapter2Lines
$macroChapter2Tex = Join-Path $outputRoot 'Macroeconomics\chapters\ch02.tex'
Convert-MarkdownFragment $macroChapter2 (Join-Path $temporaryRoot 'macro-ch02.md') $macroChapter2Tex

# 修复课堂 Markdown 中不适合 LaTeX 的旧式公式，并为宽表设置可换行列。
$macroTex = Get-Content -Raw -LiteralPath $macroChapter2Tex -Encoding UTF8
$macroTex = $macroTex.Replace(
    '\text{silica} {{1 \ RMB}\over} \text{glass} {{4 \ RMB}\over} \text{automobile} {{100 \ RMB}\over}',
    '\text{silica }(1\,\mathrm{RMB}) \longrightarrow \text{glass }(4\,\mathrm{RMB}) \longrightarrow \text{automobile }(100\,\mathrm{RMB})'
)
$macroTex = $macroTex.Replace(
    '&+\text{Dividends}' + "`r`n" + '+\text{Government Transfers to Individuals}' + "`r`n" + '+\text{Personal Interest Income}.',
    '&+\text{Dividends}+\text{Government Transfers to Individuals}\\' + "`r`n" + '&+\text{Personal Interest Income}.'
)
$macroTex = $macroTex.Replace(
    '\begin{longtable}[]{@{}lll@{}}',
    '\begin{longtable}[]{@{}>{\raggedright\arraybackslash}p{0.22\linewidth}>{\raggedright\arraybackslash}p{0.34\linewidth}>{\raggedright\arraybackslash}p{0.34\linewidth}@{}}'
)
Set-Content -LiteralPath $macroChapter2Tex -Value $macroTex -Encoding UTF8

# 概率论：只归并 2026 秋正式课程进度（1.1--1.5），不混入暑假预习章节。
$probabilityDir = Join-Path $obsidianRoot '01-Mathematics\2026-Probability-Theory'
$probabilityFiles = @(
    '2026-09-07-Note.md',
    '2026-09-09-Note.md',
    '2026-09-14-Note.md',
    '2026-09-16-Note.md'
)
$probabilitySections = @()
foreach ($fileName in $probabilityFiles) {
    $lines = Remove-CommonMetadata (Get-MarkdownBody (Join-Path $probabilityDir $fileName))
    $lines = $lines | Where-Object {
        $_ -notmatch '^## Chapter 1$'
    }
    if ($fileName -eq '2026-09-09-Note.md') {
        $lines = $lines | Where-Object { $_ -notmatch '^## 1\.2 Basics of Probability Theory' }
    }
    if ($fileName -eq '2026-09-14-Note.md') {
        $lines = $lines | ForEach-Object {
            if ($_ -match '^## [1-6]\. ') { $_ -replace '^## ', '### ' } else { $_ }
        }
    }
    if ($fileName -eq '2026-09-16-Note.md') {
        $lines = $lines | Where-Object { $_ -notmatch '^## 1\.3 Independence（独立性续）' }
        $lines = $lines | ForEach-Object {
            if ($_ -match '^## 4\. Review') { $_ -replace '^## 4\. Review', '### Review' } else { $_ }
        }
    }
    $probabilitySections += $lines
}
$probabilityChapter1 = @('# 概率论基础') + $probabilitySections
Convert-MarkdownFragment $probabilityChapter1 (Join-Path $temporaryRoot 'probability-ch01.md') (Join-Path $outputRoot 'Probability-Statistics\chapters\ch01.tex')

Write-Output 'Chapter sources regenerated successfully.'
