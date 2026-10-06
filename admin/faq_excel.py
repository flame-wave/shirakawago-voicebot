"""
質問回答集（tools/faq_master.xlsx）の読み書き。

このファイルが「正」のデータで、案内アプリが読む assets/faq.json は
ここから書き出したもの。管理画面・Excel・変換ツールのどれから見ても
同じ内容になるよう、列は名前で探して読み書きする。

列を増やしたり並べ替えたりしても壊れない。
知らない列には触らないので、Excel側で自由に列を足してよい。

保存先は2通り。
  local  … 手元のファイル。PCで動かして試すとき用。
  github … リポジトリに直接コミットする。公開した管理画面はこちら。
"""

import base64
import io
import re
from datetime import date, datetime
from pathlib import Path

import requests
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font

API = "https://api.github.com"

FAQ_SHEET = "FAQ"
LANG_SHEET = "多言語"

FONT = "Yu Gothic"
MACHINE_MARK = "自動翻訳（要確認）"

# FAQシートの列名。Excel側の見出しを変えたらここも変える。
COL = {
    "id": "ID",
    "place": "設置場所",
    "category": "カテゴリ",
    "questions": "質問例",
    "answer": "回答",
    "short": "読み上げ用の短い回答",
    "photo": "写真ファイル名",
    "link": "参考リンク",
    "audio": "音声ファイル名",
    "chip": "よくある質問",
    "enabled": "有効",
    "show_from": "掲載開始日",
    "show_until": "掲載終了日",
}

# 多言語シートの列（この順で固定）
LANG_COL = {"id": 1, "lang": 2, "questions": 3, "answer": 4, "note": 5}

# 「キャラクター」シート。案内画面に立つ絵を決める。
# FAQ以外のシート。列は見出しで引く（列番号を書くと、列を1つ足しただけで
# 別の列を読んでしまう）。値は「見出しの名前」であって、何列目かではない。
VSET_SHEET = "音声セット"
VSET_COL = {"name": "名前", "folder": "フォルダ", "note": "備考", "default": "既定"}

VOICE_SHEET = "読み上げ"
VOICE_COL = {"lang": "言語", "voices": "優先する声",
             "rate": "速さ", "pitch": "高さ", "note": "備考"}

CHAR_SHEET = "キャラクター"
CHAR_COL = {"name": "名前", "id": "ID", "idle": "通常",
            "listening": "聞き取り中", "talking": "話している",
            "mouth": "口の高さ", "face": "顔の広さ", "大きさ": "大きさ",
            "default": "既定", "enabled": "有効", "note": "備考"}


class ExcelError(Exception):
    pass


# ---------------------------------------------------------------- 値の扱い
def text(value) -> str:
    """セルの値を文字列にする。日付はそのまま読める形にする。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def lines(value) -> list:
    """改行区切りのセルを配列にする。"""
    raw = text(value).replace("\r\n", "\n").replace("\r", "\n")
    return [x.strip() for x in raw.split("\n") if x.strip()]


def as_number(value):
    """数字だけの文字列は数値に戻す。

    管理画面の表はすべて文字として扱うので、そのまま書くと Excel に
    「0.45」という文字列が入る。Excelで開いたときに数値として扱えず、
    並べ替えや手計算ができなくなるため、ここで戻している。
    """
    if not isinstance(value, str):
        return value
    body = value.strip()
    if not body:
        return value
    try:
        return int(body) if re.fullmatch(r"-?\d+", body) else float(body)
    except ValueError:
        return value


def is_enabled(value) -> bool:
    return text(value).upper() in ("TRUE", "1", "○", "有効", "YES", "")


# ---------------------------------------------------------------- 本体
class FaqBook:
    """開いた質問回答集。読み・書き・書き出しをまとめて受け持つ。"""

    def __init__(self, raw: bytes):
        self.wb = load_workbook(io.BytesIO(raw))
        if FAQ_SHEET not in self.wb.sheetnames:
            raise ExcelError(f"「{FAQ_SHEET}」シートが見つかりません")
        if LANG_SHEET not in self.wb.sheetnames:
            raise ExcelError(f"「{LANG_SHEET}」シートが見つかりません")
        self.fs = self.wb[FAQ_SHEET]
        self.ls = self.wb[LANG_SHEET]
        self.header = {
            text(self.fs.cell(1, c).value): c
            for c in range(1, self.fs.max_column + 1)
            if text(self.fs.cell(1, c).value)
        }
        for name in (COL["id"], COL["questions"], COL["answer"]):
            if name not in self.header:
                raise ExcelError(f"FAQシートに「{name}」列がありません")

    # ---- 読む -----------------------------------------------------
    def _cell(self, row: int, key: str):
        col = self.header.get(COL[key])
        return None if col is None else self.fs.cell(row, col).value

    def faq_rows(self) -> list:
        """FAQシートの各行を、扱いやすい形にして返す。"""
        items = []
        for r in range(2, self.fs.max_row + 1):
            fid = text(self._cell(r, "id"))
            if not fid:
                continue
            items.append({
                "row": r,
                "id": fid,
                "place": text(self._cell(r, "place")),
                "category": text(self._cell(r, "category")) or "other",
                "questions": lines(self._cell(r, "questions")),
                "answer": text(self._cell(r, "answer")),
                "short": text(self._cell(r, "short")),
                "photo": text(self._cell(r, "photo")),
                "link": text(self._cell(r, "link")),
                "audio": text(self._cell(r, "audio")),
                "chip": text(self._cell(r, "chip")),
                "enabled": is_enabled(self._cell(r, "enabled")),
                "show_from": text(self._cell(r, "show_from")),
                "show_until": text(self._cell(r, "show_until")),
            })
        return items

    def find(self, fid: str):
        for item in self.faq_rows():
            if item["id"] == fid:
                return item
        return None

    def places(self) -> list:
        """Excelに実際に入っている設置場所の一覧（選択肢に使う）。"""
        seen = []
        for item in self.faq_rows():
            if item["place"] and item["place"] not in seen:
                seen.append(item["place"])
        return seen

    def translation_rows(self) -> dict:
        """{(ID, 言語): 行番号} を返す。"""
        rows = {}
        for r in range(2, self.ls.max_row + 1):
            fid = text(self.ls.cell(r, LANG_COL["id"]).value)
            lang = text(self.ls.cell(r, LANG_COL["lang"]).value).lower()
            if not fid or not lang:
                continue
            rows[(fid, lang)] = r
        return rows

    def translations_of(self, fid: str) -> dict:
        """{言語: {questions, answer, note}} を返す。"""
        out = {}
        for (rid, lang), r in self.translation_rows().items():
            if rid != fid:
                continue
            out[lang] = {
                "questions": lines(self.ls.cell(r, LANG_COL["questions"]).value),
                "answer": text(self.ls.cell(r, LANG_COL["answer"]).value),
                "note": text(self.ls.cell(r, LANG_COL["note"]).value),
            }
        return out

    def translated_langs(self) -> dict:
        """{ID: {回答が入っている言語}} を返す。未翻訳の洗い出しに使う。"""
        done = {}
        for (fid, lang), r in self.translation_rows().items():
            if text(self.ls.cell(r, LANG_COL["answer"]).value):
                done.setdefault(fid, set()).add(lang)
        return done

    # ---- どのシートも同じやり方で読む --------------------------------
    def _sheet(self, name: str):
        """シートと、その見出し（名前→何列目）を返す。無ければ (None, {})。"""
        if name not in self.wb.sheetnames:
            return None, {}
        ws = self.wb[name]
        header = {
            text(ws.cell(1, c).value): c
            for c in range(1, ws.max_column + 1)
            if text(ws.cell(1, c).value)
        }
        return ws, header

    @staticmethod
    def _get(ws, header, row: int, title: str) -> str:
        """見出しの名前で値を取る。その列が無ければ空。"""
        col = header.get(title)
        return "" if col is None else text(ws.cell(row, col).value)

    @staticmethod
    def _put(ws, header, row: int, title: str, value) -> None:
        """見出しの名前で値を入れる。その列が無ければ何もしない。

        cell(..., value=None) は「消す」ではなく「何もしない」ため、
        空にするときは .value へ直接入れる。
        """
        col = header.get(title)
        if col is not None:
            ws.cell(row, col).value = value

    @staticmethod
    def _is_note(value: str) -> bool:
        """説明書きの行か（1列目が「※」で始まる行は中身ではない）。"""
        return value.startswith("※")

    def sheet_rows(self, name: str) -> tuple:
        """シートの中身を (見出しの一覧, 行の一覧) で返す。

        1列目が「※」で始まる行は説明書きなので、中身には含めない。
        """
        ws, header = self._sheet(name)
        if ws is None:
            return [], []

        titles = [t for t in header]
        rows = []
        for r in range(2, ws.max_row + 1):
            values = {t: self._get(ws, header, r, t) for t in titles}
            first = values.get(titles[0], "") if titles else ""
            if self._is_note(first):
                continue
            if not any(v for v in values.values()):
                continue   # 空行は飛ばす
            rows.append(values)
        return titles, rows

    def write_sheet(self, name: str, rows: list) -> None:
        """シートの中身を入れ替える。見出しと、下の説明書きは残す。

        行数が増減するので、いったん中身の行を消してから書き直す。
        説明書き（「※」で始まる行）は下へ送られるだけで消えない。
        """
        ws, header = self._sheet(name)
        if ws is None:
            raise ExcelError(f"「{name}」シートがありません")
        titles = list(header)
        if not titles:
            raise ExcelError(f"「{name}」シートに見出しがありません")

        # いま中身が入っている行を集める（説明書きは触らない）
        body = []
        for r in range(2, ws.max_row + 1):
            first = self._get(ws, header, r, titles[0])
            if self._is_note(first):
                continue
            if any(self._get(ws, header, r, t) for t in titles):
                body.append(r)

        # 行数が足りなければ足し、余れば消す
        start = body[0] if body else 2
        need = len(rows)
        have = len(body)
        if need > have:
            at = (body[-1] + 1) if body else 2
            ws.insert_rows(at, need - have)
        elif have > need:
            # 後ろから消す（前から消すと行番号がずれる）
            for r in reversed(body[need:]):
                ws.delete_rows(r)

        for i, values in enumerate(rows):
            r = start + i
            for t in titles:
                value = values.get(t, "")
                # 空文字はセルを空にする（cell(value=None) では消えない）
                self._put(ws, header, r, t,
                          as_number(value) if value != "" else None)

    def voice_sets(self) -> list:
        """「音声セット」シートの一覧（VOICEVOXなどで作った音声）。"""
        ws, header = self._sheet(VSET_SHEET)
        if ws is None:
            return []
        out = []
        for r in range(2, ws.max_row + 1):
            name = self._get(ws, header, r, VSET_COL["name"])
            if not name or self._is_note(name):
                continue
            out.append({
                "row": r,
                "name": name,
                "folder": self._get(ws, header, r, VSET_COL["folder"]),
                "note": self._get(ws, header, r, VSET_COL["note"]),
                "default": self._get(ws, header, r, VSET_COL["default"]).upper()
                           in ("TRUE", "1", "○", "YES"),
            })
        return out

    def set_default_voice_set(self, folder: str) -> None:
        """既定の音声セットを決める。ほかの行の印は消す。"""
        ws, header = self._sheet(VSET_SHEET)
        if ws is None:
            raise ExcelError(f"「{VSET_SHEET}」シートがありません")
        if VSET_COL["default"] not in header:
            raise ExcelError(f"「{VSET_SHEET}」シートに「既定」列がありません")
        found = False
        for item in self.voice_sets():
            mark = item["folder"] == folder
            self._put(ws, header, item["row"], VSET_COL["default"],
                      "TRUE" if mark else None)
            found = found or mark
        if not found:
            raise ExcelError("指定された音声セットが見つかりません")

    def voice_settings(self) -> list:
        """「読み上げ」シートの一覧（言語ごとの優先する声・速さ・高さ）。"""
        ws, header = self._sheet(VOICE_SHEET)
        if ws is None:
            return []
        out = []
        for r in range(2, ws.max_row + 1):
            lang = self._get(ws, header, r, VOICE_COL["lang"]).lower()
            if not lang or self._is_note(lang) or len(lang) > 5:
                continue

            def number(key, default, row=r):
                try:
                    return float(self._get(ws, header, row, VOICE_COL[key]))
                except ValueError:
                    return default

            out.append({
                "row": r,
                "lang": lang,
                "voices": self._get(ws, header, r, VOICE_COL["voices"]),
                "rate": number("rate", 1.0),
                "pitch": number("pitch", 1.0),
            })
        return out

    def update_voice_setting(self, lang: str, voices: str,
                             rate: float, pitch: float) -> None:
        """ある言語の読み上げの設定を書き換える。無い言語なら行を足す。"""
        ws, header = self._sheet(VOICE_SHEET)
        if ws is None:
            raise ExcelError(f"「{VOICE_SHEET}」シートがありません")

        existing = self.voice_settings()
        row = next((v["row"] for v in existing if v["lang"] == lang), None)
        if row is None:
            # 言語の行のすぐ下に差し込む。
            # シートの下には説明書きが結合セルで置いてあり、
            # そこへ書こうとすると openpyxl が書き込みを拒む。
            row = (max((v["row"] for v in existing), default=1)) + 1
            ws.insert_rows(row)
            self._put(ws, header, row, VOICE_COL["lang"], lang)

        self._put(ws, header, row, VOICE_COL["voices"], voices.strip() or None)
        self._put(ws, header, row, VOICE_COL["rate"], round(float(rate), 2))
        self._put(ws, header, row, VOICE_COL["pitch"], round(float(pitch), 2))

    def characters(self) -> list:
        """「キャラクター」シートの一覧。無ければ空。

        案内画面に立つ絵。職員はここで既定を決め、
        利用者は案内画面で選び直せる。
        """
        ws, header = self._sheet(CHAR_SHEET)
        if ws is None:
            return []
        out = []
        for r in range(2, ws.max_row + 1):
            name = self._get(ws, header, r, CHAR_COL["name"])
            idle = self._get(ws, header, r, CHAR_COL["idle"])
            if not name or not idle or self._is_note(name):
                continue
            enabled = self._get(ws, header, r, CHAR_COL["enabled"]).upper()
            if enabled in ("FALSE", "0", "×", "NO"):
                continue
            out.append({
                "row": r,
                "name": name,
                "id": self._get(ws, header, r, CHAR_COL["id"])
                      or idle.rsplit(".", 1)[0],
                "idle": idle,
                "default": self._get(ws, header, r, CHAR_COL["default"]).upper()
                           in ("TRUE", "1", "○", "YES"),
                "note": self._get(ws, header, r, CHAR_COL["note"]),
            })
        return out

    def set_default_character(self, character_id: str) -> None:
        """既定のキャラクターを決める。ほかの行の印は消す。

        印が複数あると、どれが立つのか決まらなくなる。
        """
        ws, header = self._sheet(CHAR_SHEET)
        if ws is None:
            raise ExcelError(f"「{CHAR_SHEET}」シートがありません")
        if CHAR_COL["default"] not in header:
            raise ExcelError(f"「{CHAR_SHEET}」シートに「既定」列がありません")
        found = False
        for item in self.characters():
            mark = item["id"] == character_id
            self._put(ws, header, item["row"], CHAR_COL["default"],
                      "TRUE" if mark else None)
            found = found or mark
        if not found:
            raise ExcelError(f"キャラクター「{character_id}」が見つかりません")

    def missing(self, langs) -> list:
        """(ID, 言語) のうち、回答がまだ入っていないものを返す。"""
        done = self.translated_langs()
        out = []
        for item in self.faq_rows():
            if not item["enabled"]:
                continue  # 案内に出さない項目は翻訳しない
            for lang in langs:
                if lang not in done.get(item["id"], set()):
                    out.append((item["id"], lang))
        return out

    # ---- 書く -----------------------------------------------------
    def _style(self, ws, row: int, cols, wrap_cols=()):
        for c in cols:
            cell = ws.cell(row=row, column=c)
            cell.font = Font(name=FONT, size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=(c in wrap_cols))

    def upsert_faq(self, item: dict) -> int:
        """同じIDの行があれば書き換え、無ければ最後に足す。戻り値は行番号。

        知らない列（Excel側で足した列）には触らない。
        """
        found = self.find(item["id"])
        row = found["row"] if found else self._next_faq_row()

        values = {
            "id": item["id"],
            "place": item.get("place", ""),
            "category": item.get("category", "other"),
            "questions": "\n".join(item.get("questions", [])),
            "answer": item.get("answer", ""),
            "short": item.get("short", ""),
            "photo": item.get("photo", ""),
            "link": item.get("link", ""),
            "audio": item.get("audio", ""),
            "chip": item.get("chip", ""),
            "enabled": "TRUE" if item.get("enabled", True) else "FALSE",
            "show_from": item.get("show_from", ""),
            "show_until": item.get("show_until", ""),
        }
        for key, value in values.items():
            col = self.header.get(COL[key])
            if col is None:
                continue  # その列がExcelに無ければ黙って飛ばす
            # cell(..., value=None) は「消す」ではなく「何もしない」ため、
            # 空にするときは .value へ直接入れる（掲載期間の解除などで必要）
            self.fs.cell(row=row, column=col).value = value or None

        wrap = {self.header.get(COL[k]) for k in ("questions", "answer", "short")}
        self._style(self.fs, row, range(1, self.fs.max_column + 1), wrap)
        return row

    def _next_faq_row(self) -> int:
        """末尾の空行を拾う（Excelが空行を持っていることがあるため）。"""
        row = self.fs.max_row + 1
        while row > 2 and not text(self.fs.cell(row - 1, self.header[COL["id"]]).value):
            row -= 1
        return row

    def upsert_translation(self, fid: str, lang: str, questions, answer: str,
                           machine: bool, source_answer: str = "") -> int:
        """多言語シートに1件書く。自動翻訳には印を付ける。"""
        rows = self.translation_rows()
        row = rows.get((fid, lang.lower()))
        if row is None:
            row = self.ls.max_row + 1
            while row > 2 and not text(self.ls.cell(row - 1, LANG_COL["id"]).value):
                row -= 1

        note = []
        if machine:
            note.append(MACHINE_MARK)
        if source_answer:
            note.append(f"日本語原文: {source_answer}")

        self.ls.cell(row=row, column=LANG_COL["id"], value=fid)
        self.ls.cell(row=row, column=LANG_COL["lang"], value=lang.lower())
        self.ls.cell(row=row, column=LANG_COL["questions"],
                     value="\n".join(questions) or None)
        self.ls.cell(row=row, column=LANG_COL["answer"], value=answer or None)
        self.ls.cell(row=row, column=LANG_COL["note"], value="｜".join(note) or None)
        self._style(self.ls, row, range(1, 6), wrap_cols=(3, 4, 5))
        return row

    def to_bytes(self) -> bytes:
        buf = io.BytesIO()
        self.wb.save(buf)
        return buf.getvalue()


# ---------------------------------------------------------------- 保存先
class LocalExcelStore:
    label = "この端末のExcelファイル"

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        """(バイト列, 目印) を返す。目印は保存時の取り違え検出に使う。"""
        if not self.path.exists():
            raise ExcelError(f"ファイルが見つかりません: {self.path}")
        return self.path.read_bytes(), None

    def save(self, raw: bytes, message: str, sha=None):
        # Excelで開いたままだと書き込めないことがあるので、理由を出す
        try:
            self.path.write_bytes(raw)
        except PermissionError:
            raise ExcelError(
                "Excelファイルに書き込めません。"
                f"{self.path.name} をExcelで開いている場合は閉じてから、もう一度お試しください。"
            )
        return None

    @property
    def location(self):
        return str(self.path)


class GitHubExcelStore:
    label = "GitHub（リポジトリのExcel）"

    def __init__(self, token, repo, path="tools/faq_master.xlsx", branch="main"):
        self.token = token
        self.repo = repo
        self.path = path
        self.branch = branch

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def load(self):
        url = f"{API}/repos/{self.repo}/contents/{self.path}"
        res = requests.get(url, headers=self._headers,
                           params={"ref": self.branch}, timeout=30)
        if res.status_code == 404:
            raise ExcelError(
                f"{self.path} がリポジトリにありません。先にExcelをpushしてください。"
            )
        if res.status_code != 200:
            raise ExcelError(f"読み込みに失敗しました（{res.status_code}）: {res.text[:200]}")
        body = res.json()
        if body.get("content"):
            raw = base64.b64decode(body["content"])
        else:
            # 1MBを超えるファイルは content が空で返るので、ダウンロードURLから取る
            raw = requests.get(body["download_url"], timeout=30).content
        return raw, body["sha"]

    def save(self, raw: bytes, message: str, sha=None):
        url = f"{API}/repos/{self.repo}/contents/{self.path}"
        payload = {
            "message": message,
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": self.branch,
        }
        if sha:
            payload["sha"] = sha
        res = requests.put(url, headers=self._headers, json=payload, timeout=60)
        if res.status_code == 409:
            raise ExcelError(
                "ほかの人が先に保存したため、保存できませんでした。"
                "画面を再読み込みして、もう一度お試しください。"
            )
        if res.status_code not in (200, 201):
            raise ExcelError(f"保存に失敗しました（{res.status_code}）: {res.text[:200]}")
        return res.json()["content"]["sha"]

    @property
    def location(self):
        return f"{self.repo} / {self.path}（{self.branch}）"
