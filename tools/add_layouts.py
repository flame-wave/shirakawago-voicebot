"""設置形態ごとの画面の形を、Excelから決められるようにする。

据え置きのタブレットと、観光客のスマートフォンでは、同じ並びが使えない。

  据え置き … 立ったまま、少し離れて使う。指は大きく動かせるので
              話すボタンは大きい方がよい。一方で「文字で質問する」欄は、
              公共の端末ではほとんど使われない。
  観光客   … 手元で見る。画面が小さいので、出すものを絞りたい。

これまでは1つの並びをどの端末でも使い回していた。

【崩れない形で持つ】
位置を px で覚えると、別の大きさの画面に移したとたんに重なるか外へ出る。
ここでは高さを「画面の高さに対する割合」、立ち位置を「0〜1の割合」で持つ。
7インチでも13インチでも、同じ見え方になる。

使い方:
    python tools/add_layouts.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "tools" / "faq_master.xlsx"

SHEET = "画面レイアウト"
HEADERS = [
    "設置場所", "並び順",
    "よくある質問の高さ", "入力欄の高さ", "話すボタンの高さ", "言語の高さ",
    "キャラクターの大きさ", "キャラクターの高さ位置", "キャラクターの左右位置",
    "吹き出しの幅", "文字の大きさ", "備考",
]
WIDTHS = [14, 32, 16, 14, 16, 12, 18, 20, 20, 12, 12, 34]

# 既定値。
#
# 据え置き（タブレット）は、立ったまま少し離れて使うので、
# 話すボタンを大きくし、文字も少し大きくする。
# 「文字で質問する」欄は公共の端末では使われにくいので外してある。
#
# 観光客（スマートフォン）は、これまでと同じ並び。
ROWS = [
    ("バスターミナル", "stage,faq,talk,languages",
     0.09, 0, 0.15, 0.10, 1.0, 0.0, 0.0, 0.46, 1.1,
     "据え置きのタブレット。話すボタンを大きく、入力欄は出さない"),
    ("であいの館", "stage,faq,talk,languages",
     0.09, 0, 0.15, 0.10, 1.0, 0.0, 0.0, 0.46, 1.1,
     "据え置きのタブレット。バスターミナルと同じ"),
    ("観光客", "stage,faq,typed,talk,languages",
     0, 0, 0, 0, 1.0, 0.0, 0.0, 0, 1.0,
     "観光客のスマートフォン。0は「決めない」＝中身なりの大きさ"),
]

GUIDE = (
    "※ 設置場所は、案内アプリのURLに付ける名前と同じにしてください"
    "（?place=バスターミナル なら「バスターミナル」）。観光客の端末は「観光客」です。"
    "「共通」と書いた行は、合う行が無いときに使われます。"
    "　並び順は、出すブロックをカンマで区切って上から順に書きます"
    "（stage=会話領域 / faq=よくある質問 / typed=文字で質問する / talk=話すボタン / "
    "languages=言語）。書かなかったブロックは出ません。"
    "　高さは画面の高さに対する割合（0.15なら15%）。0は「決めない」で、中身なりの高さになります。"
    "　キャラクターの大きさは倍率（1.0が「キャラクター」シートのまま）、"
    "高さ位置は0が下端・1が上端、左右位置は0が右端・1が左端です。"
    "　この表は管理画面の「画面レイアウト」から、画面を見ながら動かして決められます。"
)


def add_sheet(wb) -> bool:
    if SHEET in wb.sheetnames:
        print(f"「{SHEET}」シートはすでにあります。中身は触りません。")
        return False

    # 「キャラクター」の隣に置く（案内画面の見た目をまとめて見られるように）
    at = wb.sheetnames.index("キャラクター") + 1 if "キャラクター" in wb.sheetnames else None
    ws = wb.create_sheet(SHEET, at)

    for c, name in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=c, value=name)
        cell.font = Font(name="Yu Gothic", size=10, bold=True)
        cell.fill = PatternFill("solid", fgColor="EDF4E6")
    ws.freeze_panes = "B2"
    for c, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(c)].width = width

    for r, values in enumerate(ROWS, start=2):
        for c, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = Font(name="Yu Gothic", size=10)
            cell.alignment = Alignment(vertical="top",
                                       wrap_text=(c in (2, len(HEADERS))))

    row = len(ROWS) + 3
    guide = ws.cell(row=row, column=1, value=GUIDE)
    guide.font = Font(name="Yu Gothic", size=9, color="5A6B58")
    guide.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=row, start_column=1,
                   end_row=row + 4, end_column=len(HEADERS))
    print(f"「{SHEET}」シートを作り、{len(ROWS)} 件を入れました。")
    return True


def main():
    wb = load_workbook(PATH)
    if add_sheet(wb):
        wb.save(PATH)
        print(f"保存しました: {PATH}")
        print("\n管理画面の「画面レイアウト」から、画面を見ながら動かして決められます。")


if __name__ == "__main__":
    main()
