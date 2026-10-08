"""管理画面の見た目と、どの画面でも使う共通の部品。

色と書体は .streamlit/config.toml で決めている（Streamlit の部品すべてに効くため）。
ここで決めるのは、Streamlit にそのままでは無い形の部品と、その CSS。

  page_header  … 画面の題（パンくず・題・状態のバッジ）
  step         … 番号つきの手順の見出し（① どこで案内しますか …）
  notice       … 注意の帯（黄色）／うまくいった表示（緑）／お知らせ（灰色）
  badge        … 状態のバッジ（案内中・未反映 など）
  card         … 白いカード（枠つきの箱）
  save_bar     … 画面の下に固定する保存バー

どの画面からも同じ見た目で使えるように、見た目の決まりはこのファイルにだけ書く。
画面の側では色の番号や CSS を書かないこと（画面ごとに少しずつずれていくため）。

【キー（key）で形を当てている】
Streamlit の箱（st.container）に key を付けると、HTML に
「st-key-＜key＞」という印が付く。CSS はこの印で当てている。
Streamlit の内部の印（emotion-cache-… など）は版が変わると変わるので使わない。
"""
from contextlib import contextmanager
from html import escape

import streamlit as st

# ---------------------------------------------------------------- 色
# config.toml と同じ値。CSS の中で使うものだけここにも置く。
SIDEBAR = "#1F3D20"
GREEN = "#2C5F2D"
BACK = "#F4F6F1"
CARD = "#FFFFFF"
CARD_LINE = "#DDE3D8"
WARN_BG, WARN_LINE, WARN_TEXT = "#FFF4DC", "#E3B34A", "#6B4200"
OK_BG, OK_TEXT = "#E8F1E4", "#1F4D21"
# 灰色の文字。薄くしすぎると読めない（白地で 7:1 前後の濃さにしてある）
SUB = "#4A5648"
BADGE_ORANGE = "#F2B544"

# バッジの種類 → (地の色, 文字の色, 枠の色)
BADGE_STYLES = {
    "ok": (OK_BG, OK_TEXT, "#BFD6B8"),          # 案内中・反映済み
    "warn": (BADGE_ORANGE, "#3D2600", BADGE_ORANGE),  # 未反映
    "mute": ("#ECEFEA", SUB, "#D5DBD1"),         # 案内に出さない・下書き
    "info": ("#E6EEF5", "#23415C", "#C9D8E6"),   # 期間外 など
}


# ---------------------------------------------------------------- CSS
CSS = f"""
<style>
/* ── 全体 ─────────────────────────────────── */
/* 一番上の帯（Streamlit のヘッダー）。
   画面が狭いと帯に背景色が付き、スクロールした文字が帯の下に潜って読めなくなる。
   帯そのものは透明にして押せないようにし、中のボタン（サイドバーの開閉・Share など）
   だけを小さな地の上に浮かせる。 */
[data-testid="stHeader"] {{
  background: transparent !important;
  pointer-events: none;
}}
[data-testid="stHeader"] button,
[data-testid="stHeader"] a,
[data-testid="stToolbar"],
[data-testid="stExpandSidebarButton"] {{
  pointer-events: auto;
}}
[data-testid="stToolbar"],
[data-testid="stExpandSidebarButton"] {{
  background: rgba(244, 246, 241, 0.92);
  border-radius: 10px;
}}
[data-testid="stMain"] .block-container {{
  padding-top: 3.2rem;
  padding-bottom: 2rem;
  max-width: 1400px;
}}
/* 注意書き（st.caption）は13〜14px。灰色は薄くしすぎない */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {{
  font-size: 14px !important;
  color: {SUB} !important;
}}
/* 入力欄の上の見出し（ラベル） */
[data-testid="stWidgetLabel"] p {{
  font-size: 15px !important;
  font-weight: 700;
  color: #1F2A1F;
}}

/* ── 押しやすい大きさ（高さ44px以上） ─────────── */
[data-testid="stMain"] button[kind] {{
  min-height: 44px;
  padding-left: 18px;
  padding-right: 18px;
  font-weight: 700;
}}
[data-testid="stMain"] [data-baseweb="input"] > div,
[data-testid="stMain"] [data-baseweb="select"] > div {{
  min-height: 44px;
}}
/* 選択肢（ラジオ・チェック）は文字のまわりまで押せるようにする */
[data-testid="stMain"] [role="radiogroup"] label,
[data-testid="stMain"] [data-testid="stCheckbox"] label {{
  min-height: 44px;
  align-items: center;
  padding-right: 14px;
}}

/* 横に並べた選択肢（ラジオ）は、押せる範囲が分かるよう枠で囲む。
   選んでいるものは緑の太い枠と薄い緑の地にする。 */
[data-testid="stMain"] [role="radiogroup"][aria-orientation="horizontal"],
[data-testid="stMain"] div[role="radiogroup"] {{
  gap: 8px; flex-wrap: wrap;
}}
[data-testid="stMain"] [role="radiogroup"] > label {{
  border: 1px solid {CARD_LINE}; border-radius: 10px;
  padding: 8px 16px 8px 12px; background: #fff; margin: 0;
}}
[data-testid="stMain"] [role="radiogroup"] > label:has(input:checked) {{
  border: 2px solid {GREEN}; background: {OK_BG}; font-weight: 700;
}}
/* チップ型の選択肢（分類など）。選んでいるものをはっきりさせる。
   Streamlit 1.65 から印が変わった（data-variant と aria-checked）ので、新旧どちらにも当てる */
[data-testid="stMain"] [data-testid="stBaseButton-pills"],
[data-testid="stMain"] button[data-variant="pills"] {{
  min-height: 44px; padding: 6px 16px; font-weight: 400;
}}
[data-testid="stMain"] [data-testid="stBaseButton-pillsActive"],
[data-testid="stMain"] button[data-variant="pills"][aria-checked="true"] {{
  min-height: 44px; padding: 6px 16px;
  border: 2px solid {GREEN} !important; background: {OK_BG} !important;
  color: {SIDEBAR} !important; font-weight: 700 !important;
}}

/* 文字だけのボタン（「AIに言い方を提案してもらう」など）は、リンクのように見せる */
[data-testid="stMain"] [data-testid="stBaseButton-tertiary"] {{
  color: {GREEN}; text-decoration: underline; text-underline-offset: 3px;
  padding-left: 4px; padding-right: 4px;
}}
[data-testid="stMain"] [data-testid="stBaseButton-tertiary"] p {{ font-weight: 700; }}

/* 画面の中の切り替え（ui.switch）。選んでいるものを濃い緑にする */
[data-testid="stMain"] [data-testid="stBaseButton-segmented_control"],
[data-testid="stMain"] [data-testid="stBaseButton-segmented_controlActive"],
[data-testid="stMain"] button[data-variant="segmented_control"] {{
  min-height: 46px; padding: 6px 22px; font-size: 16px;
}}
[data-testid="stMain"] [data-testid="stBaseButton-segmented_controlActive"],
[data-testid="stMain"] button[data-variant="segmented_control"][aria-checked="true"] {{
  background: {GREEN} !important; border-color: {GREEN} !important;
  color: #fff !important; font-weight: 700 !important;
}}
[data-testid="stMain"] [data-testid="stBaseButton-segmented_controlActive"] *,
[data-testid="stMain"] button[data-variant="segmented_control"][aria-checked="true"] * {{
  color: #fff !important;
}}

/* キャラクターのカードは幅が狭いので、ボタンの字を1行に収める */
[data-testid="stMain"] [class*="st-key-ui-card-ch-"] button {{
  padding-left: 8px; padding-right: 8px;
}}
[data-testid="stMain"] [class*="st-key-ui-card-ch-"] button p {{
  white-space: nowrap; font-size: 14px;
}}

/* ── カード ───────────────────────────────── */
[data-testid="stMain"] [class*="st-key-ui-card"],
[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: {CARD};
  border: 1px solid {CARD_LINE} !important;
  border-radius: 14px;
}}
[data-testid="stMain"] [class*="st-key-ui-card"] {{
  padding: 20px 22px;
}}
[data-testid="stMain"] [class*="st-key-ui-card"]:has(.tile-label) {{
  padding: 14px 18px;
}}
[data-testid="stMain"] [data-testid="stHeadingWithActionElements"] h4 {{
  font-size: 17px !important;
  font-weight: 700 !important;
  margin-top: 0;
}}

/* ── 数値の札（ホームなど） ───────────────────── */
.tile-label {{ color: {SUB}; font-size: 14px; }}
.tile-value {{ color: {GREEN}; font-size: 28px; font-weight: 700; line-height: 1.3; }}
.tile-note  {{ color: {SUB}; font-size: 13px; }}
/* 補足の長さが違っても、札の高さは揃える */
.tile-label, .tile-note {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

/* ── 以前からの小さな部品（質問の入力欄で使用） ───────── */
.hint {{ color: {SUB}; font-size: 14px; }}
.lang-name {{ color: {GREEN}; font-weight: 700; font-size: 14px; }}

/* ── 画面の題 ─────────────────────────────── */
.ui-crumbs {{ font-size: 14px; color: {SUB}; margin-bottom: 2px; }}
.ui-crumbs a {{ color: {GREEN}; }}
.ui-title-row {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
                 margin: 0 0 4px; }}
.ui-title {{ font-size: 30px; font-weight: 700; color: #1F2A1F; line-height: 1.3; }}
.ui-lead {{ font-size: 15px; color: {SUB}; margin: 0 0 16px; }}

/* ── 手順の見出し ─────────────────────────── */
.ui-step {{ display: flex; align-items: center; gap: 12px; margin: 0 0 14px; }}
.ui-step-n {{
  flex: none; width: 34px; height: 34px; border-radius: 50%;
  background: {GREEN}; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 17px;
}}
.ui-step.optional .ui-step-n {{ background: #E3E7E0; color: {SUB}; }}
.ui-step-title {{ font-size: 21px; font-weight: 700; color: #1F2A1F; }}
.ui-step-opt {{ font-size: 14px; color: {SUB}; }}
.ui-step-note {{ font-size: 14px; color: {SUB}; margin: -6px 0 14px; }}

/* ── 状態のバッジ ─────────────────────────── */
.ui-badge {{
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 999px;
  font-size: 13px; font-weight: 700; line-height: 1.5;
  border: 1px solid transparent; white-space: nowrap;
}}

/* ── 注意の帯 ─────────────────────────────── */
[data-testid="stMain"] [class*="st-key-ui-notice-warn"],
.ui-notice.warn {{
  background: {WARN_BG}; border: 1px solid {WARN_LINE} !important;
  color: {WARN_TEXT};
}}
[data-testid="stMain"] [class*="st-key-ui-notice-ok"],
.ui-notice.ok {{
  background: {OK_BG}; border: 1px solid #BFD6B8 !important; color: {OK_TEXT};
}}
[data-testid="stMain"] [class*="st-key-ui-notice-info"],
.ui-notice.info {{
  background: #EEF1EC; border: 1px solid {CARD_LINE} !important; color: #1F2A1F;
}}
[data-testid="stMain"] [class*="st-key-ui-notice"],
.ui-notice {{
  border-radius: 12px; padding: 12px 18px; margin: 0 0 16px;
}}
[data-testid="stMain"] [class*="st-key-ui-notice"] p,
.ui-notice p {{ color: inherit !important; margin: 0; font-size: 15px; }}
.ui-notice-icon {{ font-weight: 700; margin-right: 8px; }}
/* 帯の中の文とボタンは、縦の真ん中で揃える */
[data-testid="stMain"] [class*="st-key-ui-notice"] [data-testid="stHorizontalBlock"] {{
  align-items: center;
}}
[data-testid="stMain"] [class*="st-key-ui-notice"] [data-testid="stColumn"] {{
  align-self: center;
}}
[data-testid="stMain"] [class*="st-key-ui-notice"] [data-testid="stMarkdownContainer"],
[data-testid="stMain"] [class*="st-key-ui-notice"] [data-testid="stMarkdownContainer"] p {{
  margin-bottom: 0 !important;
}}
[data-testid="stMain"] [class*="st-key-ui-notice"] [data-testid="stElementContainer"] {{
  margin-bottom: 0;
}}
/* 帯の中のボタンは、白地で枠を付ける（帯の色に埋もれないように） */
[data-testid="stMain"] [class*="st-key-ui-notice"] button[kind] {{
  background: #fff; border: 1px solid currentColor; color: inherit;
}}
[data-testid="stMain"] [class*="st-key-ui-notice"] button[kind] p {{
  white-space: nowrap;
}}

/* ── 下に固定する保存バー ───────────────────── */
/* 画面の下にはりつける（sticky）。
   fixed にすると、サイドバーの幅（開閉・ドラッグで変わる）に合わせて
   左端を計算し直す必要があり、ずれると文字がサイドバーの下に隠れる。
   sticky なら本文の列の幅にそのまま収まる。 */
/* はりつけるのは、箱そのものではなく外側の包み（stLayoutWrapper）。
   箱は自分と同じ大きさの包みに入っているので、箱に sticky を付けても
   動ける余地が無く、はりつかない。 */
[data-testid="stMain"] [data-testid="stLayoutWrapper"]:has(> [class*="st-key-ui-savebar"]),
[data-testid="stMain"] [data-testid="stLayoutWrapper"]:has(> [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] > [class*="st-key-ui-savebar"]) {{
  position: sticky; bottom: 0;
  z-index: 50;
}}
[data-testid="stMain"] [class*="st-key-ui-savebar"] {{
  background: {CARD};
  border: 1px solid {CARD_LINE};
  border-radius: 14px 14px 0 0;
  box-shadow: 0 -6px 18px rgba(31, 61, 32, .08);
  padding: 12px 22px;
  margin-top: 8px;
}}
[data-testid="stMain"] [class*="st-key-ui-savebar"] [data-testid="stHorizontalBlock"] {{
  align-items: center;
}}

/* ── チップ（聞き方など、1つずつ足して × で外すもの） ─────── */
[data-testid="stMain"] [class*="st-key-ui-chip-"] button,
[data-testid="stMain"] [class*="st-key-ui-chipw-"] button,
[data-testid="stMain"] [class*="st-key-ui-chipadd-"] button {{
  min-height: 44px; padding: 6px 14px; border-radius: 10px;
  font-weight: 400;
}}
[data-testid="stMain"] [class*="st-key-ui-chip-"] button {{
  background: {OK_BG}; border: 1px solid #BFD6B8; color: #1F2A1F;
}}
[data-testid="stMain"] [class*="st-key-ui-chipw-"] button {{
  background: {WARN_BG}; border: 1px solid {WARN_LINE}; color: {WARN_TEXT};
}}
[data-testid="stMain"] [class*="st-key-ui-chipadd-"] button {{
  background: #fff; border: 1px dashed {GREEN}; color: {GREEN};
}}
[data-testid="stMain"] [class*="st-key-ui-chip"] button:hover {{
  border-color: {GREEN};
}}
[data-testid="stMain"] [class*="st-key-ui-chip"] button p {{ font-size: 16px; }}

/* ── 入力欄の上の見出しと説明 ─────────────────── */
.ui-label {{ font-size: 15px; font-weight: 700; color: #1F2A1F; margin: 4px 0 2px; }}
.ui-label .req {{ font-size: 12px; font-weight: 700; color: #fff; background: {GREEN};
                  border-radius: 4px; padding: 1px 6px; margin-left: 8px; }}
.ui-label-note {{ font-size: 14px; color: {SUB}; margin: 0 0 6px; }}

/* ── 文字数の目安の棒 ─────────────────────── */
.ui-meter-row {{ display: flex; align-items: center; gap: 12px; margin: 2px 0 8px; }}
.ui-meter {{ flex: 1; height: 8px; border-radius: 4px; background: #E3E7E0; overflow: hidden; }}
.ui-meter > span {{ display: block; height: 100%; background: {GREEN}; border-radius: 4px; }}
.ui-meter.over > span {{ background: {WARN_LINE}; }}
.ui-meter-text {{ font-size: 14px; color: {SUB}; white-space: nowrap; }}
.ui-meter-text.over {{ color: {WARN_TEXT}; font-weight: 700; }}
.ui-tips {{ margin: 4px 0 0 1.1em; padding: 0; font-size: 14px; color: {SUB}; }}

/* ── 「そのほか」の1行（名前・いまの値・ボタン） ─────────── */
[data-testid="stMain"] [class*="st-key-ui-row-"] {{
  border-top: 1px solid {CARD_LINE};
  padding: 10px 0 2px;
}}
.ui-row-label {{ font-size: 16px; color: #1F2A1F; }}
.ui-row-value {{ font-size: 14px; color: {SUB}; text-align: right; }}
.ui-row-value.set {{ color: {GREEN}; font-weight: 700; }}

/* ── 小さな知らせの箱（カードの中で使う） ─────────── */
.ui-notice.small {{ padding: 10px 14px; margin: 6px 0 10px; font-size: 14px; }}
.ui-notice.small b {{ display: block; margin-bottom: 2px; }}

/* ── 表（登録されている質問など） ───────────────── */
.ui-thead {{ font-size: 13px; font-weight: 700; color: {SUB}; padding: 0 0 6px; }}
[data-testid="stMain"] [class*="st-key-ui-trow-"] {{
  border-top: 1px solid {CARD_LINE};
  padding: 8px 6px;
  margin: 0 -6px;
  border-radius: 6px;
}}
[data-testid="stMain"] [class*="st-key-ui-trow-"]:hover {{ background: #F7F9F5; }}
/* 項目名は、押すと開くリンク。左に寄せ、字は黒にして読みやすくする */
[data-testid="stMain"] [class*="st-key-ui-trow-"] [data-testid="stBaseButton-tertiary"] {{
  justify-content: flex-start; text-align: left; color: #1F2A1F;
  text-decoration: none; padding: 0; min-height: 0;
}}
[data-testid="stMain"] [class*="st-key-ui-trow-"] [data-testid="stBaseButton-tertiary"] p {{
  font-weight: 700; font-size: 15px; text-align: left;
}}
[data-testid="stMain"] [class*="st-key-ui-trow-"] [data-testid="stBaseButton-tertiary"]:hover p {{
  color: {GREEN}; text-decoration: underline;
}}
.ui-tsub {{ font-size: 13px; color: {SUB}; margin-top: 2px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ui-tcell {{ font-size: 14px; color: #1F2A1F; }}
.ui-tcell.sub {{ color: {SUB}; font-size: 13px; }}
.ui-tcell.warn {{ color: {WARN_TEXT}; font-weight: 700; }}
.ui-tbadges {{ display: flex; gap: 4px; flex-wrap: wrap; }}
[data-testid="stMain"] [class*="st-key-ui-trow-"] [data-testid="stPopover"] button {{
  min-height: 44px; font-weight: 400; padding: 4px 10px;
}}
[data-testid="stMain"] [class*="st-key-ui-trow-"] [data-testid="stPopover"] button p {{
  white-space: nowrap; font-size: 14px;
}}

/* ── サイドバー ───────────────────────────── */
/* 題字。サイドバーのいちばん上に固定で出す */
[data-testid="stSidebarHeader"] {{
  align-items: flex-start;
}}
[data-testid="stSidebarHeader"]::before {{
  content: "白川郷 音声案内\\A管理画面";
  white-space: pre;
  color: #fff;
  font-weight: 700;
  font-size: 17px;
  line-height: 1.35;
  padding: 4px 0 0 4px;
  flex: 1;
}}
/* 分類の見出し（質問と回答 など）。小さく控えめにして、行き先を目立たせる */
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] p {{
  color: #A9C2A6 !important;
  font-size: 13px !important;
  letter-spacing: .06em;
  font-weight: 700;
}}
/* 開閉の矢印（シェブロン）は、ポインタを乗せなくても常に出す。
   Streamlit の既定では乗せたときだけ出るので、開いているのか
   閉じているのかが見た目で分からない。 */
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] > div {{
  visibility: visible !important;
  opacity: 1 !important;
}}
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] [data-testid="stIconMaterial"] {{
  color: #A9C2A6 !important;
  transition: transform .15s;
}}
/* 閉じているとき（見出しの下に行き先が1つも無いとき）は、矢印を右向きにする。
   開いているとき ⌄ ／ 閉じているとき › */
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"]:last-child [data-testid="stIconMaterial"] {{
  transform: rotate(-90deg);
}}
/* 行き先 */
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {{
  border-radius: 10px;
  padding: 8px 12px;
  margin: 2px 0;
  min-height: 44px;
}}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] span {{
  font-size: 15px !important;
  /* バッジを付けたときに「案内アプリへ反…」と切れないよう、2行に折り返す */
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  line-height: 1.35;
}}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover {{
  background: #2E5431;
}}
/* いまいるページ。薄い緑の地に濃い字で、ひと目で分かるようにする */
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: {OK_BG} !important;
}}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"] * {{
  color: {SIDEBAR} !important;
  font-weight: 700 !important;
}}
/* サイドバーのボタン（最新の内容を読み直す）は、地が濃いので枠で見せる */
section[data-testid="stSidebar"] button[kind] {{
  background: transparent; border: 1px solid #6E9A70; min-height: 44px;
}}
section[data-testid="stSidebar"] button[kind]:hover {{
  background: #2E5431; border-color: #9CCB9E;
}}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
  color: #C9D8C6 !important;
}}
</style>
"""


def apply_theme():
    """共通の CSS を入れる。画面を作るたびに最初に1回呼ぶ。"""
    st.session_state["_ui_card_n"] = 0   # カードの通し番号（作り直すたびに数え直す）
    st.markdown(CSS, unsafe_allow_html=True)


def keyed_box(key):
    """印（key）の付いた箱を、印の無い箱で1枚包んで作る。with ui.keyed_box("…"): の形で使う。

    【なぜ包むか】
    Streamlit 1.6x では、保存や反映のあと st.rerun() で作り直したときに、
    その上に知らせ（「反映しました」など）が1つ増えて印の付いた箱の位置がずれると、
    ずれる前の箱が消えずに残り、薄い色の写しが重なって増えていく
    （別の画面へ移っても残る）。
    印の無い箱で包むと、ずれるのは包みの方だけになり、
    印の付いた箱はいつも包みの中の1番目のまま動かないので、写しが残らない。
    """
    return st.container().container(key=key)


def nav_badges(badges):
    """サイドバーの行き先の横にバッジを出す。

    badges … {"ページのURLの末尾": "バッジの文字"}
    （例: {"publish": "未反映 3"}）。文字が空のものは出さない。
    """
    css = _nav_badge_css(badges)
    if css:
        st.markdown(css, unsafe_allow_html=True)


def _nav_badge_css(badges):
    """サイドバーの行き先の横にバッジを出す CSS。

    行き先の文字は Streamlit が作るので、中に部品を差し込めない。
    そこで、行き先のリンク（href の末尾）を目印にして、
    後ろに文字を足している（::after）。
    """
    rules = []
    for path, text in badges.items():
        if not text:
            continue
        safe = str(text).replace("\\", "\\\\").replace('"', '\\"')
        rules.append(
            f'section[data-testid="stSidebar"] '
            f'a[data-testid="stSidebarNavLink"][href$="/{path}"]::after {{'
            f' content: "{safe}"; margin-left: auto; flex: none;'
            f' background: {BADGE_ORANGE}; color: #3D2600;'
            f' font-size: 12px; font-weight: 700; line-height: 1.3;'
            f' padding: 3px 8px; border-radius: 999px; white-space: nowrap; }}'
        )
    return "<style>" + "\n".join(rules) + "</style>" if rules else ""


# ---------------------------------------------------------------- 部品
def badge(text, kind="mute"):
    """状態のバッジの HTML。st.markdown(..., unsafe_allow_html=True) で使う。

    kind … ok（案内中）／warn（未反映）／mute（案内に出さない）／info（期間外）
    """
    bg, fg, line = BADGE_STYLES.get(kind, BADGE_STYLES["mute"])
    return (f'<span class="ui-badge" style="background:{bg};color:{fg};'
            f'border-color:{line}">{escape(str(text))}</span>')


def page_header(title, lead="", crumbs=None, status=None):
    """画面の題。

    crumbs … パンくず（例: ["登録されている質問", "新しく追加"]）
    status … 題の横に出すバッジ (文字, 種類)
    """
    parts = []
    if crumbs:
        parts.append('<div class="ui-crumbs">'
                     + " › ".join(escape(c) for c in crumbs) + "</div>")
    row = f'<div class="ui-title-row"><span class="ui-title">{escape(title)}</span>'
    # status は (文字, 種類) か、その並び
    if status and isinstance(status[0], str):
        status = [status]
    for one in status or []:
        row += badge(*one)
    row += "</div>"
    parts.append(row)
    if lead:
        parts.append(f'<p class="ui-lead">{escape(lead)}</p>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def section(title, note=""):
    """1つの画面の中の、まとまりの見出し（タブで切り替える中身の題など）。

    画面の題（page_header）より一段小さくする。同じ大きさが2つ並ぶと、
    どちらが画面の題か分からなくなるため。
    """
    html = f'<div class="ui-step-title" style="margin:4px 0 2px">{escape(title)}</div>'
    if note:
        html += f'<p class="ui-lead">{escape(note)}</p>'
    st.markdown(html, unsafe_allow_html=True)


def switch(options, key, param="tab"):
    """画面の中の切り替え（タブの代わり）。選んだものは URL の ?tab= に残す。

    st.tabs は隠れているタブの中身まで毎回作るため、
    中の部品（画面レイアウトの編集画面など）が幅0で作られて崩れる。
    こちらは選んだものだけを作る。URL に残すので、ほかの画面から
    「?tab=yomikata」のように直接開ける。

    options … {"名前": "見出し"}
    key     … この切り替えの名前（画面ごとに別にする）

    【初めの値を URL から渡さない】
    初めの値（default）を毎回 URL から渡すと、押すたびに Streamlit が
    「別の部品」と見なして作り直し、次に押したものが捨てられる（1回おきに効かない）。
    部品の名前（key）を固定し、URL が外から変わったとき（ほかの画面から
    ?tab=… で開いたとき）だけ、選んでいるものを URL に合わせる。
    """
    ss = st.session_state
    keys = list(options)
    url = st.query_params.get(param)
    seen = f"{key}__url"
    if key not in ss or ss[key] not in keys:
        ss[key] = url if url in keys else keys[0]
    elif url in keys and url != ss.get(seen):
        ss[key] = url   # ほかの画面から ?tab=… で開かれた
    picked = st.segmented_control("表示する設定", keys, format_func=options.get,
                                  key=key, label_visibility="collapsed")
    if picked not in keys:          # もう一度押して外したときは、そのまま
        picked = ss.get(f"{key}__last", keys[0])
    ss[f"{key}__last"] = picked
    if st.query_params.get(param) != picked:
        st.query_params[param] = picked
    ss[seen] = picked
    return picked


def step(number, title, note="", optional=False):
    """番号つきの手順の見出し（① どこで案内しますか）。

    optional=True … 「なくても登録できます」の手順。番号を灰色にする。
    """
    opt = '<span class="ui-step-opt">なくても登録できます</span>' if optional else ""
    html = (f'<div class="ui-step{" optional" if optional else ""}">'
            f'<span class="ui-step-n">{escape(str(number))}</span>'
            f'<span class="ui-step-title">{escape(title)}</span>{opt}</div>')
    if note:
        html += f'<p class="ui-step-note">{escape(note)}</p>'
    st.markdown(html, unsafe_allow_html=True)


_ICONS = {"warn": "⚠", "ok": "✓", "info": "ⓘ"}


def notice(text, kind="warn", action=None, key=None):
    """注意の帯。大事な警告は画面の上に出す（サイドバーの小さな字に置かない）。

    text   … 本文（**太字** が使える）
    kind   … warn（黄色）／ok（緑）／info（灰色）
    action … 右に置くボタンの文字。押されたら True を返す。
    """
    key = key or f"{kind}-{abs(hash(text)) % 10**8}"
    with keyed_box(f"ui-notice-{kind}-{key}"):
        icon = f'<span class="ui-notice-icon">{_ICONS.get(kind, "")}</span>'
        if action:
            c1, c2 = st.columns([4, 1.5])
            c1.markdown(icon + text, unsafe_allow_html=True)
            return c2.button(action, key=f"ui-notice-btn-{key}",
                             use_container_width=True)
        st.markdown(icon + text, unsafe_allow_html=True)
    return False


def tiles(cells):
    """数値の札を横に並べる。cells は (見出し, 値, 補足) の並び。"""
    columns = st.columns(len(cells))
    for column, (label, value, note) in zip(columns, cells):
        with column:
            with card():
                st.markdown(f"<div class='tile-label'>{escape(str(label))}</div>"
                            f"<div class='tile-value'>{escape(str(value))}</div>"
                            f"<div class='tile-note'>{escape(str(note))}</div>",
                            unsafe_allow_html=True)


def field_label(label, note="", required=False):
    """入力欄の上に出す見出しと説明。

    Streamlit の説明（help や caption）は欄の下や「?」の中に出るため、
    次の欄の説明と区別しにくい。説明は欄の上にまとめて書く。
    この後に置く入力欄は label_visibility="collapsed" にする。
    """
    req = '<span class="req">必須</span>' if required else ""
    html = f'<div class="ui-label">{escape(label)}{req}</div>'
    if note:
        html += f'<div class="ui-label-note">{note}</div>'
    st.markdown(html, unsafe_allow_html=True)


def chip(label, key, warn=False):
    """チップ（押すと外れる札）。押されたら True。

    warn=True … 黄色（直した方がよい言い方）
    """
    kind = "chipw" if warn else "chip"
    return st.button(label, key=f"ui-{kind}-{key}")


def chip_add(label, key):
    """点線のチップ（押すと足される案）。押されたら True。"""
    return st.button(label, key=f"ui-chipadd-{key}")


def meter(value, maximum, text):
    """目安に対してどれくらいかを示す棒（回答の文字数など）。"""
    over = value > maximum
    pct = min(100, round(value / maximum * 100)) if maximum else 0
    cls = " over" if over else ""
    st.markdown(
        f'<div class="ui-meter-row"><div class="ui-meter{cls}">'
        f'<span style="width:{pct}%"></span></div>'
        f'<span class="ui-meter-text{cls}">{escape(text)}</span></div>',
        unsafe_allow_html=True)


def box(title, text="", kind="info"):
    """カードの中に置く小さな知らせの箱の HTML。"""
    icon = _ICONS.get(kind, "")
    head = f"<b>{icon} {escape(title)}</b>" if title else ""
    return f'<div class="ui-notice small {kind}">{head}{text}</div>'


def option_row(label, value, button, key, is_set=False):
    """「そのほか」の1行。名前・いまの値・ボタン。ボタンが押されたら True。"""
    with keyed_box(f"ui-row-{key}"):
        c1, c2, c3 = st.columns([3, 2.2, 1.5], vertical_alignment="center")
        c1.markdown(f'<div class="ui-row-label">{escape(label)}</div>',
                    unsafe_allow_html=True)
        cls = " set" if is_set else ""
        c2.markdown(f'<div class="ui-row-value{cls}">{escape(value)}</div>',
                    unsafe_allow_html=True)
        return c3.button(button, key=f"ui-rowbtn-{key}", use_container_width=True)


def card(key=None):
    """白いカード（枠つきの箱）。with ui.card(): の形で使う。

    st.container(border=True) は枠は付くが、地の色を変える目印が無いため
    背景と同じ色になってしまう。印（key）を付けた箱で作り、CSS で白くしている。
    key を省くと通し番号を振る（同じ画面で同じ印を2回使うと Streamlit が止まるため）。
    """
    if key is None:
        n = st.session_state.get("_ui_card_n", 0) + 1
        st.session_state["_ui_card_n"] = n
        key = f"auto-{n}"
    return keyed_box(f"ui-card-{key}")


@contextmanager
def save_bar(note="保存しただけでは案内に出ません。最後に「案内アプリへ反映する」を押します。",
             key="main"):
    """画面の下に固定する保存バー。

    with ui.save_bar() as buttons:
        if buttons.button("保存する", type="primary"): ...

    左に一文（保存と反映が別の操作であること）、右にボタンを置く。
    返す箱にボタンを入れると、右寄せで並ぶ。
    """
    with keyed_box(f"ui-savebar-{key}"):
        left, right = st.columns([3, 2])
        left.markdown(f'<span style="font-size:14px;color:{SUB}">{escape(note)}</span>',
                      unsafe_allow_html=True)
        with right:
            yield right
