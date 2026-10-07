"""「案内アプリへ反映する」画面。

Excel に保存した内容を、案内端末が読む faq.json に書き出す。
管理画面で保存しただけでは案内端末には届かないので、最後に必ずここを押す。

  ① 前回の反映から変わったもの … 追加・修正・案内から外れる・設定
  ② 確かめた結果            … 直さないと反映できないもの／直した方がよいもの／
                               今回は案内に出ないもの
  ③ 反映する               … ボタンは1つ。押したら結果をはっきり出す

書き出す中身は publish_diff.build で作る。「未反映 N」の数え方と同じ作り方なので、
ここで見せた「変わったもの」と、実際に書き出す中身が食い違わない。
"""
from datetime import datetime
from html import escape

import streamlit as st

import publish_diff
import ui
from publish_check import friendly

KINDS = [("追加", "新しく案内に出るもの"), ("修正", "直したもの"),
         ("案内から外れる", "案内に出なくなるもの"), ("設定", "画面や読み上げの設定")]


def _when(version):
    """版（2026-10-07 15:20）を、職員さんに読みやすい形（10月7日 15:20）にする。"""
    try:
        d = datetime.strptime(version[:16], "%Y-%m-%d %H:%M")
        return f"{d.month}月{d.day}日 {d:%H:%M}"
    except (TypeError, ValueError):
        return version or "—"


def _show_result(result):
    if result["ok"]:
        parts = "・".join(f"{k}{n}" for k, n in result["by_kind"].items() if n)
        ui.notice(
            f"<b>反映しました（{escape(_when(result['version']))}）</b><br>"
            f"案内に出す質問：{result['count']} 件　／　今回変わったもの：{result['changed']} 件"
            + (f"（{escape(parts)}）" if parts else "")
            + "<br>案内端末に届くまで、<b>最大5分ほど</b>かかります"
              "（配信元の GitHub が5分ごとに新しくするため）。"
              "5分たってから案内端末の画面を開き直すと、新しい内容になります。"
              "続けて何度も押す必要はありません。"
              "据え置きの端末は、夜に一度閉じて開き直してください。",
            kind="ok", key="p-result-ok")
    else:
        ui.notice(
            f"<b>反映できませんでした</b><br>{escape(result['reason'])}<br>"
            "案内端末の内容は変わっていません。少し待ってから、もう一度押してください。",
            kind="warn", key="p-result-ng")


def render(ctx):
    ss = st.session_state
    ui.page_header("案内アプリへ反映する",
                   "管理画面で保存した内容を、案内端末に届けます。"
                   "保存しただけでは届かないので、最後に必ずここで反映します。")

    result = ss.pop("p_result", None)
    if result:
        _show_result(result)

    try:
        built, errors, warnings = publish_diff.build(ss["raw"], ctx.root / "assets")
    except Exception as e:
        ui.notice(f"質問回答集（Excel）を読み取れませんでした（{escape(str(e)[:120])}）。"
                  "「最新の内容を読み直す」を押してから、もう一度開いてください。",
                  kind="warn", key="p-read-ng")
        return

    live = ctx.published()
    changes = publish_diff.compare(built, live)
    checks = friendly(errors, warnings, ctx.items)
    stops = [c for c in checks if c["level"] == "stop"]
    notes = [c for c in checks if c["level"] == "note"]
    infos = [c for c in checks if c["level"] == "info"]

    # 札の中は狭いので、日時は短く（10/7 22:49）
    try:
        d = datetime.strptime((live or {}).get("version", "")[:16], "%Y-%m-%d %H:%M")
        last = f"{d.month}/{d.day} {d:%H:%M}"
    except ValueError:
        last = "—"
    ui.tiles([
        ("前回の反映", last, "いま案内端末に出ている版"),
        ("変わったもの", f"{len(changes)} 件", "前回の反映から"),
        ("案内に出す質問", f"{len(built['faqs'])} 件", "反映したあと"),
        ("直すところ", f"{len(stops)} 件",
         "0件なら反映できます" if not stops else "直すまで反映できません"),
    ])
    st.write("")

    # ================================================================ ①
    with ui.card("p1"):
        ui.step(1, "前回の反映から変わったもの")
        if live is None:
            st.markdown(ui.box("いま公開されている内容を読めませんでした",
                               "比べられないため、すべてを書き出します。", "info"),
                        unsafe_allow_html=True)
        elif not changes:
            st.markdown(ui.box("変わったものはありません",
                               "前回の反映のあとに、保存した変更はありません。", "ok"),
                        unsafe_allow_html=True)
        else:
            for kind, note in KINDS:
                group = [c for c in changes if c["kind"] == kind]
                if not group:
                    continue
                st.markdown(f'<div class="ui-label">{escape(kind)}（{len(group)}件）'
                            f'<span class="ui-label-note" style="font-weight:400">　{escape(note)}'
                            f"</span></div>", unsafe_allow_html=True)
                if kind == "設定":
                    st.markdown(" ".join(ui.badge(c["label"], "info") for c in group),
                                unsafe_allow_html=True)
                    continue
                for c in group:
                    with ui.keyed_box(f"ui-trow-p{kind}-{c['id']}"):
                        a, b = st.columns([5, 1], vertical_alignment="center")
                        a.markdown(f'<div class="ui-tcell">{escape(c["label"])}</div>',
                                   unsafe_allow_html=True)
                        b.page_link(ctx.add_page, label="開く",
                                    query_params={"id": c["id"]})

    # ================================================================ ②
    with ui.card("p2"):
        ui.step(2, "確かめた結果")
        if not checks:
            st.markdown(ui.box("問題は見つかりませんでした", "", "ok"),
                        unsafe_allow_html=True)
        if stops:
            st.markdown(ui.box(f"直さないと反映できません（{len(stops)}件）",
                               "これを直すまで、③ のボタンは押せません。", "warn"),
                        unsafe_allow_html=True)
            _list(ctx, stops, "stop")
        if notes:
            with st.expander(f"反映はできますが、直した方がよいもの（{len(notes)}件）",
                             expanded=len(notes) <= 5):
                _list(ctx, notes, "note")
        if infos:
            with st.expander(f"今回は案内に出ないもの（{len(infos)}件）"):
                _list(ctx, infos, "info")

    # ================================================================ ③
    with ui.card("p3"):
        ui.step(3, "反映する")
        st.caption(f"届け先：{ctx.json_store.label}")
        if stops:
            st.caption("② の「直さないと反映できません」を直すと、押せるようになります。")
        clicked = st.button("案内アプリへ反映する", type="primary", key="p_go",
                            disabled=bool(stops), use_container_width=True)
        if clicked:
            _publish(ctx, built, changes)

    with st.expander("管理者向け"):
        import json
        st.caption("書き出す中身（faq.json）を、手元に保存できます。"
                   "ふだんは使いません（不具合を調べるとき用）。")
        st.download_button(
            "faq.json を保存する",
            data=json.dumps({"version": datetime.now().strftime("%Y-%m-%d %H:%M"), **built},
                            ensure_ascii=False, indent=2),
            file_name="faq.json", mime="application/json")


def _list(ctx, rows, level):
    for i, c in enumerate(rows):
        with ui.keyed_box(f"ui-trow-c{level}{i}"):
            a, b = st.columns([5, 1], vertical_alignment="center")
            head = escape(c["title"])
            if c["label"]:
                head += f'<span class="ui-tsub" style="display:inline">　「{escape(c["label"])}」</span>'
            a.markdown(f'<div class="ui-tcell"><b>{head}</b></div>'
                       + (f'<div class="ui-tsub" style="white-space:normal">{escape(c["detail"])}</div>'
                          if c["detail"] else ""), unsafe_allow_html=True)
            if c["id"]:
                b.page_link(ctx.add_page, label="開く", query_params={"id": c["id"]})


def _publish(ctx, built, changes):
    ss = st.session_state
    version = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {"version": version, **built}
    try:
        with st.spinner("反映しています…"):
            _, sha = ctx.json_store.load()
            ctx.json_store.save(payload, f"質問回答集を反映 {version}（管理画面より）", sha)
    except Exception as e:
        ss.p_result = {"ok": False, "reason": str(e)[:200]}
        st.rerun()

    by_kind = {k: sum(1 for c in changes if c["kind"] == k) for k, _ in KINDS}
    ss.p_result = {"ok": True, "version": version, "count": len(built["faqs"]),
                   "changed": len(changes), "by_kind": by_kind}
    ss.pop("published", None)   # 公開中の内容を読み直す（ホーム・未反映の数も新しくなる）
    st.rerun()
