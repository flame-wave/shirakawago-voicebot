"""
FAQ検索の取りこぼしを測る。

観光客が実際に言いそうな言い方（questions.jsonl）を1件ずつ検索にかけ、
「正しく答えられた」「答えられなかった」「別の回答を返した」を数える。

    python tools/eval/run_eval.py
    python tools/eval/run_eval.py --faq assets/faq.json --out report.txt

検索の判定には demo/faq_engine.py を使う。
これは実機・Webアプリと同じ判定をPythonで再現したもの。

【見方】
  正解   … 期待した回答を返せた
  無回答 … 該当なしとして職員へ回した（取りこぼし）
  誤答   … 別の質問の回答を返した ← 最も悪い。無回答より害がある

期待を空（[]）にした行は「職員へ回すのが正解」の質問。
ここで回答を返してしまうものが誤答になる。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "demo"))

import faq_engine

# 日本語を確実に出せるようにする（Windowsの既定のままだと文字化けするため）
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_cases(path: Path):
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        cases.append({
            "text": row["text"],
            "expect": row.get("expect", []),
            "lang": row.get("lang", "ja"),
            "place": row.get("place"),
        })
    return cases


def run(faqs, cases, synonyms, place=None):
    results = []
    for case in cases:
        # 質問ごとに場所を指定できる（指定が無ければ全体の設定に従う）
        spot = case.get("place") or place
        hit = faq_engine.search(faqs, case["text"], case["lang"], synonyms, spot)
        got = hit.faq["id"] if hit.hit else None

        if case["expect"]:
            if got is None:
                verdict = "無回答"
            elif got in case["expect"]:
                verdict = "正解"
            else:
                verdict = "誤答"
        else:
            verdict = "正解" if got is None else "誤答"

        results.append({**case, "got": got, "verdict": verdict, "score": hit.score,
                        "matched_example": hit.matched_example})
    return results


def report(results):
    lines = []
    in_scope = [r for r in results if r["expect"]]
    out_scope = [r for r in results if not r["expect"]]

    def tally(rows, title):
        if not rows:
            return
        n = len(rows)
        ok = sum(1 for r in rows if r["verdict"] == "正解")
        miss = sum(1 for r in rows if r["verdict"] == "無回答")
        wrong = sum(1 for r in rows if r["verdict"] == "誤答")
        lines.append(f"\n【{title}】{n} 件")
        lines.append(f"  正解   {ok:3d} 件（{ok / n * 100:5.1f}%）")
        if miss:
            lines.append(f"  無回答 {miss:3d} 件（{miss / n * 100:5.1f}%）… 職員へ回った分")
        lines.append(f"  誤答   {wrong:3d} 件（{wrong / n * 100:5.1f}%）")

    tally(results, "全体")
    tally(in_scope, "回答できるはずの質問")
    tally(out_scope, "職員へ回すのが正解の質問")

    bad = [r for r in results if r["verdict"] != "正解"]
    if bad:
        lines.append(f"\n【正解でなかったもの】{len(bad)} 件")
        for r in sorted(bad, key=lambda r: r["verdict"]):
            want = "／".join(r["expect"]) if r["expect"] else "（職員へ）"
            got = r["got"] or "（職員へ）"
            lines.append(f"  {r['verdict']}: 「{r['text']}」")
            lines.append(f"      期待: {want}  → 実際: {got}")
            if r["verdict"] == "誤答" and r["matched_example"]:
                lines.append(f"      当たった質問例:「{r['matched_example']}」")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--faq", default=str(ROOT / "assets" / "faq.json"),
                    help="検索に使う faq.json")
    ap.add_argument("--cases", default=str(Path(__file__).with_name("questions.jsonl")),
                    help="評価用の質問集")
    ap.add_argument("--out", help="結果の書き出し先（任意）")
    ap.add_argument("--no-synonyms", action="store_true",
                    help="言い換え表を使わずに測る（改善前との比較用）")
    ap.add_argument("--place", default=None,
                    help="いまいる案内所（例: バスターミナル）。指定しないと共通の回答だけを見る")
    args = ap.parse_args()

    faqs, version = faq_engine.load_faqs(args.faq)
    synonyms = {} if args.no_synonyms else faq_engine.load_synonyms(args.faq)
    cases = load_cases(Path(args.cases))

    n_syn = sum(len(v) for v in synonyms.values())
    print(f"質問回答集: {len(faqs)} 件（版: {version}）")
    print(f"言い換え: {n_syn} 語" + ("（使わずに測定）" if args.no_synonyms else ""))
    print(f"評価用の質問: {len(cases)} 件")
    print(f"現在地: {args.place or '（指定なし＝共通のみ）'}")

    results = run(faqs, cases, synonyms, args.place)
    text = report(results)
    print(text)

    if args.out:
        Path(args.out).write_text(
            f"質問回答集: {len(faqs)} 件（版: {version}）\n{text}\n", encoding="utf-8"
        )
        print(f"\n書き出しました: {args.out}")


if __name__ == "__main__":
    main()
