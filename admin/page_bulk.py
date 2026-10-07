"""「まとめて翻訳する」画面。

① 翻訳するものを選ぶ … 翻訳が要るものを理由つきで並べ、費用の目安を見てから実行する
② 訳を確かめる     … 日本語と訳を並べて見て、直して「確認しました」にする

【「要確認」の印】
自動翻訳した訳には、Excel の多言語シートの備考に「自動翻訳（要確認）」と入る。
職員さんが確かめて「確認しました」を押すと、この印が外れる。
訳したときの日本語（日本語原文）は残しておき、あとで日本語の回答が変わったら
「回答が変わった」として ① に出てくる（訳し直しが要ると分かるように）。

【翻訳は Claude Haiku】
安いぶん固有名詞を間違えやすいので、② で地名・施設名を必ず確かめてもらう。
"""
from html import escape

import streamlit as st

import faq_translate as T
import ui

PER_PAGE = 5
REASONS = {
    "new": ("新しく追加", "info"),
    "changed": ("回答が変わった", "warn"),
    "lack": ("翻訳が足りない", "mute"),
}
STATE_MARK = {"none": "未", "changed": "変", "machine": "要確認", "ok": "済"}


def _head(answer, n=40):
    text = (answer or "").replace("\n", " ").strip()
    return (text[:n] + "…") if len(text) > n else text


def _lang_name(lang):
    return T.LANGS[lang].split("（")[0]


def _targets(items, status, langs):
    """翻訳が要るもの。[(ID, 理由, 訳す言語)]

    案内に出さないものは訳さない（出さないものに費用をかけないため）。
    """
    out = []
    for it in items:
        if not it["enabled"] or not it["answer"].strip():
            continue
        per = status.get(it["id"], {})
        need = [l for l in langs if per.get(l) in ("none", "changed")]
        if not need:
            continue
        if all(per.get(l) == "none" for l in langs):
            reason = "new"
        elif any(per.get(l) == "changed" for l in langs):
            reason = "changed"
        else:
            reason = "lack"
        out.append((it["id"], reason, need))
    return out


def _yen(low, high):
    if high < 1:
        return "1円未満"
    if high < 10:
        return f"約 {max(1, round(low))}〜{round(high)} 円"
    return f"約 {round(low, -1):.0f}〜{round(high, -1):.0f} 円"


def _forget(fid):
    """訳し直したあと、画面に残っている入力欄の中身を捨てる（新しい訳を出すため）。"""
    for key in [k for k in st.session_state if k.startswith(f"b_{fid}_")]:
        del st.session_state[key]


def _run(ctx, jobs, by_id):
    """翻訳して保存する。jobs は [(ID, 訳す言語)]。

    言語の組み合わせごとにまとめて頼む。途中で止まっても、
    それまでに訳せた分は保存する（費用を無駄にしないため）。
    """
    groups = {}
    for fid, langs in jobs:
        groups.setdefault(tuple(langs), []).append(fid)

    total = len(jobs)
    finished = {}
    bar = st.progress(0.0, text=f"翻訳しています… 0 / {total} 件")
    error = ""
    try:
        for langs, fids in groups.items():
            payload = {f: {"questions": by_id[f]["questions"], "answer": by_id[f]["answer"]}
                       for f in fids}

            def tick(done, _all, merged, base=len(finished)):
                bar.progress(min(1.0, (base + done) / total),
                             text=f"翻訳しています… {base + done} / {total} 件")
                for f, per in merged.items():
                    finished[f] = (per, list(langs))

            T.translate(payload, list(langs), ctx.engine, progress=tick)
    except Exception as e:
        error = str(e)
    bar.empty()

    if finished:
        def apply_changes(fresh):
            for fid, (per, langs) in finished.items():
                for lang in langs:
                    v = per.get(lang) or {}
                    if not v.get("answer"):
                        continue
                    fresh.upsert_translation(
                        fid, lang, v.get("questions", []), v["answer"], machine=True,
                        source_answer=by_id[fid]["answer"])
        try:
            ctx.save_book(apply_changes, f"自動翻訳 {len(finished)} 件（管理画面より）")
            _ = [_forget(fid) for fid in finished]
        except Exception as e:
            st.session_state.b_flash_warn = (
                f"翻訳はできましたが、保存できませんでした（{str(e)[:100]}）。"
                "「最新の内容を読み直す」を押してから、もう一度お試しください。")
            st.rerun()

    ss = st.session_state
    ss.b_recent = list(finished) + [f for f in ss.get("b_recent", []) if f not in finished]
    if finished:
        ss.b_flash = ("ok", f"{len(finished)} 件を翻訳しました。"
                            "下の「② 訳を確かめる」で、日本語と並べて確かめてください。")
    if error:
        ss.b_flash_warn = (f"翻訳の途中で止まりました（{error[:100]}）。"
                           + ("訳せた分は保存してあります。" if finished else "")
                           + "少し待ってから、もう一度お試しください。")
    st.rerun()


def render(ctx):
    ss = st.session_state
    langs = list(T.LANGS)
    items = ctx.items
    by_id = {i["id"]: i for i in items}
    status = ctx.book.translation_status(langs)

    ui.page_header("まとめて翻訳する",
                   "翻訳が要るものを選んで、5つの言語にまとめて翻訳します。"
                   "訳したあとは、日本語と並べて確かめます。")
    ctx.translation_warning()

    flash = ss.pop("b_flash", None)
    if flash:
        ui.notice(flash[1], kind=flash[0], key="b-flash")
    warn = ss.pop("b_flash_warn", None)
    if warn:
        ui.notice(warn, kind="warn", key="b-flash-warn")

    targets = _targets(items, status, langs)
    review = [i["id"] for i in items
              if any(v == "machine" for v in status.get(i["id"], {}).values())]
    checked = sum(1 for i in items
                  if status.get(i["id"]) and all(v == "ok" for v in status[i["id"]].values()))
    ui.tiles([
        ("翻訳が要るもの", f"{len(targets)} 件", "① で翻訳します"),
        ("確かめ待ち", f"{len(review)} 件", "② で日本語と見比べます"),
        ("確かめ済み", f"{checked} 件", f"登録 {len(items)} 件のうち"),
    ])
    st.write("")

    # ================================================================ ①
    with ui.card("b1"):
        ui.step(1, "翻訳するものを選ぶ",
                note="理由ごとに並べています。選んだものだけを翻訳します。"
                     "案内に出さない質問は並びません。")
        if not targets:
            st.markdown(ui.box("翻訳が要るものはありません",
                               "新しく追加した質問や、日本語の回答を直した質問があると、ここに出ます。",
                               "ok"), unsafe_allow_html=True)
        else:
            c1, c2, _ = st.columns([1, 1, 3])
            if c1.button("すべて選ぶ", key="b_all", use_container_width=True):
                for fid, _r, _l in targets:
                    ss[f"b_pick_{fid}"] = True
                st.rerun()
            if c2.button("すべて外す", key="b_none", use_container_width=True):
                for fid, _r, _l in targets:
                    ss[f"b_pick_{fid}"] = False
                st.rerun()

            picked = []
            for fid, reason, need in targets:
                it = by_id[fid]
                with ui.keyed_box(f"ui-trow-b{fid}"):
                    c = st.columns([0.5, 5, 1.6, 2.4], vertical_alignment="center")
                    key = f"b_pick_{fid}"
                    if key not in ss:
                        ss[key] = True
                    on = c[0].checkbox("選ぶ", key=key, label_visibility="collapsed")
                    c[1].markdown(f'<div class="ui-tcell"><b>{escape(_head(it["answer"]))}</b></div>',
                                  unsafe_allow_html=True)
                    c[2].markdown(ui.badge(*REASONS[reason]), unsafe_allow_html=True)
                    c[3].markdown('<div class="ui-tcell sub">'
                                  + ("5つの言語すべて" if len(need) == len(langs)
                                     else "・".join(_lang_name(l) for l in need))
                                  + "</div>", unsafe_allow_html=True)
                    if on:
                        picked.append((fid, need))

            payload = {f: {"questions": by_id[f]["questions"], "answer": by_id[f]["answer"]}
                       for f, _ in picked}
            pairs = sum(len(n) for _, n in picked)
            low, high = (0.0, 0.0)
            for need in {tuple(n) for _, n in picked}:
                part = {f: payload[f] for f, n in picked if tuple(n) == need}
                l, h = T.estimate(part, list(need))
                low, high = low + l, high + h
            st.write("")
            st.markdown(ui.box(
                f"選んだもの：{len(picked)} 件（のべ {pairs} 言語）",
                f"費用の目安：<b>{_yen(low, high)}</b>"
                f"（Claude Haiku の料金・1ドル{T.YEN_PER_USD}円で計算したおおよその額です）",
                "info"), unsafe_allow_html=True)
            if not ctx.engine:
                st.caption("翻訳の設定がまだのため、いまは翻訳できません。")
            if st.button("選んだものを翻訳する", type="primary", key="b_run",
                         disabled=not (ctx.engine and picked), use_container_width=True):
                _run(ctx, picked, by_id)

    # ================================================================ ②
    with ui.card("b2"):
        ui.step(2, "訳を確かめる",
                note="自動翻訳には「要確認」の印が付いています。日本語と見比べ、"
                     "地名・施設名・料金・時間が合っているかを確かめて「確認しました」を押します。"
                     "直したいところは、その場で書き直せます。")
        if not review:
            st.markdown(ui.box("確かめ待ちの訳はありません", "", "ok"), unsafe_allow_html=True)
            return

        recent = [f for f in ss.get("b_recent", []) if f in review]
        order = recent + [f for f in review if f not in recent]
        pages = (len(order) + PER_PAGE - 1) // PER_PAGE
        page = min(ss.get("b_page", 0), pages - 1)
        st.caption(f"確かめ待ち {len(order)} 件"
                   + (f"（{page + 1} / {pages} ページ）" if pages > 1 else ""))
        for fid in order[page * PER_PAGE:(page + 1) * PER_PAGE]:
            _review_one(ctx, fid, by_id[fid], status[fid], langs, fid in recent)

        if pages > 1:
            c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="center")
            if c1.button("← 前へ", key="b_prev", disabled=page == 0, use_container_width=True):
                ss.b_page = page - 1
                st.rerun()
            if c3.button("次へ →", key="b_next", disabled=page >= pages - 1,
                         use_container_width=True):
                ss.b_page = page + 1
                st.rerun()


def _review_one(ctx, fid, item, per, langs, is_recent):
    """1件ぶん。左に日本語、右に言語ごとの訳。"""
    ss = st.session_state
    saved = ctx.book.translations_of(fid)
    waiting = [l for l in langs if per.get(l) == "machine"]

    with ui.card(f"rv-{fid}"):
        badges = ui.badge(f"要確認 {len(waiting)} 言語", "warn")
        if is_recent:
            badges += " " + ui.badge("いま翻訳した", "info")
        st.markdown(f'<div class="ui-tcell" style="margin-bottom:8px"><b>'
                    f'{escape(_head(item["answer"], 50))}</b>　{badges}</div>',
                    unsafe_allow_html=True)
        left, right = st.columns([1, 1.35], gap="medium")
        with left:
            qs = "　".join(" ＋ ".join(q.split()) for q in item["questions"])
            st.markdown(
                f'<div class="ui-notice small info"><b>日本語</b>{escape(item["answer"])}'
                f'<div style="margin-top:8px;color:#4A5648;font-size:13px">聞き方：{escape(qs)}</div>'
                f"</div>", unsafe_allow_html=True)
        with right:
            # 「（要確認）」と書くと5言語ぶん並ばないので、印で示す
            mark = {"machine": " ⚠", "changed": " ⚠", "none": " －", "ok": " ✓"}
            tabs = st.tabs([f"{_lang_name(l)}{mark.get(per.get(l), '')}" for l in langs])
            st.caption("⚠ 要確認　✓ 確かめ済み　－ 訳がまだない")
            for tab, lang in zip(tabs, langs):
                with tab:
                    tr = saved.get(lang) or {}
                    state = per.get(lang)
                    if state == "none":
                        st.caption("まだ訳がありません。①から翻訳できます。")
                        continue
                    if state == "changed":
                        st.markdown(ui.box("", "訳したあとで日本語の回答が変わりました。"
                                               "① から訳し直してください。", "warn"),
                                    unsafe_allow_html=True)
                    ui.field_label("回答")
                    st.text_area("回答", value=tr.get("answer", ""), height=110,
                                 key=f"b_{fid}_{lang}_a", label_visibility="collapsed")
                    ui.field_label("聞き方", "1行に1つ。空白でつないだ言葉は「かつ」の意味です。")
                    st.text_area("聞き方", value="\n".join(tr.get("questions", [])), height=90,
                                 key=f"b_{fid}_{lang}_q", label_visibility="collapsed")
                    c1, c2 = st.columns(2)
                    if c1.button("確認しました" if state == "machine" else "直した訳を保存",
                                 type="primary", key=f"b_{fid}_{lang}_ok",
                                 use_container_width=True):
                        _confirm(ctx, fid, [lang])
                    if c2.button("この言語を訳し直す", key=f"b_{fid}_{lang}_re",
                                 disabled=not ctx.engine, use_container_width=True,
                                 help=None if ctx.engine else "翻訳の設定がまだのため使えません"):
                        _run(ctx, [(fid, [lang])], {fid: item})

        c1, c2, _ = st.columns([1.6, 1.6, 2])
        if waiting and c1.button(f"{len(waiting)}言語まとめて確認しました", type="primary",
                                 key=f"b_{fid}_okall", use_container_width=True):
            _confirm(ctx, fid, waiting)
        if c2.button("この質問を訳し直す", key=f"b_{fid}_reall", disabled=not ctx.engine,
                     use_container_width=True,
                     help=None if ctx.engine else "翻訳の設定がまだのため使えません"):
            _run(ctx, [(fid, langs)], {fid: item})


def _confirm(ctx, fid, langs):
    """確かめ済みにする。画面で直した訳があれば、それも保存する。"""
    ss = st.session_state

    def apply_changes(fresh):
        for lang in langs:
            answer = ss.get(f"b_{fid}_{lang}_a")
            qtext = ss.get(f"b_{fid}_{lang}_q")
            questions = None if qtext is None else [q.strip() for q in qtext.splitlines()]
            fresh.confirm_translation(fid, lang, questions=questions, answer=answer)

    try:
        ctx.save_book(apply_changes, f"訳を確認: {fid}（管理画面より）")
    except Exception as e:
        ss.b_flash_warn = (f"保存できませんでした（{str(e)[:100]}）。"
                           "「最新の内容を読み直す」を押してから、もう一度お試しください。")
        st.rerun()
    _forget(fid)
    names = "・".join(_lang_name(l) for l in langs)
    ss.b_flash = ("ok", f"{names}の訳を、確かめ済みにしました。"
                        "案内端末に出すには「案内アプリへ反映する」を押してください。")
    st.rerun()
