"""
タブレットから取り出した質問ログ（question_log.jsonl）を集計する。

取り出し方:
    adb pull /data/data/com.example.shirakawa_bot/app_flutter/question_log.jsonl
    （正確な場所はアプリの職員用画面に表示されます）

使い方:
    python analyze_log.py question_log.jsonl
    python analyze_log.py question_log.jsonl --csv out.csv
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

LANG_LABEL = {"ja": "日本語", "en": "English", "zh": "中文", "ko": "한국어"}


def load(path: Path) -> list:
    entries = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  ! {i}行目を読み飛ばしました（壊れています）")
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", help="question_log.jsonl のパス")
    ap.add_argument("--csv", help="表計算で見るためのCSV出力先")
    ap.add_argument("--top", type=int, default=20, help="上位何件を表示するか")
    args = ap.parse_args()

    path = Path(args.logfile)
    if not path.exists():
        print(f"ファイルが見つかりません: {path}")
        return

    entries = load(path)
    if not entries:
        print("記録がありません")
        return

    total = len(entries)
    matched = [e for e in entries if e.get("faq_id")]
    unmatched = [e for e in entries if not e.get("faq_id")]

    print(f"\n{'=' * 52}")
    print(f"質問ログ集計  ({path.name})")
    print(f"{'=' * 52}")

    times = [e["at"] for e in entries if e.get("at")]
    if times:
        print(f"期間: {min(times)[:16]} 〜 {max(times)[:16]}")
    print(f"質問の総数: {total} 件")
    print(f"回答できた: {len(matched)} 件 ({len(matched) / total * 100:.1f}%)")
    print(f"答えられなかった: {len(unmatched)} 件")

    print(f"\n■ 言語別の利用")
    for lang, n in Counter(e.get("lang", "") for e in entries).most_common():
        label = LANG_LABEL.get(lang, lang)
        print(f"  {label:8} {n:5} 件 ({n / total * 100:5.1f}%)")

    print(f"\n■ 答えられなかった質問（FAQ追加の候補）")
    unmatched_count = Counter(
        e.get("recognized", "").strip() for e in unmatched if e.get("recognized")
    )
    if unmatched_count:
        for text, n in unmatched_count.most_common(args.top):
            print(f"  {n:4} 件  {text}")
    else:
        print("  なし")

    print(f"\n■ よく聞かれた質問")
    for fid, n in Counter(e["faq_id"] for e in matched).most_common(args.top):
        print(f"  {n:4} 件  {fid}")

    print(f"\n■ 分類別")
    for cat, n in Counter(
        e.get("category", "") for e in matched if e.get("category")
    ).most_common():
        print(f"  {cat:14} {n:5} 件")

    # 時間帯別（設置時間の検討材料）
    hours = defaultdict(int)
    for e in entries:
        try:
            hours[datetime.fromisoformat(e["at"]).hour] += 1
        except Exception:
            pass
    if hours:
        print(f"\n■ 時間帯別")
        peak = max(hours.values())
        for h in sorted(hours):
            bar = "█" * max(1, round(hours[h] / peak * 30))
            print(f"  {h:2}時 {hours[h]:4} 件 {bar}")

    # 音声の内訳（どれだけ端末音声で代替されているか）
    voices = Counter(e.get("voice", "") for e in entries)
    if voices:
        print(f"\n■ 読み上げの方法")
        names = {
            "recorded": "用意した音声",
            "synthesized": "端末の音声",
            "failed": "失敗",
        }
        for v, n in voices.most_common():
            print(f"  {names.get(v, v):14} {n:5} 件")

    if args.csv:
        import csv

        out = Path(args.csv)
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["at", "lang", "recognized", "faq_id",
                            "category", "fallback", "voice"],
            )
            writer.writeheader()
            writer.writerows(entries)
        print(f"\nCSVを書き出しました: {out}")
        print("（Excelで開けるようBOM付きUTF-8で保存しています）")

    print()


if __name__ == "__main__":
    main()