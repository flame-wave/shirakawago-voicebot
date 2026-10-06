"""読み上げの「読み方」を、Excelから直せるようにする。

合成音声は漢字を文脈で読むため、地名や料理名をよく読み間違える。
「荻町」を「はぎまち」、「朴葉味噌」を「ぼくようみそ」、
「白山」を「しろやま」と読んでしまう。観光案内でいちばん大事な語が
いちばん間違いやすいので、読み方を人が決められるようにする。

【差し替えるのは音声だけ】
画面に出る文字は漢字のままにする（読む人には漢字の方が分かりやすい）。
読み上げに回す直前にだけカタカナへ差し替える。

【2か所で同じ表を使う】
  ・tools/make_voice.py  … VOICEVOXで音声を作るとき
  ・webapp/js/voice-service.js … ブラウザの合成音声で読むとき
どちらも faq.json の readings を見るので、直す場所は1つで済む。

使い方:
    python tools/add_readings.py            シートを作る（初回だけ）
    python tools/add_readings.py --check    回答に出てくる語との照合だけ
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "tools" / "faq_master.xlsx"

SHEET = "読み方"
HEADERS = ["表記", "読み", "有効", "備考"]
WIDTHS = [22, 30, 8, 44]

# 回答の日本語から拾った、合成音声が読み間違えやすい語。
# 「要確認」と書いたものは、正式な読みを職員に確かめてほしいもの。
ROWS = [
    # ── 地名・施設名 ──────────────────────────────
    ("白川郷", "シラカワゴウ", "TRUE", "「しらかわきょう」と読まれることがある"),
    ("白川村", "シラカワムラ", "TRUE", ""),
    ("荻町", "オギマチ", "TRUE", "「はぎまち」「おぎちょう」と読まれやすい"),
    ("鳩谷", "ハトガヤ", "TRUE", "「はとや」と読まれやすい"),
    ("飯島", "イイジマ", "TRUE", ""),
    ("寺尾", "テラオ", "TRUE", ""),
    ("和田家", "ワダケ", "TRUE", "「わだか」「わだいえ」と読まれやすい"),
    ("城山", "シロヤマ", "TRUE", "城山展望台。「じょうざん」と読まれやすい"),
    ("白山", "ハクサン", "TRUE", "「しろやま」と読まれやすい"),
    ("庄川", "ショウガワ", "TRUE", ""),
    ("白水湖", "シラミズコ", "TRUE", ""),
    ("白水園", "シラミズエン", "TRUE", "飲食店。要確認"),
    ("三方岩岳", "サンボウイワダケ", "TRUE", "要確認"),
    ("野谷荘司山", "ノダニショウジヤマ", "TRUE", "要確認"),
    ("猪臥山", "イブシヤマ", "TRUE", "要確認"),
    ("民家園", "ミンカエン", "TRUE", "合掌造り民家園"),
    ("白川八幡神社", "シラカワハチマンジンジャ", "TRUE", "社名はひとまとめで読ませる"),
    ("鳩谷八幡神社", "ハトガヤハチマンジンジャ", "TRUE", ""),
    ("飯島八幡神社", "イイジマハチマンジンジャ", "TRUE", ""),
    ("今藤商店", "イマトウショウテン", "TRUE", "要確認"),
    # ── 料理・名物 ────────────────────────────────
    ("朴葉味噌", "ホオバミソ", "TRUE", "「ぼくようみそ」と読まれやすい"),
    ("岩魚", "イワナ", "TRUE", "「がんぎょ」と読まれやすい"),
    ("飛騨牛", "ヒダギュウ", "TRUE", "「ひだうし」と読まれやすい"),
    ("石豆腐", "イシドウフ", "TRUE", ""),
    ("合掌造り", "ガッショウヅクリ", "TRUE", ""),
    # ── 祭り・神事 ────────────────────────────────
    # 回答に「春駒（はるこま）」と読み方が添えてある箇所がある。
    # 「春駒」だけを直すと「ハルコマ（はるこま）」と二重に読む。
    ("春駒（はるこま）", "ハルコマ", "TRUE", "読み方が添えてある箇所ごと差し替える"),
    ("春駒", "ハルコマ", "TRUE", "民謡。「しゅんく」と読まれやすい"),
    ("白川連獅子", "シラカワレンジシ", "TRUE", "要確認"),
    ("獅子舞", "シシマイ", "TRUE", ""),
    ("神幸祭", "シンコウサイ", "TRUE", "「じんこうさい」の社もある。要確認"),
    ("還御", "カンギョ", "TRUE", ""),
    ("初穂料", "ハツホリョウ", "TRUE", ""),
    ("記念盃", "キネンハイ", "TRUE", ""),
    ("志納", "シノウ", "TRUE", ""),
    ("徳利", "トックリ", "TRUE", ""),
    ("五穀豊穣", "ゴコクホウジョウ", "TRUE", ""),
    ("郷土芸能", "キョウドゲイノウ", "TRUE", ""),
    # ── 案内の言い方 ──────────────────────────────
    ("入村料", "ニュウソンリョウ", "TRUE", ""),
    ("村内", "ソンナイ", "TRUE", "「むらうち」と読まれやすい"),
    ("当村", "トウソン", "TRUE", ""),
    ("窓口机上", "マドグチノツクエノウエ", "TRUE",
     "回答の文そのものを「窓口の机の上」に直した方が読みやすい"),
    ("拾得物", "シュウトクブツ", "TRUE", ""),
    ("紙巻", "カミマキ", "TRUE", "紙巻きたばこ"),
    ("加熱式", "カネツシキ", "TRUE", ""),
]

GUIDE = (
    "※ 読み上げるときだけ「表記」を「読み」に差し替えます。画面に出る文字は変わりません。"
    "「読み」はカタカナで書いてください（ひらがなでも動きますが、カタカナの方が安定します）。"
    "長い語から先に差し替えるので、「白川八幡神社」と「白川郷」のように"
    "重なる語を両方書いても大丈夫です。"
    "日本語の読み上げにだけ使います（英語などの読み上げには当てません）。"
    "備考に「要確認」と書いた行は、正しい読みを確かめてから使ってください。"
)


def add_sheet(wb) -> bool:
    if SHEET in wb.sheetnames:
        print(f"「{SHEET}」シートはすでにあります。中身は触りません。")
        return False

    # 「読み上げ」の隣に置く（声の設定とまとめて見られるように）
    at = wb.sheetnames.index("読み上げ") + 1 if "読み上げ" in wb.sheetnames else None
    ws = wb.create_sheet(SHEET, at)

    for c, name in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=c, value=name)
        cell.font = Font(name="Yu Gothic", size=10, bold=True)
        cell.fill = PatternFill("solid", fgColor="EDF4E6")
    ws.freeze_panes = "A2"
    for c, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(c)].width = width

    for r, values in enumerate(ROWS, start=2):
        for c, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = Font(name="Yu Gothic", size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=(c == 4))

    row = len(ROWS) + 3
    guide = ws.cell(row=row, column=1, value=GUIDE)
    guide.font = Font(name="Yu Gothic", size=9, color="5A6B58")
    guide.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=row, start_column=1, end_row=row + 3, end_column=4)
    print(f"「{SHEET}」シートを作り、{len(ROWS)} 語を入れました。")
    return True


def check(wb) -> None:
    """読み方の表と、実際に読み上げる文を突き合わせる。

    読み上げないのに書いてある語（質問例にしか出てこない語など）は、
    直す必要がないので取り除いた方が表が見やすくなる。
    """
    ws = wb["FAQ"]
    header = {str(ws.cell(1, c).value).strip(): c
              for c in range(1, ws.max_column + 1) if ws.cell(1, c).value}
    spoken = []
    for r in range(2, ws.max_row + 1):
        for col in ("読み上げ用の短い回答", "回答"):
            if col in header:
                value = ws.cell(r, header[col]).value
                if value:
                    spoken.append(str(value))
                    break

    text = "\n".join(spoken)
    rows = ROWS
    if SHEET in wb.sheetnames:
        rs = wb[SHEET]
        rows = [(str(rs.cell(r, 1).value or ""), str(rs.cell(r, 2).value or ""),
                 "", "")
                for r in range(2, rs.max_row + 1)
                if rs.cell(r, 1).value and not str(rs.cell(r, 1).value).startswith("※")]

    print(f"\n読み上げる文 {len(spoken)} 件と、読み方 {len(rows)} 語を照合します。\n")
    unused = []
    for surface, reading, *_ in rows:
        n = text.count(surface)
        if n == 0:
            unused.append(surface)
        else:
            print(f"  {surface:<12} {n:>3} 箇所  → {reading}")
    if unused:
        print(f"\n読み上げる文に出てこない語（消してよい）: {'、'.join(unused)}")

    # 読み方の表に無い、読み間違えそうな長い漢語を拾う
    known = {s for s, *_ in rows}
    found = sorted(set(re.findall(r"[一-龥]{4,}", text)))
    others = [w for w in found if not any(k in w for k in known)]
    if others:
        print(f"\n読み方の表に無い4文字以上の漢語（確認の目安）:\n  {'、'.join(others)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="シートを作らず、回答との照合だけを表示する")
    args = ap.parse_args()

    wb = load_workbook(PATH)
    if args.check:
        check(wb)
        return
    if add_sheet(wb):
        wb.save(PATH)
        print(f"保存しました: {PATH}")
    check(wb)


if __name__ == "__main__":
    main()
