@echo off
rem Transcribe.bat: このファイル自身にファイルをドラッグ&ドロップすると文字起こしを実行する。
rem install.ps1 が %LOCALAPPDATA%\transcribe-anywhere\ にこのファイルと scripts\ を
rem コピーするため、%~dp0（このファイル自身の場所）を基準にパスを解決する。
setlocal enabledelayedexpansion
set "HERE=%~dp0"

if "%~1"=="" (
    echo 音声/動画ファイルをこのアイコンにドラッグ^&ドロップしてください。
    echo YouTube URLを使いたい場合は、次の行に貼り付けてEnterを押してください（不要ならそのままEnter）。
    set /p URL=URL:
    if "!URL!"=="" (
        pause
        exit /b
    )
    python "%HERE%scripts\transcribe_only.py" "!URL!"
    goto :done
)

set ARGS=
:loop
if "%~1"=="" goto run
set ARGS=%ARGS% "%~1"
shift
goto loop

:run
python "%HERE%scripts\transcribe_only.py" %ARGS%

:done
echo.
echo 完了しました。出力フォルダを開きます...
start "" "%HERE%output"
pause
