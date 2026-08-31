# Transcribe アプリ版（Claude Code不要）

Claude Codeを使わずに、音声/動画ファイルをドラッグ&ドロップするだけで文字起こしできる
デスクトップアプリです。ターミナル操作は初回インストール時の1回だけです。

## Mac

1. このリポジトリを [ZIPでダウンロード](https://github.com/yukkihagi1008-art/transcribe/archive/refs/heads/main.zip)して展開する
2. `app/mac/install.command` をダブルクリックする
   - 初回、Finderで「開発元を確認できないため開けません」と出た場合は、
     ファイルを右クリック→「開く」を選び直すと実行できる
   - ffmpeg・Whisper・yt-dlpの導入で数分かかる（Homebrewが未導入の場合は
     先に [brew.sh](https://brew.sh) の手順でHomebrewを入れてから再実行する）
3. 完了すると **デスクトップに `Transcribe.app` ができる**
4. 使い方:
   - 音声/動画ファイルをアイコンにドラッグ&ドロップ → 完了すると通知が出て、
     テキストファイルの入ったフォルダが自動で開く
   - YouTube URLを使いたい場合はアイコンをダブルクリックし、ダイアログに貼り付ける
5. `Transcribe.app` は自己完結型なので、Desktop以外の好きな場所に移動しても動く
   （元のZIP展開フォルダは削除してよい）

## Windows

1. このリポジトリを [ZIPでダウンロード](https://github.com/yukkihagi1008-art/transcribe/archive/refs/heads/main.zip)して展開する
2. `app/windows/install.ps1` を右クリック→「PowerShellで実行」する
   - 実行がブロックされる場合は、PowerShellを管理者権限で開いて
     `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` を実行してから再度試す
   - Python・ffmpeg・Whisper・yt-dlpの導入で数分かかる
3. 完了すると **デスクトップに `Transcribe` ショートカットができる**
4. 使い方:
   - 音声/動画ファイルをショートカットにドラッグ&ドロップ → 完了すると出力フォルダが自動で開く
   - YouTube URLを使いたい場合はショートカットをダブルクリックし、聞かれたら貼り付ける

> **注意**: Windows版はこのリポジトリの開発機（macOS）では実機確認できていません。
> 動作しない場合は [Issue](https://github.com/yukkihagi1008-art/transcribe/issues) で
> エラーメッセージを報告してほしい。

## 仕組み

- Mac版はAppleScriptで作った軽量な `.app`（ドロップレット）で、中身は `scripts/` を
  そのまま同梱してPython経由で呼び出しているだけ。Claude Code版の `/transcribe` と
  完全に同じスクリプト・同じ出力
- Windows版は `.bat` ファイル（ドラッグ&ドロップでファイルパスを引数として受け取れる）
- どちらも「初回だけ依存関係をインストールし、以後はアイコンにドラッグ&ドロップ」という
  同じ体験になるよう揃えている
