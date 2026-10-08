"""「質問を追加・修正する」画面。

職員さんが、観光客から聞かれたことを1件ずつ足す・直す画面。
4つの手順に分けてある。

  ① どこで案内しますか   … 設置場所・分類
  ② 観光客はどう聞きますか … 聞き方（1つずつ足すチップ）
  ③ なんと答えますか     … 回答
  ④ そのほか             … 写真・参考ページ・よくある質問・期間（なくても登録できる）

右側には、保存する前に確かめられる欄を置く。
  ・試しに聞いてみる   … 案内アプリと同じ決め方で、この回答が出るかを見る
  ・案内画面での見え方 … 吹き出し・写真・QRコード、読み上げも聞ける
  ・翻訳               … 5つの言語の状態

【保存の中身は以前と同じ】
Excel の「FAQ」「多言語」シートに書く。列や形は変えていない。
画面が変わっただけなので、Excel で直した内容もそのまま読める。
"""
import io
import re
from datetime import date
from html import escape

import streamlit as st

import faq_excel as X
import faq_translate as T
import matcher
import speech
import ui
from faq_store import VALID_CATEGORIES
from photo_store import safe_name

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
COMMON = "共通"
# 設置場所ごとに、管理用の名前の後ろに付ける印（これまでの付け方に合わせる）
PLACE_SUFFIX = {"バスターミナル": "_bt", "であいの館": "_deai"}
# 回答の長さの目安（これを超えると聞き取りにくい）
ANSWER_GOAL = 120

SAVE_NOTE = ("保存しただけでは案内に出ません。最後に「案内アプリへ反映する」を押します。"
             "「下書きとして保存」は、案内に出さない状態で残します。")


# ---------------------------------------------------------------- 下ごしらえ
def _places(book):
    """設置場所の選択肢。「共通」を先頭に、設置場所シートの名前を並べる。"""
    names = []
    try:
        _, rows = book.sheet_rows("設置場所")
        names = [r.get("名前", "").strip() for r in rows if r.get("名前", "").strip()]
    except Exception:
        pass
    for p in book.places():
        if p and p != COMMON and p not in names:
            names.append(p)
    return [COMMON] + names


def _place_label(place, places):
    if place == COMMON:
        return "両方の案内所" if len(places) == 3 else "すべての案内所"
    return f"{place}だけ"


def _in_period(item, today=None):
    today = today or date.today().isoformat()
    if item.get("show_from") and today < item["show_from"][:10]:
        return False
    if item.get("show_until") and today > item["show_until"][:10]:
        return False
    return True


def _period_text(f, u):
    if not f and not u:
        return "いつも案内する"
    fmt = lambda d: f"{int(d[5:7])}/{int(d[8:10])}" if d else ""
    return f"{fmt(f) or '…'} 〜 {fmt(u) or '…'}"


def _problems(q):
    """聞き方の心配な点。無ければ空。"""
    words = [w for w in q.split() if w]
    out = []
    if words and all(w.lower() in T.GENERIC for w in words):
        out.append(f"「{' ＋ '.join(words)}」だけだと、ほかの質問にも反応してしまいます。"
                   "「喫煙所 ＋ どこ」のように、内容を表す言葉と組み合わせてください。")
    short = [w for w in words if len(w) < 2]
    if short:
        out.append(f"「{'」「'.join(short)}」は1文字のため、ほかの言葉の一部にも当たってしまいます。"
                   "2文字以上の言葉にしてください。")
    if len(words) == 1 and _is_sentence(words[0]):
        out.append(f"「{words[0]}」は文のままです。まったく同じ言い方のときにしか当たらないので、"
                   "「かんじき 借りる」のように、言葉を空白で分けた言い方も足してください。")
    return out


# 文の終わり方。名前（「ゲストハウスKei」など）を文と取り違えないよう、長さではなく形で見る。
_SENTENCE_END = ("か", "たい", "ます", "ください", "いい", "ある", "できる", "です")


def _is_sentence(text):
    """空白で分けていない、話し言葉のままの文か（利用状況から持ってきた質問など）。"""
    t = text.strip().rstrip("？?！!。")
    return len(t) >= 6 and (any(m in text for m in "？?。、") or t.endswith(_SENTENCE_END))


def _clean(q):
    return re.sub(r"\s+", " ", (q or "").replace("　", " ")).strip()


def _blank():
    return {"id": "", "place": COMMON, "category": "other", "questions": [],
            "answer": "", "short": "", "photo": "", "link": "", "audio": "",
            "chip": "", "enabled": True, "show_from": "", "show_until": ""}


# ---------------------------------------------------------------- 状態
# 入力中の内容は session_state の「q_」で始まる名前に持つ。
# 別の質問を開いたときだけ読み込み直し、それ以外は入力を保つ。
def _load(target, item):
    ss = st.session_state
    item = item or _blank()
    ss.q_loaded = target
    ss.q_place = item["place"] or COMMON
    ss.q_cat = item["category"] if item["category"] in VALID_CATEGORIES else "other"
    ss.q_questions = list(item["questions"])
    ss.q_answer = item["answer"]
    ss.q_short = item["short"]
    ss.q_photo = item["photo"]
    ss.q_link = item["link"]
    ss.q_chip = item["chip"]
    ss.q_from = item["show_from"][:10] if item["show_from"] else ""
    ss.q_until = item["show_until"][:10] if item["show_until"] else ""
    ss.q_audio = item.get("audio", "")
    ss.q_id_manual = ""
    ss.q_open = ""
    ss.q_suggest = []
    ss.q_photo_new = False
    ss.q_try = ""


def _draft(fid):
    ss = st.session_state
    return {
        "id": fid,
        "place": ss.q_place or COMMON,
        "category": ss.q_cat or "other",
        "questions": list(ss.q_questions),
        "answer": (ss.q_answer or "").strip(),
        "short": (ss.q_short or "").strip(),
        "photo": ss.q_photo,
        "link": ss.q_link,
        "audio": ss.q_audio,
        "chip": ss.q_chip,
        "show_from": ss.q_from,
        "show_until": ss.q_until,
    }


# ---------------------------------------------------------------- 管理用の名前
def _auto_id(ctx, answer, category, place, taken):
    """回答の内容から管理用の名前を作る。すでにある名前とは重ならないようにする。

    AIの設定があれば内容に合った英語の名前（smoking_area）、
    無ければ分類と番号（manner_012）にする。
    設置場所が決まっていれば、これまでどおり _bt / _deai を後ろに付ける。
    """
    ss = st.session_state
    base = ""
    text = answer.strip()
    if ctx.engine and len(text) >= 10:
        cache = ss.setdefault("q_slug_cache", {})
        if text not in cache:
            try:
                with st.spinner("管理用の名前を考えています…"):
                    cache[text] = T.make_slug(text, ctx.engine)
            except Exception:
                cache[text] = ""
        base = cache[text]
    if not base or not ID_PATTERN.match(base):
        nums = [int(m.group(1)) for i in taken
                if (m := re.match(rf"^{re.escape(category)}_(\d+)", i))]
        base = f"{category}_{(max(nums) + 1 if nums else 1):03d}"

    candidate = base + PLACE_SUFFIX.get(place, "")
    if candidate not in taken:
        return candidate
    n = 2
    while f"{candidate}_{n}" in taken:
        n += 1
    return f"{candidate}_{n}"


# ---------------------------------------------------------------- 試しに聞いてみる
def _synonyms(book):
    out = {}
    try:
        _, rows = book.sheet_rows("言い換え")
    except Exception:
        return out
    for r in rows:
        lang = (r.get("言語") or "ja").strip().lower() or "ja"
        rep = (r.get("代表語") or "").strip()
        words = [w.strip() for w in re.split(r"[\n、,]", r.get("同じ意味の語") or "")
                 if w.strip()]
        if rep and words:
            out.setdefault(lang, {})[rep] = words
    return out


def _label_of(faq):
    text = (faq.get("answer") or "").replace("\n", " ")
    return text[:26] + ("…" if len(text) > 26 else "")


def _try(ctx, draft, places, text):
    """入力した文で、案内アプリならどの回答を出すかを確かめる。

    保存前の内容（入力中のこの回答）も含めて照合する。
    ほかの回答は、いま案内に出ているもの（案内に出す・期間内）だけを使う。
    """
    me = dict(draft, id=draft["id"] or "__draft__")
    faqs = []
    placed = False
    for item in ctx.items:
        if item["id"] == ctx.editing:
            faqs.append(me)
            placed = True
        elif item["enabled"] and _in_period(item):
            faqs.append(item)
    if not placed:
        faqs.append(me)

    syn = _synonyms(ctx.book)
    if me["place"] == COMMON:
        contexts = [None] + [p for p in places if p != COMMON]
    else:
        contexts = [me["place"]]

    results = []
    for where in contexts:
        hit, found = matcher.search(faqs, text, syn, where)
        if hit and hit[1]["id"] == me["id"]:
            others = [f for s, f, _ in found if f["id"] != me["id"] and s >= 2]
            results.append(("ok", where, hit[2], others))
        elif hit:
            results.append(("taken", where, hit[2], hit[1]))
        else:
            results.append(("none", where, None, None))
    return results


def _where_text(where):
    return "現在地を選んでいない観光客の端末" if where is None else f"{where}の端末"


def _render_try(results):
    kinds = {r[0] for r in results}
    # どの端末でも同じ結果なら、1つにまとめて出す
    if len(kinds) == 1 and len({(r[2], getattr(r[3], "get", lambda k: None)("id")
                                if r[0] == "taken" else None) for r in results}) == 1:
        results = results[:1]
        single = True
    else:
        single = False

    html = []
    for kind, where, q, extra in results:
        head = "" if single else f"{_where_text(where)}では、"
        if kind == "ok":
            matched = " ＋ ".join(q.split())
            if extra:
                tail = (f"ほかに「{escape(_label_of(extra[0]))}」にも当たりますが、"
                        "こちらが優先されます。")
            else:
                tail = "ほかの回答とはぶつかっていません。"
            html.append(ui.box(f"{head}この回答が出ます",
                               f"「{escape(matched)}」に当たりました。{tail}", "ok"))
        elif kind == "taken":
            matched = " ＋ ".join(q.split())
            html.append(ui.box(
                f"{head}ほかの回答が出ます",
                f"「{escape(_label_of(extra))}」の「{escape(matched)}」に当たりました。"
                "② に、もっと具体的な言い方を足してください。", "warn"))
        else:
            html.append(ui.box(
                f"{head}どの回答も出ません",
                "この聞き方に含まれる言葉を、② の言い方に足してください。", "info"))
    st.markdown("".join(html), unsafe_allow_html=True)


# ---------------------------------------------------------------- 見え方・読み上げ
def _readings(book):
    """読み方の表のうち、有効なもの [(表記, 読み)]。"""
    try:
        _, rows = book.sheet_rows("読み方")
    except Exception:
        return []
    return [(src, yomi) for src, yomi, on in speech.clean_reading_rows(rows) if on]


def _preview(ctx, draft, places):
    thumb = None
    chars = ctx.book.characters()
    standing = next((c for c in chars if c["default"]), chars[0] if chars else None)
    if standing:
        thumb = ctx.character_thumb(standing["idle"])
    char_html = (f'<img src="{thumb["url"]}" style="height:150px;display:block">'
                 if thumb else
                 '<div style="width:64px;height:120px;border-radius:30px 30px 10px 10px;'
                 'border:2px dashed #8FB08C;background:#B9CDB4"></div>')
    answer = draft["answer"] or "③ に回答を入れると、ここに出ます"
    color = "#1F2A1F" if draft["answer"] else "#8A9A88"
    st.markdown(f"""
<div style="background:#DDE7E6;border-radius:12px;padding:14px;display:flex;
            gap:10px;align-items:flex-end;min-height:170px">
  <div style="flex:1;background:#fff;border-radius:12px;padding:12px 14px;
              font-size:14px;line-height:1.7;color:{color};align-self:flex-start;
              max-height:260px;overflow:auto">{escape(answer)}</div>
  <div style="flex:none">{char_html}</div>
</div>""", unsafe_allow_html=True)

    tags = []
    tags.append(ui.badge("写真あり", "ok") if draft["photo"] else ui.badge("写真なし", "mute"))
    tags.append(ui.badge("QRコードあり", "ok") if draft["link"] else ui.badge("QRコードなし", "mute"))
    if draft["show_from"] or draft["show_until"]:
        tags.append(ui.badge("期間 " + _period_text(draft["show_from"], draft["show_until"]), "info"))
    tags.append(ui.badge(_place_label(draft["place"], places), "mute"))
    st.markdown('<div style="display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 8px">'
                + "".join(tags) + "</div>", unsafe_allow_html=True)

    # 案内アプリの読み上げと同じく、読み方の直しを当てた文を読む
    # （回答ごとに用意した録音がある場合、案内アプリはそちらを鳴らす）
    voices, rate, pitch = speech.voice_of(
        next((v for v in ctx.book.voice_settings() if v.get("lang") == "ja"), {}))
    speech.listen_button(speech.apply_readings(draft["answer"], _readings(ctx.book)),
                         "ja", voices, rate, pitch, label="🔈 読み上げを聞いてみる")


def _translation_state(ctx, draft):
    """5つの言語の状態。[(言語名, 文字, 種類)]"""
    out = []
    saved = ctx.book.translations_of(ctx.editing) if ctx.editing else {}
    for lang, name in T.LANGS.items():
        short = name.split("（")[0]
        tr = saved.get(lang)
        if not tr or not tr.get("answer"):
            out.append((short, "保存で翻訳" if ctx.engine else "未翻訳",
                        "mute"))
            continue
        m = re.search(r"日本語原文: (.*)", tr.get("note", ""), re.S)
        source = m.group(1).split("｜")[0].strip() if m else None
        if source is not None and source != draft["answer"]:
            out.append((short, "保存で訳し直し" if ctx.engine else "日本語が変わった",
                        "warn"))
        elif X.MACHINE_MARK in tr.get("note", ""):
            out.append((short, "自動翻訳", "info"))
        else:
            out.append((short, "翻訳済み", "ok"))
    return out


# ---------------------------------------------------------------- 保存
def _validate(draft, is_new, taken):
    errors = []
    if not draft["questions"]:
        errors.append("② の言い方を1つ以上追加してください。")
    if not draft["answer"]:
        errors.append("③ の回答を入れてください。")
    if is_new and not ID_PATTERN.match(draft["id"] or ""):
        errors.append("管理用の名前は、英小文字・数字・_ だけで付けてください。")
    if is_new and draft["id"] in taken:
        errors.append("その管理用の名前は、すでに使われています。")
    if draft["link"] and not re.match(r"^https?://", draft["link"]):
        errors.append("参考ページは http:// か https:// で始まる形で入れてください。")
    if draft["show_from"] and draft["show_until"] and draft["show_from"] > draft["show_until"]:
        errors.append("案内する期間の「いつから」が「いつまで」より後になっています。")
    return errors


def _save(ctx, draft, enabled, is_new, taken):
    ss = st.session_state
    errors = _validate(draft, is_new, taken)
    if errors:
        ss.q_errors = errors
        st.toast("直してほしいところがあります（画面の上に出しています）", icon="⚠️")
        st.rerun()

    item = dict(draft, enabled=enabled)
    before = None if is_new else ctx.book.find(draft["id"])
    # 日本語が変わったときだけ訳し直す（人が直した訳を、むやみに上書きしないため）
    ja_changed = (before is None or before["answer"] != item["answer"]
                  or before["questions"] != item["questions"])

    per_lang, tr_error = {}, ""
    if ctx.engine and ja_changed:
        try:
            with st.spinner("5つの言語に翻訳しています…（数十秒かかることがあります）"):
                result = T.translate({item["id"]: {"questions": item["questions"],
                                                   "answer": item["answer"]}},
                                     list(T.LANGS), ctx.engine)
            per_lang = {k: v for k, v in result.get(item["id"], {}).items()
                        if k in T.LANGS and v.get("answer")}
        except Exception as e:
            tr_error = str(e)

    def apply_changes(fresh):
        fresh.upsert_faq(item)
        for lang, v in per_lang.items():
            fresh.upsert_translation(item["id"], lang, v.get("questions", []),
                                     v["answer"], machine=True,
                                     source_answer=item["answer"])

    who = "追加" if is_new else "修正"
    try:
        ctx.save_book(apply_changes, f"{who}: {item['id']}（管理画面より）")
    except X.ExcelError as e:
        ss.q_errors = [str(e)]
        st.rerun()
    except Exception as e:
        ss.q_errors = [f"保存できませんでした: {e}"]
        st.rerun()

    if enabled:
        msg = "保存しました。"
    else:
        msg = "下書きとして保存しました（案内には出ていません）。"
    if per_lang:
        msg += f"{len(per_lang)}つの言語にも翻訳しました。"
    msg += "案内アプリに出すには、左の「案内アプリへ反映する」を押してください。"
    ss.q_flash = ("ok", msg)
    if tr_error:
        ss.q_flash_warn = ("日本語は保存しましたが、翻訳はできませんでした"
                           f"（{tr_error[:80]}）。あとで「まとめて翻訳する」から翻訳できます。")
    # 保存した質問を「修正」で開き直す
    st.query_params["id"] = item["id"]
    ss.q_loaded = None
    st.toast(msg[:40] + "…", icon="✅")
    st.rerun()


# ---------------------------------------------------------------- 画面
def render(ctx):
    ss = st.session_state
    book, items = ctx.book, ctx.items
    by_id = {i["id"]: i for i in items}
    taken = set(by_id)
    places = _places(book)

    target = st.query_params.get("id", "")
    if target and target not in by_id:
        target = ""
    ctx.editing = target
    is_new = not target
    if ss.get("q_loaded") != target:
        _load(target, by_id.get(target))

    # 利用状況の「この質問を追加する」から来たとき（?q=聞かれた文）。
    # その文を聞き方に入れ、試しに聞いてみる欄にも入れておく。
    # 「AIが答えた質問」から来たときは、AIの答えも下書きとして入れる（?a=AIの答え）。
    asked = st.query_params.get("q", "")
    ai_answer = st.query_params.get("a", "")
    if is_new and asked and ss.get("q_seeded") != asked:
        _load("", None)
        ss.q_questions = [_clean(asked)]
        ss.q_try = asked
        ss.q_seeded = asked
        if ai_answer:
            ss.q_answer = ai_answer
            ss.q_flash = ("info", f"AIが答えた質問「{escape(asked)}」から開きました。"
                                  "AIの答えを回答の下書きに入れてあります。"
                                  "<b>料金・時間・場所が正しいかを確かめて</b>から保存してください。")
        else:
            ss.q_flash = ("info", f"利用状況で答えられなかった質問「{escape(asked)}」から開きました。"
                                  "聞き方に入れてあります。言葉を空白で分けた言い方も足すと、"
                                  "似た聞き方にも当たるようになります。")
    if ss.q_place not in places:
        places.append(ss.q_place)

    # ---- 画面の題
    saved = by_id.get(target)
    if is_new:
        status = ("新しく追加・まだ案内には出ていません", "mute")
    else:
        if not saved["enabled"]:
            status = [("案内に出さない（下書き）", "mute")]
        elif not _in_period(saved):
            status = [("期間外 " + _period_text(saved["show_from"], saved["show_until"]), "info")]
        else:
            status = [("案内中", "ok")]
        pending = {c.get("id") for c in (ctx.unpublished() or [])}
        if target in pending:
            status.append(("未反映", "warn"))
    # パンくず。「登録されている質問」は押すと一覧へ戻る
    st.page_link(ctx.list_page, label="登録されている質問 › "
                 + ("新しく追加" if is_new else "修正"), icon=":material/arrow_back:")
    ui.page_header("質問を追加する" if is_new else "質問を修正する", status=status)

    ctx.translation_warning()

    # ---- 保存の結果・直してほしいところ（画面の上に出す）
    flash = ss.pop("q_flash", None)
    if flash:
        ui.notice(flash[1], kind=flash[0], key="q-flash")
    warn = ss.pop("q_flash_warn", None)
    if warn:
        ui.notice(warn, kind="warn", key="q-flash-warn")
    errors = ss.pop("q_errors", None)
    if errors:
        ui.notice("直してほしいところがあります。<br>" + "<br>".join(
            "・" + escape(e) for e in errors), kind="warn", key="q-errors")

    # ---- 修正するものを開く（主な入口は「登録されている質問」の一覧）
    with st.expander("登録済みの質問を開いて直す" if is_new else "ほかの質問を開く・新しく追加する"):
        options = [""] + [i["id"] for i in items]
        labels = {"": "（選んでください）"}
        for i in items:
            labels[i["id"]] = f"{_label_of(i)}（{_place_label(i['place'] or COMMON, places)}）"
        pick = st.selectbox("開く質問", options, format_func=labels.get,
                            index=options.index(target) if target in options else 0,
                            key="q_pick", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        if c1.button("この質問を開く", disabled=not pick or pick == target,
                     use_container_width=True):
            st.query_params["id"] = pick
            st.rerun()
        if not is_new and c2.button("新しく追加する", use_container_width=True):
            st.query_params.clear()
            ss.q_loaded = None
            st.rerun()
        st.caption("ふだんは「登録されている質問」の一覧で、直したい質問の項目名を押して開きます。")

    left, right = st.columns([2.15, 1], gap="large")

    # ================================================================ 左
    with left:
        # ① どこで案内しますか
        with ui.card("q1"):
            ui.step(1, "どこで案内しますか")
            ui.field_label("設置場所", "どの案内所の端末で、この回答を出すかを選びます。")
            st.radio("設置場所", places, key="q_place", horizontal=True,
                     format_func=lambda p: _place_label(p, places),
                     label_visibility="collapsed")
            ui.field_label("分類")
            st.pills("分類", list(VALID_CATEGORIES), key="q_cat",
                     format_func=VALID_CATEGORIES.get, selection_mode="single",
                     label_visibility="collapsed")

        # ② 観光客はどう聞きますか
        with ui.card("q2"):
            ui.step(2, "観光客はどう聞きますか",
                    note="言い方を1つずつ追加します。「＋」でつないだ言葉が全部入っているときに、この回答が出ます。")
            if ss.q_questions:
                problems = []
                with st.container(horizontal=True, key="q-chips"):
                    for i, q in enumerate(list(ss.q_questions)):
                        bad = _problems(q)
                        problems += bad
                        if ui.chip(" ＋ ".join(q.split()) + "　✕",
                                   key=f"q{i}-{abs(hash(q)) % 10**6}", warn=bool(bad)):
                            ss.q_questions.remove(q)
                            st.rerun()
                if problems:
                    st.markdown("".join(ui.box("", escape(p), "warn") for p in problems),
                                unsafe_allow_html=True)
            else:
                st.markdown(ui.box("", "まだ言い方がありません。下の欄から追加してください。", "info"),
                            unsafe_allow_html=True)

            with st.form("q_add_form", clear_on_submit=True, border=False):
                ui.field_label("新しい言い方", "言葉と言葉の間は空白にします（例：たばこ どこ）。")
                c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
                new_q = c1.text_input("新しい言い方", placeholder="例：たばこ どこ",
                                      label_visibility="collapsed")
                if c2.form_submit_button("追加", use_container_width=True):
                    q = _clean(new_q)
                    if q and q not in ss.q_questions:
                        ss.q_questions.append(q)
                        st.rerun()

            if st.button("AIに言い方を提案してもらう", type="tertiary", key="q_ai"):
                if not ctx.engine:
                    ss.q_ai_msg = ("AIの設定がまだのため、いまは使えません。"
                                   "翻訳の設定をすると使えるようになります。")
                elif not (ss.q_answer or "").strip():
                    ss.q_ai_msg = "先に ③ の回答を入れてください。回答の内容から言い方を考えます。"
                else:
                    try:
                        with st.spinner("言い方を考えています…"):
                            ss.q_suggest = T.suggest_questions(ss.q_answer, ss.q_questions,
                                                               ctx.engine)
                        ss.q_ai_msg = "" if ss.q_suggest else "案が出ませんでした。もう一度お試しください。"
                    except Exception as e:
                        ss.q_ai_msg = f"AIに頼めませんでした（{str(e)[:60]}）。"
            if ss.get("q_ai_msg"):
                st.markdown(ui.box("", escape(ss.q_ai_msg), "info"), unsafe_allow_html=True)
            if ss.q_suggest:
                st.caption("AIの案です。押すと言い方に追加されます。")
                with st.container(horizontal=True, key="q-suggest"):
                    for i, q in enumerate(list(ss.q_suggest)):
                        if ui.chip_add("＋ " + " ＋ ".join(q.split()), key=f"s{i}-{abs(hash(q)) % 10**6}"):
                            if q not in ss.q_questions:
                                ss.q_questions.append(q)
                            ss.q_suggest.remove(q)
                            st.rerun()

        # ③ なんと答えますか
        with ui.card("q3"):
            ui.step(3, "なんと答えますか")
            ui.field_label("回答（画面に出て、このまま読み上げられます）", required=True)
            st.text_area("回答", key="q_answer", height=150, label_visibility="collapsed",
                         placeholder="例：喫煙所は、白川郷バスターミナルの裏手にございます。")
            n = len((ss.q_answer or "").strip())
            ui.meter(n, ANSWER_GOAL, f"{n}字 ／ 目安{ANSWER_GOAL}字")
            st.markdown('<ul class="ui-tips"><li>料金・時間・条件は省略せずに書いてください</li>'
                        f'<li>{ANSWER_GOAL}字を超えると、読み上げ用の短い文を入れる欄が出ます</li>'
                        '<li>文字数は、欄の外を押すと数え直します</li></ul>',
                        unsafe_allow_html=True)
            if n > ANSWER_GOAL or (ss.q_short or "").strip():
                ui.field_label("読み上げ用の短い回答",
                               "長い回答は聞き取りにくいため、読み上げの音声を作るときはこちらを使います。"
                               "画面には上の回答がそのまま出ます。")
                st.text_area("読み上げ用の短い回答", key="q_short", height=100,
                             label_visibility="collapsed")

        # ④ そのほか
        with ui.card("q4"):
            ui.step(4, "そのほか", optional=True)
            _photo_row(ctx)
            _link_row()
            _chip_row(ctx, places)
            _period_row()

            # 管理用の名前（職員には見せる必要が薄いので、下に小さく）
            if is_new:
                fid = ss.q_id_manual or _auto_id(ctx, ss.q_answer or "", ss.q_cat or "other",
                                                 ss.q_place, taken)
                c1, c2 = st.columns([5, 1.2], vertical_alignment="center")
                c1.caption(f"管理用の名前：{fid}"
                           + ("（自分で決めた名前）" if ss.q_id_manual else "（自動で付きます）"))
                with c2.popover("変更", use_container_width=True):
                    st.caption("英小文字・数字・_ だけで付けます。ふだんは自動のままで大丈夫です。")
                    manual = st.text_input("管理用の名前", value=ss.q_id_manual or fid,
                                           key="q_id_input")
                    if st.button("この名前にする", key="q_id_set"):
                        manual = manual.strip().lower()
                        if not ID_PATTERN.match(manual):
                            st.error("英小文字・数字・_ だけで付けてください。")
                        elif manual in taken:
                            st.error("その名前は、すでに使われています。")
                        else:
                            ss.q_id_manual = manual
                            st.rerun()
                    if ss.q_id_manual and st.button("自動に戻す", key="q_id_auto"):
                        ss.q_id_manual = ""
                        st.rerun()
            else:
                fid = target
                st.caption(f"管理用の名前：{fid}（登録済みのため変えられません）")

    draft = _draft(fid)

    # ================================================================ 右
    with right:
        with ui.card("try"):
            st.markdown("#### 試しに聞いてみる")
            ui.field_label("", "観光客になったつもりで入力します。保存前の内容でも確かめられます。")
            text = st.text_input("試しに聞く文", key="q_try",
                                 placeholder="例：たばこを吸える場所はありますか",
                                 label_visibility="collapsed")
            if text.strip() and draft["questions"]:
                _render_try(_try(ctx, draft, places, text))
            elif text.strip():
                st.markdown(ui.box("", "先に ② の言い方を追加してください。", "info"),
                            unsafe_allow_html=True)

        with ui.card("view"):
            st.markdown("#### 案内画面での見え方")
            _preview(ctx, draft, places)

        with ui.card("tr"):
            st.markdown("#### 翻訳")
            st.caption("保存すると5つの言語に自動で翻訳されます。" if ctx.engine
                       else "翻訳の設定がまだのため、日本語だけで保存されます。")
            states = _translation_state(ctx, draft)
            st.markdown('<div style="display:flex;gap:6px;flex-wrap:wrap">' + "".join(
                f'<span title="{escape(t)}">{ui.badge(f"{name}・{t}", k)}</span>'
                for name, t, k in states) + "</div>", unsafe_allow_html=True)

    # ================================================================ 下の保存バー
    with ui.save_bar(SAVE_NOTE, key="q") as bar:
        b1, b2 = bar.columns(2)
        draft_click = b1.button("下書きとして保存", key="q_save_draft",
                                use_container_width=True)
        save_click = b2.button("保存する", type="primary", key="q_save",
                               use_container_width=True)
    if draft_click:
        _save(ctx, draft, enabled=False, is_new=is_new, taken=taken)
    if save_click:
        _save(ctx, draft, enabled=True, is_new=is_new, taken=taken)


# ---------------------------------------------------------------- ④ の各行
def _toggle(name):
    ss = st.session_state
    ss.q_open = "" if ss.q_open == name else name


def _photo_row(ctx):
    ss = st.session_state
    value = ss.q_photo or "なし"
    if ui.option_row("写真", value, "変更" if ss.q_photo else "写真を選ぶ", "photo",
                     is_set=bool(ss.q_photo)):
        _toggle("photo")
        st.rerun()
    if ss.q_photo_new:
        st.markdown(ui.box(
            "案内端末に出すには、もう一手間あります",
            "追加した写真は、案内アプリの置き場所（ロリポップの assets/photo）にも"
            "同じものを上げる必要があります。管理者にお願いしてください。", "warn"),
            unsafe_allow_html=True)
    if ss.q_open != "photo":
        return

    pick_tab, new_tab = st.tabs(["上げてある写真から選ぶ", "新しい写真を追加する"])
    with pick_tab:
        names = ctx.photos.list()
        if not names:
            st.caption("まだ写真がありません。「新しい写真を追加する」から追加できます。")
        else:
            options = [""] + names
            choice = st.selectbox("写真", options,
                                  index=options.index(ss.q_photo) if ss.q_photo in options else 0,
                                  format_func=lambda n: n or "（写真なし）", key="q_photo_pick")
            if choice:
                data = ctx.photos.read(choice)
                if data:
                    st.image(data, width=260)
            c1, c2 = st.columns(2)
            if c1.button("この写真にする", type="primary", key="q_photo_use",
                         use_container_width=True):
                ss.q_photo = choice
                ss.q_photo_new = False
                ss.q_open = ""
                st.rerun()
            if ss.q_photo and c2.button("写真を外す", key="q_photo_clear",
                                        use_container_width=True):
                ss.q_photo = ""
                ss.q_open = ""
                st.rerun()
    with new_tab:
        up = st.file_uploader("写真のファイル（jpg・png）", type=["jpg", "jpeg", "png", "webp"],
                              key="q_upload")
        if up is not None:
            st.image(up, width=260)
            name = safe_name(up.name)
            existing = set(ctx.photos.list())
            stem, ext = name.rsplit(".", 1)
            n = 2
            while name in existing:
                name = f"{stem}_{n}.{ext}"
                n += 1
            st.caption(f"「{name}」という名前で追加します。")
            if st.button("この写真を追加して使う", type="primary", key="q_upload_go"):
                try:
                    with st.spinner("写真を追加しています…"):
                        ctx.photos.save(name, _shrink(up.getvalue(), name))
                    ss.q_photo = name
                    ss.q_photo_new = True
                    ss.q_open = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"写真を追加できませんでした: {e}")
        st.caption("大きな写真は、観光客のスマートフォンで速く開けるよう、自動で小さくして保存します。")


def _shrink(data, name):
    """写真を、案内画面で十分な大きさ（長い辺1600px）に縮める。

    スマートフォンで撮った写真は1枚5MBほどあり、観光客の端末では開くのに時間がかかる。
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if max(img.size) <= 1600 and len(data) < 900_000:
            return data
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        if name.lower().endswith(".png"):
            img.save(buf, format="PNG", optimize=True)
        else:
            img.convert("RGB").save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue()
    except Exception:
        return data   # 縮められないときは、そのまま使う


def _link_row():
    ss = st.session_state
    if ui.option_row("参考ページ（QRコードで表示）", ss.q_link or "なし",
                     "変更" if ss.q_link else "URLを入れる", "link", is_set=bool(ss.q_link)):
        _toggle("link")
        st.rerun()
    if ss.q_open != "link":
        return
    ui.field_label("参考ページのURL",
                   "据え置きの端末ではQRコード、観光客のスマートフォンでは押せるリンクになります。")
    url = st.text_input("URL", value=ss.q_link, placeholder="https://…", key="q_link_input",
                        label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button("このURLにする", type="primary", key="q_link_set", use_container_width=True):
        ss.q_link = url.strip()
        ss.q_open = ""
        st.rerun()
    if ss.q_link and c2.button("参考ページを外す", key="q_link_clear", use_container_width=True):
        ss.q_link = ""
        ss.q_open = ""
        st.rerun()


def _chip_row(ctx, places):
    ss = st.session_state
    if ui.option_row("「よくある質問」に並べる", ss.q_chip or "並べない",
                     "変更" if ss.q_chip else "設定する", "chip", is_set=bool(ss.q_chip)):
        _toggle("chip")
        st.rerun()
    if ss.q_open != "chip":
        return
    ui.field_label("流れる札に出す文言",
                   "案内画面の上を流れる「よくある質問」の札になります。"
                   "押すとこの文言で探すので、この回答に当たるかを下で確かめてください。")
    text = st.text_input("文言", value=ss.q_chip, placeholder="例：喫煙所はどこ",
                         key="q_chip_input", label_visibility="collapsed")
    if text.strip() and ss.q_questions:
        _render_try(_try(ctx, _draft("__draft__"), places, text))
    c1, c2 = st.columns(2)
    if c1.button("この文言にする", type="primary", key="q_chip_set", use_container_width=True):
        ss.q_chip = text.strip()
        ss.q_open = ""
        st.rerun()
    if ss.q_chip and c2.button("並べないことにする", key="q_chip_clear", use_container_width=True):
        ss.q_chip = ""
        ss.q_open = ""
        st.rerun()


def _period_row():
    ss = st.session_state
    has = bool(ss.q_from or ss.q_until)
    if ui.option_row("案内する期間（お祭りなど）", _period_text(ss.q_from, ss.q_until),
                     "変更" if has else "期間を決める", "period", is_set=has):
        _toggle("period")
        st.rerun()
    if ss.q_open != "period":
        return
    ui.field_label("案内する期間",
                   "期間の外になると、「案内アプリへ反映する」ときに自動で案内から外れます。")
    def as_date(v):
        try:
            return date.fromisoformat(v[:10])
        except (TypeError, ValueError):
            return date.today()
    c1, c2 = st.columns(2)
    f = c1.date_input("この日から", value=as_date(ss.q_from), key="q_from_input")
    u = c2.date_input("この日まで", value=as_date(ss.q_until), key="q_until_input")
    c1, c2 = st.columns(2)
    if c1.button("この期間にする", type="primary", key="q_period_set", use_container_width=True):
        ss.q_from, ss.q_until = f.isoformat(), u.isoformat()
        ss.q_open = ""
        st.rerun()
    if has and c2.button("いつも案内するにする", key="q_period_clear", use_container_width=True):
        ss.q_from = ss.q_until = ""
        ss.q_open = ""
        st.rerun()
