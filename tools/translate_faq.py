"""
日本語のFAQを、他の言語へまとめて翻訳して多言語シートに書き込む。

日本語を1件書けば、残りの言語は自動で埋まる状態にするためのツール。

────────────────────────────────────────────────
使い方は2通り。APIキーの有無で選ぶ。

【A】APIを使う（自動）
    set ANTHROPIC_API_KEY=（キー）
    python tools/translate_faq.py --source tools/faq_master.xlsx

【B】APIを使わない（手貼り）
    1) 翻訳を依頼する文面を書き出す
       python tools/translate_faq.py --source tools/faq_master.xlsx --export-prompt prompt.txt
    2) prompt.txt の中身をClaudeなどに貼り、返ってきたJSONを result.json に保存
    3) 取り込む
       python tools/translate_faq.py --source tools/faq_master.xlsx --import-json result.json
────────────────────────────────────────────────

既に翻訳が入っている行は触らない（--overwrite を付けたときだけ上書きする）。
自動翻訳した行は備考に印を付けるので、確認済みのものと区別できる。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font

FONT = "Yu Gothic"
MACHINE_MARK = "自動翻訳（要確認）"

LANG_NAMES = {
    "en": "英語",
    "zh": "中国語（簡体字）",
    "ko": "韓国語",
    "es": "スペイン語",
    "fr": "フランス語",
}

# 翻訳の質を決めるのはこの指示。特に質問例の書き方が重要。
INSTRUCTIONS = """\
あなたは観光案内の翻訳者です。日本の白川郷（世界遺産の合掌造り集落）の
観光案内所に置く音声案内システムの、質問回答集を翻訳します。

各項目について、次の2つを作ってください。

1. answer（回答文）
   - 観光客に読み上げられる案内文です。丁寧で簡潔な口語にしてください。
   - 数字は読み上げやすい表記にしてください。
   - 料金・時間・条件（例「小学生は半額」「当日のみ」）は絶対に省略・要約しないでください。
     条件を落とすと料金トラブルの原因になります。
   - 施設名・地名は、その言語圏の観光客が地図と照合できる表記にしてください。

2. questions（想定される聞かれ方）
   - その言語の観光客が実際に口にしそうな言い方を4〜6個。
   - 【重要】1行が1つの言い方です。行内の半角スペースは「かつ」を意味します。
     例「trash bin」は trash と bin の両方が含まれるときだけ一致します。
   - そのため、一般的すぎる語（where, time, どこ 相当の語）だけの行は作らないでください。
     内容を表す語を必ず含めてください。
   - 2文字未満の語だけの行は作らないでください（短すぎて判定に使えません）。
   - 韓国語は活用形が一致しないことがあるため、
     「맡기」と「맡길」のように語幹の異なる形を複数入れてください。
   - 英語は英式・米式の綴り（tyre / tire）の両方を入れてください。

出力は次の形式のJSONのみ。説明や前置きは一切書かないでください。

{
  "項目のID": {
    "言語コード": {
      "questions": ["言い方1", "言い方2"],
      "answer": "回答文"
    }
  }
}
"""


def cell(ws, row, col):
    v = ws.cell(row=row, column=col).value
    return "" if v is None else str(v).strip()


def read_sheets(path: Path):
    wb = load_workbook(path)
    if "FAQ" not in wb.sheetnames or "多言語" not in wb.sheetnames:
        raise RuntimeError("「FAQ」「多言語」シートが必要です")
    return wb, wb["FAQ"], wb["多言語"]


def collect_japanese(fs):
    """FAQシートから、有効な日本語の項目を読む。"""
    header = {cell(fs, 1, c): c for c in range(1, fs.max_column + 1)}
    need = ["ID", "質問例", "回答", "有効"]
    for n in need:
        if n not in header:
            raise RuntimeError(f"FAQシートに「{n}」列がありません")

    items = {}
    for r in range(2, fs.max_row + 1):
        fid = cell(fs, r, header["ID"])
        if not fid:
            continue
        if cell(fs, r, header["有効"]).upper() not in ("TRUE", "1", "○", "YES", ""):
            continue
        items[fid] = {
            "questions": [x.strip() for x in cell(fs, r, header["質問例"]).splitlines() if x.strip()],
            "answer": cell(fs, r, header["回答"]),
        }
    return items


def find_missing(ls, japanese, langs, overwrite):
    """(ID, 言語) のうち、翻訳が未記入のものを返す。行番号も持つ。"""
    rows = {}
    for r in range(2, ls.max_row + 1):
        fid, lang = cell(ls, r, 1), cell(ls, r, 2).lower()
        if not fid or lang not in langs:
            continue
        rows[(fid, lang)] = r

    missing = []
    for fid in japanese:
        for lang in langs:
            r = rows.get((fid, lang))
            if r is None:
                missing.append((fid, lang, None))       # 行そのものが無い
            elif overwrite or not cell(ls, r, 4):
                missing.append((fid, lang, r))
    return missing, rows


def build_prompt(japanese, missing):
    """翻訳を依頼する文面を組み立てる。"""
    by_id = {}
    for fid, lang, _ in missing:
        by_id.setdefault(fid, set()).add(lang)

    payload = {}
    for fid, langs in by_id.items():
        payload[fid] = {
            "日本語の質問例": japanese[fid]["questions"],
            "日本語の回答": japanese[fid]["answer"],
            "翻訳する言語": sorted(langs),
        }

    langs_used = sorted({l for s in by_id.values() for l in s})
    names = "、".join(f"{l}（{LANG_NAMES.get(l, l)}）" for l in langs_used)

    return (
        INSTRUCTIONS
        + f"\n翻訳する言語コード: {names}\n\n"
        + "以下が翻訳対象です。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def parse_result(text):
    """返ってきた文字列からJSONを取り出す。前後に説明が付いていても拾う。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("JSONが見つかりません")
    return json.loads(text[start:end + 1])


def call_api(prompt):
    """APIで翻訳する。SDKが無い/キーが無い場合は分かるように止める。"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "環境変数 ANTHROPIC_API_KEY が設定されていません。\n"
            "APIを使わない場合は --export-prompt を使ってください。"
        )
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic パッケージがありません。\n"
            "  pip install anthropic\n"
            "を実行するか、--export-prompt を使ってください。"
        )

    client = anthropic.Anthropic(api_key=key)
    res = client.messages.create(
        model="claude-opus-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in res.content if getattr(b, "type", "") == "text")


def write_back(wb, ls, path, result, japanese, rows, langs):
    """翻訳結果を多言語シートに書き込む。無い行は末尾に足す。"""
    written, skipped = 0, []
    next_row = ls.max_row + 1

    for fid, per_lang in result.items():
        if fid not in japanese:
            skipped.append(f"{fid}: FAQシートに無いIDです")
            continue
        for lang, data in per_lang.items():
            lang = lang.lower()
            if lang not in langs:
                skipped.append(f"{fid}/{lang}: 対象外の言語です")
                continue
            answer = (data.get("answer") or "").strip()
            questions = [q.strip() for q in (data.get("questions") or []) if q.strip()]
            if not answer or not questions:
                skipped.append(f"{fid}/{lang}: 回答か質問例が空でした")
                continue

            r = rows.get((fid, lang))
            if r is None:
                r = next_row
                next_row += 1
                ls.cell(row=r, column=1, value=fid)
                ls.cell(row=r, column=2, value=lang)
                rows[(fid, lang)] = r

            ls.cell(row=r, column=3, value="\n".join(questions))
            ls.cell(row=r, column=4, value=answer)
            ls.cell(row=r, column=5, value=MACHINE_MARK)
            for c in range(1, 6):
                cc = ls.cell(row=r, column=c)
                cc.font = Font(name=FONT, size=10)
                cc.alignment = Alignment(vertical="top", wrap_text=(c in (3, 4, 5)))
            written += 1

    wb.save(path)
    return written, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="faq_master.xlsx のパス")
    ap.add_argument("--langs", default="en,zh,ko,es,fr", help="翻訳する言語（カンマ区切り）")
    ap.add_argument("--overwrite", action="store_true", help="既存の翻訳も置き換える")
    ap.add_argument("--export-prompt", help="翻訳を依頼する文面を書き出す先")
    ap.add_argument("--import-json", help="返ってきたJSONを取り込む")
    args = ap.parse_args()

    path = Path(args.source)
    langs = [x.strip().lower() for x in args.langs.split(",") if x.strip()]
    wb, fs, ls = read_sheets(path)
    japanese = collect_japanese(fs)
    print(f"日本語の項目: {len(japanese)} 件")

    # ---- 取り込みだけ行う場合
    if args.import_json:
        result = parse_result(Path(args.import_json).read_text(encoding="utf-8"))
        _, rows = find_missing(ls, japanese, langs, True)
        written, skipped = write_back(wb, ls, path, result, japanese, rows, langs)
        print(f"書き込み: {written} 件")
        for s in skipped:
            print("  ・" + s)
        print("\n備考欄に「自動翻訳（要確認）」と入ります。確認したら消してください。")
        return

    missing, rows = find_missing(ls, japanese, langs, args.overwrite)
    if not missing:
        print("未翻訳はありません。")
        return

    by_lang = {}
    for _, lang, _ in missing:
        by_lang[lang] = by_lang.get(lang, 0) + 1
    print("未翻訳: " + "、".join(f"{l} {n}件" for l, n in sorted(by_lang.items())))

    prompt = build_prompt(japanese, missing)

    # ---- 文面を書き出すだけ
    if args.export_prompt:
        out = Path(args.export_prompt)
        out.write_text(prompt, encoding="utf-8")
        print(f"\n翻訳を依頼する文面を書き出しました: {out}")
        print("この中身をClaudeなどに貼り、返ってきたJSONを保存してから:")
        print(f"  python tools/translate_faq.py --source {args.source} --import-json 保存先.json")
        return

    # ---- APIで翻訳
    print("翻訳中...")
    try:
        text = call_api(prompt)
    except RuntimeError as e:
        print("\n" + str(e))
        sys.exit(1)

    result = parse_result(text)
    written, skipped = write_back(wb, ls, path, result, japanese, rows, langs)
    print(f"書き込み: {written} 件")
    for s in skipped:
        print("  ・" + s)
    print("\n備考欄に「自動翻訳（要確認）」と入ります。確認したら消してください。")


if __name__ == "__main__":
    main()
