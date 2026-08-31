#!/usr/bin/env python3
"""YouTube URL → MP3 ダウンロードのユーティリティ（transcribe_only.py から利用）。

yt-dlp で音声のみを取得して MP3 化する（<repo>/input/<タイトル先頭50字>_<動画ID>.mp3）。
ファイル名の末尾に動画ID（常に11字・衝突なし）を付けるのは、タイトルだけだとUTF-8で
255バイト境界に近い長いタイトルのとき実行ごとにOS依存の切り詰め位置がずれて
同じ動画でも別ファイル扱いになり、ダウンロードのキャッシュが効かなくなる問題が
あったため（動画IDで決定的な名前にする）。同じ動画なら yt-dlp 自身が再ダウンロードを
スキップする。

yt-dlp は CLI（`brew install yt-dlp` 等）があればそれを優先し、無ければ Python
モジュール（`pip3 install --user -U yt-dlp`）を使う。YouTube 側の仕様変更に追随
できていない古い yt-dlp では取得に失敗するため、失敗時は更新を案内する。

このファイル自体はライブラリで、単体のコマンドラインエントリは持たない
（YouTube URL の文字起こしは /transcribe から使う: transcribe_only.py 参照）。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_DIR.parent
UPDATE_HINT = ("yt-dlp が YouTube の現行仕様に追随できていない可能性があります。\n"
               "  brew install yt-dlp        # 推奨（独自のPythonを同梱するため3.9問題を回避）\n"
               "  pip3 install --user -U yt-dlp")

# タイトルの切り詰め文字数。動画IDサフィックス（"_"+11字）と ".mp3" を足しても
# UTF-8で255バイト（macOS/ext4等のファイル名上限）に確実に収まる余裕を持たせる
TITLE_CHARS = 50


def _cli_download(ytdlp: str, url: str, input_dir: Path) -> Path:
    """CLI 版 yt-dlp で MP3 を取得して保存先パスを返す。"""
    meta = subprocess.run(
        [ytdlp, "--skip-download", "--no-warnings",
         "--cookies-from-browser", "chrome",
         "--print", "%(id)s", "--print", "%(title)s", "--print", "%(duration)s", url],
        capture_output=True, text=True, timeout=600,
    )
    if meta.returncode != 0:
        raise RuntimeError(f"動画情報の取得に失敗しました: {meta.stderr.strip()}\n{UPDATE_HINT}")
    lines = [l for l in meta.stdout.splitlines() if l.strip()]
    title = lines[1] if len(lines) > 1 else "(不明)"
    duration = float(lines[2]) if len(lines) > 2 and lines[2].replace(".", "").isdigit() else 0.0
    print(f"タイトル: {title}")
    print(f"長さ: {duration / 60:.1f}分")

    print("ダウンロード中...（同じ動画IDなら yt-dlp が自動でキャッシュを再利用）")
    r = subprocess.run(
        [ytdlp, "-f", "bestaudio/best", "-x", "--audio-format", "mp3",
         "--audio-quality", "192K", "--no-warnings", "--no-progress",
         "--cookies-from-browser", "chrome",
         "-o", str(input_dir / f"%(title).{TITLE_CHARS}s_%(id)s.%(ext)s"),
         "--no-simulate", "--print", "after_move:filepath", url],
        capture_output=True, text=True, timeout=3600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ダウンロードに失敗しました: {r.stderr.strip()}\n{UPDATE_HINT}")
    if "has already been downloaded" in r.stdout:
        print("MP3キャッシュあり（再ダウンロードをスキップ）")
    paths = [Path(l.strip()) for l in r.stdout.splitlines() if l.strip().endswith(".mp3")]
    if not paths or not paths[-1].exists():
        raise RuntimeError(f"MP3 の生成に失敗しました\n{r.stdout.strip()}")
    return paths[-1]


def _module_download(url: str, input_dir: Path) -> Path:
    """Python モジュール版 yt-dlp で MP3 を取得して保存先パスを返す。"""
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("yt-dlp が見つかりません。`brew install yt-dlp` または "
                            "`pip3 install --user -U yt-dlp` を実行してください")

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(input_dir / f"%(title).{TITLE_CHARS}s_%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "cookiesfrombrowser": ("chrome",),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            print(f"タイトル: {info.get('title')}")
            print(f"長さ: {(info.get('duration') or 0) / 60:.1f}分")
            downloads = info.get("requested_downloads") or []
            if downloads and downloads[0].get("filepath"):
                mp3_path = Path(downloads[0]["filepath"])
            else:
                mp3_path = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
    except Exception as e:  # yt_dlp.utils.DownloadError 等
        raise RuntimeError(f"{e}\n{UPDATE_HINT}")

    if not mp3_path.exists():
        raise RuntimeError(f"MP3 の生成に失敗しました: {mp3_path}")
    return mp3_path


def download_mp3(url: str, input_dir: Path) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    ytdlp = shutil.which("yt-dlp")
    mp3_path = _cli_download(ytdlp, url, input_dir) if ytdlp else _module_download(url, input_dir)
    print(f"MP3: {mp3_path}")
    return mp3_path


def osa_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str) -> None:
    """macOS 通知センターに通知を出す。失敗しても本処理は止めない（ベストエフォート）。"""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{osa_escape(message)}" with title "{osa_escape(title)}"'],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass
