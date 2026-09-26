$ErrorActionPreference = 'Stop'

& python (Join-Path $PSScriptRoot 'build_notes.py') build
if ($LASTEXITCODE -ne 0) {
    throw '课程笔记构建失败。'
}
