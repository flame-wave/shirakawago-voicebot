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
from datetime import date, datetime
from pathlib import Path

import pandas as pd

VALID_CATEGORIES = {
    "bus", "facility", "sightseeing", "food",
    "season", "accessibility", "manner", "emergency", "event", "other",
}
VALID_LANGS = {"en", "zh", "ko", "es", "fr"}
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


def in_period(row, today=None) -> bool:
    """掲載期間の中かどうか。空欄はいつでも掲載する。

    お祭りなど期間限定の案内を、消し忘れずに出し入れするための仕組み。
    """
    today = today or datetime.now().date()
    start, end = cell_date(row.get("掲載開始日")), cell_date(row.get("掲載終了日"))
    if start and today < start:
        return False
    if end and today > end:
        return False
    return True


def cell_date(cell):
    """日付セルを date にする。読めない値は「指定なし」として扱う。"""
    if pd.isna(cell):
        return None
    if isinstance(cell, datetime):
        return cell.date()
    if isinstance(cell, date):
        return cell
    try:
        return datetime.fromisoformat(str(cell).strip()[:10]).date()
    except ValueError:
        return None


def build(source: str, assets_dir: Path | None):
    """戻り値: (FAQ一覧, エラー, 確認事項, 未翻訳件数, 言い換え表, 設置場所, 音声セット, 参考資料, キャラクター, 読み上げ)"""
    return build_from_bytes(load_workbook_bytes(source), assets_dir)


# 案内所の名前を、観光客の画面にその言語で出すための列。
# 日本語のままだと、読めない方には選びようがない。
PLACE_LABEL_COLUMNS = {
    "en": "英語名",
    "zh": "中国語名",
    "ko": "韓国語名",
    "es": "スペイン語名",
    "fr": "フランス語名",
}


def read_places(book) -> list:
    """「設置場所」シートを読む。無ければ空。

    案内所ごとに座標と範囲を持ち、利用者がどの案内所の近くにいるかを
    判定するために使う。座標が入っていない行は判定に使えないので飛ばす。

    各言語の名前は任意。書かれていない言語は日本語の名前を使う
    （書き忘れても選べなくなることはない）。
    """
    sheet = book.get("設置場所")
    if sheet is None:
        return []

    places = []
    for _, row in sheet.iterrows():
        name = cell_str(row.get("名前"))
        if not name or name.startswith("※"):
            continue
        try:
            lat = float(row.get("緯度"))
            lon = float(row.get("経度"))
        except (TypeError, ValueError):
            continue
        try:
            radius = int(float(row.get("範囲(m)")))
        except (TypeError, ValueError):
            radius = 250

        labels = {}
        for lang, column in PLACE_LABEL_COLUMNS.items():
            label = cell_str(row.get(column))
            if label:
                labels[lang] = label

        place = {"name": name, "lat": lat, "lon": lon, "radius": radius}
        if labels:
            place["labels"] = labels
        places.append(place)
    return places


# PNGファイルの先頭8バイト。これで本当にPNGかを確かめる。
PNG_SIGNATURE = bytes([137, 80, 78, 71, 13, 10, 26, 10])


def png_size(path: Path):
    """PNGの幅と高さを読む。読めなければ None。

    画像の縦横比は、吹き出しの位置を決めるのに要る。
    そのためだけに画像ライブラリを増やしたくないので、
    PNGの先頭（IHDR）から直接読む。
    """
    try:
        with path.open("rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != PNG_SIGNATURE:
        return None
    width = int.from_bytes(head[16:20], "big")
    height = int.from_bytes(head[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return width, height


def read_characters(book, assets_dir: Path | None) -> list:
    """「キャラクター」シートを読む。無ければ空。

    画面に立つキャラクター。利用者が選べるようにするため、
    1件ではなく一覧として持つ。

    「通常」だけ書かれていれば、聞き取り中も話している間も同じ絵を使う。
    表情差分が無いキャラクターでもそのまま動くようにしている。
    """
    sheet = book.get("キャラクター")
    if sheet is None:
        return []

    characters = []
    for _, row in sheet.iterrows():
        name = cell_str(row.get("名前"))
        idle = cell_str(row.get("通常"))
        if not name or not idle or name.startswith("※"):
            continue
        if cell_str(row.get("有効")).upper() in ("FALSE", "0", "×", "NO"):
            continue

        cid = cell_str(row.get("ID")) or idle.rsplit(".", 1)[0]

        def ratio(column, default, upper=1.0, allow_zero=False):
            try:
                value = float(row.get(column))
            except (TypeError, ValueError):
                return default
            low = 0.0 if allow_zero else None
            if low is None:
                return value if 0 < value <= upper else default
            return value if low <= value <= upper else default

        character = {
            "id": cid,
            "name": name,
            # 表情が無ければ通常の絵を使う（1枚でも動かせるようにするため）
            "idle": idle,
            "listening": cell_str(row.get("聞き取り中")) or idle,
            "talking": cell_str(row.get("話している")) or idle,
            "mouth": ratio("口の高さ", 0.14),
            "face": ratio("顔の広さ", 0.31),
            # 横長のキャラクターを高さいっぱいに立たせると画面を覆ってしまう
            "scale": ratio("大きさ", 1.0, upper=2.0),
            # 0＝下端に立たせる（人物）／1＝上端まで持ち上げる。
            # ゆるキャラは地面に立つものではないので、持ち上げて
            # 顔を吹き出しの高さに合わせる。
            "rise": ratio("高さ位置", 0.0, upper=1.0, allow_zero=True),
            "default": cell_str(row.get("既定")).upper() in ("TRUE", "1", "○", "YES"),
        }

        # 縦横比は画像から読む。書き間違いが起きない方に寄せる。
        if assets_dir:
            size = png_size(Path(assets_dir) / "character" / idle)
            if size:
                character["aspect"] = round(size[0] / size[1], 4)
        characters.append(character)

    # 「既定」がどれにも付いていなければ、先頭を既定にする
    if characters and not any(c["default"] for c in characters):
        characters[0]["default"] = True
    return characters


def read_reference(book) -> list:
    """「参考資料」シートを読む。無ければ空。

    質問回答集は「この質問にはこう答える」という形なので、
    そこに無い聞かれ方には答えられない。
    参考資料は、AIが答えを組み立てるときの下地として渡す説明文。

    決まった答えを返したい質問は「FAQ」シートに書く。
    ここに書くのは、言い換えて使ってよい背景の説明。
    """
    sheet = book.get("参考資料")
    if sheet is None:
        return []

    notes = []
    for _, row in sheet.iterrows():
        title = cell_str(row.get("見出し"))
        body = cell_str(row.get("内容"))
        if not title or not body or title.startswith("※"):
            continue
        if cell_str(row.get("有効")).upper() in ("FALSE", "0", "×", "NO"):
            continue
        notes.append({"title": title, "text": body})
    return notes


def read_voice_sets(book) -> list:
    """「音声セット」シートを読む。無ければ空。

    VOICEVOXなどで作った音声を、話者ごとにフォルダで分けて持てるようにする。
    案内アプリ側で、どのセットを鳴らすかを選べる。
    """
    sheet = book.get("音声セット")
    if sheet is None:
        return []

    sets = []
    for _, row in sheet.iterrows():
        name = cell_str(row.get("名前"))
        if not name or name.startswith("※"):
            continue
        sets.append({
            "id": cell_str(row.get("フォルダ")),   # 空なら assets/audio 直下
            "label": name,
            "note": cell_str(row.get("備考")),
            "default": cell_str(row.get("既定")).upper() in ("TRUE", "1", "○", "YES"),
        })

    # 「既定」がどれにも付いていなければ、先頭を既定にする
    if sets and not any(v["default"] for v in sets):
        sets[0]["default"] = True
    return sets


def read_voice_settings(book) -> dict:
    """「読み上げ」シートを読む。無ければ空。

    言語ごとに「優先する声」「速さ」「高さ」を持つ。

    端末に入っている声は端末ごとに違うので、ここで決められるのは
    「どれを優先するか」まで。実際にどれを使うかは案内アプリ側が、
    その端末に入っている声と突き合わせて決める。
    """
    sheet = book.get("読み上げ")
    if sheet is None:
        return {}

    settings = {}
    for _, row in sheet.iterrows():
        lang = cell_str(row.get("言語")).lower()
        if not lang or lang.startswith("※") or len(lang) > 5:
            continue

        voices = [v.strip() for v in cell_str(row.get("優先する声")).split(",")]
        entry = {"voices": [v for v in voices if v]}

        for key, column, default in (("rate", "速さ", 1.0), ("pitch", "高さ", 1.0)):
            try:
                value = float(row.get(column))
            except (TypeError, ValueError):
                value = default
            # 行き過ぎた値は聞き取れなくなるので、常識の範囲に収める
            entry[key] = value if 0.1 <= value <= 3.0 else default

        settings[lang] = entry
    return settings


def read_synonyms(book) -> dict:
    """「言い換え」シートを読む。無ければ空。

    観光客は登録した質問例とは違う語で聞いてくる。
    その差を吸収するための対応表で、検索のときだけ使う。
    """
    sheet = book.get("言い換え")
    if sheet is None:
        return {}

    out = {}
    for _, row in sheet.iterrows():
        lang = (cell_str(row.get("言語")) or "ja").lower()
        rep_word = cell_str(row.get("代表語"))
        words = split_lines(row.get("同じ意味の語"))
        if not rep_word or not words:
            continue
        out.setdefault(lang, {})[rep_word] = words
    return out


def build_from_bytes(raw: bytes, assets_dir: Path | None):
    """xlsxのバイト列から変換する。管理画面もここを呼ぶ。

    戻り値: (FAQ一覧, エラー, 確認事項, 未翻訳件数, 言い換え表, 設置場所, 音声セット, 参考資料, キャラクター, 読み上げ)
    """
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

        if not in_period(row):
            warnings.append(f"{fid}: 掲載期間外のため、今回は出力しません")
            continue

        category = cell_str(row.get("カテゴリ")) or "other"
        if category not in VALID_CATEGORIES:
            errors.append(f"FAQ {line}行目({fid}): カテゴリ「{category}」は未定義です")

        questions = split_lines(row.get("質問例"))
        if not questions:
            errors.append(f"FAQ {line}行目({fid}): 質問例が空です")
        elif len(questions) < 2:
            warnings.append(f"{fid}: 質問例が1つだけです。言い方を増やすと認識しやすくなります")

        # どの質問にも出てくる語だけの質問例は、他の質問まで拾ってしまう
        GENERIC = {"どこ", "場所", "時間", "いつ", "何時", "料金", "値段",
                   "ある", "ありますか", "教えて", "できる"}
        for q in questions:
            words = [w for w in q.split() if w]
            if words and all(w in GENERIC for w in words):
                warnings.append(
                    f"{fid}: 質問例「{q}」は一般的な語だけのため、"
                    "関係ない質問にも反応する恐れがあります。"
                    "内容を表す語（例: ごみ、トイレ）を足してください"
                )

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
        # 画面に並べる「よくある質問」の文言。空なら並べない。
        chip = cell_str(row.get("よくある質問"))
        # どの案内所向けの回答か。「共通」はどこでも使う。
        place = cell_str(row.get("設置場所")) or "共通"

        if assets_dir:
            if photo and not (assets_dir / "photo" / photo).exists():
                warnings.append(f"{fid}: 写真 {photo} が見つかりません（写真なしで動作します）")
            if audio:
                folders = [""] + [v["id"] for v in read_voice_sets(book) if v["id"]]
                if not any((assets_dir / "audio" / f / audio).exists() for f in folders):
                    warnings.append(
                        f"{fid}: 音声 {audio} が見つかりません（端末音声で読み上げます）")

        faqs.append({
            "id": fid,
            "category": category,
            "questions": questions,
            "answer": answer,
            "audio": audio,
            "photo": photo,
            "link": link,
            "chip": chip,
            "place": place,
            "translations": {},
        })

    # ---- 多言語シートの取り込み
    pending = 0
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
                errors.append(f"多言語 {line}行目: 言語「{lang}」は en / zh / ko / es / fr のいずれかです")
                continue
            if fid not in by_id:
                warnings.append(
                    f"多言語 {line}行目: ID「{fid}」がFAQシートに見つかりません（無効行の可能性）"
                )
                continue
            answer = cell_str(row.get("回答"))
            if not answer:
                # 質問例だけ書かれている場合、黙って捨てると原因が分からないので知らせる
                if split_lines(row.get("質問例")):
                    warnings.append(
                        f"多言語 {line}行目({fid}/{lang}): 質問例は入力されていますが回答が空です。"
                        "回答を入れないとこの言語では反応しません"
                    )
                pending += 1  # 未翻訳。エラーではない
                continue
            by_id[fid]["translations"][lang] = {
                "questions": split_lines(row.get("質問例")),
                "answer": answer,
                "audio": "",
            }

    places = read_places(book)
    if places:
        known = {p["name"] for p in places} | {"共通", ""}
        for faq in faqs:
            if faq["place"] not in known:
                warnings.append(
                    f"{faq['id']}: 設置場所「{faq['place']}」が「設置場所」シートにありません"
                )

    return (faqs, errors, warnings, pending, read_synonyms(book), places,
            read_voice_sets(book), read_reference(book),
            read_characters(book, assets_dir), read_voice_settings(book))


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
    (faqs, errors, warnings, pending, synonyms, places, voice_sets,
     reference, characters, voice) = build(args.source, assets_dir)

    print(f"\n読み込み結果: 有効な質問 {len(faqs)} 件 / 言い換え {sum(len(v) for v in synonyms.values())} 語"
          + (f" / 参考資料 {len(reference)} 件" if reference else ""))
    n_tr = sum(len(f["translations"]) for f in faqs)
    print(f"  多言語の回答: {n_tr} 件" + (f"（未翻訳 {pending} 件）" if pending else ""))
    for lang in ("en", "zh", "ko", "es", "fr"):
        c = sum(1 for f in faqs if lang in f["translations"])
        print(f"    {lang}: {c}/{len(faqs)} 件")

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
        "synonyms": synonyms,        # 検索のときだけ使う言い換え表
        "places": places,            # 案内所の場所（近い方の回答を選ぶのに使う）
        "voice_sets": voice_sets,    # 用意した音声の種類（話者ごと）
        "reference": reference,      # AIが回答を組み立てるときの下地
        "characters": characters,    # 画面に立つキャラクター（利用者が選べる）
        "voice": voice,              # 言語ごとの読み上げの設定
    }
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n書き出しました: {out}（版: {version}）")

    if not errors:
        print("問題は見つかりませんでした。")


if __name__ == "__main__":
    main()