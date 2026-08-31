# スキルテンプレート (/transcribe)

以下の `{{PROJECT_ROOT}}` を実際の絶対パスに置換してください。
生成したファイルは `~/.claude/commands/transcribe.md` に保存する。

---

## 生成するスキルファイルの内容

````markdown
---
description: 音声/動画ファイル、またはYouTube URL（複数・混在可）をプレーンテキストに文字起こしする（SRT化・意味区切り改行なし、.txt出力のみ）。
---

# 文字起こし (/transcribe)

## 使い方

```
/transcribe /path/to/audio_or_video
/transcribe https://www.youtube.com/watch?v=xxxxxxxxxxx
```

ローカルファイルとYouTube URLはスペース区切りで複数・混在させて渡せる
（1件ずつ順番に処理し、1件失敗しても残りは続行する）:

```
/transcribe /path/to/a.mp3 https://youtu.be/aaa https://youtu.be/bbb
```

- YouTube URLの場合、音声は先にMP3として
  `{{PROJECT_ROOT}}/input/<タイトル先頭50字>_<動画ID>.mp3`
  にダウンロードされる（ファイル名末尾の動画IDのおかげで同じ動画は常に同じ名前になり、
  再ダウンロード・再転写のキャッシュが確実に効く）
- 出力txtは常に `{{PROJECT_ROOT}}/output/<ファイル名>.txt`
  （1件のみの場合に限り `-o <path>` で変更可）

**YouTube URLを使う前提**: `yt-dlp` が必要（CLI版があれば優先して使う。無ければPythonモジュール版）。
`The page needs to be reloaded` 等のエラーが出たら yt-dlp が古い証拠なので
`brew install yt-dlp`（推奨）または `pip3 install --user -U yt-dlp` で更新する。

## 実行手順

### Step 1: 入力確認

引数を1つずつ、ローカルの音声/動画ファイルパスかYouTube URLかを判定する
（`http://` `https://` で始まればURL、それ以外はローカルパスとして存在を確認。
存在しないローカルパスやURLとして怪しいものはユーザーに確認）。
パスは空白を含み得るので、URLは `&` などシェルの特殊文字を含み得るので、
どちらも必ず1つずつダブルクオートで囲む。

### Step 2: 文字起こし実行（bash直・エージェント不使用）

```bash
python3 "{{PROJECT_ROOT}}/scripts/transcribe_only.py" "<入力1>" "<入力2>" ...
```

**Bash タイムアウト: 600000ms（10分）必須**（GPU転写は音声長の約1/8だが、YouTube URLは
ダウンロード時間も加わるため長尺・複数件では特に時間がかかる。mlx-whisper があれば
単一パスGPU転写、無ければ自動的にCPU並列転写にフォールバックする）。10分超が
見込まれる場合は `run_in_background: true` で実行し完了通知を待ってから次へ進む。

- 標準出力の `完了: <path>` が各件の出力txtの絶対パス
- 複数件渡した場合、**1件完了するたび**に macOS 通知（`osascript`）が飛ぶ
  （成功時「文字起こし完了」、失敗時「文字起こし失敗」）。1件のみの場合は通知なし
- 複数件時は最後に `=== 完了サマリー (n/m 成功) ===` が出力される。1件のみの場合は出ない

### Step 3: 完了報告

各入力について:
1. （YouTube URLの場合のみ）動画タイトルと長さ
2. 出力txtの絶対パス（失敗した場合はエラー内容）
3. 文字数
4. 使用エンジン（mlx-single-pass / cpu-parallel / cache）

複数件の場合は最後に成功/失敗の一覧をまとめる。
````
