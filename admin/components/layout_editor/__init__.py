"""画面レイアウトを、絵を見ながら動かして決めるための部品。

Streamlit のつまみ（スライダー）だけで画面の形を決めるのは難しい。
「話すボタンを画面の15%に」と言われても、それがどう見えるのかは
書き出して端末で開くまで分からない。

ここでは案内アプリと同じ形の絵を出し、ブロックを直接つまんで
高さ・並び順・出す出さないを決められるようにしている。

【作りについて】
Streamlit の部品は普通 npm で作るが、ここでは index.html 1枚で済ませている。
職員のパソコンにも Streamlit Cloud にも npm は無いし、
この部品のためだけに作りの手順を増やしたくないため。
やり取りは Streamlit の決まり（postMessage）に手で合わせてある。
"""
from pathlib import Path

import streamlit.components.v1 as components

_DIR = Path(__file__).resolve().parent

_component = components.declare_component("layout_editor", path=str(_DIR))


def layout_editor(value, shape, character=None, key=None, height=620):
    """編集画面を出し、動かされた結果を返す。

    value     … いまの設定（dict）
    shape     … 画面の形 {"w": 1024, "h": 1366, "label": "タブレット（縦）"}
    character … 立ち絵 {"url": データURI, "aspect": 0.36, "mouth": 0.16}
    戻り値    … 動かしたあとの設定（動かしていなければ value のまま）
    """
    return _component(
        value=value, shape=shape, character=character or {},
        key=key, default=value, height=height,
    )
