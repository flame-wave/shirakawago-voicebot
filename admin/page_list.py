"""「登録されている質問」画面。

登録してある質問を表で見て、直したいものを開く画面。
「質問を追加・修正する」画面の、修正するときの入口でもある。

  ・項目名（回答の書き出し）を押すと、その質問が「修正」で開く
  ・状態はバッジで出す（案内中／期間外／案内に出さない／未反映）
  ・削除はしない。「案内から外す」で案内に出さないようにする
    （行を残しておけば、いつ何を案内していたかが分かり、あとで戻せる）
"""
from datetime import date
from html import escape

import streamlit as st

import faq_translate as T
import matcher
import ui
from faq_store import VALID_CATEGORIES

COMMON = "共通"
PER_PAGE = 25
# 表の列の幅（見出しと各行で同じ比にしないと、列がずれる）
WIDTHS = [3.6, 1.4, 1.2, 1.9, 0.7, 1.1, 1.8]
HEADS = ["項目名", "設置場所", "分類", "状態", "翻訳", "最終更新", ""]
SORTS = ["最終更新が新しい順", "登録した順", "設置場所ごと", "分類ごと"]
STATES = ["すべて", "案内中", "期間外", "案内に出さない"]


def _place_label(place, n_places):
    if (place or COMMON) == COMMON:
        return "両方の案内所" if n_places == 2 else "すべての案内所"
    return f"{place}だけ"


def _state(item, today):
    """(状態の名前, バッジの文字, 種類)"""
    if not item["enabled"]:
        return "案内に出さない", "案内に出さない", "mute"
    f, u = item["show_from"][:10], item["show_until"][:10]
    if (f and today < f) or (u and today > u):
        fmt = lambda d: f"{int(d[5:7])}/{int(d[8:10])}" if d else "…"
        return "期間外", f"期間外 {fmt(f)}〜{fmt(u)}", "info"
    return "案内中", "案内中", "ok"


def _head(answer, n=34):
    text = (answer or "").replace("\n", " ").strip()
    return (text[:n] + "…") if len(text) > n else (text or "（回答なし）")


def _updated(value):
    """最終更新を短く（10/07 14:20）。記録が無ければ —。"""
    if not value or len(value) < 16:
        return "—"
    return f"{value[5:7]}/{value[8:10]} {value[11:16]}"


def render(ctx):
    ss = st.session_state
    book, items, done = ctx.book, ctx.items, ctx.done
    today = date.today().isoformat()

    places = sorted({i["place"] or COMMON for i in items} - {COMMON})
    n_places = len(places)
    pending = {c.get("id") for c in (ctx.unpublished() or []) if c.get("id")}

    ui.page_header("登録されている質問",
                   "項目名を押すと、その質問を開いて直せます。")

    # ---- 知らせ（案内から外した・戻したあと）
    flash = ss.pop("l_flash", None)
    if flash:
        ui.notice(flash, kind="ok", key="l-flash")

    c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
    c1.markdown(" ".join([
        ui.badge(f"登録 {len(items)} 件", "mute"),
        ui.badge(f"案内中 {sum(1 for i in items if _state(i, today)[0] == '案内中')} 件", "ok"),
        ui.badge(f"未反映 {len(pending & {i['id'] for i in items})} 件", "warn")
        if pending else "",
    ]), unsafe_allow_html=True)
    if c2.button("＋ 質問を追加する", type="primary", use_container_width=True):
        st.switch_page(ctx.add_page)

    # ---- 絞り込み
    with ui.card("filter"):
        ui.field_label("キーワード", "回答や聞き方に入っている言葉で探します。")
        word = st.text_input("キーワード", key="l_word", placeholder="例：トイレ　バス",
                             label_visibility="collapsed")
        c1, c2, c3, c4 = st.columns(4)
        place_opts = ["すべて", COMMON] + places
        with c1:
            ui.field_label("設置場所")
            place = st.selectbox("設置場所", place_opts, key="l_place",
                                 format_func=lambda p: p if p == "すべて"
                                 else _place_label(p, n_places),
                                 label_visibility="collapsed")
        with c2:
            ui.field_label("分類")
            cat = st.selectbox("分類", ["すべて"] + list(VALID_CATEGORIES), key="l_cat",
                               format_func=lambda c: c if c == "すべて"
                               else VALID_CATEGORIES[c],
                               label_visibility="collapsed")
        with c3:
            ui.field_label("状態")
            state = st.selectbox("状態", STATES, key="l_state",
                                 label_visibility="collapsed")
        with c4:
            ui.field_label("並び順")
            sort = st.selectbox("並び順", SORTS, key="l_sort",
                                label_visibility="collapsed")
        c1, c2, _ = st.columns([1.4, 1.4, 2])
        lack = c1.checkbox("翻訳が足りないもの", key="l_lack")
        unpub = c2.checkbox("未反映のもの", key="l_unpub")

    # ---- 当てはまるものを選ぶ
    words = [matcher.normalize(w) for w in (word or "").replace("　", " ").split()
             if matcher.normalize(w)]
    shown = []
    for order, it in enumerate(items):
        if place != "すべて" and (it["place"] or COMMON) != place:
            continue
        if cat != "すべて" and it["category"] != cat:
            continue
        st_name = _state(it, today)[0]
        if state != "すべて" and st_name != state:
            continue
        n_tr = len(done.get(it["id"], set()) & set(T.LANGS))
        if lack and n_tr >= len(T.LANGS):
            continue
        if unpub and it["id"] not in pending:
            continue
        if words:
            hay = matcher.normalize(it["answer"] + " ".join(it["questions"]) + it["id"])
            if not all(w in hay for w in words):
                continue
        shown.append((order, it, n_tr))

    if sort == "最終更新が新しい順":
        # 記録の無いもの（管理画面でまだ保存していないもの）は、登録した順で後ろに
        dated = [x for x in shown if x[1]["updated"]]
        rest = [x for x in shown if not x[1]["updated"]]
        shown = sorted(dated, key=lambda x: x[1]["updated"], reverse=True) + rest
    elif sort == "設置場所ごと":
        shown.sort(key=lambda x: ((x[1]["place"] or COMMON) != COMMON, x[1]["place"], x[0]))
    elif sort == "分類ごと":
        keys = list(VALID_CATEGORIES)
        shown.sort(key=lambda x: (keys.index(x[1]["category"])
                                  if x[1]["category"] in keys else 99, x[0]))

    # 絞り込みを変えたら1ページ目に戻す
    sig = (word, place, cat, state, sort, lack, unpub)
    if ss.get("l_sig") != sig:
        ss.l_sig, ss.l_page = sig, 0
    pages = max(1, (len(shown) + PER_PAGE - 1) // PER_PAGE)
    ss.l_page = min(ss.get("l_page", 0), pages - 1)
    part = shown[ss.l_page * PER_PAGE:(ss.l_page + 1) * PER_PAGE]

    st.caption(f"{len(items)} 件のうち {len(shown)} 件を表示しています。")
    if not shown:
        ui.notice("当てはまる質問がありません。絞り込みを変えてください。", kind="info",
                  key="l-empty")
        return

    # ---- 表
    with ui.card("table"):
        cols = st.columns(WIDTHS)
        for c, h in zip(cols, HEADS):
            c.markdown(f'<div class="ui-thead">{h}</div>', unsafe_allow_html=True)

        for order, it, n_tr in part:
            fid = it["id"]
            st_name, st_text, st_kind = _state(it, today)
            with st.container(key=f"ui-trow-{fid}"):
                c = st.columns(WIDTHS, vertical_alignment="center")
                # 項目名を押すと「修正」で開く
                if c[0].button(_head(it["answer"]), key=f"l_open_{fid}", type="tertiary",
                               help="押すと、この質問を開いて直せます"):
                    st.switch_page(ctx.add_page, query_params={"id": fid})
                qs = "　".join(" ＋ ".join(q.split()) for q in it["questions"][:3])
                c[0].markdown(f'<div class="ui-tsub">{escape(qs)}</div>',
                              unsafe_allow_html=True)
                c[1].markdown(f'<div class="ui-tcell">{escape(_place_label(it["place"], n_places))}</div>',
                              unsafe_allow_html=True)
                c[2].markdown(f'<div class="ui-tcell">{escape(VALID_CATEGORIES.get(it["category"], "その他"))}</div>',
                              unsafe_allow_html=True)
                badges = ui.badge(st_text, st_kind)
                if fid in pending:
                    badges += " " + ui.badge("未反映", "warn")
                c[3].markdown(f'<div class="ui-tbadges">{badges}</div>', unsafe_allow_html=True)
                full = n_tr >= len(T.LANGS)
                c[4].markdown(f'<div class="ui-tcell {"" if full else "warn"}">'
                              f'{n_tr}/{len(T.LANGS)}</div>', unsafe_allow_html=True)
                c[5].markdown(f'<div class="ui-tcell sub">{_updated(it["updated"])}</div>',
                              unsafe_allow_html=True)
                _action(ctx, c[6], it, st_name)

    # ---- ページ送り
    if pages > 1:
        c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="center")
        if c1.button("← 前へ", disabled=ss.l_page == 0, use_container_width=True):
            ss.l_page -= 1
            st.rerun()
        c2.markdown(f'<div style="text-align:center">{ss.l_page + 1} / {pages} ページ</div>',
                    unsafe_allow_html=True)
        if c3.button("次へ →", disabled=ss.l_page >= pages - 1, use_container_width=True):
            ss.l_page += 1
            st.rerun()


def _action(ctx, col, item, state_name):
    """「案内から外す／案内に戻す」。押す前に確かめる（ポップアップの中で決める）。"""
    fid = item["id"]
    name = _head(item["answer"], 24)
    if item["enabled"]:
        with col.popover("案内から外す", use_container_width=True):
            st.markdown(f"**「{escape(name)}」を案内に出さないようにします。**")
            st.caption("削除ではありません。行は残るので、あとで「案内に戻す」で戻せます。"
                       "案内端末から消えるのは「案内アプリへ反映する」をしたときです。")
            if st.button("案内から外す", type="primary", key=f"l_hide_{fid}",
                         use_container_width=True):
                ctx.save_book(lambda fresh: fresh.set_enabled(fid, False),
                              f"案内から外す: {fid}（管理画面より）")
                st.session_state.l_flash = (f"「{name}」を案内から外しました。"
                                            "案内端末から消すには「案内アプリへ反映する」を押してください。")
                st.rerun()
    else:
        with col.popover("案内に戻す", use_container_width=True):
            st.markdown(f"**「{escape(name)}」を、また案内に出すようにします。**")
            st.caption("案内端末に出るのは「案内アプリへ反映する」をしたときです。")
            if st.button("案内に戻す", type="primary", key=f"l_show_{fid}",
                         use_container_width=True):
                ctx.save_book(lambda fresh: fresh.set_enabled(fid, True),
                              f"案内に戻す: {fid}（管理画面より）")
                st.session_state.l_flash = (f"「{name}」を案内に戻しました。"
                                            "案内端末に出すには「案内アプリへ反映する」を押してください。")
                st.rerun()
