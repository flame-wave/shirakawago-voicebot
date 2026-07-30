"""
質問回答集（Excel / Googleスプレッドシート）を faq.json に変換する。

使い方:
    # ローカルのExcelファイルから
    python build_faq.py --source faq_master.xlsx

    # GoogleスプレッドシートのURLから（共有設定を「リンクを知る全員が閲覧可」に）
    python build_faq.py --source "https://docs.google.com/spreadsheets/d/XXXX/edit#gid=0"

    # 出力先を指定
    python build_faq.py --source faq_master.xlsx --out assets/faq.json

Googleスプレッドシートも内部でxlsxとして取得するため、処理は完全に同じ。
"""

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

VALID_CATEGORIES = {
    "bus", "facility", "sightseeing", "food",
    "season", "accessibility", "manner", "other",
}
VALID_LANGS = {"en", "zh", "ko"}
ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
ANSWER_WARN_LEN = 120  # これを超えると読み上げが長すぎる可能性


# ---------------------------------------------------------------- 取得
def to_export_url(url: str) -> str:
    """GoogleスプレッドシートのURLを xlsx ダウンロードURLに変換する。"""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not m:
        raise ValueError("GoogleスプレッドシートのURLとして認識できません: " + url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx"


def load_workbook_bytes(source: str) -> bytes:
    """ローカルパスでもGoogleスプレッドシートURLでも、xlsxのバイト列を返す。"""
    if source.startswith("http://") or source.startswith("https://"):
        import requests  # 必要なときだけ読み込む
        export_url = to_export_url(source)
        print(f"  Googleスプレッドシートを取得中: {export_url}")
        res = requests.get(export_url, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(
                f"取得に失敗しました (HTTP {res.status_code})。"
                "共有設定が「リンクを知っている全員が閲覧可」になっているか確認してください。"
            )
        return res.content
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {path}")
    return path.read_bytes()


# ---------------------------------------------------------------- 変換
def split_lines(cell) -> list:
    """改行区切りのセルを配列にする。全角スペースや空行も整理。"""
    if pd.isna(cell):
        return []
    text = str(cell).replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in text.split("\n") if line.strip()]


def cell_str(cell) -> str:
    if pd.isna(cell):
        return ""
    return str(cell).strip()


def is_true(cell) -> bool:
    return cell_str(cell).upper() in ("TRUE", "1", "○", "有効", "YES")


def build(source: str, assets_dir: Path | None):
    raw = load_workbook_bytes(source)
    book = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype=object)

    if "FAQ" not in book:
        raise RuntimeError("「FAQ」シートが見つかりません。シート名を確認してください。")

    df = book["FAQ"]
    tr = book.get("多言語")

    errors, warnings = [], []
    faqs, seen_ids = [], set()

    for idx, row in df.iterrows():
        line = idx + 2  # ヘッダー行のぶん
        fid = cell_str(row.get("ID"))

        if not fid:
            if all(not cell_str(v) for v in row.values):
                continue  # 完全な空行は無視
            errors.append(f"FAQ {line}行目: IDが空です")
            continue

        if not ID_PATTERN.match(fid):
            errors.append(f"FAQ {line}行目: ID「{fid}」は半角英小文字・数字・_ のみ使えます")
        if fid in seen_ids:
            errors.append(f"FAQ {line}行目: IDが重複しています →「{fid}」")
        seen_ids.add(fid)

        if not is_true(row.get("有効")):
            continue  # 無効行はスキップ（削除せず残せる）

        category = cell_str(row.get("カテゴリ")) or "other"
        if category not in VALID_CATEGORIES:
            errors.append(f"FAQ {line}行目({fid}): カテゴリ「{category}」は未定義です")

        questions = split_lines(row.get("質問例"))
        if not questions:
            errors.append(f"FAQ {line}行目({fid}): 質問例が空です")
        elif len(questions) < 2:
            warnings.append(f"{fid}: 質問例が1つだけです。言い方を増やすと認識しやすくなります")

        answer = cell_str(row.get("回答"))
        if not answer:
            errors.append(f"FAQ {line}行目({fid}): 回答が空です")
        elif len(answer) > ANSWER_WARN_LEN:
            warnings.append(
                f"{fid}: 回答が{len(answer)}字あります。"
                f"読み上げが長くなるため、{ANSWER_WARN_LEN}字程度への短縮を検討してください"
            )

        link = cell_str(row.get("参考リンク"))
        if link and not link.startswith(("http://", "https://")):
            errors.append(f"FAQ {line}行目({fid}): 参考リンクがURLの形式ではありません")

        photo = cell_str(row.get("写真ファイル名"))
        audio = cell_str(row.get("音声ファイル名"))

        if assets_dir:
            if photo and not (assets_dir / "photo" / photo).exists():
                warnings.append(f"{fid}: 写真 {photo} が見つかりません（写真なしで動作します）")
            if audio and not (assets_dir / "audio" / audio).exists():
                warnings.append(f"{fid}: 音声 {audio} が見つかりません（端末音声で読み上げます）")

        faqs.append({
            "id": fid,
            "category": category,
            "questions": questions,
            "answer": answer,
            "audio": audio,
            "photo": photo,
            "link": link,
            "translations": {},
        })

    # ---- 多言語シートの取り込み
    if tr is not None:
        by_id = {f["id"]: f for f in faqs}
        for idx, row in tr.iterrows():
            line = idx + 2
            fid = cell_str(row.get("ID"))
            lang = cell_str(row.get("言語")).lower()
            if not fid and not lang:
                continue
            if fid.startswith("※") or (not lang and not ID_PATTERN.match(fid)):
                continue  # 注釈行などは無視
            if cell_str(row.get("備考")) == "記入例":
                continue  # テンプレートの記入例はスキップ
            if lang not in VALID_LANGS:
                errors.append(f"多言語 {line}行目: 言語「{lang}」は en / zh / ko のいずれかです")
                continue
            if fid not in by_id:
                warnings.append(
                    f"多言語 {line}行目: ID「{fid}」がFAQシートに見つかりません（無効行の可能性）"
                )
                continue
            answer = cell_str(row.get("回答"))
            if not answer:
                errors.append(f"多言語 {line}行目({fid}/{lang}): 回答が空です")
                continue
            by_id[fid]["translations"][lang] = {
                "questions": split_lines(row.get("質問例")),
                "answer": answer,
                "audio": "",
            }

    return faqs, errors, warnings


# ---------------------------------------------------------------- 実行
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    help="Excelファイルのパス、またはGoogleスプレッドシートのURL")
    ap.add_argument("--out", default="faq.json", help="出力先(既定: faq.json)")
    ap.add_argument("--assets", default=None,
                    help="assetsフォルダのパス。指定すると写真・音声の有無を確認します")
    ap.add_argument("--force", action="store_true",
                    help="エラーがあっても書き出す")
    args = ap.parse_args()

    assets_dir = Path(args.assets) if args.assets else None

    print("読み込み中...")
    faqs, errors, warnings = build(args.source, assets_dir)

    print(f"\n読み込み結果: 有効な質問 {len(faqs)} 件")
    n_tr = sum(len(f["translations"]) for f in faqs)
    if n_tr:
        print(f"  多言語の回答: {n_tr} 件")

    if warnings:
        print(f"\n【確認】{len(warnings)} 件")
        for w in warnings:
            print("  ・" + w)

    if errors:
        print(f"\n【エラー】{len(errors)} 件 — 修正が必要です")
        for e in errors:
            print("  ×" + e)
        if not args.force:
            print("\n書き出しを中止しました。上記を直して再実行してください。")
            sys.exit(1)
        print("\n--force が指定されたため、エラーを無視して書き出します。")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    version = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "version": version,          # 端末側が更新の有無を判定するために使う
        "count": len(faqs),
        "faqs": faqs,
    }
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n書き出しました: {out}（版: {version}）")

    if not errors:
        print("問題は見つかりませんでした。")


if __name__ == "__main__":
    main()