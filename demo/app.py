"""
白川郷 音声案内チャットボット デモ

実機アプリと同じFAQ検索を、ブラウザ上で試せるようにしたもの。
外部の方に内容を確認していただくためのデモで、音声入力の代わりに
テキスト入力を使う。判定結果は実機とまったく同じになる。

起動:
    streamlit run demo/app.py
"""

import base64
import io
from pathlib import Path

import qrcode
import streamlit as st

from faq_engine import answer_for, load_faqs, load_synonyms, search

# ── 設定 ───────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
FAQ_PATH = ROOT / "assets" / "faq.json"
PHOTO_DIR = ROOT / "assets" / "photo"

LANGS = {"ja": "日本語", "en": "English", "zh": "中文", "ko": "한국어",
         "es": "Español", "fr": "Français"}

UI = {
    "prompt": {
        "ja": "質問を入力してください",
        "en": "Type your question",
        "zh": "请输入您的问题",
        "ko": "질문을 입력해 주세요",
        "es": "Escriba su pregunta",
        "fr": "Saisissez votre question",
    },
    "staff": {
        "ja": "申し訳ございません。その質問は案内所の係員にお尋ねください。",
        "en": "Sorry, I could not find an answer. Please ask the staff at the information desk.",
        "zh": "很抱歉，未能找到答案。请向服务台的工作人员咨询。",
        "ko": "죄송합니다. 안내소 직원에게 문의해 주세요.",
        "es": "Lo sentimos, no hemos encontrado una respuesta. Pregunte al personal del centro de información.",
        "fr": "Désolé, nous n'avons pas trouvé de réponse. Veuillez demander au personnel du centre d'information.",
    },
    "pending": {
        "ja": "",
        "en": "English text is not ready yet. Showing Japanese.",
        "zh": "该语言的内容正在准备中，暂以日语显示。",
        "ko": "해당 언어는 준비 중입니다. 일본어로 표시합니다.",
        "es": "El texto en español aún no está disponible. Se muestra en japonés.",
        "fr": "Le texte français n'est pas encore disponible. Affichage en japonais.",
    },
    "details": {
        "ja": "詳しくはこちら",
        "en": "Scan for details",
        "zh": "扫码查看详情",
        "ko": "자세한 내용은 스캔",
        "es": "Escanee para más detalles",
        "fr": "Scannez pour en savoir plus",
    },
}

CATEGORY_LABEL = {
    "bus": "バス・交通", "facility": "施設・設備", "sightseeing": "観光・見学",
    "food": "食事", "season": "季節・天候", "accessibility": "バリアフリー",
    "manner": "マナー・お願い", "other": "その他",
}

SAMPLES = {
    "ja": ["トイレはどこですか", "ごみはどこに捨てればいいですか",
           "展望台へのバスはありますか", "荷物を預けたいのですが",
           "スタッドレスタイヤは必要ですか", "wifiは使えますか"],
    "en": ["Where is the restroom?", "Where can I throw away trash?",
           "Is there a bus to the observatory?"],
    "zh": ["洗手间在哪里", "垃圾扔在哪里"],
    "ko": ["화장실은 어디입니까", "쓰레기는 어디에 버립니까"],
    "es": ["¿Dónde están los aseos?", "¿Dónde puedo tirar la basura?"],
    "fr": ["Où sont les toilettes ?", "Où puis-je jeter mes déchets ?"],
}

st.set_page_config(page_title="白川郷 音声案内 デモ", page_icon="🏘️", layout="wide")

# ── スタイル ────────────────────────────────────────────
st.markdown("""
<style>
  .answer-box {
    background: #ffffff; border: 1px solid #c3d2bc; border-radius: 12px;
    padding: 20px 24px; font-size: 20px; line-height: 1.7; color: #2b2b2b;
  }
  .staff-box {
    background: #fff6f5; border: 1px solid #e8c4c0; border-radius: 12px;
    padding: 20px 24px; font-size: 20px; line-height: 1.7; color: #b85042;
  }
  .pending { color: #b85042; font-size: 13px; margin-bottom: 8px; }
  .qr-cap { text-align: center; font-size: 12px; color: #5a6b58; }
  .meta { color: #5a6b58; font-size: 13px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def get_faqs(mtime: float):
    return load_faqs(FAQ_PATH) + (load_synonyms(FAQ_PATH),)


def qr_image(url: str) -> str:
    qr = qrcode.QRCode(box_size=5, border=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


if not FAQ_PATH.exists():
    st.error(f"質問回答集が見つかりません: {FAQ_PATH}")
    st.stop()

faqs, version, synonyms = get_faqs(FAQ_PATH.stat().st_mtime)

# ── サイドバー ──────────────────────────────────────────
with st.sidebar:
    st.markdown("### 表示言語")
    lang = st.radio("言語", list(LANGS), format_func=lambda k: LANGS[k],
                    label_visibility="collapsed", horizontal=False)

    st.divider()
    st.markdown("### このデモについて")
    st.caption(
        "設置予定のタブレット端末と**同じ判定**で回答を選んでいます。"
        "実機ではマイクに話しかけますが、ここではテキスト入力で試せます。"
    )
    st.caption(
        "回答は用意された質問回答集の中からのみ選ばれ、"
        "AIが文章を作ることはありません。"
        "該当がない場合は係員へご案内します。"
    )

    st.divider()
    st.markdown(f"<div class='meta'>質問回答集 {len(faqs)} 件<br>版: {version}</div>",
                unsafe_allow_html=True)

st.title("白川郷 音声案内チャットボット")
st.caption("バスターミナル・観光案内所での観光客対応支援｜デモ版")

tab_try, tab_list, tab_check = st.tabs(["試す", "質問回答集の一覧", "動作の確認"])

# その言語の翻訳がまだ無い場合、デモが壊れて見えないよう先に断っておく
translated = sum(
    1 for f in faqs
    if (f.get("translations") or {}).get(lang, {}).get("answer")
)
if lang != "ja" and translated == 0:
    st.warning(
        f"**{LANGS[lang]}の翻訳は未登録です（0 / {len(faqs)} 件）**　"
        f"この言語で質問しても該当しません。日本語でお試しください。"
        f"　実機では、翻訳が無い項目は日本語の回答を表示し、その旨を画面に断ります。"
    )
elif lang != "ja":
    st.info(f"{LANGS[lang]}の翻訳: {translated} / {len(faqs)} 件が登録済みです。")

# ── 試す ───────────────────────────────────────────────
with tab_try:
    if "q" not in st.session_state:
        st.session_state.q = ""

    st.markdown("**質問例**（押すと入力されます）")
    cols = st.columns(3)
    for i, sample in enumerate(SAMPLES.get(lang, SAMPLES["ja"])):
        if cols[i % 3].button(sample, key=f"s{i}", use_container_width=True):
            st.session_state.q = sample

    question = st.text_input(UI["prompt"][lang], key="q")

    if question.strip():
        result = search(faqs, question, lang, synonyms)

        st.markdown("---")
        if not result.hit:
            st.markdown(f"<div class='staff-box'>{UI['staff'][lang]}</div>",
                        unsafe_allow_html=True)
            st.caption(
                "該当する回答がないため、係員にご案内します。"
                "この質問は記録され、質問回答集に追加すべき候補として集計されます。"
            )
        else:
            faq = result.faq
            text, is_fallback = answer_for(faq, lang)
            has_link = bool(faq.get("link"))

            main, side = st.columns([3, 1] if has_link else [1, 0.001])
            with main:
                pending = (f"<div class='pending'>{UI['pending'][lang]}</div>"
                           if is_fallback and UI["pending"][lang] else "")
                st.markdown(f"<div class='answer-box'>{pending}{text}</div>",
                            unsafe_allow_html=True)

            if has_link:
                with side:
                    st.markdown(
                        f"<img src='data:image/png;base64,{qr_image(faq['link'])}' "
                        f"style='width:100%;max-width:150px;display:block;margin:0 auto'>"
                        f"<div class='qr-cap'>{UI['details'][lang]}</div>",
                        unsafe_allow_html=True)

            photo = faq.get("photo", "")
            if photo:
                path = PHOTO_DIR / photo
                if path.exists():
                    st.image(str(path), width=420)
                else:
                    st.info(f"写真「{photo}」は未登録です（実機では写真なしで表示されます）")

            with st.expander("なぜこの回答が選ばれたか"):
                st.markdown(f"**該当ID**: `{faq['id']}`　"
                            f"**分類**: {CATEGORY_LABEL.get(faq['category'], faq['category'])}")
                st.markdown(f"**一致した質問例**: 「{result.matched_example}」")
                st.markdown(f"**照合された語**: {'、'.join(result.keywords)}")
                st.caption(
                    "質問例のスペースは「かつ」を意味します。"
                    "書かれた語がすべて含まれるときだけ一致します。"
                )

# ── 一覧 ───────────────────────────────────────────────
with tab_list:
    cats = sorted({f["category"] for f in faqs})
    chosen = st.multiselect("分類でしぼる",
                            cats, format_func=lambda c: CATEGORY_LABEL.get(c, c))
    shown = [f for f in faqs if not chosen or f["category"] in chosen]
    st.caption(f"{len(shown)} 件")

    for faq in shown:
        text, is_fallback = answer_for(faq, lang)
        label = f"{CATEGORY_LABEL.get(faq['category'], faq['category'])}｜{faq['id']}"
        with st.expander(label):
            if is_fallback and lang != "ja":
                st.caption("この言語の翻訳は未登録のため、日本語を表示しています")
            st.write(text)
            st.markdown(f"<div class='meta'>想定される聞かれ方: "
                        f"{'、'.join(faq['questions'])}</div>", unsafe_allow_html=True)
            if faq.get("link"):
                st.markdown(f"[詳細ページ]({faq['link']})")

# ── 動作の確認 ──────────────────────────────────────────
with tab_check:
    st.markdown("複数の質問をまとめて試せます。1行に1つ入力してください。")
    default = "\n".join(SAMPLES["ja"])
    lines = st.text_area("質問（1行に1つ）", value=default, height=180)

    if st.button("まとめて確認", type="primary"):
        rows = []
        hit = 0
        for line in [x.strip() for x in lines.splitlines() if x.strip()]:
            r = search(faqs, line, lang, synonyms)
            hit += r.hit
            rows.append({
                "質問": line,
                "結果": r.faq["id"] if r.hit else "— 該当なし —",
                "一致した質問例": r.matched_example if r.hit else "",
            })
        if rows:
            st.markdown(f"**回答できた割合: {hit}/{len(rows)}**")
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption(
                "「該当なし」が多い場合は、質問回答集の「質問例」に"
                "その言い方を足すと拾えるようになります。"
            )