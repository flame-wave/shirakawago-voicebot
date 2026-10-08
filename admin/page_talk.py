"""キャラクターの会話（「こんにちは」「ありがとう」などへの返事）。

「キャラクター」の画面の下に置く。質問回答集には入れず、キャラクターの側に持たせる。
（あいさつは案内ではないし、キャラクターごとに話し方を変えたいため）

  ・キャラクター（または「共通」）を選び、種類ごとに返事を書く（1行に1つ）
    何通りか書くと、案内アプリがその中から選んで答える（同じ返事ばかりにならない）
  ・あいさつ／お礼／名前／元気／さようなら のほかに、種類を自分で足せる
    （「好きな食べ物」など。聞き方＝どう言われたらその返事をするか、も書く）
  ・空のままの種類は「共通」の返事になる
  ・保存すると、新しく書いた返事と聞き方だけを自動で翻訳する（翻訳の設定があるとき）

どれにも当たらない話しかけは、AIの中継がキャラクターとして短く返す（ask.php の small_talk）。
中身は Excel の「会話」シート（tools/add_talk.py で作る）。
"""
import re
from html import escape

import streamlit as st

import build_faq as B
import faq_excel as X
import faq_translate as T
import ui

SHEET = "会話"
EXAMPLES = {
    "あいさつ": "「こんにちは」「Hello」「你好」など",
    "お礼": "「ありがとう」「Thank you」など",
    "名前": "「お名前は？」「Who are you?」など",
    "元気": "「元気？」「How are you?」など",
    "さようなら": "「さようなら」「Goodbye」など",
}
LANG_NAMES = {"en": "英語", "zh": "中国語", "ko": "韓国語", "es": "スペイン語", "fr": "フランス語"}
# 翻訳のあいだ {名前} を守るための目印（訳されないよう英字にしておく）
NAME_MARK = "{NAME}"
JAPANESE = re.compile(r"[぀-ヿ一-鿿]")


def _lines(text):
    return [w.strip() for w in str(text or "").splitlines() if w.strip()]


def _who_matches(row_who, cid, cname):
    return row_who in (cid, cname) or (cid == B.TALK_COMMON and row_who in ("", B.TALK_COMMON))


def _by_kind(rows, cid, cname):
    """{種類: [行, ...]}（そのキャラクターの行だけ）"""
    out = {}
    for r in rows:
        if _who_matches(r.get("キャラクター", ""), cid, cname) and r.get("種類"):
            out.setdefault(r["種類"], []).append(r)
    return out


def _phrases(rows):
    seen = []
    for r in rows:
        for w in _lines(r.get("聞き方")):
            if w not in seen:
                seen.append(w)
    return seen


def _translate(engine, replies, phrases):
    """新しい返事と聞き方を、ほかの言語へ訳す。

    replies … {鍵: 日本語の返事}、phrases … {種類: [日本語の聞き方]}
    戻り値 ({鍵: {言語: 返事}}, {種類: [各言語の聞き方]})
    """
    items = {f"r{i}": {"questions": [], "answer": text.replace("{名前}", NAME_MARK)}
             for i, text in enumerate(replies.values())}
    keys = dict(zip(items, replies))
    for j, (kind, words) in enumerate(phrases.items()):
        items[f"p{j}"] = {"questions": words, "answer": kind}
        keys[f"p{j}"] = kind
    if not items:
        return {}, {}
    done = T.translate(items, list(T.LANGS), engine)
    out_r, out_p = {}, {}
    for item, per in done.items():
        key = keys.get(item)
        if item.startswith("r"):
            had_name = "{名前}" in replies[key]
            out_r[key] = {}
            for lang, v in per.items():
                answer = v.get("answer") or ""
                # 訳の中で {名前} の目印が消えたら、その言語は入れない（共通の返事になる）
                if answer and not (had_name and NAME_MARK not in answer):
                    out_r[key][lang] = answer.replace(NAME_MARK, "{名前}")
        else:
            words = []
            for v in per.values():
                words += [w for w in (v.get("questions") or []) if isinstance(w, str) and w.strip()]
            out_p[key] = words
    return out_r, out_p


def render(book, engine, save_book):
    ss = st.session_state
    ui.section("会話（あいさつなど）",
               "話しかけられたときの返事です。質問回答集で見つからなかったときに使います。"
               "キャラクターごとに書けて、空のままの種類は「共通」の返事になります。"
               "どれにも当たらない話しかけには、AIがキャラクターとして短く返します。")

    titles, rows = book.sheet_rows(SHEET)
    if not titles:
        st.warning("「会話」シートがありません。`python tools/add_talk.py` で作れます。")
        return
    if "聞き方" not in titles:
        st.warning("「会話」シートが古い形です。`python tools/add_talk.py --recreate` で作り直してください。")
        return

    flash = ss.pop("talk_saved", None)
    if flash:
        ui.notice(flash, kind="ok", key="talk-saved")

    chars = book.characters()
    options = [B.TALK_COMMON] + [c["id"] for c in chars]
    names = {B.TALK_COMMON: "共通（全員）", **{c["id"]: c["name"] for c in chars}}
    who = st.radio("どのキャラクターの返事を書きますか", options, format_func=names.get,
                   horizontal=True, key="talk_who")
    cname = names[who] if who != B.TALK_COMMON else B.TALK_COMMON

    mine = _by_kind(rows, who, cname)
    common = _by_kind(rows, B.TALK_COMMON, B.TALK_COMMON)
    added = ss.setdefault(f"talk_added_{who}", [])
    custom = [k for k in list(common) + list(mine) + added if k not in B.TALK_KINDS]
    kinds = list(B.TALK_KINDS) + list(dict.fromkeys(custom))

    new_replies, new_phrases = {}, {}
    with ui.card("talk"):
        st.caption("返事は1行に1つ書きます。何通りか書くと、その中から選んで答えます。"
                   "{名前} と書くと、そのキャラクターの名前（選んでいる言語での名前）に置き換わります。"
                   "保存すると、新しく書いた返事はほかの5つの言語へ自動で翻訳します。")
        for kind in kinds:
            builtin = kind in B.TALK_KINDS
            ui.field_label(kind, EXAMPLES.get(kind, "自分で足した種類"))
            own_rows = mine.get(kind, [])
            saved = "\n".join(r.get("返事", "") for r in own_rows)
            base_rows = common.get(kind, [])
            fallback = " ／ ".join(r.get("返事", "") for r in base_rows)
            if not builtin:
                saved_p = "\n".join(_phrases(own_rows))
                new_phrases[kind] = st.text_area(
                    f"{kind}の聞き方", value=saved_p, key=f"talk_p_{who}_{kind}", height=68,
                    placeholder=("空なら共通の聞き方：" + " ／ ".join(_phrases(base_rows))
                                 if who != B.TALK_COMMON and base_rows
                                 else "どう言われたらこの返事をするか（1行に1つ。例：好きな食べ物は）"),
                    help="どう言われたらこの返事をするかを、1行に1つ書きます。どの言語でもかまいません。"
                         "日本語で書くと、保存するときにほかの言語の言い方も足します。")
            new_replies[kind] = st.text_area(
                f"{kind}の返事", value=saved, key=f"talk_r_{who}_{kind}", height=92,
                label_visibility="collapsed",
                placeholder=(f"空なら共通の返事：{fallback}" if who != B.TALK_COMMON and fallback
                             else "返事を書きます（1行に1つ）"))
            n = len(_lines(saved))
            if _lines(new_replies[kind]) != _lines(saved):
                st.caption("保存すると、新しい返事をほかの言語へ翻訳します。")
            elif n:
                done = sum(1 for r in own_rows if all(r.get(B.TALK_COLUMNS[l]) for l in LANG_NAMES))
                st.caption(f"返事 {n} 通り・翻訳がそろっているもの {done} 通り")
            elif who != B.TALK_COMMON and base_rows:
                st.caption(f"共通の返事（{len(base_rows)} 通り）を使います。")

        changed = any(_lines(new_replies[k]) != _lines("\n".join(r.get("返事", "") for r in mine.get(k, [])))
                      for k in kinds) or any(
            _lines(new_phrases[k]) != _phrases(mine.get(k, [])) for k in new_phrases)
        c1, c2 = st.columns([1, 3])
        if c1.button("この返事で保存", type="primary", disabled=not changed,
                     key=f"talk_save_{who}", use_container_width=True):
            _save(engine, save_book, who, names[who], mine, kinds, new_replies, new_phrases)
        c2.caption("保存しただけでは案内端末に届きません。最後に「案内アプリへ反映する」を押します。"
                   if changed else "まだ直していません。")

    with ui.card("talk-add"):
        ui.field_label("会話の種類を足す", "例：好きな食べ物／趣味／好きな季節")
        a, b = st.columns([3, 1], vertical_alignment="bottom")
        name = a.text_input("種類の名前", key=f"talk_new_{who}", label_visibility="collapsed",
                            placeholder="種類の名前（例：好きな季節）")
        if b.button("＋ 足す", key=f"talk_add_{who}", use_container_width=True,
                    disabled=not name.strip() or name.strip() in kinds):
            added.append(name.strip())
            st.rerun()
        st.caption("足したら、上に出る欄に「聞き方」と「返事」を書いて保存します。"
                   "返事を空にして保存すると、その種類は消えます。")

    with st.expander("会話の表を直接直す"):
        st.caption("各言語の返事を、自動翻訳ではなく自分で直したいときに使います。")
        _table(save_book, titles, rows)


def _save(engine, save_book, who, label, mine, kinds, new_replies, new_phrases):
    ss = st.session_state
    # 翻訳が要るのは、前に無かった返事と、変わった聞き方（日本語の分）だけ
    old_text = {r.get("返事", ""): r for rows in mine.values() for r in rows}
    fresh_lines = {f"{k}\n{line}": line for k in kinds for line in _lines(new_replies[k])
                   if line not in old_text}
    fresh_phrases = {k: [w for w in _lines(v) if JAPANESE.search(w)]
                     for k, v in new_phrases.items() if _lines(v) != _phrases(mine.get(k, []))}
    fresh_phrases = {k: v for k, v in fresh_phrases.items() if v}

    translated, more_phrases, note = {}, {}, ""
    if (fresh_lines or fresh_phrases) and engine:
        try:
            with st.spinner("ほかの言語へ翻訳しています…"):
                translated, more_phrases = _translate(engine, fresh_lines, fresh_phrases)
        except Exception as e:
            note = f"翻訳はできませんでした（{escape(str(e)[:80])}）。"
    elif fresh_lines:
        note = "翻訳の設定が無いため、ほかの言語は共通の返事になります。"

    def apply(fresh):
        titles, rows = fresh.sheet_rows(SHEET)
        if not titles:
            raise X.ExcelError("「会話」シートがありません")
        cname = label if who != B.TALK_COMMON else B.TALK_COMMON
        keep = [r for r in rows if not _who_matches(r.get("キャラクター", ""), who, cname)]
        for kind in kinds:
            phrases = _lines(new_phrases.get(kind, ""))
            for w in more_phrases.get(kind, []):
                if w not in phrases:
                    phrases.append(w)
            for line in _lines(new_replies[kind]):
                old = old_text.get(line, {})
                row = {t: "" for t in titles}
                row.update({"種類": kind, "キャラクター": who, "聞き方": "\n".join(phrases),
                            "返事": line, "備考": old.get("備考", "")})
                done = translated.get(f"{kind}\n{line}", {})
                for lang, col in B.TALK_COLUMNS.items():
                    if lang != "ja" and col in row:
                        row[col] = done.get(lang) or old.get(col, "")
                keep.append(row)
        fresh.write_sheet(SHEET, keep)

    try:
        save_book(apply, f"「{label}」の会話を変更（管理画面より）")
    except X.ExcelError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"保存できませんでした: {e}")
        return
    ss.pop(f"talk_added_{who}", None)
    ss["talk_saved"] = (f"「{label}」の返事を保存しました。{note}"
                        "案内端末に届けるには「案内アプリへ反映する」を押してください。")
    st.rerun()


def _table(save_book, titles, rows):
    import pandas as pd
    frame = pd.DataFrame(rows, columns=titles) if rows else pd.DataFrame(columns=titles)
    edited = st.data_editor(frame, num_rows="dynamic", use_container_width=True,
                            hide_index=True, key="editor_talk")
    if st.button("この表で保存", key="talk_table_save"):
        new_rows = [{t: ("" if pd.isna(v) else str(v)).strip() for t, v in r.items()}
                    for r in edited.to_dict("records")]
        new_rows = [r for r in new_rows if any(r.values())]
        try:
            save_book(lambda fresh: fresh.write_sheet(SHEET, new_rows),
                      "「会話」を変更（管理画面より）")
            st.session_state["talk_saved"] = (f"{len(new_rows)} 行を保存しました。"
                                              "案内端末に届けるには「案内アプリへ反映する」を押してください。")
            st.rerun()
        except Exception as e:
            st.error(f"保存できませんでした: {e}")
