"""管理画面の共通部品（admin/ui.py）の見本。

部品の見た目を直したときに、全部をまとめて確かめるための画面。
職員が使うものではない。

    streamlit run tools/ui_gallery.py --server.port 8503
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "admin"))
import ui  # noqa: E402

st.set_page_config(page_title="部品の見本", layout="wide")
ui.apply_theme()

ui.page_header("質問を追加する", crumbs=["登録されている質問", "新しく追加"],
               status=("下書き・まだ案内には出ていません", "mute"))
ui.notice("翻訳の設定がまだです。このまま保存すると**日本語だけ**で登録されます。",
          kind="warn", action="翻訳を設定する", key="g1")
ui.notice("保存しました。", kind="ok", key="g2")
ui.notice("この画面は見本です。", kind="info", key="g3")

left, right = st.columns([2.2, 1])
with left:
    with ui.card("step1"):
        ui.step(1, "どこで案内しますか")
        st.radio("設置場所", ["両方の案内所", "バスターミナルだけ", "であいの館だけ"],
                 horizontal=True)
    with ui.card("step4"):
        ui.step(4, "そのほか", optional=True)
        st.write("写真・参考ページ など")
    for n in range(8):
        st.write(f"長い画面の確かめ用の行 {n + 1}")
with right:
    with ui.card("side"):
        st.markdown("#### 状態のバッジ")
        st.markdown(" ".join([ui.badge("案内中", "ok"), ui.badge("未反映", "warn"),
                              ui.badge("案内に出さない", "mute"),
                              ui.badge("期間外 10/1〜10/31", "info")]),
                    unsafe_allow_html=True)
    ui.tiles([("案内に出す質問", 73, "登録は 74 件")])

with ui.save_bar() as bar:
    a, b = bar.columns(2)
    a.button("下書きとして保存", use_container_width=True)
    b.button("保存する", type="primary", use_container_width=True)
