# スキルテンプレート (/yt-transcribe)

以下の `{{PROJECT_ROOT}}` を実際の絶対パスに置換してください。
生成したファイルは `~/.claude/commands/yt-transcribe.md` に保存する。

`/transcribe` がYouTube URLも直接受け付けるため通常は `/transcribe` だけで足りるが、
「ダウンロード＋文字起こしだけを単体で」呼びたい場合のための単機能版。

---

## 生成するスキルファイルの内容

````markdown
---
description: YouTubeのURLから音声をMP3でダウンロードし、そのままプレーンテキストに文字起こしする（.txt出力のみ）。
---

# YouTube → 文字起こし (/yt-transcribe)

## 使い方

```
/yt-transcribe https://www.youtube.com/watch?v=xxxxxxxxxxx
```

- MP3: `{{PROJECT_ROOT}}/input/<タイトル先頭50字>_<動画ID>.mp3`
- テキスト: `{{PROJECT_ROOT}}/output/<ファイル名>.txt`

**前提**: `yt-dlp` が必要（CLI版があれば優先して使う。無ければPythonモジュール版）。
`The page needs to be reloaded` 等のエラーが出たら yt-dlp が古い証拠なので
`brew install yt-dlp`（推奨）または `pip3 install --user -U yt-dlp` で更新する。

## 実行手順

### Step 1: URL確認

引数がYouTubeのURLであることを確認する（URLでなければユーザーに確認）。
URLは `&` などシェルの特殊文字を含むので必ずダブルクオートで囲む。

### Step 2: ダウンロード＋文字起こし（bash直・エージェント不使用）

```bash
python3 "{{PROJECT_ROOT}}/scripts/transcribe_only.py" "<YouTubeのURL>"
```

**Bash タイムアウト: 600000ms（10分）必須**。ダウンロード時間＋転写時間（GPUで音声長の
約1/8）がかかる。長尺は `run_in_background: true` で実行し完了通知を待ってから次へ進む。

- 同名MP3が `input/` に既にあればダウンロードをスキップする
- 標準出力の `完了: <path>` が出力txtの絶対パス

### Step 3: 完了報告

1. 動画タイトルと長さ
2. 出力txtの絶対パス
3. 文字数
4. 使用エンジン（mlx-single-pass / cpu-parallel / cache）
````
