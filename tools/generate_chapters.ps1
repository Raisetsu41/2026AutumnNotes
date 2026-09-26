$ErrorActionPreference = 'Stop'

Write-Warning 'generate_chapters.ps1 已并入配置驱动的 build_notes.py。'
& python (Join-Path $PSScriptRoot 'build_notes.py') generate
if ($LASTEXITCODE -ne 0) {
    throw '章节生成失败。'
}
