"""「利用状況」画面。

案内端末で何が聞かれたかを、案内所ごとに見る。
いちばん大事なのは「答えられなかった質問」で、それを質問回答集に足すと
答えられる割合が上がる。その質問は、ここから直接「質問を追加する」画面へ渡せる。

記録は中継サーバ（server/api/logs.php）から読む。案内端末の画面からは見られない。

【記録を消す】
本番を始める前に、試しの頃の記録を消せるようにしてある。
消すと、中継サーバはその時点（または指定の日）より前の時刻の記録を受け取らなくなる。
案内端末に送れずに残っていた古い記録が、あとで届いて戻ってくることも無い。

【グラフの色】
色は案内所に付ける（並び順や多い順では変えない）。log_stats.CLIENT_COLORS を参照。
色だけで見分けなくて済むよう、凡例を出し、数の表も添える。
"""
import csv
import io
from datetime import date, datetime, timedelta, timezone
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import log_stats as L
import ui

LANG_NAMES = {"ja": "日本語", "en": "英語", "zh": "中国語", "ko": "韓国語",
              "es": "スペイン語", "fr": "フランス語"}
PERIODS = {"7": "直近7日", "30": "直近30日", "all": "すべて"}
JST = timezone(timedelta(hours=9))


FRESH_SECONDS = 60   # 一度読んだ記録を使い回す長さ


def load_rows(url, token, force=False, kind="question"):
    """記録を読む。kind="ai" なら、AIが答えた分の記録（質問と答え）。

    画面を作り直すたびに読みに行くと遅いので、少しの間だけ持っておく。
    以前はずっと持ち続けていたため、「記録を読み直す」を押さないと
    新しい質問が出てこず、記録が届いていないように見えた。
    """
    import time
    ss = st.session_state
    key = "log_rows" if kind == "question" else f"log_rows_{kind}"
    error = "log_error" if kind == "question" else f"log_error_{kind}"
    stale = time.time() - ss.get(f"{key}_at", 0) > FRESH_SECONDS
    if force or stale:
        ss.pop(key, None)
    if key not in ss:
        try:
            ss[key] = L.fetch(url, token, kind=kind)
            ss[error] = ""
        except Exception as e:
            ss[key] = []
            ss[error] = str(e)
        ss[f"{key}_at"] = time.time()
    return ss[key]


def _day(row):
    """記録の日付（日本時間）。"""
    at = L._when(row)
    return at.astimezone(JST).date() if at else None


def _label(items_by_id, fid, n=34):
    it = items_by_id.get(fid)
    if not it:
        return "（いまは無い質問）"
    text = (it["answer"] or "").replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def _color(client):
    return L.CLIENT_COLORS.get(client, L.OTHER_COLOR)


def render(ctx):
    ss = st.session_state
    ui.page_header("利用状況",
                   "案内端末で何が聞かれたかを、案内所ごとに見ます。"
                   "案内端末の画面からは見られないようにしてあります。")

    if not ctx.log_url or not ctx.log_token:
        ui.notice("記録の読み出し先が、まだ設定されていません。"
                  "中継サーバ（ロリポップの api/）を置いたあと、Streamlit の"
                  "「Settings → Secrets」に <b>[logs]</b> の url と token を入れると見られます。",
                  kind="info", key="stats-nosetup")
        return

    flash = ss.pop("stats_flash", None)
    if flash:
        ui.notice(flash, kind="ok", key="stats-flash")

    c1, c2 = st.columns([4, 1.3], vertical_alignment="center")
    with c1:
        period = st.segmented_control("期間", list(PERIODS), format_func=PERIODS.get,
                                      key="stats_period", default="30",
                                      label_visibility="collapsed") or "30"
    if c2.button("記録を読み直す", use_container_width=True, key="stats_reload"):
        load_rows(ctx.log_url, ctx.log_token, force=True)
        load_rows(ctx.log_url, ctx.log_token, force=True, kind="ai")
        st.rerun()

    all_rows = load_rows(ctx.log_url, ctx.log_token)
    if ss.get("log_error"):
        ui.notice(f"記録を読めませんでした（{ss.log_error[:120]}）", kind="warn", key="stats-err")
        return

    days = None if period == "all" else int(period)
    rows = L.within(all_rows, days)
    items_by_id = {i["id"]: i for i in ctx.items}

    if not rows:
        ui.notice("この期間の記録はまだありません。", kind="info", key="stats-empty")
    else:
        _overview(rows)
        _daily(rows, days)
        _by_place_and_lang(rows)
        _top(ctx, rows, items_by_id)
        _unmatched(ctx, rows)
        _ai_answers(ctx, days)
        _only_here(rows)

    st.write("")
    _housekeeping(ctx, all_rows)


# ---------------------------------------------------------------- 全体
def _overview(rows):
    s = L.summarize(rows)
    by = s["by_source"]
    ui.tiles([
        ("質問の総数", f"{s['total']} 件", "この期間"),
        ("その場で答えられた", f"{s['answered_rate']:.0%}", "質問回答集かAIで答えた割合"),
        ("AIが答えた", f"{by.get('ai', 0)} 件", "質問回答集に無かったもの"),
        ("職員へ回った", f"{by.get('none', 0)} 件", "答えを足す候補です"),
    ])
    st.write("")


def _daily(rows, days):
    """日ごとの件数（案内所ごとに積み上げ）。"""
    counts = {}
    for r in rows:
        d = _day(r)
        if d is None:
            continue
        key = (d, str(r.get("client") or "不明"))
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return
    clients = L.clients_in(rows)
    # 記録の無い日も0件として並べる（日が飛ぶと、増え方を読み違えるため）
    first = min(d for d, _ in counts)
    last = datetime.now(JST).date()
    if days:
        first = max(first, last - timedelta(days=days - 1))
    all_days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    data = pd.DataFrame([{"日付": d, "場所": c, "件数": counts.get((d, c), 0)}
                         for d in all_days for c in clients])

    with ui.card("stats-daily"):
        st.markdown("#### 日ごとの件数")
        chart = (
            alt.Chart(data)
            .mark_bar(stroke="#ffffff", strokeWidth=2)   # 積み上げの間に2pxのすき間
            .encode(
                x=alt.X("yearmonthdate(日付):T", title=None,
                        axis=alt.Axis(format="%-m/%-d", labelColor="#4A5648",
                                      grid=False, tickColor="#DDE3D8", domainColor="#DDE3D8")),
                y=alt.Y("sum(件数):Q", title="件数",
                        axis=alt.Axis(labelColor="#4A5648", titleColor="#4A5648",
                                      gridColor="#EEF1EC", domain=False, tickCount=5)),
                color=alt.Color("場所:N", sort=clients,
                                scale=alt.Scale(domain=clients,
                                                range=[_color(c) for c in clients]),
                                legend=alt.Legend(orient="top", title=None,
                                                  labelColor="#1F2A1F", labelFontSize=13)),
                order=alt.Order("場所:N"),
                tooltip=[alt.Tooltip("yearmonthdate(日付):T", title="日付", format="%-m月%-d日"),
                         alt.Tooltip("場所:N"), alt.Tooltip("sum(件数):Q", title="件数")],
            )
            .properties(height=260)
            .configure_view(stroke=None, fill="#ffffff")
            .configure(font="BIZ UDPGothic", background="#ffffff")
        )
        # theme=None … Streamlit の色づけ（灰色の地）を使わず、カードの白に合わせる
        st.altair_chart(chart, use_container_width=True, theme=None)
        with st.expander("数で見る"):
            table = data.pivot_table(index="日付", columns="場所", values="件数",
                                     aggfunc="sum").reindex(columns=clients).fillna(0).astype(int)
            table["合計"] = table.sum(axis=1)
            table.index = [f"{d.month}/{d.day}" for d in table.index]
            st.dataframe(table.iloc[::-1], use_container_width=True)
    st.write("")


def _by_place_and_lang(rows):
    groups = L.by_client(rows)
    left, right = st.columns(2)
    with left:
        with ui.card("stats-place"):
            st.markdown("#### 案内所ごと")
            total = sum(g["total"] for g in groups.values()) or 1
            html = []
            for name, g in groups.items():
                pct = g["total"] / total * 100
                html.append(
                    f'<div style="margin:10px 0 2px;display:flex;align-items:center;gap:8px">'
                    f'<span style="width:12px;height:12px;border-radius:3px;background:{_color(name)};'
                    f'flex:none"></span><b style="font-size:15px">{name}</b>'
                    f'<span style="margin-left:auto;font-size:15px">{g["total"]} 件</span></div>'
                    f'<div class="ui-meter" style="height:6px"><span style="width:{pct:.0f}%;'
                    f'background:{_color(name)}"></span></div>'
                    f'<div class="ui-tsub">その場で答えられた {g["answered_rate"]:.0%}　'
                    f'職員へ {g["by_source"].get("none", 0)} 件</div>')
            st.markdown("".join(html), unsafe_allow_html=True)
    with right:
        with ui.card("stats-lang"):
            st.markdown("#### 言語ごと")
            counts = L.summarize(rows)["by_lang"]
            data = pd.DataFrame([{"言語": LANG_NAMES.get(k, k), "件数": v}
                                 for k, v in sorted(counts.items(), key=lambda x: -x[1])])
            bars = alt.Chart(data).encode(
                y=alt.Y("言語:N", sort=None, title=None,
                        axis=alt.Axis(labelColor="#1F2A1F", labelFontSize=13, domain=False,
                                      ticks=False)),
                x=alt.X("件数:Q", title=None, axis=None),
                tooltip=["言語", "件数"],
            )
            chart = (bars.mark_bar(color="#2C5F2D", cornerRadiusEnd=4, size=16)
                     + bars.mark_text(align="left", dx=6, color="#1F2A1F", fontSize=13)
                     .encode(text="件数:Q"))
            st.altair_chart(chart.properties(height=36 * len(data) + 10)
                            .configure_view(stroke=None, fill="#ffffff")
                            .configure(font="BIZ UDPGothic", background="#ffffff"),
                            use_container_width=True, theme=None)
    st.write("")


def _top(ctx, rows, items_by_id):
    """よく聞かれた質問（質問回答集で答えたもの）。"""
    top = L.summarize(rows)["top_faq"][:10]
    if not top:
        return
    with ui.card("stats-top"):
        st.markdown("#### よく聞かれた質問")
        st.caption("質問回答集の回答が出たものを、多い順に並べています。")
        most = top[0][1] or 1
        for i, (fid, n) in enumerate(top):
            with ui.keyed_box(f"ui-trow-top{i}"):
                a, b, c = st.columns([5, 1, 1], vertical_alignment="center")
                a.markdown(
                    f'<div class="ui-tcell">{i + 1}. {_label(items_by_id, fid)}</div>'
                    f'<div class="ui-meter" style="height:5px;margin-top:4px"><span '
                    f'style="width:{n / most * 100:.0f}%"></span></div>',
                    unsafe_allow_html=True)
                b.markdown(f'<div class="ui-tcell">{n} 回</div>', unsafe_allow_html=True)
                if fid in items_by_id:
                    c.page_link(ctx.add_page, label="開く", query_params={"id": fid})
    st.write("")


def _unmatched(ctx, rows):
    """答えられなかった質問。ここに並ぶものを足すと、答えられる割合が上がる。"""
    counts, where = {}, {}
    for r in rows:
        if str(r.get("source") or "none") != "none":
            continue
        text = str(r.get("recognized") or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
        where.setdefault(text, set()).add(str(r.get("client") or "不明"))
    with ui.card("stats-unmatched"):
        st.markdown("#### 答えられなかった質問")
        if not counts:
            st.markdown(ui.box("答えられなかった質問はありません", "", "ok"),
                        unsafe_allow_html=True)
            return
        st.caption("職員へ回った質問です。「この質問を追加する」を押すと、"
                   "聞き方にこの文が入った状態で、質問を追加する画面が開きます。")
        ordered = sorted(counts.items(), key=lambda x: -x[1])
        for i, (text, n) in enumerate(ordered[:15]):
            _unmatched_row(ctx, i, text, n, where[text])
        if len(ordered) > 15:
            with st.expander(f"ほかの {len(ordered) - 15} 件"):
                for i, (text, n) in enumerate(ordered[15:], start=15):
                    _unmatched_row(ctx, i, text, n, where[text])
    st.write("")


def _unmatched_row(ctx, i, text, n, places):
    with ui.keyed_box(f"ui-trow-un{i}"):
        a, b, c = st.columns([4.5, 1, 1.8], vertical_alignment="center")
        dots = "".join(f'<span title="{p}" style="display:inline-block;width:10px;height:10px;'
                       f'border-radius:50%;background:{_color(p)};margin-right:3px"></span>'
                       for p in L.clients_in([{"client": p} for p in places]))
        a.markdown(f'<div class="ui-tcell"><b>{escape(text)}</b></div>'
                   f'<div class="ui-tsub">{dots}{"・".join(L.clients_in([{"client": p} for p in places]))}</div>',
                   unsafe_allow_html=True)
        b.markdown(f'<div class="ui-tcell">{n} 回</div>', unsafe_allow_html=True)
        if c.button("この質問を追加する", key=f"stats_add_{i}", use_container_width=True):
            st.switch_page(ctx.add_page, query_params={"q": text})


def _ai_answers(ctx, days):
    """AIが答えた質問と、その答え。

    質問回答集に無かった質問に、AIが資料から答えたもの。中継サーバ（ask.php）が
    質問と答えを記録している。よく聞かれるものは質問回答集に入れておくと、
    AIに頼らず決まった答えを返せる（速く、答えもぶれない）。
    AIの答えが資料と食い違っていないかを、職員が確かめる場所でもある。
    """
    ss = st.session_state
    rows = L.within(load_rows(ctx.log_url, ctx.log_token, kind="ai"), days)
    answered = [r for r in rows if r.get("result") == "answered" and r.get("question")]
    answered.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    with ui.card("stats-ai"):
        st.markdown("#### AIが答えた質問")
        if ss.get("log_error_ai"):
            st.markdown(ui.box("AIの記録を読めませんでした", escape(ss.log_error_ai[:120]), "warn"),
                        unsafe_allow_html=True)
            return
        if not answered:
            st.markdown(ui.box("この期間に、AIが答えた質問はありません", "", "ok"),
                        unsafe_allow_html=True)
            return
        st.caption("質問回答集に無かった質問に、AIが資料から答えたものです（新しい順）。"
                   "答えが正しいかを確かめ、よく聞かれるものは「質問回答集に入れる」を押すと、"
                   "質問とAIの答えが入った状態で、質問を追加する画面が開きます。")
        for i, r in enumerate(answered[:10]):
            _ai_row(ctx, i, r)
        if len(answered) > 10:
            with st.expander(f"ほかの {len(answered) - 10} 件"):
                for i, r in enumerate(answered[10:], start=10):
                    _ai_row(ctx, i, r)
    st.write("")


def _ai_row(ctx, i, r):
    at = L._when(r)
    when = f"{at.astimezone(JST):%m/%d %H:%M}" if at else ""
    lang_code = str(r.get("lang") or "ja")
    lang = LANG_NAMES.get(lang_code, lang_code)
    place = str(r.get("place") or "") or "場所の指定なし"
    question, answer = str(r.get("question") or ""), str(r.get("answer") or "")
    with ui.keyed_box(f"ui-trow-ai{i}"):
        a, b = st.columns([5, 1.8], vertical_alignment="center")
        a.markdown(f'<div class="ui-tcell"><b>{escape(question)}</b></div>'
                   f'<div class="ui-tsub" style="white-space:normal">{escape(answer)}</div>'
                   f'<div class="ui-tsub">{escape(when)}　{escape(lang)}　{escape(place)}</div>',
                   unsafe_allow_html=True)
        if b.button("質問回答集に入れる", key=f"stats_ai_add_{i}", use_container_width=True):
            # 日本語以外の質問は、AIの答えもその言語なので、下書きには入れない
            params = {"q": question}
            if lang_code == "ja":
                params["a"] = answer
            st.switch_page(ctx.add_page, query_params=params)


def _only_here(rows):
    clients = L.clients_in(rows)
    found = {c: L.only_here(rows, c) for c in clients}
    if not any(found.values()):
        return
    with ui.card("stats-only"):
        st.markdown("#### その案内所でだけ聞かれた質問")
        st.caption("ほかの案内所では出ていない質問です。"
                   "その案内所向けの回答（設置場所を選んだ回答）を足す候補になります。")
        for c in clients:
            if found[c]:
                with st.expander(f"{c}（{len(found[c])} 種類）"):
                    for text, n in found[c]:
                        st.markdown(f"- {text}　（{n} 回）")
    st.write("")


# ---------------------------------------------------------------- 控えと削除
def _csv(rows):
    """Excel でそのまま開ける形（UTF-8・BOM付き）の控え。"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["日時（日本時間）", "端末", "現在地", "言語", "聞かれた言葉", "答え方", "答えた質問"])
    for r in rows:
        at = L._when(r)
        w.writerow([at.astimezone(JST).strftime("%Y-%m-%d %H:%M") if at else "",
                    r.get("client", ""), r.get("place", ""),
                    LANG_NAMES.get(r.get("lang", ""), r.get("lang", "")),
                    r.get("recognized", ""), L.SOURCES.get(r.get("source", ""), ""),
                    r.get("faq_id", "")])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _housekeeping(ctx, all_rows):
    ss = st.session_state
    with ui.card("stats-clear"):
        st.markdown("#### 記録の控えと削除")
        st.caption("本番を始める前に、試しの頃の記録を消せます。消す前に控えを保存しておけます。")
        st.download_button(
            f"記録の控えを保存する（{len(all_rows)} 件・Excel で開けます）",
            data=_csv(all_rows), file_name=f"利用状況_{date.today():%Y%m%d}.csv",
            mime="text/csv", disabled=not all_rows, key="stats_csv")

        st.write("")
        ui.field_label("消す記録")
        mode = st.radio("消す記録", ["all", "before"], horizontal=True, key="stats_clear_mode",
                        format_func={"all": "すべての記録",
                                     "before": "ある日より前の記録"}.get,
                        label_visibility="collapsed")
        before = None
        if mode == "before":
            ui.field_label("この日より前を消す", "選んだ日の記録は残ります（日本時間）。")
            before = st.date_input("この日より前を消す", value=date.today(),
                                   key="stats_clear_date", label_visibility="collapsed")
            cut = datetime(before.year, before.month, before.day, tzinfo=JST)
            target = sum(1 for r in all_rows if (L._when(r) is None or L._when(r) < cut))
        else:
            target = len(all_rows)

        st.markdown(ui.box(
            f"消える記録：{target} 件" + ("（すべて）" if mode == "all" else f"（{before:%Y年%m月%d日} より前）"),
            "消した記録は元に戻せません。消したあとは、それより前の時刻の記録が"
            "案内端末から届いても受け取りません（端末を1台ずつ回って消さなくて大丈夫です）。"
            "AIの記録も同じように消えます。", "warn"), unsafe_allow_html=True)
        ui.field_label("確かめのため「消す」と入力してください")
        typed = st.text_input("確かめ", key="stats_clear_confirm", placeholder="消す",
                              label_visibility="collapsed")
        go = st.button("記録を消す", type="primary", key="stats_clear_go",
                       disabled=(typed.strip() != "消す" or target == 0),
                       use_container_width=True)
        if go:
            try:
                with st.spinner("記録を消しています…"):
                    result = L.clear(ctx.log_url, ctx.log_token,
                                     before=before.isoformat() if before else None)
                del ss["stats_clear_confirm"]
                load_rows(ctx.log_url, ctx.log_token, force=True)
                ss.stats_flash = (f"{result.get('deleted', 0)} 件の記録を消しました"
                                  f"（残した記録 {result.get('kept', 0)} 件）。"
                                  "これより前の時刻の記録は、案内端末から届いても受け取りません。")
            except Exception as e:
                ss.stats_flash = None
                st.error(str(e))
                return
            st.rerun()
