# 音声/動画 → 文字起こし — セットアップウィザード

## 起動判定（まずここを確認）

- カレントディレクトリに `.template/skill-template.md` がローカルに存在し読める
  → **既にこのリポジトリがclone済み**。Step B へ進む
- 存在しない・読めない（＝チャット越しにこのファイルを読んでいるだけで、まだcloneされていない）
  → Step A へ進む

## Step A: 未clone（GitHubのURLを渡されてこのファイルを読んでいる場合）

**重要**: このファイルの内容を WebFetch で読んでいる場合、`.template/skill-template.md` 等の
正確な原文は WebFetch では取得できない（要約されてしまい内容が変質する）。
必ず先にリポジトリを一時ディレクトリへ clone し、以降は Read でローカルファイルを読むこと。

1. `~/.claude/CLAUDE.md` が存在すれば読み込み、文体・スタイルを把握する
2. まず OS の一時ディレクトリ配下にこのリポジトリを clone する（保存先はまだ聞かない）:
   ```bash
   TMPDIR_SETUP="$(mktemp -d)/transcribe-anywhere"
   git clone https://github.com/yukkihagi1008-art/transcribe.git "$TMPDIR_SETUP"
   ```
3. ユーザーに1問だけ聞く:

   **このセットアップを保存するフォルダはどこにしますか？**
   絶対パスで（例: `~/ClaudeCode/projects/transcribe-anywhere/`）。ここにこのリポジトリを
   clone し、以後ダウンロードした音声・出力テキストもこの中に入る。

4. 回答が絶対パスで得られたら、親ディレクトリを作ってから一時ディレクトリを移動する:
   ```bash
   mkdir -p "$(dirname "<回答の絶対パス>")"
   mv "$TMPDIR_SETUP" "<回答の絶対パス>"
   ```
5. 移動後の絶対パスを `{{PROJECT_ROOT}}` として Step B へ進む

## Step B: 生成（ローカルにこのリポジトリがある状態）

1. `{{PROJECT_ROOT}}` を確定する（Step Aから来た場合は移動後の絶対パス。直接この状態から
   始まった場合は `pwd` でこのリポジトリの絶対パスを取得する）
2. `.template/skill-template.md` の `{{PROJECT_ROOT}}` を実際の絶対パスに置換したものを
   `~/.claude/commands/transcribe.md` に保存する
3. `.template/skill-template-yt.md` の `{{PROJECT_ROOT}}` を実際の絶対パスに置換したものを
   `~/.claude/commands/yt-transcribe.md` に保存する
4. `ffmpeg -version` と `python3 -c "import faster_whisper"` を実行し、未インストールなら
   `pip3 install --user faster-whisper` / `brew install ffmpeg` を案内する
   （Apple Silicon Mac の場合は `pip3 install --user mlx-whisper` も併せて案内し、
   入っていれば自動でGPU転写が使われる旨を伝える）
5. YouTube URLも使いたいか確認し、使う場合は `yt-dlp` の有無を確認する
   （無ければ `brew install yt-dlp` を推奨、代替として `pip3 install --user -U yt-dlp`）
6. `/transcribe <音声ファイルの絶対パスまたはYouTube URL>` で使い始められる旨を伝えて終了する

## 注意

- 質問は必ず1問ずつ。まとめて聞かない
- テンプレート原文（skill-template.md / skill-template-yt.md）は必ず **Read で
  ローカルファイルとして** 読む。WebFetch は使わない（要約されて内容が変質するため）
- `scripts/` は既に同梱済みのファイルなので変更しない
- コマンド名は常に `transcribe` / `yt-transcribe` で固定。出力先は常に
  `{{PROJECT_ROOT}}/output/<ファイル名>.txt`（スクリプトが自動決定するため聞かない）
- セットアップ後にフォルダを移動したくなった場合は、手動でフォルダごと移動してから
  そのディレクトリで再度セットアップを実行すればよい（Step B が新しい `pwd` を
  `{{PROJECT_ROOT}}` として `~/.claude/commands/` 配下のコマンドを作り直す）
