#!/usr/bin/env python3
"""入力（ローカルの音声/動画ファイル、または YouTube URL。複数・混在可） →
単一パス転写 → プレーンテキストのみ出力（/transcribe）。

mlx-whisper GPU単一パス／CPUフォールバックで転写し、意味区切り改行やSRT化は
せず全文テキストをそのまま書き出す。入力が http(s):// で始まる場合は
youtube_to_text.py で先に MP3 をダウンロードしてから同じ流れで転写する。
出力txtは常に <repo>/output/<stem>.txt。セグメント/WAVキャッシュは
output/srt/<stem>/ に残るため、同じファイルへの再実行は転写をやり直さず
キャッシュを再利用する。複数件渡すと1件ずつ順番に処理し、1件失敗しても
残りは続行する。

usage:
  transcribe_only.py <input_or_url> [<input_or_url> ...] [-o <output.txt>] [--repo REPO]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_DIR.parent
ENGINE = SCRIPT_DIR / "transcribe_engine.py"
PARALLEL = SCRIPT_DIR / "transcribe_parallel.py"
YOUTUBE = SCRIPT_DIR / "youtube_to_text.py"
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_HAS_WHISPER = ("import importlib.util,sys;"
                "sys.exit(0 if importlib.util.find_spec('mlx_whisper') "
                "or importlib.util.find_spec('faster_whisper') else 1)")


def _ensure_whisper_python() -> None:
    """mlx_whisper / faster_whisper を import できる python でなければ再exec する。

    Homebrew python が PATH 上で system python を隠すと、whisper を入れた側の
    python が使われず転写に失敗するため、使える python を自動で探して橋渡しする。
    """
    if os.environ.get("_TRANSCRIBE_REEXEC"):
        return
    if importlib.util.find_spec("mlx_whisper") or importlib.util.find_spec("faster_whisper"):
        return

    cands = ["/usr/bin/python3", "/opt/homebrew/bin/python3"]
    cands += [shutil.which(f"python3.{m}") for m in range(9, 15)]
    for cand in cands:
        if not cand or not Path(cand).exists() or Path(cand).resolve() == Path(sys.executable).resolve():
            continue
        try:
            ok = subprocess.run([cand, "-c", _HAS_WHISPER], timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError):
            continue
        if ok:
            print(f"whisper が使える python に切り替え: {cand}")
            os.execve(cand, [cand, str(Path(__file__).resolve()), *sys.argv[1:]],
                      {**os.environ, "_TRANSCRIBE_REEXEC": "1"})


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_engine_mod = None
_yt_mod = None


def _engine():
    global _engine_mod
    if _engine_mod is None:
        _engine_mod = _load_module(ENGINE, "transcribe_engine")
    return _engine_mod


def _yt():
    global _yt_mod
    if _yt_mod is None:
        _yt_mod = _load_module(YOUTUBE, "youtube_to_text")
    return _yt_mod


def _mlx_available() -> bool:
    import platform
    if platform.system() != "Darwin":
        return False
    if os.environ.get("SRT_WHISPER_ENGINE", "mlx") == "cpu":
        return False
    return importlib.util.find_spec("mlx_whisper") is not None


def ensure_wav16k(src: Path, out_dir: Path, stem: str) -> Path:
    full_wav = out_dir / f"{stem}.wav"
    if not full_wav.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", str(full_wav)],
            check=True, capture_output=True, timeout=3600,
        )
    return full_wav


def transcribe(src: Path, full_wav: Path, seg_path: Path) -> str:
    """segments.json を生成し、使用エンジン名を返す。既存キャッシュがあれば何もしない。"""
    if seg_path.exists():
        print(f"転写キャッシュあり: {seg_path}")
        return "cache"
    if _mlx_available():
        segs = _engine().run_whisper(str(full_wav))
        seg_path.write_text(json.dumps(segs, ensure_ascii=False, indent=2))
        return "mlx-single-pass"
    # CPU 環境: 並列転写（境界復元込み）に委譲。同じ seg_path を出力する
    r = subprocess.run(
        [sys.executable, str(PARALLEL), str(src), "--jobs", "3"],
        timeout=7200,
    )
    if r.returncode != 0 or not seg_path.exists():
        print("エラー: 転写に失敗しました")
        sys.exit(1)
    return "cpu-parallel"


def resolve_source(item: str, repo: Path) -> Path:
    """URL なら yt-dlp でダウンロードして mp3 パスを返す。ローカルパスならそのまま返す。"""
    if _URL_RE.match(item):
        return _yt().download_mp3(item, repo / "input")
    src = Path(item).expanduser()
    if not src.exists():
        raise RuntimeError(f"入力が見つかりません: {src}")
    return src


def transcribe_one(src: Path, repo: Path) -> tuple[Path, int, str]:
    """1件を文字起こしし、(出力txtパス, 文字数, engine) を返す。"""
    stem = src.stem
    out_dir = repo / "output" / "srt" / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    seg_path = out_dir / f"{stem}.segments.json"

    full_wav = ensure_wav16k(src, out_dir, stem)
    engine = transcribe(src, full_wav, seg_path)

    segs = json.loads(seg_path.read_text())
    segs = [s for s in segs if s.get("text", "").strip()]
    if not segs:
        raise RuntimeError("転写結果が空です")
    text = "".join(s["text"] for s in segs)

    out_path = repo / "output" / f"{stem}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path, len(text), engine


def process_one(item: str, repo: Path) -> tuple[Path, int, str]:
    src = resolve_source(item, repo)
    return transcribe_one(src, repo)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="/transcribe: 音声/動画ファイルまたはYouTube URL（複数・混在可）をプレーンテキストに文字起こし")
    ap.add_argument("inputs", nargs="+",
                    help="音声/動画ファイルの絶対パス、または YouTube URL（複数指定可・混在可）")
    ap.add_argument("-o", "--out", default=None,
                    help="出力txtパス（1件のときのみ有効。省略時は <repo>/output/<stem>.txt）")
    ap.add_argument("--repo", default=str(DEFAULT_REPO), help="出力・転写キャッシュ用リポジトリルート")
    a = ap.parse_args()

    _ensure_whisper_python()

    repo = Path(a.repo)
    n = len(a.inputs)
    results: list[tuple[str, Path | None, int, str | None, str | None]] = []
    # (item, out_path, chars, engine, error)

    for i, item in enumerate(a.inputs, 1):
        if n > 1:
            print(f"\n=== [{i}/{n}] {item} ===")
        try:
            out_path, chars, engine = process_one(item, repo)
            if a.out and n == 1:
                custom = Path(a.out).expanduser().resolve()
                custom.parent.mkdir(parents=True, exist_ok=True)
                custom.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
                out_path = custom
            print(f"完了: {out_path}")
            print(f"文字数: {chars} / engine={engine}")
            results.append((item, out_path, chars, engine, None))
            if n > 1:
                _yt().notify("文字起こし完了", f"[{i}/{n}] {out_path.stem}")
        except Exception as e:
            print(f"エラー: {e}")
            results.append((item, None, 0, None, str(e)))
            if n > 1:
                _yt().notify("文字起こし失敗", f"[{i}/{n}] {item}")

    if n > 1:
        ok = sum(1 for _, p, *_ in results if p)
        print(f"\n=== 完了サマリー ({ok}/{n} 成功) ===")
        for item, out_path, chars, engine, err in results:
            print(f"  {'OK ' if out_path else 'NG '}{item}")
            if out_path:
                print(f"      → {out_path} ({chars}字 / {engine})")
            if err:
                print(f"      → {err.splitlines()[0]}")

    if all(err for *_, err in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
