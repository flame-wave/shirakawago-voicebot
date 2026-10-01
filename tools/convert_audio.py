"""用意した音声（WAV）をmp3に変換する。

VOICEVOXが書き出すWAVは1件あたり0.5MBほどあり、73件で37MBになる。
観光客のスマートフォンは、回答のたびにこれを読み込むことになる。
mp3にすると10分の1ほどになり、聞いた感じはほとんど変わらない。

【やること】
1. assets/audio/ の .wav を .mp3 に変換する
2. Excelの「音声ファイル名」列の拡張子を .mp3 に書き換える
3. 元の .wav を消す（--keep を付ければ残す）

音声はいつでも作り直せる（tools/make_voice.py）ので、消しても取り返しがつく。

使い方:
    python tools/convert_audio.py --dry-run    どうなるかだけ見る
    python tools/convert_audio.py              変換する
    python tools/convert_audio.py --keep       元のWAVも残す
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "assets" / "audio"
BOOK = ROOT / "tools" / "faq_master.xlsx"

# 案内の読み上げなので、音楽ほどの質は要らない。
# 64kbps・モノラル・24kHz で、聞いた感じはWAVとほとんど変わらない。
BITRATE = "64k"
CHANNELS = "1"
RATE = "24000"


def find_ffmpeg() -> str:
    """ffmpeg を探す。PATHに無ければ winget の置き場も見る。"""
    found = shutil.which("ffmpeg")
    if found:
        return found
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if base.is_dir():
        for path in base.rglob("ffmpeg.exe"):
            return str(path)
    return ""


def convert(ffmpeg: str, src: Path, dst: Path) -> bool:
    result = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
         "-codec:a", "libmp3lame", "-b:a", BITRATE,
         "-ac", CHANNELS, "-ar", RATE, str(dst)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        print("  × " + src.name + ": " + (result.stderr or "").strip()[:120])
        return False
    return True


def update_book(dry_run: bool) -> int:
    """Excelの「音声ファイル名」列を .mp3 に書き換える。"""
    from openpyxl import load_workbook

    wb = load_workbook(BOOK)
    ws = wb["FAQ"]
    header = {str(ws.cell(1, c).value).strip(): c
              for c in range(1, ws.max_column + 1) if ws.cell(1, c).value}
    col = header.get("音声ファイル名")
    if col is None:
        print("FAQシートに「音声ファイル名」列がありません")
        return 0

    changed = 0
    for r in range(2, ws.max_row + 1):
        value = ws.cell(r, col).value
        name = str(value).strip() if value else ""
        if name.lower().endswith(".wav"):
            if not dry_run:
                ws.cell(r, col).value = name[:-4] + ".mp3"
            changed += 1
    if changed and not dry_run:
        wb.save(BOOK)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="どうなるかだけ見る")
    ap.add_argument("--keep", action="store_true", help="元のWAVも残す")
    args = ap.parse_args()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ffmpeg が見つかりません。\n"
              "  winget install --id Gyan.FFmpeg -e で入れてください。")
        sys.exit(1)

    # 直下と、音声セットのフォルダの両方を見る
    files = sorted(AUDIO.glob("*.wav")) + sorted(AUDIO.glob("*/*.wav"))
    if not files:
        print("変換するWAVがありません。")
        return

    before = sum(f.stat().st_size for f in files)
    print(f"変換するもの: {len(files)} 件 / {before / 1048576:.1f} MB")
    if args.dry_run:
        print("（--dry-run のため、変換も書き換えもしません）")
        print(f"Excelの書き換え対象: {update_book(True)} 行")
        return

    made, failed = 0, 0
    for i, src in enumerate(files, start=1):
        dst = src.with_suffix(".mp3")
        if convert(ffmpeg, src, dst):
            made += 1
        else:
            failed += 1
        if i % 20 == 0:
            print(f"  {i} / {len(files)} 件")

    after = sum(f.stat().st_size for f in AUDIO.glob("*.mp3"))
    after += sum(f.stat().st_size for f in AUDIO.glob("*/*.mp3"))
    print(f"\n変換できた: {made} 件" + (f" / 失敗 {failed} 件" if failed else ""))
    print(f"大きさ: {before / 1048576:.1f} MB → {after / 1048576:.1f} MB"
          f"（{after / before * 100:.0f}%）")

    rows = update_book(False)
    print(f"Excelの「音声ファイル名」を書き換え: {rows} 行")

    if args.keep:
        print("\n元のWAVはそのまま残してあります（--keep）。")
    elif failed:
        print("\n失敗したものがあるため、元のWAVは残しました。")
    else:
        for f in files:
            f.unlink()
        print(f"\n元のWAV {len(files)} 件を消しました"
              "（tools/make_voice.py でいつでも作り直せます）。")

    print("\n次にやること:")
    print("  python tools/build_faq.py --source tools/faq_master.xlsx "
          "--out assets/faq.json --assets assets")


if __name__ == "__main__":
    main()
