"""キャラクターを足す・絵を差し替える・名前を直す・案内画面に出す出さない。

「キャラクター」の画面の、立ち絵のカードの下に置く。
職員さんが FTP やファイルを触らずに、ここだけで済むようにする。

【絵の置き場所】
上げた絵は GitHub（assets/character）に置く。案内アプリは、ロリポップに同じ絵が無ければ
GitHub から読むので（webapp/js/assets.js）、FTP で上げ直さなくても案内端末に出る。

【ファイル名】
差し替えのたびに、日時の入った新しい名前を付ける（例: c202610131530_idle_202610131530.png）。
案内端末は絵を1時間ほど覚えているので、同じ名前で上書きすると古い絵が出続けるため。

【大きさ】
大きすぎる絵（数MB）は、案内端末の読み込みが遅くなる。高さ1600pxまでに縮めて保存する。
背景が透けていない絵は、四角い背景のまま立つので、知らせる。
"""
import io
import re
from datetime import datetime
from html import escape

import streamlit as st

import faq_excel as X
import ui

MAX_HEIGHT = 1600
LANGS = [("en", "英語"), ("zh", "中国語"), ("ko", "韓国語"), ("es", "スペイン語"), ("fr", "フランス語")]
FACES = [("idle", "通常", "通常"), ("listening", "聞き取り中", "聞き取り中"), ("talking", "話している", "話している")]
# 絵の形ごとの、最初の値（あとで「画面レイアウト」の編集画面や表で合わせられる）
SHAPES = {
    "人物（全身の立ち絵）": {"口の高さ": 0.16, "顔の広さ": 0.30, "大きさ": 1.0, "高さ位置": 0.0},
    "ゆるキャラ・看板（顔が大きい）": {"口の高さ": 0.45, "顔の広さ": 0.9, "大きさ": 0.45, "高さ位置": 0.75},
}
NEW = "__new__"


def prepare(data: bytes):
    """上げた絵を、案内端末で使える形（PNG・高さ1600pxまで）にする。(PNGの中身, 透けているか, 縦横比)"""
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    img.load()
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA")
    if has_alpha:
        has_alpha = img.getchannel("A").getextrema()[0] < 255   # 本当に透けている所があるか
    if img.height > MAX_HEIGHT:
        img = img.resize((round(img.width * MAX_HEIGHT / img.height), MAX_HEIGHT), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), has_alpha, round(img.width / img.height, 4)


def file_name(cid: str, face: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", cid).strip("_").lower() or "char"
    return f"{safe}_{face}_{stamp}.png"


def render(book, save_book, store, thumb):
    ss = st.session_state
    ui.section("キャラクターを直す・足す",
               "立ち絵の差し替え、名前（各言語）の変更、案内画面に出す出さない、新しいキャラクターの追加ができます。"
               "上げた絵は、FTP を使わなくても案内端末に出ます（「案内アプリへ反映する」のあと）。")
    flash = ss.pop("chedit_flash", None)
    if flash:
        ui.notice(flash, kind="ok", key="chedit-flash")
    # 足したあとは、そのキャラクターを開いておく。
    # 選択の値は、その選択を描く前にしか変えられないので、次の作り直しのここで変える。
    added = ss.pop("chedit_added", None)
    if added:
        ss["chedit_pick"] = added

    chars = book.characters(include_hidden=True)
    options = [c["id"] for c in chars] + [NEW]
    label = {c["id"]: c["name"] + ("" if c["enabled"] else "（案内画面に出していない）") for c in chars}
    label[NEW] = "＋ 新しいキャラクターを足す"
    pick = st.selectbox("どのキャラクターを直しますか", options, format_func=label.get, key="chedit_pick")

    # 保存したら入力欄を空に戻す（上げた絵が欄に残ったまま、もう一度保存されないように）。
    # 欄の名前に回数を入れて、保存のたびに別の欄にする。
    ver = ss.setdefault("chedit_ver", 0)
    with ui.card("chedit"):
        if pick == NEW:
            _new(book, save_book, store, ver)
        else:
            _edit(book, save_book, store, thumb, next(c for c in chars if c["id"] == pick), ver)


def _image_inputs(key, current=None, thumb=None, required=False):
    """通常・聞き取り中・話している の絵を受け取る欄。{face: アップロードしたファイル or None}"""
    got = {}
    cols = st.columns(3)
    for col, (face, title, _) in zip(cols, FACES):
        with col:
            need = "（必ず）" if required and face == "idle" else "（なくてもよい）" if face != "idle" else ""
            ui.field_label(f"{title}の絵{need}",
                           "空なら通常の絵を使います" if face != "idle" else "背景が透けたPNGがおすすめです")
            name = (current or {}).get(face) or ""
            if current is not None:
                t = thumb(name) if name else None
                if t:
                    st.markdown(f'<div style="background:#E9F0EA;border-radius:8px;padding:6px;text-align:center">'
                                f'<img src="{t["url"]}" style="height:120px;max-width:100%;object-fit:contain"></div>',
                                unsafe_allow_html=True)
                    st.caption(name)
                else:
                    st.caption("（通常の絵を使っています）" if face != "idle" else "（絵が見つかりません）")
            got[face] = st.file_uploader(f"{title}の絵", type=["png", "webp", "jpg", "jpeg"],
                                         key=f"{key}_{face}", label_visibility="collapsed")
            if current is not None and face != "idle" and name:
                got[f"clear_{face}"] = st.checkbox("この絵を外して、通常の絵を使う", key=f"{key}_clear_{face}")
    return got


def _upload(store, cid, files):
    """上げられた絵を整えて保存する。({見出し: ファイル名}, 知らせ)"""
    values, notes = {}, []
    for face, title, column in FACES:
        f = files.get(face)
        if f is None:
            continue
        data, alpha, _ = prepare(f.getvalue())
        name = file_name(cid, face)
        store.save(name, data)
        values[column] = name
        if not alpha:
            notes.append(f"{title}の絵は背景が透けていないため、四角い背景のまま立ちます。")
    return values, notes


def _edit(book, save_book, store, thumb, c, ver):
    ss = st.session_state
    key = f"chedit_{c['id']}_{ver}"
    ui.field_label("名前（日本語）")
    name = st.text_input("名前", value=c["name"], key=f"{key}_name", label_visibility="collapsed")
    with st.expander("ほかの言語での名前（案内画面をその言語にしたときに出ます）"):
        names = {}
        cols = st.columns(len(LANGS))
        for col, (lang, title) in zip(cols, LANGS):
            names[lang] = col.text_input(title, value=c["names"].get(lang, ""), key=f"{key}_n_{lang}",
                                         placeholder="空なら日本語の名前")
    files = _image_inputs(key, {"idle": c["idle"], "listening": c.get("listening"),
                                "talking": c.get("talking")}, thumb)
    show = st.checkbox("案内画面に出す（利用者が選べる一覧に入れる）", value=c["enabled"], key=f"{key}_show",
                       disabled=c["default"],
                       help="最初に立つキャラクターは外せません。先にほかのキャラクターを「最初に立たせる」にしてください。")

    if st.button("この内容で保存", type="primary", key=f"{key}_save"):
        if not name.strip():
            st.error("名前を入れてください。")
            return
        try:
            with st.spinner("保存しています…"):
                values, notes = _upload(store, c["id"], files)
                for face, _, column in FACES:
                    if face != "idle" and files.get(f"clear_{face}") and column not in values:
                        values[column] = ""
                values["名前"] = name.strip()
                for lang, title in LANGS:
                    values[X.CHAR_NAME_COLS[lang]] = names[lang].strip()
                values["有効"] = "TRUE" if show else "FALSE"
                save_book(lambda fresh: fresh.update_character(c["id"], values),
                          f"キャラクター「{name.strip()}」を変更（管理画面より）")
        except Exception as e:
            st.error(f"保存できませんでした: {escape(str(e))}")
            return
        ss["chedit_flash"] = (f"「{escape(name.strip())}」を保存しました。" + "".join(notes)
                              + "案内端末に届けるには「案内アプリへ反映する」を押してください。")
        ss["chedit_ver"] = ver + 1
        st.rerun()


def _new(book, save_book, store, ver):
    ss = st.session_state
    k = f"chnew{ver}"
    ui.field_label("名前（日本語）", "案内画面のキャラクターの一覧に出る名前です。")
    name = st.text_input("名前", key=f"{k}_name", label_visibility="collapsed", placeholder="例：白川しろう")
    with st.expander("ほかの言語での名前（あとからでも入れられます）"):
        names = {}
        cols = st.columns(len(LANGS))
        for col, (lang, title) in zip(cols, LANGS):
            names[lang] = col.text_input(title, key=f"{k}_n_{lang}", placeholder="空なら日本語の名前")
    ui.field_label("絵の形", "吹き出しの△の向きと、立つ高さの最初の値が決まります。あとで「画面レイアウト」で合わせられます。")
    shape = st.radio("絵の形", list(SHAPES), key=f"{k}_shape", horizontal=True, label_visibility="collapsed")
    files = _image_inputs(k, required=True)
    show = st.checkbox("案内画面に出す（利用者が選べる一覧に入れる）", value=True, key=f"{k}_show")

    if st.button("このキャラクターを足す", type="primary", key=f"{k}_save"):
        if not name.strip() or files.get("idle") is None:
            st.error("名前と、通常の絵は必ず入れてください。")
            return
        cid = "c" + datetime.now().strftime("%Y%m%d%H%M")
        try:
            with st.spinner("保存しています…"):
                values, notes = _upload(store, cid, files)
                values.update({"名前": name.strip(), "ID": cid, "有効": "TRUE" if show else "FALSE",
                               "備考": "管理画面で追加", **SHAPES[shape]})
                for lang, title in LANGS:
                    if names[lang].strip():
                        values[X.CHAR_NAME_COLS[lang]] = names[lang].strip()
                save_book(lambda fresh: fresh.add_character(values),
                          f"キャラクター「{name.strip()}」を追加（管理画面より）")
        except Exception as e:
            st.error(f"足せませんでした: {escape(str(e))}")
            return
        ss["chedit_added"] = cid
        ss["chedit_ver"] = ver + 1
        ss["chedit_flash"] = (f"「{escape(name.strip())}」を足しました。" + "".join(notes)
                              + "吹き出しの△の向きは「画面レイアウト」で合わせられます。"
                              + "案内端末に届けるには「案内アプリへ反映する」を押してください。")
        st.rerun()
