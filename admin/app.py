"""
白川郷 音声案内 かんたん管理画面

日本語で質問と回答を入れると、他の言語は自動で翻訳され、
質問回答集（tools/faq_master.xlsx）の「FAQ」「多言語」シートに追加される。

Excelを直接触らなくても、ブラウザだけで編集できる。
Excelで開いて直しても構わない。どちらで編集しても同じファイルを見ている。

案内アプリに反映するときは「案内アプリへ反映する」から書き出す。

起動:
    streamlit run admin/app.py
"""

import json
import os
import time
from html import escape
import sys
from datetime import date, datetime
from pathlib import Path

# 時刻は日本時間で扱う。Streamlit Cloud の時計は世界標準時（9時間遅れ）なので、
# そのままだと「前回の反映 10/7 16:13」（日本では 10/8 1:13）のようにずれ、
# 案内期間の「今日」も夜9時までは前の日になってしまう。
os.environ["TZ"] = "Asia/Tokyo"
if hasattr(time, "tzset"):   # Windows には無い（手元のWindowsは元から日本時間）
    time.tzset()

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import faq_excel as X
import publish_diff
import ui
from components.layout_editor import layout_editor
import faq_translate as T
import log_stats as L
import build_faq
from faq_store import VALID_CATEGORIES, GitHubStore, LocalStore, StoreError

st.set_page_config(page_title="音声案内 管理画面", page_icon="🏘️", layout="wide")

# 見た目（色・書体・共通の部品）は ui.py と .streamlit/config.toml にまとめてある。
# 画面の側では色や CSS を書かないこと。
ui.apply_theme()


# ---------------------------------------------------------------- 設定
def secret(section, key, default=None):
    """設定ファイルが無くても落ちないようにまとめて包む。
    手元で試すときは設定なしで動き、公開時だけ設定を置けばよい。"""
    try:
        return st.secrets[section][key]
    except Exception:
        return default


def get_engine():
    """翻訳の方式を決める。設定が無ければ None（＝日本語のみで運用）。

    どちらを選んでも処理はクラウド側で行われるので、
    職員のパソコンには何も入れなくてよい。

    CHAATBOT_FAKE_TRANSLATE=1 を付けて起動したときだけ、決まった訳を返す
    試し用の翻訳を使う（本物のキーが無い状態で画面の流れを確かめるため）。
    """
    import os
    if os.environ.get("CHAATBOT_FAKE_TRANSLATE") == "1":
        return T.fake_engine()
    return T.describe_engine(
        anthropic_key=secret("anthropic", "api_key"),
        open_model={
            "base_url": secret("open_model", "base_url"),
            "api_key": secret("open_model", "api_key"),
            "model": secret("open_model", "model"),
        },
        prefer=secret("translate", "engine"),
    )


def get_store():
    """質問回答集（Excel）の置き場所。"""
    token, repo = secret("github", "token"), secret("github", "repo")
    if token and repo:
        return X.GitHubExcelStore(
            token=token,
            repo=repo,
            path=secret("github", "excel_path", "tools/faq_master.xlsx"),
            branch=secret("github", "branch", "main"),
        )
    return X.LocalExcelStore(ROOT / "tools" / "faq_master.xlsx")


def get_json_store():
    """案内アプリが読む faq.json の置き場所。"""
    token, repo = secret("github", "token"), secret("github", "repo")
    if token and repo:
        return GitHubStore(
            token=token,
            repo=repo,
            path=secret("github", "path", "assets/faq.json"),
            branch=secret("github", "branch", "main"),
        )
    return LocalStore(ROOT / "assets" / "faq.json")


# ---------------------------------------------------------------- 合言葉
def check_password():
    expected = secret("app", "password")
    if not expected:
        return True  # 設定していなければ確認しない（手元で試すとき用）
    if st.session_state.get("ok"):
        return True
    st.title("白川郷 音声案内　管理画面")
    with st.form("login"):
        pw = st.text_input("合言葉", type="password")
        if st.form_submit_button("入る"):
            if pw == expected:
                st.session_state["ok"] = True
                st.rerun()
            else:
                st.error("合言葉が違います")
    return False


if not check_password():
    st.stop()

store = get_store()
engine = get_engine()


# ---------------------------------------------------------------- 読み込み
def load_book():
    raw, sha = store.load()
    st.session_state["raw"] = raw
    st.session_state["sha"] = sha
    return X.FaqBook(raw)


if "raw" not in st.session_state:
    try:
        load_book()
    except (X.ExcelError, Exception) as e:
        st.error(f"質問回答集を開けませんでした: {e}")
        st.stop()

book = X.FaqBook(st.session_state["raw"])
items = book.faq_rows()
done = book.translated_langs()


def save_book(apply_changes, message):
    """保存直前にもう一度読み直してから書き込む。

    Excel側や他の人の編集を上書きしてしまわないようにするため。
    """
    raw, sha = store.load()
    fresh = X.FaqBook(raw)
    apply_changes(fresh)
    new_raw = fresh.to_bytes()
    new_sha = store.save(new_raw, message, sha)
    st.session_state["raw"] = new_raw
    st.session_state["sha"] = new_sha
    # 公開中の内容との食い違いを、次の表示で測り直す
    st.session_state.pop("published", None)


# ---------------------------------------------------------------- 画面の部品
def panel_title(title, note=""):
    """画面の題と一行の説明（共通の部品 ui.page_header を使う）。"""
    ui.page_header(title, note)


def tiles(cells):
    """数値の札（共通の部品 ui.tiles を使う）。"""
    ui.tiles(cells)


def reload_book():
    for k in ("raw", "sha", "pending", "published"):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------- 反映の状況
def published_summary():
    """いま案内アプリに出ている内容を読む。読めなければ None。

    Excelに保存しただけでは案内端末に届かない。実際に書き出したものと
    見比べられないと、職員は「直したのに変わらない」で止まってしまう。
    （現に、キャラクターを変えたのに書き出さず、古いまま公開されていた）
    """
    if "published" in st.session_state:
        return st.session_state["published"]
    try:
        data, _ = get_json_store().load()   # 読み込んだ時点で辞書になっている
    except Exception:
        data = None
    st.session_state["published"] = data
    return data


def unpublished():
    """まだ案内アプリに反映していない変更の一覧。読めないときは None。

    書き出しと同じ変換（build_faq）を通して、公開中のものと1件ずつ比べる。
    サイドバーの「未反映 3」とホームの一覧は、どちらもこれを見る。
    """
    return publish_diff.cached(st.session_state, st.session_state["raw"],
                               published_summary(), ROOT / "assets")


def publish_gaps():
    """ホームに出す、反映されていない変更の説明（一行ずつ）。"""
    changes = unpublished()
    if not changes:
        return []
    return [f"{c['kind']}：{c['label']}" for c in changes]


# ---------------------------------------------------------------- 画面の上に出す警告
def translation_warning():
    """翻訳の設定がまだのとき、画面の上に注意の帯を出す。

    以前はサイドバーの下に小さく書いていたため、気づかないまま
    日本語だけで登録してしまうことがあった。
    """
    if engine:
        return
    if ui.notice("翻訳の設定がまだです。このまま保存すると**日本語だけ**で登録されます。",
                 kind="warn", action="翻訳を設定する", key="translation"):
        st.session_state["show_translation_help"] = True
    if st.session_state.get("show_translation_help"):
        st.info(
            "翻訳の設定は、管理画面を置いている人（管理者）が行います。\n\n"
            "Streamlit の「Settings → Secrets」に翻訳用のキーを入れると、"
            "この警告が消えて自動で翻訳されるようになります。"
            "設定が済むまでは日本語だけで保存し、あとで「まとめて翻訳する」から"
            "翻訳を足すこともできます。"
        )


# ---------------------------------------------------------------- ホーム
def page_home():
    """ホーム（中身は page_home.py）。今やることを並べる。"""
    from types import SimpleNamespace

    import page_home as H
    H.render(SimpleNamespace(
        book=book, items=items, engine=engine, store=store, unpublished=unpublished,
        log_source=log_source, translation_warning=translation_warning, pages=PAGE_REFS,
    ))


# ---------------------------------------------------------------- 画面レイアウト
# 据え置きのタブレットと観光客のスマートフォンでは、押しやすい大きさも
# 見せたいものも違う。設置場所ごとに画面の形を決められるようにする。

# 設置場所ごとに、先に出すプレビューの形。
# 据え置きはタブレット、観光客はスマートフォン。
LAYOUT_SHAPES = {
    "バスターミナル": "tablet-v",
    "であいの館": "tablet-v",
    "観光客": "phone",
}


@st.cache_data(show_spinner=False)
def character_thumb(name: str):
    """立ち絵の小さな写し（編集画面に出すため）。

    もとの絵は2MBある。編集のたびに送ると重いので、
    高さ320pxに縮めたものを作って使い回す。
    """
    import base64
    import io

    path = ROOT / "assets" / "character" / name
    if not path.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(path).convert("RGBA")
        ratio = img.width / img.height
        img.thumbnail((int(320 * ratio), 320))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        data = base64.b64encode(buf.getvalue()).decode("ascii")
        return {"url": f"data:image/png;base64,{data}",
                "aspect": round(ratio, 4)}
    except Exception:
        return None


def page_layout():
    ui.section("画面レイアウト",
               "設置形態ごとに、画面の並びと大きさを決めます。"
               "絵の中のブロックを直接つかんで動かせます。")

    rows = book.layouts()
    if not rows:
        st.warning("「画面レイアウト」シートがありません。"
                   "`python tools/add_layouts.py` で作れます。")
        return

    names = [r["place"] for r in rows]
    place = st.radio("どの端末の画面を直しますか", names, horizontal=True,
                     key="layout_place")
    current = next(r for r in rows if r["place"] == place)
    if current["note"]:
        st.caption(current["note"])

    # 立ち絵は、職員が決めた既定のものを出す（実際に立つ絵で確かめられるように）
    chars = book.characters()
    standing = next((c for c in chars if c["default"]), chars[0] if chars else None)
    thumb = character_thumb(standing["idle"]) if standing else None

    # 吹き出しの尻尾（△）の向く先。これは絵そのものの形なので、
    # 設置場所ごとではなく「キャラクター」シートに1つだけ持つ。
    tail = ({"mouth": standing["mouth"], "face": standing["face"]} if standing
            else {"mouth": 0.14, "face": 0.31})
    before = {k: current[k] for k in ("order", "heights", "character", "bubble")}
    before["tail"] = tail

    # 編集画面の印に、いまの設定の指紋を混ぜる。
    # 印が同じままだと、編集画面は最初に受け取った設定を持ち続け、
    # 保存や「最新の内容を読み直す」のあとも古い設定のまま動く。
    # そのまま次の保存をすると、古い設定で上書きしてしまう
    # （入力欄を出したのに、次の保存で消えていた）。
    import hashlib
    import json
    rev = hashlib.sha1(json.dumps(before, sort_keys=True, ensure_ascii=False)
                       .encode("utf-8")).hexdigest()[:10]
    edited = layout_editor(
        value=before,
        shape={"id": LAYOUT_SHAPES.get(place, "phone")},
        character=thumb or {},
        key=f"layout_{place}_{rev}",
        rev=rev,
    )
    # 古い編集画面から届いた値（指紋が違う）は使わない
    if not isinstance(edited, dict) or edited.get("rev") != rev:
        edited = before
    edited = {k: v for k, v in edited.items() if k != "rev"}

    if standing:
        st.caption(f"立ち絵は「{standing['name']}」で表示しています。"
                   "△（口の位置・顔の広さ）は**この立ち絵の形**なので、"
                   "どの端末でも同じ値が使われます。")
    else:
        st.caption("立ち絵の設定がありません")

    # 保存すると画面を作り直すので、知らせはここで出す
    # （作り直す前に出すと、出た瞬間に消えてしまう）。
    flash = st.session_state.pop("layout_saved", None)
    if flash:
        st.success(flash)

    changed = edited != before
    c1, c2 = st.columns([1, 3])
    if c1.button("この内容で保存", type="primary", disabled=not changed,
                 key=f"save_layout_{place}"):
        tail_moved = bool(standing) and edited.get("tail") != tail

        def apply_changes(fresh):
            # この画面を開いたあとに、別のタブなどで同じ端末の形が保存されていたら止める。
            # この画面の形をそのまま書くと、その保存を黙って消してしまうため。
            now = next((r for r in fresh.layouts() if r["place"] == place), None)
            if now is not None and any(now[k] != before[k]
                                       for k in ("order", "heights", "character", "bubble")):
                raise X.ExcelError(
                    f"この画面を開いたあとに、「{place}」の画面が別の所（別のタブなど）で"
                    "保存されています。上書きしないよう、保存を止めました。"
                    "左の「最新の内容を読み直す」を押してから、もう一度直してください。")
            fresh.update_layout(place, edited)
            # △は絵ごとの値なので、動かされたときだけ別に書く
            if tail_moved:
                fresh.update_character_shape(
                    standing["id"], edited["tail"]["mouth"], edited["tail"]["face"])

        try:
            save_book(apply_changes,
                      f"「{place}」の画面レイアウトを変更（管理画面より）")
            note = (f"△の位置は「{standing['name']}」の立ち絵に保存しました"
                    "（どの端末にも効きます）。") if tail_moved else ""
            st.session_state["layout_saved"] = (
                f"「{place}」の画面を保存しました。" + note
                + "「案内アプリへ反映する」で書き出すと案内端末に届きます。")
            st.rerun()
        except X.ExcelError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"保存できませんでした: {e}")
    c2.caption("動かしただけでは保存されません。"
               if changed else "まだ動かしていません。")

    with st.expander("数値で直す"):
        sheet_editor("画面レイアウト", title="画面レイアウト（表）",
                     note="編集画面で動かした結果がこの表に入ります。"
                          "細かい数字を直接入れたいときに使います。")


# ---------------------------------------------------------------- キャラクター
def page_character():
    ui.section("キャラクター",
               "案内画面に立つ絵です。絵を見ながら、案内端末を開いたときに立つものを選びます。"
               "利用者は案内画面で選び直せます。")

    chars = book.characters()
    if not chars:
        st.warning("「キャラクター」シートがありません。"
                   "`python tools/add_characters.py` で作れます。")
        return

    flash = st.session_state.pop("char_saved", None)
    if flash:
        ui.notice(flash, kind="ok", key="char-saved")

    per_row = 5
    for start in range(0, len(chars), per_row):
        cols = st.columns(per_row)
        for col, c in zip(cols, chars[start:start + per_row]):
            with col:
                with ui.card(f"ch-{c['id']}"):
                    thumb = character_thumb(c["idle"])
                    img = (f'<img src="{thumb["url"]}" style="height:170px;max-width:100%;'
                           'object-fit:contain;display:block;margin:0 auto">'
                           if thumb else
                           '<div style="height:170px;display:flex;align-items:center;'
                           'justify-content:center;color:#8A9A88">絵が見つかりません</div>')
                    st.markdown(f'<div style="background:#E9F0EA;border-radius:10px;'
                                f'padding:8px">{img}</div>', unsafe_allow_html=True)
                    faces = len({c["idle"], c.get("listening") or c["idle"],
                                 c.get("talking") or c["idle"]})
                    st.markdown(f'<div class="ui-tcell" style="margin-top:8px"><b>'
                                f'{escape(c["name"])}</b></div>'
                                f'<div class="ui-tsub">表情 {faces} 枚</div>',
                                unsafe_allow_html=True)
                    if c["default"]:
                        st.markdown(ui.badge("最初に立つ", "ok"), unsafe_allow_html=True)
                    elif st.button("最初に立たせる", key=f"char_pick_{c['id']}",
                                   use_container_width=True):
                        try:
                            save_book(lambda fresh, cid=c["id"]: fresh.set_default_character(cid),
                                      f"既定のキャラクターを{c['name']}に変更（管理画面より）")
                            st.session_state["char_saved"] = (
                                f"「{c['name']}」が最初に立つようにしました。"
                                "案内端末に届けるには「案内アプリへ反映する」を押してください。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"保存できませんでした: {e}")

    st.caption("表情が1枚のキャラクターは、聞き取り中・話している間も同じ絵で立ちます。"
               "吹き出しの△の向きは「画面レイアウト」で合わせられます。")
    with st.expander("表で細かく直す"):
        sheet_editor("キャラクター", title="キャラクター（表）",
                     note="画像は `assets/character/` に置きます。"
                          "「聞き取り中」「話している」は空欄でよく、"
                          "空なら「通常」の画像を使います。")


# ---------------------------------------------------------------- 追加・修正
def get_photo_store():
    """回答に付ける写真の置き場所（GitHub が設定されていれば GitHub）。"""
    from photo_store import GitHubPhotoStore, LocalPhotoStore
    token, repo = secret("github", "token"), secret("github", "repo")
    if token and repo:
        return GitHubPhotoStore(token, repo, secret("github", "branch", "main"), ROOT)
    return LocalPhotoStore(ROOT)


def page_add():
    """質問を追加・修正する画面（中身は page_question.py）。"""
    from types import SimpleNamespace

    import page_question
    page_question.render(SimpleNamespace(
        book=book, items=items, engine=engine, save_book=save_book,
        unpublished=unpublished, character_thumb=character_thumb,
        photos=get_photo_store(), translation_warning=translation_warning,
        list_page=PAGE_LIST,
    ))


# ---------------------------------------------------------------- 一覧
def page_list():
    """登録されている質問の一覧（中身は page_list.py）。"""
    from types import SimpleNamespace

    import page_list as L_page
    L_page.render(SimpleNamespace(
        book=book, items=items, done=done, save_book=save_book,
        unpublished=unpublished, add_page=PAGE_ADD,
    ))


# ---------------------------------------------------------------- まとめて翻訳
def page_bulk():
    """まとめて翻訳する画面（中身は page_bulk.py）。"""
    from types import SimpleNamespace

    import page_bulk as B
    B.render(SimpleNamespace(
        book=book, items=items, engine=engine, save_book=save_book,
        translation_warning=translation_warning,
    ))


# ---------------------------------------------------------------- 書き出し
def page_publish():
    """案内アプリへ反映する画面（中身は page_publish.py）。"""
    from types import SimpleNamespace

    import page_publish as P
    P.render(SimpleNamespace(
        items=items, root=ROOT, json_store=get_json_store(),
        published=published_summary, add_page=PAGE_ADD,
    ))


# ---------------------------------------------------------------- 利用状況
def log_source():
    """記録の読み出し先 (url, 合言葉)。

    ふだんは Secrets の [logs] から読む。
    CHAATBOT_LOGS_URL / CHAATBOT_LOGS_TOKEN を付けて起動したときだけ、そちらを使う
    （仮の記録を置いた試しの中継サーバで、画面を確かめるため）。
    """
    import os
    if os.environ.get("CHAATBOT_LOGS_URL"):
        return os.environ["CHAATBOT_LOGS_URL"], os.environ.get("CHAATBOT_LOGS_TOKEN", "")
    return secret("logs", "url"), secret("logs", "token")


def page_stats():
    """利用状況の画面（中身は page_stats.py）。"""
    from types import SimpleNamespace

    import page_stats as S
    url, token = log_source()
    S.render(SimpleNamespace(items=items, log_url=url, log_token=token, add_page=PAGE_ADD))


# ---------------------------------------------------------------- 読み上げの声
def _sample_audio(folder):
    """用意した音声の中から、試しに鳴らす1つを選ぶ。(ファイルの中身, 回答の書き出し)"""
    base = ROOT / "assets" / "audio" / folder if folder else ROOT / "assets" / "audio"
    for it in items:
        name = it.get("audio")
        if name and (base / name).exists():
            text = it["answer"].replace("\n", " ")
            return (base / name).read_bytes(), text[:30] + ("…" if len(text) > 30 else "")
    return None, ""


def page_voice():
    import speech

    ui.section("読み上げの声",
               "どの案内端末でも同じになるようにします。変えた声は、その場で聞いて確かめられます。")

    flash = st.session_state.pop("voice_saved", None)
    if flash:
        ui.notice(flash, kind="ok", key="voice-saved")

    with ui.card():
        # ---- 用意した音声（VOICEVOXなどで作ったもの）
        st.markdown("#### 用意した音声（日本語）")
        sets = book.voice_sets()
        if not sets:
            st.caption("「音声セット」シートがありません。"
                       "`python tools/make_voice.py` で音声を作ると登録されます。")
        else:
            st.caption("回答ごとに用意した音声のうち、どれを鳴らすかを決めます。"
                       "用意した音声が無い回答は、下の「端末の声」で読み上げます。")
            labels = [v["name"] for v in sets]
            folders = [v["folder"] for v in sets]
            now = next((i for i, v in enumerate(sets) if v["default"]), 0)
            c1, c2 = st.columns([1, 1.3], vertical_alignment="bottom")
            picked = c1.selectbox(
                "いつも鳴らす音声", range(len(sets)),
                index=now, format_func=lambda i: labels[i], key="voice_set_default",
            )
            data, label = _sample_audio(folders[picked])
            with c2:
                if data:
                    st.caption(f"聞いてみる：「{label}」")
                    st.audio(data, format="audio/mpeg")
                else:
                    st.caption("この音声のファイルが見つからないため、試しに鳴らせません。")
            if sets[picked]["note"]:
                st.caption(sets[picked]["note"])
            if picked != now:
                try:
                    save_book(lambda fresh: fresh.set_default_voice_set(folders[picked]),
                              f"既定の音声を{labels[picked]}に変更（管理画面より）")
                    st.session_state["voice_saved"] = f"「{labels[picked]}」を鳴らすようにしました。"
                    st.rerun()
                except Exception as e:
                    st.error(f"保存できませんでした: {e}")

    st.write("")

    with ui.card():
        # ---- 端末の声（言語ごと）
        st.markdown("#### 端末の声")
        st.caption("端末に入っている声は、端末ごとに違います。ここで決められるのは"
                   "「どれを優先するか」まで。書いた声が入っていない端末では、"
                   "その言語の声から自動で選びます。")

        rows = book.voice_settings()
        if not rows:
            st.caption("「読み上げ」シートがありません。"
                       "`python tools/add_voice_settings.py` で作れます。")
            return
        by_lang = {r["lang"]: r for r in rows}
        names = {"ja": "日本語", **T.LANGS}
        readings = [(a, b) for a, b, on in speech.clean_reading_rows(
            book.sheet_rows("読み方")[1]) if on]
        for lang in ["ja"] + list(T.LANGS):
            row = by_lang.get(lang)
            if row is None:
                continue
            with st.expander(f"{names.get(lang, lang)}", expanded=(lang == "ja")):
                ui.field_label("優先する声",
                               "上から順に探します。カンマで区切ります。名前の一部が合えば使います"
                               "（「Microsoft Aria」と書けば「Microsoft Aria - English」に当たります）。")
                voices = st.text_area("優先する声", value=row["voices"], height=70,
                                      key=f"voices_{lang}", label_visibility="collapsed")
                c1, c2 = st.columns(2)
                with c1:
                    ui.field_label("速さ", "1.0が標準。小さいほどゆっくり。")
                    rate = st.slider("速さ", 0.5, 1.5, float(row["rate"]), 0.05,
                                     key=f"rate_{lang}", label_visibility="collapsed")
                with c2:
                    ui.field_label("高さ", "1.0が標準。大きいほど高い声。")
                    pitch = st.slider("高さ", 0.5, 1.5, float(row["pitch"]), 0.05,
                                      key=f"pitch_{lang}", label_visibility="collapsed")

                # 保存する前の値で聞ける（つまみを動かしてすぐ確かめるため）
                sample = speech.SAMPLES.get(lang, "")
                if lang == "ja":
                    sample = speech.apply_readings(sample, readings)
                want = [v.strip() for v in voices.split(",") if v.strip()]
                c1, c2 = st.columns([1.3, 1], vertical_alignment="top")
                with c1:
                    speech.listen_button(sample, lang, want, rate, pitch,
                                         label="🔈 この設定で聞いてみる")
                changed = (voices.strip() != row["voices"].strip()
                           or abs(rate - float(row["rate"])) > 1e-9
                           or abs(pitch - float(row["pitch"])) > 1e-9)
                if c2.button("この設定を保存", type="primary", key=f"voice_save_{lang}",
                             disabled=not changed, use_container_width=True):
                    try:
                        save_book(
                            lambda fresh, lg=lang, v=voices, r=rate, pt=pitch:
                                fresh.update_voice_setting(lg, v, r, pt),
                            f"{names.get(lang, lang)}の読み上げ設定を変更（管理画面より）",
                        )
                        st.session_state["voice_saved"] = (
                            f"{names.get(lang, lang)}の声の設定を保存しました。"
                            "案内端末に届けるには「案内アプリへ反映する」を押してください。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存できませんでした: {e}")


# ---------------------------------------------------------------- その他の設定
# Excelを開かなくても、管理画面だけで設定を変えられるようにする。
# 表の形はExcelのままなので、どちらで直しても同じ結果になる。
SETTING_SHEETS = {
    "言い換え": {
        "説明": "観光客の言い方を、質問例に書かれている語へ橋渡しします。"
                "「銀行」と聞かれたら「atm」の質問に当てる、という具合です。",
        "注意": "「代表語」は**質問例に実際にある語**にしてください。"
                "無い語を書いても、どの質問にも当たりません。",
        "幅広": ["同じ意味の語", "備考"],
    },
    "設置場所": {
        "説明": "案内所の場所です。観光客の現在地から近い方の回答を選ぶのに使います。"
                "各言語の名前は、観光客の画面に出る表記です。",
        "注意": "「名前」はFAQシートの「設置場所」列と同じ文字にしてください。"
                "座標はGoogleマップで右クリック→座標をコピーで取れます。",
        "幅広": ["備考", "英語名", "中国語名", "韓国語名", "スペイン語名", "フランス語名"],
    },
    "参考資料": {
        "説明": "AIが答えを組み立てるときの下地です。質問回答集に無い聞かれ方"
                "（「雨の日は大丈夫ですか」など）に答えられるようになります。",
        "注意": "**ここに書いたことは、AIがそのまま根拠にします。**"
                "確かめていないことは書かないでください。"
                "`【質問回答集より】` で始まる行は自動で作られるので、直接直さないでください。",
        "幅広": ["内容", "備考"],
    },
    "読み方": {
        "説明": "読み上げの読み間違いを直します。合成音声は「荻町」を「はぎまち」、"
                "「朴葉味噌」を「ぼくようみそ」のように読んでしまうため、"
                "読み上げるときだけカタカナに差し替えます。",
        "注意": "**画面に出る文字は変わりません**（読み上げだけに使います）。"
                "「読み」はカタカナで書いてください。日本語の読み上げにだけ当てます。"
                "備考に「要確認」と書いてある行は、正しい読みを確かめてから使ってください。",
        "幅広": ["備考"],
    },
    "画面レイアウト": {
        "説明": "設置形態ごとの画面の並びと大きさです。"
                "ふだんは上の編集画面で動かして決めます。",
        "注意": "**値はすべて割合です**（高さ0.15なら画面の15%）。"
                "px で持つと、別の大きさの画面に移したときに崩れるためです。"
                "「設置場所」は案内アプリのURLに付ける名前と同じにしてください。",
        "幅広": ["並び順", "備考"],
    },
    "キャラクター": {
        "説明": "案内画面に立つキャラクターです。画像は `assets/character/` に置きます。"
                "「聞き取り中」「話している」は空欄でよく、空なら「通常」の画像を使います。",
        "注意": "「口の高さ」「顔の広さ」は吹き出しの尻尾を口元に向けるための値、"
                "「大きさ」は1.0が基準、「高さ位置」は0が下端・1が上端です。",
        "幅広": ["備考"],
    },
}

def sheet_editor(sheet, title=None, note=None):
    """表をそのまま直す部品。設定のシートはどれも同じ形なので1つで足りる。

    戻り値は、画面で直した（まだ保存していない）表。
    読み方の「聞いて確かめる」のように、保存する前の値で試したいときに使う。
    """
    import pandas as pd

    meta = SETTING_SHEETS[sheet]
    ui.section(title or sheet, meta["説明"] if note is None else note)
    st.info(meta["注意"])

    flash = st.session_state.pop(f"sheet_saved_{sheet}", None)
    if flash:
        ui.notice(flash, kind="ok", key=f"sheet-saved-{sheet}")

    titles, rows = book.sheet_rows(sheet)
    if not titles:
        st.error(f"「{sheet}」シートがありません。")
        return None

    frame = pd.DataFrame(rows, columns=titles) if rows else pd.DataFrame(columns=titles)
    config = {t: st.column_config.TextColumn(t, width="large" if t in meta["幅広"] else None)
              for t in titles}
    edited = st.data_editor(
        frame, column_config=config, num_rows="dynamic",
        use_container_width=True, hide_index=True, key=f"editor_{sheet}",
    )

    c1, c2 = st.columns([1, 3])
    if c1.button("この内容で保存", type="primary", key=f"save_{sheet}"):
        # すべて空の行は保存しない（表の下に出る入力用の空行を拾わないため）
        new_rows = [
            {t: ("" if pd.isna(v) else str(v)).strip() for t, v in record.items()}
            for record in edited.to_dict("records")
        ]
        new_rows = [r for r in new_rows if any(r.values())]
        try:
            save_book(lambda fresh: fresh.write_sheet(sheet, new_rows),
                      f"「{sheet}」を変更（管理画面より）")
            st.session_state[f"sheet_saved_{sheet}"] = (
                f"{len(new_rows)} 行を保存しました。"
                "案内端末に届けるには「案内アプリへ反映する」を押してください。")
            st.rerun()
        except X.ExcelError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"保存できませんでした: {e}")
    c2.caption("行の追加は表の一番下、削除は行を選んで Delete キーです。")
    return edited


# ---------------------------------------------------------------- 読み方
def page_readings():
    """読み方：表で直し、1行ずつ「直す前／直したあと」を聞き比べる。"""
    import speech

    ui.section("読み方",
               "合成音声が読み間違える言葉と、その正しい読みの表です。"
               "1行ずつ「直す前」と「直したあと」を聞き比べて確かめられます。")
    # 聞き比べの表を先に置き、その下に表の直し方を置く。
    # 聞き比べは、下で直した（まだ保存していない）内容で読むので、
    # 中身は下の表を作ってから入れる（先に場所だけ取っておく）。
    slot = st.container()
    st.write("")
    with st.expander("読み方を足す・直す（表）", expanded=False):
        edited = sheet_editor("読み方", title="読み方の表")
    if edited is None:
        return
    voices, rate, pitch = speech.voice_of(
        next((r for r in book.voice_settings() if r.get("lang") == "ja"), {}))
    with slot:
        with ui.card("yomi-listen"):
            st.caption("「直す前」で読み間違いを確かめ、「直したあと」で直った読みを聞きます。"
                       "取り消し線の行は「有効」が FALSE で、読み上げには当てません。"
                       "下の表で直すと、保存する前でもここで聞けます。")
            speech.readings_player(speech.clean_reading_rows(edited.to_dict("records")),
                                   voices, rate, pitch)


# ---------------------------------------------------------------- まとめたページ
# 「案内画面」の4つと「現地の情報」の3つは、それぞれ1ページにまとめ、
# 中を切り替えて使う（左の一覧が長くなりすぎて、探しにくかったため）。
SCREEN_TABS = {"layout": "画面レイアウト", "character": "キャラクター",
               "voice": "読み上げの声", "yomikata": "読み方"}
LOCAL_TABS = {"sanko": "参考資料", "basho": "設置場所", "iikae": "言い換え"}


def page_screen():
    ui.page_header("画面・キャラクター・声",
                   "案内端末の見た目と読み上げを決めます。"
                   "変えた結果は、その場で見たり聞いたりして確かめられます。")
    tab = ui.switch(SCREEN_TABS, key="screen_tab")
    st.write("")
    {"layout": page_layout, "character": page_character,
     "voice": page_voice, "yomikata": page_readings}[tab]()


def page_local():
    ui.page_header("現地の情報",
                   "AIが答えるときの下地や、案内所の場所、観光客の言い方を決めます。"
                   "最初に決めたら、ふだんはあまり触りません。")
    tab = ui.switch(LOCAL_TABS, key="local_tab")
    st.write("")
    sheet_editor({"sanko": "参考資料", "basho": "設置場所", "iikae": "言い換え"}[tab])


# ---------------------------------------------------------------- 画面の並び
# 役割ごとに4つへ分ける。
#
# 以前は横に7つのタブが並び、そのうち「その他の設定」の中にさらに5種類が
# 入っていた。毎日使うもの（質問を足す）と、最初に決めたら滅多に触らないもの
# （設置場所・言い換え）が同じ高さに並んでいたため、探すのに手間がかかった。
#
# いまは「毎日使うもの」を上、「決めたら触らないもの」を下にまとめてある。
# 一覧から「修正」で開く・追加の画面から一覧へ戻る、のように
# 画面どうしで行き来するため、行き先を名前で持っておく。
PAGE_ADD = st.Page(page_add, title="質問を追加・修正する", icon=":material/add_circle:")
PAGE_LIST = st.Page(page_list, title="登録されている質問", icon=":material/list:")

PAGE_HOME = st.Page(page_home, title="ホーム", icon=":material/home:", default=True)
PAGE_BULK = st.Page(page_bulk, title="まとめて翻訳する", icon=":material/translate:")
PAGE_SCREEN = st.Page(page_screen, title="画面・キャラクター・声", icon=":material/palette:",
                      url_path="screen")
PAGE_LOCAL = st.Page(page_local, title="現地の情報", icon=":material/map:", url_path="local")
PAGE_PUBLISH = st.Page(page_publish, title="案内アプリへ反映する", icon=":material/publish:")
PAGE_STATS = st.Page(page_stats, title="利用状況", icon=":material/bar_chart:")

PAGE_REFS = {"home": PAGE_HOME, "add": PAGE_ADD, "list": PAGE_LIST, "bulk": PAGE_BULK,
             "screen": PAGE_SCREEN, "local": PAGE_LOCAL, "publish": PAGE_PUBLISH,
             "stats": PAGE_STATS}

PAGES = {
    "": [PAGE_HOME],
    "質問と回答": [PAGE_ADD, PAGE_LIST, PAGE_BULK],
    "案内の設定": [PAGE_SCREEN, PAGE_LOCAL],
    "運用": [PAGE_PUBLISH, PAGE_STATS],
}

# expanded=True にしないと、画面の数が多いとき後ろが
# 「View 3 more」に畳まれて、「案内アプリへ反映する」が見えなくなる。
nav = st.navigation(PAGES, expanded=True)

# 「案内アプリへ反映する」の横に、まだ反映していない件数を出す。
# 保存しただけで終わったと思い、書き出しを忘れることが実際にあったため。
_pending = unpublished()
if _pending:
    ui.nav_badges({"page_publish": f"未反映 {len(_pending)}"})

with st.sidebar:
    st.divider()
    if st.button("最新の内容を読み直す", use_container_width=True,
                 help="Excel をほかの人が直したときや、別の画面で直したあとに押します。"):
        reload_book()
        st.rerun()

nav.run()
