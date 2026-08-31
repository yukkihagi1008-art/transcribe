# transcribe

音声/動画ファイル、またはYouTube URLをプレーンテキストに文字起こしする `/transcribe`（と
単機能版 `/yt-transcribe`）の **セットアップウィザード** テンプレートです。

## 使い方（Claude Code）

ターミナルで `git clone` する必要はありません。Claude Code に次のメッセージを渡すだけです。

> `https://github.com/yukkihagi1008-art/transcribe` の CLAUDE.md に従ってセットアップして

壁打ち（1問: 保存先フォルダ）が始まります。答え終わると自動でセットアップが作られ、
`/transcribe` がすぐ使えるようになります。

## 何をしてくれるか

- `mlx-whisper`（Apple Silicon GPU）または `faster-whisper`（CPU）で音声を単一パス転写
- 無音・低音量区間はCPU Whisper(VAD付き)で再転写し、欠落しがちな短い発話を自動補完
- ローカルファイルとYouTube URLを複数・混在で渡せる（1件失敗しても残りは続行）
- 出力は句読点区切りのプレーンテキストのみ（SRT化・タイムコード付与はしない）

SRT字幕（Premiere Pro用のタイムコード付きテロップ）が欲しい場合は
[premiere-srt-fast-template](https://github.com/fuuuuuuma/premiere-srt-fast-template) の
`/srt-fast` を使ってください。このリポジトリは意図的にSRT生成機能を持たず、
プレーンテキストの文字起こしだけに専念しています。

## 同梱されているもの（変更不要）

- `scripts/transcribe_engine.py` — 転写コア（GPU単一パス・gap補完・CPUフォールバック）
- `scripts/transcribe_parallel.py` + `scripts/chunk_tools/` — GPU非搭載環境向けのCPU並列転写経路
- `scripts/transcribe_only.py` — `/transcribe` 本体（複数入力対応）
- `scripts/youtube_to_text.py` — YouTube URL → MP3 ダウンロード

## 壁打ちで生成されるもの

- `~/.claude/commands/transcribe.md`
- `~/.claude/commands/yt-transcribe.md`

## 前提環境

- `ffmpeg`
- `mlx-whisper`（Apple Silicon Mac。無ければ自動でCPUフォールバック）または `faster-whisper`
- YouTube URLを使う場合は `yt-dlp`

## 注意（YouTube URLを使う場合）

自分のチャンネル・利用権限のある動画に対してのみ使用してください。
ダウンロードした音声・動画コンテンツの取り扱いはYouTubeの利用規約に従ってください。
