#!/bin/bash
# Transcribe.app インストーラ（macOS）。ダブルクリックで実行する。
# ffmpeg・Whisper・yt-dlp を導入し、デスクトップに Transcribe.app を作る。
set -e
cd "$(dirname "$0")"
APP_DIR="$(pwd)"
REPO_ROOT="$(cd ../.. && pwd)"
DEST_APP="$HOME/Desktop/Transcribe.app"

echo "=== Transcribe.app セットアップを開始します ==="
echo

if ! command -v brew >/dev/null 2>&1; then
    echo "エラー: Homebrew が見つかりません。"
    echo "先に https://brew.sh の手順で Homebrew をインストールしてから、このファイルをもう一度ダブルクリックしてください。"
    read -n 1 -s -r -p "何かキーを押すと終了します..."
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[1/4] ffmpeg をインストールしています..."
    brew install ffmpeg
else
    echo "[1/4] ffmpeg は導入済みです"
fi

if ! command -v yt-dlp >/dev/null 2>&1; then
    echo "[2/4] yt-dlp をインストールしています（YouTube URL対応）..."
    brew install yt-dlp
else
    echo "[2/4] yt-dlp は導入済みです"
fi

echo "[3/4] Whisper をインストールしています（数分かかる場合があります）..."
# faster-whisper は常に必要（mlx-whisper 経路でも、無音明けの短い発話を拾う
# gap補完ステップがCPU+VADの faster-whisper に委譲するため）。
pip3 install --user --quiet faster-whisper || pip3 install --user --break-system-packages --quiet faster-whisper
if [ "$(uname -m)" = "arm64" ]; then
    pip3 install --user --quiet mlx-whisper || pip3 install --user --break-system-packages --quiet mlx-whisper
fi

echo "[4/4] Transcribe.app を作成しています..."
rm -rf "$DEST_APP"
osacompile -o "$DEST_APP" "$APP_DIR/Transcribe.applescript"
mkdir -p "$DEST_APP/Contents/Resources/scripts" "$DEST_APP/Contents/Resources/input" "$DEST_APP/Contents/Resources/output"
cp -R "$REPO_ROOT/scripts/." "$DEST_APP/Contents/Resources/scripts/"
xattr -cr "$DEST_APP" 2>/dev/null || true
codesign --force --deep --sign - "$DEST_APP" 2>/dev/null || true

echo
echo "=== 完了しました ==="
echo "デスクトップに Transcribe.app ができました。"
echo "音声/動画ファイルをアイコンにドラッグ&ドロップすると文字起こしが始まります。"
echo "YouTube URLを使いたい場合はダブルクリックして貼り付けてください。"
echo
read -n 1 -s -r -p "何かキーを押すとこのウィンドウを閉じます..."
