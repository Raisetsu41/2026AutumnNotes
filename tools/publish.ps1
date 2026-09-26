[CmdletBinding()]
param(
    [string]$Message = "docs: publish course notes $(Get-Date -Format 'yyyy-MM-dd HH:mm')",
    [switch]$NoPush,
    [switch]$AllowDirty,
    [switch]$DirectVercel
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repositoryRoot
try {
    $before = @(git status --porcelain)
    if ($LASTEXITCODE -ne 0) {
        throw '无法读取 Git 状态。'
    }
    if ($before.Count -gt 0 -and -not $AllowDirty) {
        throw '仓库已有未提交修改。请先处理它们，或确认后使用 -AllowDirty。'
    }

    & python (Join-Path $PSScriptRoot 'build_notes.py') build
    if ($LASTEXITCODE -ne 0) {
        throw '笔记构建失败，未执行 Git 提交或部署。'
    }

    $generatedPaths = @(
        'Financial-Economics',
        'Macroeconomics',
        'Probability-Statistics',
        'public',
        '.gitignore',
        'notes.config.json',
        'shared-preamble.tex',
        'tools',
        'README.md',
        'vercel.json'
    )
    & git add -- $generatedPaths
    if ($LASTEXITCODE -ne 0) {
        throw 'git add 失败。'
    }

    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Output '笔记内容没有变化，无需创建提交。'
    }
    elseif ($LASTEXITCODE -eq 1) {
        & git commit -m $Message
        if ($LASTEXITCODE -ne 0) {
            throw 'git commit 失败。'
        }
    }
    else {
        throw '无法检查暂存区状态。'
    }

    if (-not $NoPush) {
        & git push origin HEAD
        if ($LASTEXITCODE -ne 0) {
            throw 'git push 失败。本地提交已保留，尚未触发远程部署。'
        }
        Write-Output '已推送 GitHub；若 Vercel 已连接此仓库，将自动开始部署。'
    }

    if ($DirectVercel) {
        $vercel = Get-Command vercel -ErrorAction SilentlyContinue
        if ($vercel) {
            & vercel --prod --yes
        }
        else {
            $npx = Get-Command npx -ErrorAction SilentlyContinue
            if (-not $npx) {
                throw '找不到 vercel 或 npx，无法直接部署。'
            }
            & npx --yes vercel@latest --prod --yes
        }
        if ($LASTEXITCODE -ne 0) {
            throw 'Vercel 直接部署失败。请先运行 npx vercel login 和 npx vercel link。'
        }
    }
}
finally {
    Pop-Location
}
