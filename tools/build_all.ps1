$ErrorActionPreference = 'Stop'

$notesRoot = Split-Path -Parent $PSScriptRoot
$courses = @(
    'Financial-Economics',
    'Macroeconomics',
    'Probability-Statistics'
)

& (Join-Path $PSScriptRoot 'generate_chapters.ps1')

foreach ($course in $courses) {
    $courseRoot = Join-Path $notesRoot $course
    Copy-Item `
        -LiteralPath (Join-Path $notesRoot 'math-shortcuts.sty') `
        -Destination (Join-Path $courseRoot 'math-shortcuts.sty') `
        -Force

    Push-Location $courseRoot
    try {
        & latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
        if ($LASTEXITCODE -ne 0) {
            throw "LaTeX build failed: $course"
        }
    }
    finally {
        Pop-Location
    }
}

Write-Output 'All course notes were regenerated and compiled successfully.'

