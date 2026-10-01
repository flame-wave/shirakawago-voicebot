"""「参考資料」シートを、質問回答集の内容から組み立てる。

【なぜ質問回答集と別に持つのか】
質問回答集は「この質問にはこう答える」という形なので、
聞かれ方が登録した言い方と離れていると当たらない。
参考資料は、質問の内容にかかわらず毎回そのままAIへ渡す。
「この村について何が分かっているか」の一覧をAIが常に持っている状態になる。

【文章を書き換えない】
回答文はそのまま並べる。要約すると「小学生は半額」のような条件が落ちて、
そこだけを読んだAIが条件なしで答えてしまう。

【案内所ごとに違う回答は入れない】
ATMやロッカーは案内所ごとに答えが違う。全部を毎回渡すと、
離れた案内所の答えを混ぜて案内してしまう。
「この話題は案内所によって違う」とだけ伝え、中身は検索で選ばれたものに任せる。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "tools/faq_master.xlsx"
SHEET = "参考資料"

# 分類の表示名。AIが話題ごとにまとまって読めるようにする。
CATEGORY_LABEL = {
    "bus": "交通・バス",
    "facility": "施設・設備",
    "sightseeing": "見どころ・観光",
    "manner": "見学のマナー・注意",
    "food": "食事",
    "season": "季節・天候",
    "accessibility": "車椅子・バリアフリー",
    "other": "その他",
}
ORDER = ["sightseeing", "bus", "facility", "food", "season",
         "accessibility", "manner", "other"]

# この見出しで始まる行は、作り直すたびに入れ替える。
# 職員が手で足した行は残す。
PREFIX = "【質問回答集より】"


def main():
    faq = json.loads((ROOT / "assets/faq.json").read_text(encoding="utf-8"))
    items = faq["faqs"]

    common = [f for f in items if (f.get("place") or "共通") == "共通"]
    by_place = [f for f in items if (f.get("place") or "共通") != "共通"]

    # ---- 分類ごとにまとめる（回答文はそのまま）
    groups = {}
    for f in common:
        groups.setdefault(f.get("category") or "other", []).append(f)

    rows = []
    for key in ORDER:
        if key not in groups:
            continue
        label = CATEGORY_LABEL.get(key, key)
        body = "　".join(
            f["answer"].replace("\r", " ").replace("\n", " ").strip()
            for f in groups[key]
        )
        rows.append((
            f"{PREFIX}{label}",
            body,
            f"質問回答集の{label} {len(groups[key])}件をそのまま並べたもの（自動生成・直接編集しない）",
        ))

    # ---- 案内所ごとに違う話題は、中身ではなく「違う」ことだけ伝える
    # 話題の名前は、札の文字（chip）があればそれを、無ければ質問例を使う。
    # 質問例の空白は「かつ」の印なので、読み物にするときは詰める。
    topics = {}
    for f in by_place:
        stem = f["id"].rsplit("_", 1)[0]
        label = (f.get("chip") or "").strip()
        if not label:
            label = (f.get("questions") or [""])[0].replace(" ", "").replace("　", "")
        topics.setdefault(stem, label)
    listed = "、".join(sorted(v for v in topics.values() if v))
    rows.append((
        f"{PREFIX}案内所によって答えが違うこと",
        f"次の話題は、バスターミナルとであいの館で答えが違います: {listed}。"
        "これらは、いまいる案内所の資料に書かれている内容だけを使って答えてください。"
        "資料に無い案内所の情報を持ち出さないでください。",
        f"案内所ごとの回答 {len(by_place)}件から自動生成（直接編集しない）",
    ))

    # ---- 書き込み
    wb = load_workbook(PATH)
    ws = wb[SHEET]

    # 前に自動生成した行を消す（職員が手で足した行は残す）
    for r in range(ws.max_row, 1, -1):
        title = ws.cell(r, 1).value
        if title and str(title).startswith(PREFIX):
            ws.delete_rows(r)

    # 中身の行の、いちばん下の次に書く。
    # 単に「空いている最初の行」を探すと、シート下の説明書き（※ で始まる行）を
    # 上書きしてしまう。
    row = 2
    for r in range(2, ws.max_row + 1):
        value = ws.cell(r, 1).value
        if value and not str(value).startswith("※"):
            row = r + 1

    for title, body, note in rows:
        for c, value in enumerate([title, body, "TRUE", note], start=1):
            cell = ws.cell(row=row, column=c, value=value)
            cell.font = Font(name="Yu Gothic", size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=(c in (2, 4)))
        row += 1

    wb.save(PATH)

    print(f"「{SHEET}」シートに {len(rows)} 行を入れました。")
    total = 0
    for title, body, _ in rows:
        total += len(body)
        print(f"  {title:<30} {len(body):>5} 文字")
    print(f"  合計 {total} 文字（毎回そのままAIへ渡されます）")


if __name__ == "__main__":
    main()
