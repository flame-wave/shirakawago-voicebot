"""案内アプリの「どの回答を出すか」の決め方を、管理画面で再現する。

webapp/js/faq-service.js の search と同じ手順をそのまま写してある。
管理画面の「試しに聞いてみる」は、ここで決めた答えを見せる。
案内アプリと決め方がずれると、「管理画面では出たのに現地では出ない」が起きるので、
faq-service.js を直したときは、こちらも必ず同じように直すこと。

  1. 表記の揺れをならす（カタカナ→ひらがな、全角英数→半角、記号と空白を消す）
  2. 言い換え表で、入力に代表語を足す（「銀行」→「atm」）
  3. 質問例の語が「全部」入っているものだけを候補にする（空白は「かつ」）
  4. 語の長さの合計（2語以上なら +1）がいちばん大きいものを選ぶ
  5. 合計が2未満なら「該当なし」（1文字だけの一致は弱すぎる）

案内所の扱い:
  いる場所が分かるとき … その案内所向けの回答を先に探し、無ければ「共通」から
  分からないとき       … 「共通」の回答だけから探す
"""
import re

COMMON = "共通"
SEP = "\x00"   # 足した語が元の文とつながって誤って一致しないようにする区切り

_STRIP = re.compile(r"[\s　、。，．,.!?！？・ー]")
_SPLIT = re.compile(r"[\s　]+")
# 語尾が活用する語（「預ける」→「預けたい」）
_INFLECT = "るうくすつぬぶむいたてえ"


def normalize(text: str) -> str:
    out = []
    for ch in text or "":
        c = ord(ch)
        if 0xFF10 <= c <= 0xFF5A:       # 全角英数 → 半角
            c -= 0xFEE0
        if 0x30A1 <= c <= 0x30F6:       # カタカナ → ひらがな
            c -= 0x60
        out.append(chr(c))
    return _STRIP.sub("", "".join(out).lower())


def expand(text: str, synonyms: dict, lang: str = "ja") -> str:
    """言い換え表を使って、入力文に代表語を足す（元の文は消さない）。"""
    table = {**(synonyms.get("ja") or {}), **(synonyms.get(lang) or {})}
    extra = []
    for rep, words in table.items():
        rep_n = normalize(rep)
        if not rep_n or rep_n in text:
            continue
        for w in words:
            wn = normalize(w)
            if wn and wn in text:
                extra.append(rep_n)
                break
    return text + SEP + SEP.join(extra) if extra else text


def _contains(keyword: str, text: str) -> bool:
    if keyword in text:
        return True
    return (len(keyword) >= 3 and keyword[-1] in _INFLECT
            and keyword[:-1] in text)


def _place(faq) -> str:
    return faq.get("place") or COMMON


def candidates(faqs, text):
    """当たった回答を、点の高い順に返す。[(点, 回答, 当たった言い方)]"""
    best = {}
    for faq in faqs:
        for q in faq.get("questions", []):
            keywords = [normalize(k) for k in _SPLIT.split(q) if normalize(k)]
            if not keywords or not all(_contains(k, text) for k in keywords):
                continue
            score = sum(len(k) for k in keywords) + (1 if len(keywords) > 1 else 0)
            fid = faq["id"]
            if fid not in best or score > best[fid][0]:
                best[fid] = (score, faq, q)
    return sorted(best.values(), key=lambda x: -x[0])


def _within(faqs, text):
    """案内アプリの _searchWithin と同じ。点が「より大きい」ときだけ入れ替えるので、
    同点のときは先に見つかった方が残る（並び順も案内アプリと同じにすること）。"""
    best, best_score = None, 0
    for faq in faqs:
        for q in faq.get("questions", []):
            keywords = [normalize(k) for k in _SPLIT.split(q) if normalize(k)]
            if not keywords or not all(_contains(k, text) for k in keywords):
                continue
            score = sum(len(k) for k in keywords) + (1 if len(keywords) > 1 else 0)
            if score > best_score:
                best_score, best = score, (score, faq, q)
    found = candidates(faqs, text)
    if best_score < 2:
        return None, found
    return best, found


def search(faqs, user_text, synonyms=None, place=None, lang="ja"):
    """案内アプリと同じ決め方で、出る回答を選ぶ。

    戻り値: (出る回答 (点, 回答, 当たった言い方) か None, 当たった候補すべて)
    """
    text = expand(normalize(user_text), synonyms or {}, lang)
    if not text:
        return None, []
    if place:
        here = [f for f in faqs if _place(f) == place]
        hit, found = _within(here, text)
        if hit:
            return hit, found
        common = [f for f in faqs if _place(f) == COMMON]
        hit, found2 = _within(common, text)
        return hit, found + found2
    common = [f for f in faqs if _place(f) == COMMON]
    return _within(common, text)
