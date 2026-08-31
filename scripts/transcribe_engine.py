#!/usr/bin/env python3
"""音声 → Whisper 転写エンジン（GPU単一パス／CPUフォールバック共用のcanonical実装）。

premiere-srt-fast-template の whisper_to_srt.py から、SRT組み立て・XML同期・
LLM改行用のword出力など /srt-fast 専用機能を除いた「転写だけ」を切り出したもの。
run_whisper() が唯一のエントリポイントで、text/word_timestamps付きの
segmentsリストを返す。

usage（ライブラリとして import して使う。単体CLIエントリは持たない）:
    import transcribe_engine as engine
    segs = engine.run_whisper("audio.wav")
"""
from __future__ import annotations

import json
import os
import platform
import re
import sys
from pathlib import Path

# 置換は長い文字列から先に適用される（部分一致の衝突を防ぐ）。
# チャンネル固有の固有名詞・言い間違い修正が必要なら
# config/corrections.local.json（このリポジトリ直下・gitignore対象）に
# {"誤認識文字列": "正規表記"} 形式で追記すれば自動反映される。
CORRECTIONS: dict[str, str] = {
    # 口語→書き言葉（文字数削減。汎用ルールとして既定で有効）
    "っていう": "という",
}
REGEX_CORRECTIONS: list[tuple[re.Pattern, str]] = []


def _load_local_corrections() -> None:
    """config/corrections.local.json があれば CORRECTIONS にマージする（無ければ何もしない）"""
    path = Path(__file__).resolve().parent.parent / "config" / "corrections.local.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if isinstance(data, dict):
        CORRECTIONS.update({
            str(k): str(v) for k, v in data.items() if not str(k).startswith("_")
        })


_load_local_corrections()

# フィラー削除パターン（正規表現）。否定先読み (?!...) で複合語の誤削除を防止
FILLER_PATTERNS: list[str] = [
    r'(?<!まあ)まあ(?!まあ)',          # 「まあまあ」（程度表現）は保護
    r'え[ーえっ]*と',                  # えっと、ええと、えーと
    r'もう(?![少一すい終])',            # もう少し、もう一度、もうすぐ等は保護
    r'はい(?![るっり])',               # はいる等は保護
]


def _add_number_commas(text: str) -> str:
    """4桁以上の数字にカンマを挿入（1000→1,000、10000→10,000）。"""
    def fmt(m: re.Match) -> str:
        n = m.group(0)
        result = []
        for i, c in enumerate(reversed(n)):
            if i > 0 and i % 3 == 0:
                result.append(",")
            result.append(c)
        return "".join(reversed(result))
    return re.sub(r"\d{4,}(?!つ|本目|回目|年|月|日|番|号|階|枚|個)", fmt, text)


_KANJI_NUM_MAP = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
                  "六": "6", "七": "7", "八": "8", "九": "9"}
_KANJI_COUNTER_PAT = re.compile(
    r"([一二三四五六七八九])(番|個|枚|回|本|台|冊|件|倍|段|列|杯|着|曲|位|種|組)"
)


def _convert_kanji_numbers(text: str) -> str:
    """漢数字（一〜九）＋量詞を算用数字に変換。"""
    return _KANJI_COUNTER_PAT.sub(lambda m: _KANJI_NUM_MAP[m.group(1)] + m.group(2), text)


def apply_corrections(text: str) -> str:
    for wrong in sorted(CORRECTIONS, key=len, reverse=True):
        text = text.replace(wrong, CORRECTIONS[wrong])
    for pattern, repl in REGEX_CORRECTIONS:
        text = pattern.sub(repl, text)
    text = _convert_kanji_numbers(text)
    text = _add_number_commas(text)
    return text


def remove_fillers(text: str) -> str:
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, "", text)
    text = text.replace("?", "").replace("？", "")
    text = re.sub(r"^[、,\s]+", "", text)
    text = re.sub(r"[、,]{2,}", "、", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# ── Whisper ──────────────────────────────────────────────────────────────────

MLX_MODEL = os.environ.get("SRT_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")


def run_whisper(audio_path: str, cpu_threads: int = 0) -> list[dict]:
    """Whisperを実行してセグメントリストを返す（word_timestamps含む）。

    Apple Silicon では mlx-whisper (GPU・large-v3-turbo) を既定に使う。
    SRT_WHISPER_ENGINE=cpu で従来エンジン強制、SRT_WHISPER_MODEL でmlxモデル差し替え。
    mlx-whisper 未導入・実行失敗時は faster-whisper (CPU) に自動フォールバック。

    音声のスプライス（無音カット等の接続点）付近で Whisper が同じフレーズを
    繰り返す「反復ハルシネーション」を起こすことがあるため、返す前に
    collapse_hallucinated_repeats() で圧縮する。
    """
    return collapse_hallucinated_repeats(_run_whisper_dispatch(audio_path, cpu_threads))


def _run_whisper_dispatch(audio_path: str, cpu_threads: int = 0) -> list[dict]:
    if platform.system() == "Darwin" and os.environ.get("SRT_WHISPER_ENGINE", "mlx") != "cpu":
        try:
            return _run_whisper_mlx(audio_path, cpu_threads)
        except ImportError:
            print("mlx-whisper 未導入 → faster-whisper (CPU) で続行。"
                  "高速化: pip3 install --break-system-packages mlx-whisper")
        except Exception:
            import traceback
            traceback.print_exc()
            print("mlx-whisper 失敗 → faster-whisper (CPU) にフォールバック")
    return _run_whisper_faster(audio_path, cpu_threads)


# 反復ハルシネーション圧縮の対象は MIN_REPEAT_CHARS 文字以上の完全一致フレーズのみ。
# 「本当に本当に」「そうそう」のような話者本人による短い自然な反復（実測: 3〜4字単位）を
# 誤って圧縮しないための下限（無音カットのスプライス直後に起きる反復ハルシネーションは
# 実測で1節まるごと=10字超の単位で起きるため、この閾値なら両者を判別できる）。
MIN_REPEAT_CHARS = 6
MAX_REPEAT_UNIT_WORDS = 30  # 探索する繰り返しユニットの最大語数（性能上限）


def _dedupe_repeated_words(words: list[dict]) -> tuple[list[dict], int]:
    """words（フラットな単語列）から直後に繰り返される同一フレーズを検出し、
    最後の出現だけを残して圧縮する。戻り値は (圧縮後words, 削除した単語数)。

    ハルシネーション中も Whisper 内部時計は実時間を刻み続けるため、最後の
    出現の時刻が「実際に音声再生がそこまで進んだ位置」に最も近い。よって
    先頭〜直前の出現ではなく最後の出現を残す。
    """
    n = len(words)
    texts = [w["word"] for w in words]
    result: list[dict] = []
    removed = 0
    i = 0
    while i < n:
        best_L = 0
        max_L = min(MAX_REPEAT_UNIT_WORDS, (n - i) // 2)
        for L in range(1, max_L + 1):
            unit = "".join(texts[i:i + L])
            if len(unit) < MIN_REPEAT_CHARS:
                continue
            if unit == "".join(texts[i + L:i + 2 * L]):
                best_L = L  # より長い一致を優先して更新し続ける
        if best_L:
            unit = "".join(texts[i:i + best_L])
            reps = 2
            while "".join(texts[i + reps * best_L:i + (reps + 1) * best_L]) == unit:
                reps += 1
            keep_start = i + (reps - 1) * best_L
            result.extend(words[keep_start:keep_start + best_L])
            removed += (reps - 1) * best_L
            i += reps * best_L
        else:
            result.append(words[i])
            i += 1
    return result, removed


def collapse_hallucinated_repeats(seg_list: list[dict]) -> list[dict]:
    """seg_list 全体（segment境界をまたぐ反復も含む）から反復ハルシネーションを圧縮する。
    words を持たないセグメントはそのまま素通しする。"""
    for si, seg in enumerate(seg_list):
        for w in seg.get("words", []):
            w["_seg"] = si

    flat_words = [w for seg in seg_list for w in seg.get("words", [])]
    if not flat_words:
        return seg_list

    # 圧縮すると新たに隣接する反復が現れることがある（多層の反復ハルシネーション）
    # ため、これ以上減らなくなるまで繰り返す。判定基準は変えていないので安全側。
    deduped = flat_words
    total_removed = 0
    while True:
        deduped, removed = _dedupe_repeated_words(deduped)
        total_removed += removed
        if removed == 0:
            break

    if total_removed == 0:
        for w in flat_words:
            w.pop("_seg", None)
        return seg_list

    print(f"反復ハルシネーション検出: {total_removed}語を圧縮")

    kept_by_seg: dict[int, list[dict]] = {}
    for w in deduped:
        kept_by_seg.setdefault(w.pop("_seg"), []).append(w)

    new_segs = []
    for si, seg in enumerate(seg_list):
        kept = kept_by_seg.get(si, [])
        if not kept:
            continue
        new_seg = dict(seg)
        new_seg["start"] = kept[0]["start"]
        new_seg["end"] = kept[-1]["end"]
        new_seg["text"] = "".join(w["word"] for w in kept)
        new_seg["words"] = kept
        new_segs.append(new_seg)
    return new_segs


def _run_whisper_mlx(audio_path: str, cpu_threads: int = 0) -> list[dict]:
    """mlx-whisper (Apple GPU) 経路。出力スキーマ・補正処理はCPU経路と完全一致。

    mlx は VAD を持たず、長い無音明けの短い発話を落とすことがある（実測で確認）。
    そのため転写後にタイムラインの未カバー区間だけを CPU+VAD で補完転写する
    （_rescue_gaps）。字幕用途のカバレッジを baseline 同等に保つための必須工程。
    """
    import mlx_whisper  # 未導入なら ImportError → フォールバック

    print(f"mlx-whisper {MLX_MODEL} (Apple GPU) 転写中: {audio_path}")
    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=MLX_MODEL,
        language="ja",
        word_timestamps=True,
        temperature=0.0,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        hallucination_silence_threshold=2.0,
    )

    seg_list = []
    for seg in result["segments"]:
        raw_text = apply_corrections(seg["text"].strip())
        clean_text = remove_fillers(raw_text)
        if not clean_text:
            continue

        words = []
        for w in seg.get("words", []):
            word_raw = apply_corrections(w["word"].strip())
            word_clean = remove_fillers(word_raw)
            if word_clean:
                words.append({
                    "word": word_clean,
                    "start": w["start"],
                    "end": w["end"],
                })

        seg_list.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": clean_text,
            "words": words,
        })

    seg_list = _rescue_gaps(audio_path, seg_list, cpu_threads)

    print(f"Whisperセグメント数: {len(seg_list)}")
    return seg_list


GAP_RESCUE_MIN_S = 1.5   # 空白警告閾値
GAP_RESCUE_MARGIN_S = 0.25
GAP_RESCUE_SPACER_S = 2.0  # 連結時の無音スペーサ（VADに区間境界を跨がせない）
GAP_RESCUE_SR = 16000


def _rescue_gaps(audio_path: str, seg_list: list[dict], cpu_threads: int = 0) -> list[dict]:
    """mlx転写の未カバー区間（無音扱いされた区間）だけを CPU+VAD で補完転写する。

    大半の空白は真の無音だが、無音明けの短い接続句が落ちるケースがある（実測）。
    Whisperは音声長に関わらず30秒窓単位で推論するため、区間を1本ずつ転写すると
    区間数×窓コストで長尺動画が破綻する。→ 全区間を無音スペーサ入りで1本の
    音声に連結し、CPU+VADで**1回だけ**転写してから元のタイムラインへ写像する。
    """
    import subprocess
    import tempfile
    import wave

    try:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip())
    except Exception:
        dur = float(seg_list[-1]["end"]) if seg_list else 0.0

    gaps = []
    prev = 0.0
    for s in seg_list:
        if s["start"] - prev >= GAP_RESCUE_MIN_S:
            gaps.append((float(prev), float(s["start"])))
        prev = max(prev, s["end"])
    if dur - prev >= GAP_RESCUE_MIN_S:
        gaps.append((float(prev), dur))
    if not gaps:
        return seg_list

    print(f"gap補完: {len(gaps)}区間を連結してCPU Whisper(VAD付き)で再転写 "
          f"{[(round(float(a), 1), round(float(b), 1)) for a, b in gaps]}")

    # 各gap（±マージン）を s16le/16k/mono で切り出し、無音スペーサを挟んで連結
    spacer = b"\x00\x00" * int(GAP_RESCUE_SPACER_S * GAP_RESCUE_SR)
    slices = []   # (concat開始秒, 元音声開始秒, スライス長秒)
    pcm_parts = []
    concat_pos = 0.0
    for g0, g1 in gaps:
        s0 = max(0.0, g0 - GAP_RESCUE_MARGIN_S)
        length = g1 - s0 + GAP_RESCUE_MARGIN_S
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(s0), "-t", str(length),
             "-i", audio_path, "-f", "s16le", "-acodec", "pcm_s16le",
             "-ac", "1", "-ar", str(GAP_RESCUE_SR), "-"],
            capture_output=True, timeout=120, check=True,
        )
        pcm = r.stdout
        slices.append((concat_pos, s0, len(pcm) / 2 / GAP_RESCUE_SR))
        pcm_parts.append(pcm)
        pcm_parts.append(spacer)
        concat_pos += len(pcm) / 2 / GAP_RESCUE_SR + GAP_RESCUE_SPACER_S

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(GAP_RESCUE_SR)
            wf.writeframes(b"".join(pcm_parts))

        model = _fw_load_model(cpu_threads)
        # 30秒窓の中で複数スライスが1セグメントに融合することがあるため、
        # セグメント単位ではなく語タイムスタンプ単位でスライスへ写像し、
        # スライスごとにセグメントを組み直す。
        words_by_slice = {}
        for seg in _fw_transcribe(model, tmp):
            for w in seg["words"]:
                mid_local = (w["start"] + w["end"]) / 2
                for k, (c0, s0, slen) in enumerate(slices):
                    if c0 <= mid_local < c0 + slen:
                        g0, g1 = gaps[k]
                        shift = s0 - c0
                        if g0 <= mid_local + shift < g1:  # マージン由来の重複は捨てる
                            words_by_slice.setdefault(k, []).append({
                                "word": w["word"],
                                "start": w["start"] + shift,
                                "end": w["end"] + shift,
                            })
                        break
        rescued = []
        for k, words in sorted(words_by_slice.items()):
            rescued.append({
                "start": words[0]["start"],
                "end": words[-1]["end"],
                "text": "".join(w["word"] for w in words),
                "words": words,
            })
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    if rescued:
        print(f"gap補完: {len(rescued)}セグメント回復 "
              f"{[s['text'][:15] for s in rescued]}")
        seg_list = sorted(seg_list + rescued, key=lambda s: s["start"])
    return seg_list


def _fw_load_model(cpu_threads: int = 0):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("エラー: faster-whisper が見つかりません。")
        print("インストール: pip install faster-whisper")
        sys.exit(1)

    if platform.system() == "Darwin":
        device, compute_type = "cpu", "int8"
    else:
        device, compute_type = "auto", "auto"

    print(f"Whisper large-v3 を読み込み中... (device={device})")
    return WhisperModel("large-v3", device=device, compute_type=compute_type,
                        cpu_threads=cpu_threads)


def _run_whisper_faster(audio_path: str, cpu_threads: int = 0) -> list[dict]:
    """faster-whisper (CPU) 経路。"""
    model = _fw_load_model(cpu_threads)
    print(f"文字起こし中: {audio_path}")
    seg_list = _fw_transcribe(model, audio_path)
    print(f"Whisperセグメント数: {len(seg_list)}")
    return seg_list


def _fw_transcribe(model, audio_path: str) -> list[dict]:
    # beam_size=1 (greedy), best_of=1, VAD しきい値緩め。
    # large-v3 を維持しつつ推論コストを削減して高速化
    segments, _ = model.transcribe(
        audio_path,
        language="ja",
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={
            "threshold": 0.45,
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,
        },
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        hallucination_silence_threshold=2.0,
    )

    seg_list = []
    for seg in segments:
        raw_text = apply_corrections(seg.text.strip())
        clean_text = remove_fillers(raw_text)
        if not clean_text:
            continue

        words = []
        if seg.words:
            for w in seg.words:
                word_raw = apply_corrections(w.word.strip())
                word_clean = remove_fillers(word_raw)
                if word_clean:
                    words.append({
                        "word": word_clean,
                        "start": w.start,
                        "end": w.end,
                    })

        seg_list.append({
            "start": seg.start,
            "end": seg.end,
            "text": clean_text,
            "words": words,
        })

    return seg_list
