# Transcribe インストーラ（Windows）。PowerShellで右クリック→実行 する。
# ffmpeg・faster-whisper・yt-dlp を導入し、デスクトップに Transcribe へのショートカットを作る。
# 未検証: このリポジトリの開発機は macOS のため、Windows実機での動作確認はまだ済んでいない。
# 動かない場合は Issue で報告してほしい。

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$InstallDir = "$env:LOCALAPPDATA\transcribe-anywhere"

Write-Host "=== Transcribe セットアップを開始します ===" -ForegroundColor Cyan

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "winget")) {
    Write-Host "エラー: winget が見つかりません。Windows 10 (2004以降) / 11 の 'アプリ インストーラー' を" -ForegroundColor Red
    Write-Host "Microsoft Store から導入してから、もう一度実行してください。" -ForegroundColor Red
    Read-Host "Enterキーで終了"
    exit 1
}

if (-not (Test-Command "python")) {
    Write-Host "[1/5] Python をインストールしています..."
    winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
} else {
    Write-Host "[1/5] Python は導入済みです"
}

if (-not (Test-Command "ffmpeg")) {
    Write-Host "[2/5] ffmpeg をインストールしています..."
    winget install --id Gyan.FFmpeg --source winget --accept-package-agreements --accept-source-agreements
} else {
    Write-Host "[2/5] ffmpeg は導入済みです"
}

Write-Host "[3/5] Whisper・yt-dlp をインストールしています（数分かかる場合があります）..."
python -m pip install --user --quiet faster-whisper yt-dlp

Write-Host "[4/5] Transcribe をセットアップしています..."
New-Item -ItemType Directory -Force -Path "$InstallDir\scripts" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\input" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\output" | Out-Null
Copy-Item -Path "$RepoRoot\scripts\*" -Destination "$InstallDir\scripts\" -Recurse -Force
Copy-Item -Path "$PSScriptRoot\Transcribe.bat" -Destination "$InstallDir\Transcribe.bat" -Force

Write-Host "[5/5] デスクトップにショートカットを作成しています..."
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Transcribe.lnk")
$Shortcut.TargetPath = "$InstallDir\Transcribe.bat"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()

Write-Host ""
Write-Host "=== 完了しました ===" -ForegroundColor Green
Write-Host "デスクトップの Transcribe ショートカットに音声/動画ファイルをドラッグ&ドロップすると文字起こしが始まります。"
Write-Host "YouTube URLを使いたい場合はダブルクリックして貼り付けてください。"
Read-Host "Enterキーでこのウィンドウを閉じます"
