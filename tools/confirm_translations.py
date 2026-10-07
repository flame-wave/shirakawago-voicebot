"""今ある自動翻訳の「要確認」の印を、まとめて外す（1回だけ使う道具）。

2026年10月、管理画面に「訳を確かめる」手順を入れたとき、
それまでに自動翻訳した訳はすべて「自動翻訳（要確認）」の印が付いたままだった。
これらは地名の誤りを人の手で直したあとのものなので（運用者の判断）、
印だけを外して「確かめ済み」にする。

  ・訳の文（回答・聞き方）は変えない
  ・「日本語原文」は残す（あとで回答を直したら、訳し直しが要ると分かるように）
  ・訳したあとで日本語の回答が変わっているものは外さない
    （それは確かめ済みにしてはいけない。管理画面の ① に「回答が変わった」と出る）

使い方:
    python tools/confirm_translations.py --dry-run   どうなるかだけ見る
    python tools/confirm_translations.py             外して保存する
"""
import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "admin"))

import faq_excel as X  # noqa: E402

LANGS = ["en", "zh", "ko", "es", "fr"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "tools" / "faq_master.xlsx"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.source)
    book = X.FaqBook(path.read_bytes())
    status = book.translation_status(LANGS)

    done, skipped = 0, []
    for fid, per in status.items():
        for lang, state in per.items():
            if state == "machine":
                book.confirm_translation(fid, lang)   # 文は渡さない＝変えない
                done += 1
            elif state == "changed":
                skipped.append(f"{fid}/{lang}")

    print(f"確かめ済みにする訳: {done} 件")
    if skipped:
        print(f"日本語の回答が変わっているため外さなかった訳: {len(skipped)} 件")
        for s in skipped:
            print("  ・" + s)
    if args.dry_run:
        print("（--dry-run のため保存していません）")
        return
    path.write_bytes(book.to_bytes())
    print(f"保存しました: {path}")


if __name__ == "__main__":
    main()
