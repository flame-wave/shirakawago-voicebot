"""
白川郷 音声案内 かんたん管理画面

日本語で質問と回答を入れると、他の言語は自動で翻訳され、
質問回答集（tools/faq_master.xlsx）の「FAQ」「多言語」シートに追加される。

Excelを直接触らなくても、ブラウザだけで編集できる。
Excelで開いて直しても構わない。どちらで編集しても同じファイルを見ている。

案内アプリに反映するときは「案内アプリへ反映する」から書き出す。

起動:
    streamlit run admin/app.py
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import faq_excel as X
import faq_translate as T
import log_stats as L
import build_faq
from faq_store import VALID_CATEGORIES, GitHubStore, LocalStore, StoreError

st.set_page_config(page_title="音声案内 管理画面", page_icon="🏘️", layout="wide")

st.markdown("""
<style>
  .hint { color:#5A6B58; font-size:13px; }
  .lang-name { color:#2C5F2D; font-weight:bold; font-size:13px; }
  div[data-testid="stForm"] { border-color:#C3D2BC; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- 設定
def secret(section, key, default=None):
    """設定ファイルが無くても落ちないようにまとめて包む。
    手元で試すときは設定なしで動き、公開時だけ設定を置けばよい。"""
    try:
        return st.secrets[section][key]
    except Exception:
        return default


def get_engine():
    """翻訳の方式を決める。設定が無ければ None（＝日本語のみで運用）。

    どちらを選んでも処理はクラウド側で行われるので、
    職員のパソコンには何も入れなくてよい。
    """
    return T.describe_engine(
        anthropic_key=secret("anthropic", "api_key"),
        open_model={
            "base_url": secret("open_model", "base_url"),
            "api_key": secret("open_model", "api_key"),
            "model": secret("open_model", "model"),
        },
        prefer=secret("translate", "engine"),
    )


def get_store():
    """質問回答集（Excel）の置き場所。"""
    token, repo = secret("github", "token"), secret("github", "repo")
    if token and repo:
        return X.GitHubExcelStore(
            token=token,
            repo=repo,
            path=secret("github", "excel_path", "tools/faq_master.xlsx"),
            branch=secret("github", "branch", "main"),
        )
    return X.LocalExcelStore(ROOT / "tools" / "faq_master.xlsx")


def get_json_store():
    """案内アプリが読む faq.json の置き場所。"""
    token, repo = secret("github", "token"), secret("github", "repo")
    if token and repo:
        return GitHubStore(
            token=token,
            repo=repo,
            path=secret("github", "path", "assets/faq.json"),
            branch=secret("github", "branch", "main"),
        )
    return LocalStore(ROOT / "assets" / "faq.json")


# ---------------------------------------------------------------- 合言葉
def check_password():
    expected = secret("app", "password")
    if not expected:
        return True  # 設定していなければ確認しない（手元で試すとき用）
    if st.session_state.get("ok"):
        return True
    st.title("白川郷 音声案内　管理画面")
    with st.form("login"):
        pw = st.text_input("合言葉", type="password")
        if st.form_submit_button("入る"):
            if pw == expected:
                st.session_state["ok"] = True
                st.rerun()
            else:
                st.error("合言葉が違います")
    return False


if not check_password():
    st.stop()

store = get_store()
engine = get_engine()


# ---------------------------------------------------------------- 読み込み
def load_book():
    raw, sha = store.load()
    st.session_state["raw"] = raw
    st.session_state["sha"] = sha
    return X.FaqBook(raw)


if "raw" not in st.session_state:
    try:
        load_book()
    except (X.ExcelError, Exception) as e:
        st.error(f"質問回答集を開けませんでした: {e}")
        st.stop()

book = X.FaqBook(st.session_state["raw"])
items = book.faq_rows()
done = book.translated_langs()


def save_book(apply_changes, message):
    """保存直前にもう一度読み直してから書き込む。

    Excel側や他の人の編集を上書きしてしまわないようにするため。
    """
    raw, sha = store.load()
    fresh = X.FaqBook(raw)
    apply_changes(fresh)
    new_raw = fresh.to_bytes()
    new_sha = store.save(new_raw, message, sha)
    st.session_state["raw"] = new_raw
    st.session_state["sha"] = new_sha


# ---------------------------------------------------------------- 横の欄
with st.sidebar:
    st.markdown("### 保存先")
    st.caption(store.label)
    st.caption(store.location)

    st.markdown("### 登録数")
    st.caption(f"{len(items)} 件（うち案内に出す {sum(1 for i in items if i['enabled'])} 件）")

    st.markdown("### 翻訳の状況")
    for lang, name in T.LANGS.items():
        n = sum(1 for i in items if lang in done.get(i["id"], set()))
        st.caption(f"{name}: {n} / {len(items)} 件")

    st.markdown("### 翻訳に使うもの")
    if engine:
        st.caption(engine["label"])
    else:
        st.warning("翻訳の設定がされていないため、自動翻訳は使えません。"
                   "日本語のみで保存できます。")

    st.markdown("### 案内画面のキャラクター")
    characters = book.characters()
    if not characters:
        st.caption("「キャラクター」シートがありません。"
                   "`python tools/add_characters.py` で作れます。")
    else:
        names = [c["name"] for c in characters]
        ids = [c["id"] for c in characters]
        current = next((i for i, c in enumerate(characters) if c["default"]), 0)
        picked = st.selectbox(
            "いつも立たせるキャラクター", range(len(characters)),
            index=current, format_func=lambda i: names[i],
            key="character_default",
            help="案内端末を開いたときのキャラクターです。"
                 "利用者は案内画面で選び直せます。",
        )
        if picked != current:
            try:
                save_book(lambda fresh: fresh.set_default_character(ids[picked]),
                          f"既定のキャラクターを{names[picked]}に変更（管理画面より）")
                st.success(f"{names[picked]} にしました。"
                           "「案内アプリへ反映する」から書き出すと反映されます。")
                st.rerun()
            except X.ExcelError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"保存できませんでした: {e}")
        note = characters[picked]["note"]
        if note:
            st.caption(note)

    st.divider()
    if st.button("最新の内容を読み直す", use_container_width=True):
        for k in ("raw", "sha", "pending"):
            st.session_state.pop(k, None)
        st.rerun()

st.title("白川郷 音声案内　管理画面")
st.caption("日本語で入力すると、英語・中国語・韓国語・スペイン語・フランス語に自動で翻訳され、"
           "質問回答集のExcelに追加されます。")

(tab_add, tab_list, tab_bulk, tab_settings, tab_voice,
 tab_publish, tab_stats) = st.tabs(
    ["質問を追加・修正する", "登録されている質問", "まとめて翻訳する",
     "その他の設定", "読み上げの声", "案内アプリへ反映する", "利用状況"]
)


# ---------------------------------------------------------------- 入力欄
def blank():
    return {
        "id": "", "place": "", "category": "other", "questions": [], "answer": "",
        "short": "", "photo": "", "link": "", "audio": "", "chip": "",
        "enabled": True, "show_from": "", "show_until": "",
    }


def parse_date(value):
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return date.today()


def edit_form(item, is_new, places):
    st.markdown("#### 日本語で入力してください")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        fid = st.text_input(
            "管理用の名前（半角英字。あとから変えないでください）",
            value=item["id"], disabled=not is_new, placeholder="例: smoking_area",
        )
    with c2:
        place_options = places + ["（新しく入力する）"]
        idx = place_options.index(item["place"]) if item["place"] in places else 0
        place = st.selectbox("設置場所", place_options, index=idx)
        if place == "（新しく入力する）":
            place = st.text_input("設置場所の名前", value="")
    with c3:
        cat_keys = list(VALID_CATEGORIES)
        category = st.selectbox(
            "分類", cat_keys,
            index=cat_keys.index(item["category"]) if item["category"] in cat_keys else 0,
            format_func=lambda k: VALID_CATEGORIES[k],
        )

    questions = st.text_area(
        "観光客の聞き方（1行に1つ）", value="\n".join(item["questions"]),
        height=130, placeholder="喫煙所\nたばこ 吸える\n喫煙 場所",
    )
    st.markdown(
        "<div class='hint'>1行に1つの言い方を書きます。行の中の空白は「かつ」の意味です。"
        "「たばこ 吸える」は、たばこ と 吸える の両方が入っているときだけ反応します。</div>",
        unsafe_allow_html=True,
    )

    answer = st.text_area(
        "回答（このまま読み上げられます）", value=item["answer"], height=140,
        placeholder="喫煙所は……にございます。",
    )
    st.markdown(
        "<div class='hint'>料金や時間の条件は省略せずに書いてください。"
        "「9時から16時」のように、数字は読み上げやすい形にすると自然に聞こえます。</div>",
        unsafe_allow_html=True,
    )

    short = st.text_area(
        "読み上げ用の短い回答（任意）", value=item["short"], height=80,
        placeholder="回答が長いときに、読み上げ向けの短い言い方を書きます",
    )

    c4, c5 = st.columns(2)
    with c4:
        photo = st.text_input("写真のファイル名（任意）", value=item["photo"],
                              placeholder="例: shuttle_stop.jpg")
    with c5:
        link = st.text_input("参考ページのURL（任意）", value=item["link"],
                             placeholder="https://…")

    chip = st.text_input(
        "よくある質問に出す文言（任意）", value=item["chip"],
        placeholder="例: トイレの場所",
    )
    st.markdown(
        "<div class='hint'>入れると、案内画面の上部に流れる「よくある質問」に並びます。"
        "押すとその文言で検索するので、<b>この文言でこの回答に当たるか</b>を確かめてください。</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### 掲載の期間（お祭りなど期間限定の案内に使います）")
    c6, c7 = st.columns([1, 1])
    with c6:
        enabled = st.checkbox("案内に表示する", value=item["enabled"])
    with c7:
        use_period = st.checkbox(
            "期間を決める", value=bool(item["show_from"] or item["show_until"]),
        )
    show_from = show_until = ""
    if use_period:
        c8, c9 = st.columns(2)
        with c8:
            show_from = st.date_input(
                "この日から", value=parse_date(item["show_from"])).isoformat()
        with c9:
            show_until = st.date_input(
                "この日まで", value=parse_date(item["show_until"])).isoformat()
        st.markdown(
            "<div class='hint'>期間外になると、書き出しのときに自動で案内から外れます。</div>",
            unsafe_allow_html=True,
        )

    return {
        "id": fid.strip(),
        "place": place.strip(),
        "category": category,
        "questions": [q.strip() for q in questions.splitlines() if q.strip()],
        "answer": answer.strip(),
        "short": short.strip(),
        "photo": photo.strip(),
        "link": link.strip(),
        "audio": item["audio"],
        "chip": chip.strip(),
        "enabled": enabled,
        "show_from": show_from,
        "show_until": show_until,
    }


def validate(item, is_new, existing_ids):
    errors = []
    if not item["id"]:
        errors.append("管理用の名前を入れてください")
    elif not all(c.islower() or c.isdigit() or c == "_" for c in item["id"]):
        errors.append("管理用の名前は半角の小文字・数字・アンダースコアだけで書いてください")
    elif is_new and item["id"] in existing_ids:
        errors.append(f"「{item['id']}」はすでに使われています")
    if not item["questions"]:
        errors.append("観光客の聞き方を1つ以上入れてください")
    if not item["answer"]:
        errors.append("回答を入れてください")
    if item["link"] and not item["link"].startswith(("http://", "https://")):
        errors.append("参考ページのURLが正しくありません")
    if item["show_from"] and item["show_until"] and item["show_from"] > item["show_until"]:
        errors.append("掲載期間の開始日が終了日より後になっています")
    return errors


# ---------------------------------------------------------------- 追加・修正
with tab_add:
    options = ["＋ 新しく追加する"] + [f"{i['id']}｜{i['answer'][:26]}…" for i in items]
    picked = st.selectbox("編集するもの", options, key="pick")
    is_new = picked == options[0]
    target = blank() if is_new else items[options.index(picked) - 1]

    item = edit_form(target, is_new, book.places())

    st.divider()
    c1, c2 = st.columns([1, 3])
    with c1:
        do_translate = st.checkbox("他の言語に翻訳する", value=True, disabled=not engine)
    with c2:
        langs = st.multiselect(
            "翻訳する言語", list(T.LANGS), default=list(T.LANGS),
            format_func=lambda k: T.LANGS[k], disabled=not engine,
        )

    if st.button("確認する", type="primary", use_container_width=True):
        errors = validate(item, is_new, {i["id"] for i in items})
        if errors:
            for e in errors:
                st.error(e)
        else:
            for w in T.check_questions(item["questions"]):
                st.warning(w)

            # すでに入っている翻訳は消さずに引き継ぐ
            translations = {} if is_new else {
                lang: dict(tr, machine=X.MACHINE_MARK in tr["note"])
                for lang, tr in book.translations_of(item["id"]).items()
            }

            if do_translate and engine and langs:
                with st.spinner("翻訳しています…"):
                    try:
                        result = T.translate(
                            {item["id"]: {"questions": item["questions"],
                                          "answer": item["answer"]}},
                            langs, engine,
                        )
                        per_lang = result.get(item["id"], {})
                        for lang, v in per_lang.items():
                            if lang in T.LANGS and v.get("answer"):
                                translations[lang] = {
                                    "questions": v.get("questions", []),
                                    "answer": v["answer"],
                                    "machine": True,
                                }
                        st.success(f"{len(per_lang)} 言語に翻訳しました。内容をご確認ください。")
                    except Exception as e:
                        st.error(f"翻訳できませんでした: {e}")
                        st.info("日本語のみで保存することもできます。")

            st.session_state["pending"] = {"item": item, "translations": translations,
                                           "is_new": is_new}

    # ---- 確認して保存
    pending = st.session_state.get("pending")
    if pending and pending["item"]["id"] == item["id"]:
        st.divider()
        st.markdown("### この内容で保存します")
        st.markdown("**日本語**")
        st.info(pending["item"]["answer"])

        if pending["translations"]:
            st.markdown("**翻訳（必要なら直接直せます）**")
            for lang in T.LANGS:
                tr = pending["translations"].get(lang)
                if not tr:
                    continue
                st.markdown(
                    f"<div class='lang-name'>{T.LANGS[lang]}"
                    + ("　※自動翻訳" if tr.get("machine") else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )
                tr["answer"] = st.text_area(
                    f"回答（{T.LANGS[lang]}）", value=tr["answer"],
                    key=f"a_{lang}", height=90, label_visibility="collapsed",
                )
                tr["questions"] = [
                    q.strip() for q in st.text_area(
                        f"聞き方（{T.LANGS[lang]}）",
                        value="\n".join(tr["questions"]),
                        key=f"q_{lang}", height=90,
                    ).splitlines() if q.strip()
                ]

        if st.button("保存する", type="primary", use_container_width=True):
            saved = pending

            def apply_changes(fresh):
                fresh.upsert_faq(saved["item"])
                for lang, tr in saved["translations"].items():
                    if not tr["answer"]:
                        continue
                    fresh.upsert_translation(
                        saved["item"]["id"], lang, tr["questions"], tr["answer"],
                        machine=tr.get("machine", False),
                        source_answer=saved["item"]["answer"],
                    )

            who = "追加" if saved["is_new"] else "修正"
            try:
                save_book(apply_changes, f"{who}: {saved['item']['id']}（管理画面より）")
                st.session_state.pop("pending", None)
                st.success(
                    "質問回答集に保存しました。"
                    "案内アプリに反映するには「案内アプリへ反映する」から書き出してください。"
                )
                st.balloons()
                st.rerun()
            except X.ExcelError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"保存できませんでした: {e}")


# ---------------------------------------------------------------- 一覧
with tab_list:
    if not items:
        st.info("まだ登録がありません。")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            places = st.multiselect("設置場所でしぼる", book.places())
        with c2:
            cats = sorted({i["category"] for i in items})
            chosen = st.multiselect(
                "分類でしぼる", cats,
                format_func=lambda c: VALID_CATEGORIES.get(c, c),
            )
        with c3:
            only_missing = st.checkbox("翻訳が足りないものだけ")

        shown = [
            i for i in items
            if (not places or i["place"] in places)
            and (not chosen or i["category"] in chosen)
            and (not only_missing or len(done.get(i["id"], set())) < len(T.LANGS))
        ]
        st.caption(f"{len(shown)} 件")

        for i in shown:
            have = done.get(i["id"], set())
            mark = "" if i["enabled"] else "（非表示）"
            period = ""
            if i["show_from"] or i["show_until"]:
                period = f"　掲載: {i['show_from'] or '—'} 〜 {i['show_until'] or '—'}"
            with st.expander(
                f"{i['place'] or '—'}｜{VALID_CATEGORIES.get(i['category'], i['category'])}"
                f"｜{i['id']}{mark}"
            ):
                st.write(i["answer"])
                st.caption(f"聞き方: {'、'.join(i['questions'])}")
                missing = [T.LANGS[l] for l in T.LANGS if l not in have]
                st.caption(
                    f"翻訳: {len(have)} / {len(T.LANGS)} 言語"
                    + (f"（未: {'、'.join(missing)}）" if missing else "")
                    + period
                )


# ---------------------------------------------------------------- まとめて翻訳
with tab_bulk:
    st.markdown("### 未翻訳をまとめて翻訳する")
    st.caption("日本語だけ入っている項目を探し、選んだ言語に翻訳して多言語シートに追加します。"
               "すでに入っている翻訳には触りません。")

    bulk_langs = st.multiselect(
        "翻訳する言語", list(T.LANGS), default=list(T.LANGS),
        format_func=lambda k: T.LANGS[k], key="bulk_langs",
    )
    missing = book.missing(bulk_langs)

    if not bulk_langs:
        st.info("言語を選んでください。")
    elif not missing:
        st.success("未翻訳はありません。")
    else:
        by_lang = {}
        for _, lang in missing:
            by_lang[lang] = by_lang.get(lang, 0) + 1
        st.warning(
            "未翻訳: " + "、".join(f"{T.LANGS[l]} {n}件" for l, n in sorted(by_lang.items()))
        )

        ids = sorted({fid for fid, _ in missing})
        limit = st.slider(
            "一度に翻訳する項目数", min_value=1, max_value=max(1, len(ids)),
            value=min(10, len(ids)),
            help="多いほど時間と料金がかかります。まず少数で試すことをおすすめします。",
        )
        st.caption("対象: " + "、".join(ids[:limit]))

        if not engine:
            st.info("翻訳の設定（Secrets の [anthropic] または [open_model]）が"
                    "されていないため実行できません。")
        elif st.button("この内容で翻訳する", type="primary", use_container_width=True):
            targets = ids[:limit]
            by_id = {i["id"]: i for i in items}
            need = {}
            for fid in targets:
                need[fid] = {
                    "questions": by_id[fid]["questions"],
                    "answer": by_id[fid]["answer"],
                }

            try:
                with st.spinner(f"{len(targets)} 件を翻訳しています…（数分かかることがあります）"):
                    result = T.translate(need, bulk_langs, engine)
            except Exception as e:
                st.error(f"翻訳できませんでした: {e}")
                result = None

            if result:
                wrote, skipped = [], []

                def apply_changes(fresh):
                    already = fresh.translated_langs()
                    for fid, per_lang in result.items():
                        if fid not in by_id:
                            skipped.append(f"{fid}: 質問回答集にありません")
                            continue
                        for lang, v in per_lang.items():
                            lang = lang.lower()
                            answer = (v.get("answer") or "").strip()
                            questions = [q.strip() for q in (v.get("questions") or []) if q.strip()]
                            if lang not in bulk_langs:
                                continue
                            if lang in already.get(fid, set()):
                                skipped.append(f"{fid}/{lang}: すでに翻訳があるため残しました")
                                continue
                            if not answer or not questions:
                                skipped.append(f"{fid}/{lang}: 回答か聞き方が空でした")
                                continue
                            fresh.upsert_translation(
                                fid, lang, questions, answer, machine=True,
                                source_answer=by_id[fid]["answer"],
                            )
                            wrote.append(f"{fid}/{lang}")

                try:
                    save_book(apply_changes, f"自動翻訳 {len(targets)} 件（管理画面より）")
                    st.success(f"{len(wrote)} 件を多言語シートに追加しました。")
                    for s in skipped:
                        st.caption("・" + s)
                    st.info("自動翻訳には備考欄に「自動翻訳（要確認）」と入ります。"
                            "料金や条件を含む回答は、公開前に必ず人の目で確認してください。")
                    st.rerun()
                except X.ExcelError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"保存できませんでした: {e}")


# ---------------------------------------------------------------- 書き出し
with tab_publish:
    st.markdown("### 案内アプリへ反映する")
    st.caption("質問回答集（Excel）から faq.json を書き出します。"
               "案内アプリは次の起動でこの内容になります。")

    try:
        (faqs, errors, warnings, pending_tr, synonyms, places,
         voice_sets, reference, char_list, voice_cfg,
         readings) = build_faq.build_from_bytes(
            st.session_state["raw"], ROOT / "assets"
        )
    except Exception as e:
        st.error(f"読み取れませんでした: {e}")
        faqs, errors, warnings, pending_tr = [], [str(e)], [], 0
        synonyms, places, voice_sets, reference = {}, [], [], []
        char_list, voice_cfg, readings = [], {}, []

    c1, c2, c3 = st.columns(3)
    c1.metric("案内に出す質問", f"{len(faqs)} 件")
    c2.metric("翻訳済みの回答", sum(len(f["translations"]) for f in faqs))
    c3.metric("エラー", f"{len(errors)} 件")

    st.caption("　".join(
        f"{T.LANGS[l]}: {sum(1 for f in faqs if l in f['translations'])}/{len(faqs)}"
        for l in T.LANGS
    ))

    if errors:
        st.error("エラーを直すまで書き出せません。")
        for e in errors:
            st.write("× " + e)
    if warnings:
        with st.expander(f"確認したいこと（{len(warnings)} 件）"):
            for w in warnings:
                st.write("・" + w)

    # いま書き出される内容のうち、現場で効き方が見えにくいものを先に見せる。
    # 以前、管理画面でキャラクターを変えたのに書き出しを忘れ、
    # 案内端末には古いキャラクターが立ち続けたことがあった。
    default_char = next((c["name"] for c in char_list if c.get("default")), None)
    if default_char:
        st.caption(f"最初に立つキャラクター: **{default_char}**　"
                   f"読み方の直し: {len(readings)} 語")
        st.warning("キャラクターや設定を変えたときは、**この書き出しをするまで"
                   "案内端末には届きません。**")

    json_store = get_json_store()
    st.caption(f"書き出し先: {json_store.label}")

    def make_payload():
        return {
            "version": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "count": len(faqs),
            "faqs": faqs,
            "synonyms": synonyms,
            "places": places,
            "voice_sets": voice_sets,
            "reference": reference,
            "characters": char_list,
            "voice": voice_cfg,
            "readings": readings,
        }

    if st.button("書き出す", type="primary", disabled=bool(errors),
                 use_container_width=True):
        payload = make_payload()
        try:
            _, sha = json_store.load()
            json_store.save(payload, "質問回答集を反映（管理画面より）", sha)
            st.success(f"書き出しました（版: {payload['version']}）。"
                       "案内端末は次の起動で新しい内容になります。")
        except StoreError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"書き出せませんでした: {e}")

    st.download_button(
        "faq.json をダウンロード",
        data=json.dumps(make_payload(), ensure_ascii=False, indent=2),
        file_name="faq.json",
        mime="application/json",
        use_container_width=True,
    )


# ---------------------------------------------------------------- 利用状況
with tab_stats:
    st.subheader("利用状況")
    st.caption("案内端末で何が聞かれたかを、設置場所ごとに見られます。"
               "案内端末の画面からは見られないようにしてあります。")

    log_url = secret("logs", "url")
    log_token = secret("logs", "token")

    if not log_url or not log_token:
        st.info(
            "記録の読み出し先が設定されていません。\n\n"
            "中継サーバを置いた場所を Secrets に書いてください。\n\n"
            "```toml\n[logs]\nurl   = \"https://例.com/api/logs.php\"\n"
            "token = \"中継サーバの config.php に書いた log_token と同じ文字列\"\n```"
        )
    else:
        period = st.radio(
            "期間", ["直近7日", "直近30日", "すべて"],
            horizontal=True, key="stats_period",
        )
        days = {"直近7日": 7, "直近30日": 30, "すべて": None}[period]

        if st.button("記録を読み込む", key="stats_load"):
            st.session_state.pop("log_rows", None)

        if "log_rows" not in st.session_state:
            with st.spinner("記録を読み込んでいます…"):
                try:
                    st.session_state["log_rows"] = L.fetch(log_url, log_token)
                except Exception as e:
                    st.error(str(e))
                    st.session_state["log_rows"] = []

        rows = L.within(st.session_state.get("log_rows", []), days)

        if not rows:
            st.info("この期間の記録はまだありません。")
        else:
            overall = L.summarize(rows)
            c1, c2, c3 = st.columns(3)
            c1.metric("質問の総数", overall["total"])
            # 職員に回さずに済んだ割合。設置の効果はこの数字で見る。
            c2.metric("その場で答えられた", f"{overall['answered_rate']:.0%}")
            c3.metric("職員へ回った", overall["by_source"].get("none", 0))

            st.divider()
            st.markdown("#### 設置場所ごと")

            groups = L.by_client(rows)
            columns = st.columns(max(len(groups), 1))
            for column, (name, stat) in zip(columns, groups.items()):
                with column:
                    st.markdown(f"**{name}**")
                    st.metric("質問数", stat["total"])
                    st.caption(f"その場で答えられた {stat['answered_rate']:.0%}")
                    for key, label in L.SOURCES.items():
                        st.caption(f"{label}: {stat['by_source'].get(key, 0)} 件")
                    langs = "　".join(
                        f"{k}:{v}" for k, v in
                        sorted(stat["by_lang"].items(), key=lambda x: -x[1])
                    )
                    st.caption(f"言語 {langs}")

            st.divider()
            st.markdown("#### 答えられなかった質問")
            st.caption("ここに並ぶものを質問回答集に足すと、答えられる割合が上がります。")

            for name, stat in groups.items():
                if not stat["unmatched"]:
                    continue
                with st.expander(f"{name}（{len(stat['unmatched'])} 種類）"):
                    for text, count in stat["unmatched"]:
                        st.write(f"{count} 回　{text}")

            st.divider()
            st.markdown("#### その場所でだけ聞かれた質問")
            st.caption("ほかの案内所では出ていない質問です。"
                       "その案内所向けの回答（設置場所を指定した回答）を足す候補になります。")

            for name in groups:
                unique = L.only_here(rows, name)
                if not unique:
                    continue
                with st.expander(f"{name}（{len(unique)} 種類）"):
                    for text, count in unique:
                        st.write(f"{count} 回　{text}")

            st.divider()
            st.markdown("#### よく聞かれた質問")
            for name, stat in groups.items():
                if not stat["top_faq"]:
                    continue
                with st.expander(name):
                    for faq_id, count in stat["top_faq"]:
                        label = next(
                            (i["answer"][:40] for i in items if i["id"] == faq_id), ""
                        )
                        st.write(f"{count} 回　`{faq_id}`　{label}")


# ---------------------------------------------------------------- 読み上げの声
with tab_voice:
    st.subheader("読み上げの声")
    st.caption("どの案内端末でも同じになるようにします。"
               "ここで決めた内容は「案内アプリへ反映する」で書き出すと効きます。")

    # ---- 用意した音声（VOICEVOXなどで作ったもの）
    st.markdown("#### 用意した音声")
    sets = book.voice_sets()
    if not sets:
        st.caption("「音声セット」シートがありません。"
                   "`python tools/make_voice.py` で音声を作ると登録されます。")
    else:
        st.caption("回答ごとに用意した音声のうち、どれを鳴らすかを決めます。"
                   "選んだ音声が無い回答は、端末の声で読み上げます。")
        labels = [v["name"] for v in sets]
        folders = [v["folder"] for v in sets]
        now = next((i for i, v in enumerate(sets) if v["default"]), 0)
        picked = st.selectbox(
            "いつも鳴らす音声", range(len(sets)),
            index=now, format_func=lambda i: labels[i], key="voice_set_default",
        )
        if picked != now:
            try:
                save_book(lambda fresh: fresh.set_default_voice_set(folders[picked]),
                          f"既定の音声を{labels[picked]}に変更（管理画面より）")
                st.success(f"{labels[picked]} にしました。")
                st.rerun()
            except X.ExcelError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"保存できませんでした: {e}")
        if sets[picked]["note"]:
            st.caption(sets[picked]["note"])

    st.divider()

    # ---- 端末の声（言語ごと）
    st.markdown("#### 端末の声")
    st.info(
        "**端末に入っている声は、端末ごとに違います。**　"
        "ここで決められるのは「どれを優先するか」までです。"
        "書いた声が入っていない端末では、その言語の声から自動で選びます。\n\n"
        "入っている声の一覧と試し聞きは、案内端末の画面でしかできません"
        "（URLに `?setup=1` を付けて開く）。"
    )

    rows = book.voice_settings()
    if not rows:
        st.caption("「読み上げ」シートがありません。"
                   "`python tools/add_voice_settings.py` で作れます。")
    else:
        by_lang = {r["lang"]: r for r in rows}
        names = {"ja": "日本語", **T.LANGS}
        for lang in ["ja"] + list(T.LANGS):
            row = by_lang.get(lang)
            if row is None:
                continue
            with st.expander(f"{names.get(lang, lang)}（{lang}）", expanded=(lang == "ja")):
                with st.form(f"voice_{lang}"):
                    voices = st.text_area(
                        "優先する声（上から順に探します。カンマ区切り）",
                        value=row["voices"], height=80, key=f"voices_{lang}",
                        help="名前の一部が合えば採用します。"
                             "例: 「Microsoft Aria」と書けば "
                             "「Microsoft Aria - English (United States)」に当たります。",
                    )
                    c1, c2 = st.columns(2)
                    rate = c1.slider("速さ", 0.5, 1.5, float(row["rate"]), 0.05,
                                     key=f"rate_{lang}",
                                     help="1.0が標準。小さいほどゆっくり話します。")
                    pitch = c2.slider("高さ", 0.5, 1.5, float(row["pitch"]), 0.05,
                                      key=f"pitch_{lang}",
                                      help="1.0が標準。大きいほど高い声になります。")
                    if st.form_submit_button("この言語の設定を保存", type="primary"):
                        try:
                            save_book(
                                lambda fresh, lg=lang, v=voices, r=rate, pt=pitch:
                                    fresh.update_voice_setting(lg, v, r, pt),
                                f"{names.get(lang, lang)}の読み上げ設定を変更（管理画面より）",
                            )
                            st.success("保存しました。"
                                       "「案内アプリへ反映する」で書き出すと効きます。")
                            st.rerun()
                        except X.ExcelError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"保存できませんでした: {e}")


# ---------------------------------------------------------------- その他の設定
# Excelを開かなくても、管理画面だけで設定を変えられるようにする。
# 表の形はExcelのままなので、どちらで直しても同じ結果になる。
SETTING_SHEETS = {
    "言い換え": {
        "説明": "観光客の言い方を、質問例に書かれている語へ橋渡しします。"
                "「銀行」と聞かれたら「atm」の質問に当てる、という具合です。",
        "注意": "「代表語」は**質問例に実際にある語**にしてください。"
                "無い語を書いても、どの質問にも当たりません。",
        "幅広": ["同じ意味の語", "備考"],
    },
    "設置場所": {
        "説明": "案内所の場所です。観光客の現在地から近い方の回答を選ぶのに使います。"
                "各言語の名前は、観光客の画面に出る表記です。",
        "注意": "「名前」はFAQシートの「設置場所」列と同じ文字にしてください。"
                "座標はGoogleマップで右クリック→座標をコピーで取れます。",
        "幅広": ["備考", "英語名", "中国語名", "韓国語名", "スペイン語名", "フランス語名"],
    },
    "参考資料": {
        "説明": "AIが答えを組み立てるときの下地です。質問回答集に無い聞かれ方"
                "（「雨の日は大丈夫ですか」など）に答えられるようになります。",
        "注意": "**ここに書いたことは、AIがそのまま根拠にします。**"
                "確かめていないことは書かないでください。"
                "`【質問回答集より】` で始まる行は自動で作られるので、直接直さないでください。",
        "幅広": ["内容", "備考"],
    },
    "読み方": {
        "説明": "読み上げの読み間違いを直します。合成音声は「荻町」を「はぎまち」、"
                "「朴葉味噌」を「ぼくようみそ」のように読んでしまうため、"
                "読み上げるときだけカタカナに差し替えます。",
        "注意": "**画面に出る文字は変わりません**（読み上げだけに使います）。"
                "「読み」はカタカナで書いてください。日本語の読み上げにだけ当てます。"
                "備考に「要確認」と書いてある行は、正しい読みを確かめてから使ってください。",
        "幅広": ["備考"],
    },
    "キャラクター": {
        "説明": "案内画面に立つキャラクターです。画像は `assets/character/` に置きます。"
                "「聞き取り中」「話している」は空欄でよく、空なら「通常」の画像を使います。",
        "注意": "「口の高さ」「顔の広さ」は吹き出しの尻尾を口元に向けるための値、"
                "「大きさ」は1.0が基準、「高さ位置」は0が下端・1が上端です。",
        "幅広": ["備考"],
    },
}

with tab_settings:
    st.subheader("その他の設定")
    st.caption("Excelを開かずに直せます。直したあとは"
               "「案内アプリへ反映する」から書き出すと、案内端末に届きます。")

    sheet = st.radio("設定の種類", list(SETTING_SHEETS), horizontal=True,
                     key="setting_sheet")
    meta = SETTING_SHEETS[sheet]
    st.markdown(meta["説明"])
    st.info(meta["注意"])

    titles, rows = book.sheet_rows(sheet)
    if not titles:
        st.error(f"「{sheet}」シートがありません。")
    else:
        import pandas as pd

        frame = pd.DataFrame(rows, columns=titles) if rows else \
            pd.DataFrame(columns=titles)

        config = {}
        for t in titles:
            if t in meta["幅広"]:
                config[t] = st.column_config.TextColumn(t, width="large")
            else:
                config[t] = st.column_config.TextColumn(t)

        edited = st.data_editor(
            frame, column_config=config, num_rows="dynamic",
            use_container_width=True, hide_index=True,
            key=f"editor_{sheet}",
        )

        c1, c2 = st.columns([1, 3])
        if c1.button("この内容で保存", type="primary", key=f"save_{sheet}"):
            # すべて空の行は保存しない（表の下に出る入力用の空行を拾わないため）
            new_rows = [
                {t: ("" if pd.isna(v) else str(v)).strip()
                 for t, v in record.items()}
                for record in edited.to_dict("records")
            ]
            new_rows = [r for r in new_rows if any(r.values())]
            try:
                save_book(lambda fresh: fresh.write_sheet(sheet, new_rows),
                          f"「{sheet}」を変更（管理画面より）")
                st.success(f"{len(new_rows)} 行を保存しました。"
                           "「案内アプリへ反映する」で書き出すと効きます。")
                st.rerun()
            except X.ExcelError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"保存できませんでした: {e}")
        c2.caption("行の追加は表の一番下、削除は行を選んで Delete キーです。")
