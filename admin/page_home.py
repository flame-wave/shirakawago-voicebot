"""ホーム。今やることを並べる。

管理画面を開いた職員さんが、まずどこを触ればよいかが分かるようにする。
数値の札で全体を見せ、その下に「今やること」を1行ずつ並べる。
どれも、押すとその作業をする画面が開く。

  ・反映していない変更          → 案内アプリへ反映する
  ・翻訳が要るもの／確かめ待ちの訳 → まとめて翻訳する
  ・もうすぐ案内する期間が終わる  → その質問を開く
  ・最近の答えられなかった質問    → 聞き方に入れた状態で、質問を追加する
  ・読み方の「要確認」          → 読み方
"""
from datetime import date
from html import escape

import streamlit as st

import faq_translate as T
import ui

SOON_DAYS = 14   # 「もうすぐ期間が終わる」とみなす日数


def _head(text, n=34):
    text = (text or "").replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def _todo(key, kind, title, detail, link=None, button=None):
    """今やることの1行。link=(ページ, query_params, 文字)、button=(文字, 押したときの処理)"""
    with st.container(key=f"ui-trow-todo-{key}"):
        a, b = st.columns([5, 1.6], vertical_alignment="center")
        icon = {"warn": "⚠", "info": "ⓘ", "ok": "✓"}[kind]
        color = {"warn": "#6B4200", "info": "#23415C", "ok": "#1F4D21"}[kind]
        a.markdown(f'<div class="ui-tcell"><b style="color:{color}">{icon}</b>　<b>{escape(title)}</b></div>'
                   + (f'<div class="ui-tsub" style="white-space:normal">{detail}</div>' if detail else ""),
                   unsafe_allow_html=True)
        if link:
            page, params, label = link
            b.page_link(page, label=label, query_params=params or None)
        elif button:
            label, action = button
            if b.button(label, key=f"todo-btn-{key}", use_container_width=True):
                action()


def render(ctx):
    ui.page_header("ホーム", "いまの状態と、今やることです。")
    ctx.translation_warning()

    book, items = ctx.book, ctx.items
    today = date.today()
    langs = list(T.LANGS)
    status = book.translation_status(langs)
    pending = ctx.unpublished() or []
    need = [i for i in items if i["enabled"] and i["answer"].strip()
            and any(status.get(i["id"], {}).get(l) in ("none", "changed") for l in langs)]
    review = [i for i in items
              if any(v == "machine" for v in status.get(i["id"], {}).values())]

    chars = book.characters()
    standing = next((c["name"] for c in chars if c["default"]), "—")
    ui.tiles([
        ("案内に出す質問", f"{sum(1 for i in items if i['enabled'])} 件", f"登録は {len(items)} 件"),
        ("反映していない変更", f"{len(pending)} 件",
         "保存したが案内端末に届いていない" if pending else "すべて届いています"),
        ("翻訳", f"{len(need)} 件" if need else "そろっています",
         f"確かめ待ち {len(review)} 件" if review else "確かめ待ちはありません"),
        ("最初に立つキャラクター", standing, f"選べるのは {len(chars)} 体"),
    ])
    st.write("")

    with ui.card("home-todo"):
        st.markdown("#### 今やること")
        count = 0

        # 1. 反映していない変更
        if pending:
            kinds = {}
            for c in pending:
                kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
            _todo("publish", "warn", f"反映していない変更が {len(pending)} 件あります",
                  "・".join(f"{k} {n}" for k, n in kinds.items())
                  + "。保存しただけでは案内端末に届きません。",
                  link=(ctx.pages["publish"], None, "反映する"))
            count += 1

        # 2. 翻訳
        if need:
            _todo("translate", "warn", f"翻訳が要る質問が {len(need)} 件あります",
                  "新しく追加した質問や、日本語の回答を直した質問です。",
                  link=(ctx.pages["bulk"], None, "翻訳する"))
            count += 1
        if review:
            _todo("review", "info", f"確かめ待ちの訳が {len(review)} 件あります",
                  "自動翻訳した訳です。地名や料金が合っているかを見て「確認しました」を押します。",
                  link=(ctx.pages["bulk"], None, "確かめる"))
            count += 1

        # 3. もうすぐ案内する期間が終わる
        soon = []
        for it in items:
            u = (it.get("show_until") or "")[:10]
            f = (it.get("show_from") or "")[:10]
            if not it["enabled"] or not u:
                continue
            try:
                until = date.fromisoformat(u)
            except ValueError:
                continue
            started = not f or f <= today.isoformat()
            if started and 0 <= (until - today).days <= SOON_DAYS:
                soon.append((until, it))
        # 同じ日に終わるもの（お祭りの案内など）は1行にまとめる。
        # 1件ずつ並べると、同じ知らせが何行も続いて読みにくいため。
        by_day = {}
        for until, it in soon:
            by_day.setdefault(until, []).append(it)
        for until in sorted(by_day):
            group = by_day[until]
            left = (until - today).days
            when = "今日まで" if left == 0 else f"あと {left} 日（{until.month}/{until.day} まで）"
            if len(group) == 1:
                it = group[0]
                _todo(f"soon-{it['id']}", "info", f"もうすぐ案内する期間が終わります：{when}",
                      escape(_head(it["answer"]))
                      + "　期間を延ばすときは、質問を開いて ④ の期間を直します。",
                      link=(ctx.pages["add"], {"id": it["id"]}, "開く"))
            else:
                _todo(f"soon-{until}", "info",
                      f"{len(group)} 件の案内が、もうすぐ期間を終えます：{when}",
                      "「" + escape(_head(group[0]["answer"], 24)) + "」など。"
                      "期間を延ばすときは、下の一覧から質問を開いて ④ の期間を直します。")
                with st.expander(f"{until.month}/{until.day} で終わる {len(group)} 件を見る"):
                    for it in group:
                        a, b = st.columns([5, 1.2], vertical_alignment="center")
                        a.markdown(f'<div class="ui-tcell">{escape(_head(it["answer"], 40))}</div>',
                                   unsafe_allow_html=True)
                        b.page_link(ctx.pages["add"], label="開く", query_params={"id": it["id"]})
            count += 1

        # 4. 読み方の「要確認」
        try:
            _, rows = book.sheet_rows("読み方")
        except Exception:
            rows = []
        unsure = [r for r in rows if "要確認" in (r.get("備考") or "")]
        if unsure:
            _todo("yomi", "info", f"読みを確かめていない言葉が {len(unsure)} 語あります",
                  "「" + "」「".join(escape(r.get("表記", "")) for r in unsure[:6]) + "」"
                  + ("など" if len(unsure) > 6 else "") + "。聞き比べて、正しければ備考の「要確認」を消します。",
                  link=(ctx.pages["screen"], {"tab": "yomikata"}, "聞き比べる"))
            count += 1

        # 5. 最近の答えられなかった質問
        recent = _recent_unmatched(ctx)
        if recent is None:
            pass   # 記録の読み出し先が未設定。下に一言だけ出す
        else:
            for i, (text, n) in enumerate(recent):
                _todo(f"un-{i}", "warn", f"答えられなかった質問：「{text}」（{n} 回）",
                      "直近7日に職員へ回った質問です。質問回答集に足すと、次から案内で答えられます。",
                      button=("この質問を追加する",
                              lambda t=text: st.switch_page(ctx.pages["add"], query_params={"q": t})))
                count += 1

        if count == 0:
            st.markdown(ui.box("今やることはありません", "反映・翻訳・期間はすべてそろっています。", "ok"),
                        unsafe_allow_html=True)
        if recent is None:
            st.caption("利用状況（答えられなかった質問）は、記録の読み出し先を設定すると、ここにも出ます。")

    with st.expander("この管理画面の設定"):
        st.caption(f"保存先：{ctx.store.label}（{ctx.store.location}）")
        st.caption("翻訳に使うもの：" + (ctx.engine["label"] if ctx.engine else "設定されていません"))


def _recent_unmatched(ctx, days=7, limit=5):
    """直近の答えられなかった質問。読み出し先が無ければ None。"""
    import log_stats as L
    import page_stats

    url, token = ctx.log_source()
    if not url or not token:
        return None
    rows = page_stats.load_rows(url, token)
    if st.session_state.get("log_error"):
        return []
    counts = {}
    for r in L.within(rows, days):
        if str(r.get("source") or "none") == "none":
            t = str(r.get("recognized") or "").strip()
            if t:
                counts[t] = counts.get(t, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])[:limit]
