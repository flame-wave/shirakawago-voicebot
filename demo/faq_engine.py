"""
FAQ検索ロジック（lib/faq_service.dart と同じ判定をPythonで再現したもの）

デモや分析で「実機と同じ結果」を確認するために使う。
Dart側を変更したら、こちらも必ず合わせること。
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# 語尾の活用に耐えるための末尾文字（faq_service.dart と同じ）
VERB_ENDINGS = "るうくすつぬぶむいたてえ"
SCORE_THRESHOLD = 2


def normalize(s: str) -> str:
    """カタカナ→ひらがな、全角英数→半角、記号と空白の除去。"""
    out = []
    for ch in s:
        c = ord(ch)
        if 0xFF10 <= c <= 0xFF5A:
            c -= 0xFEE0
        if 0x30A1 <= c <= 0x30F6:
            c -= 0x60
        out.append(chr(c))
    return re.sub(r"[\s　、。，．,.!?！？・ー]", "", "".join(out).lower())


def contains(keyword: str, text: str) -> bool:
    """「預ける」が「預けたい」に当たるよう、語尾1文字を落とした形でも照合する。"""
    if keyword in text:
        return True
    if len(keyword) >= 3 and keyword[-1] in VERB_ENDINGS and keyword[:-1] in text:
        return True
    return False


# 入力文に足した語を区切る印。語のまたがり一致を防ぐために挟む。
SEP = chr(0)


def expand(text: str, synonyms: dict, lang: str = "ja") -> str:
    """言い換え表を使って、入力文に代表語を足す。

    「銀行ありますか」→ 末尾に atm を足す、というように、
    観光客の言い方を、質問例に書かれている語へ橋渡しする。
    元の文は消さずに足すだけなので、これまで当たっていたものは当たり続ける。
    """
    if not synonyms:
        return text

    table = {}
    for key in ("ja", lang):
        table.update(synonyms.get(key) or {})

    extra = []
    for rep_word, words in table.items():
        rep_n = normalize(rep_word)
        if not rep_n or rep_n in text:
            continue  # すでに入っているなら足さない
        for w in words:
            wn = normalize(w)
            if wn and wn in text:
                extra.append(rep_n)
                break
    if not extra:
        return text
    return text + SEP + SEP.join(extra)


@dataclass
class MatchResult:
    faq: dict | None
    score: int
    matched_example: str = ""
    keywords: list = field(default_factory=list)

    @property
    def hit(self) -> bool:
        return self.faq is not None


def questions_for(faq: dict, lang: str) -> list:
    """その言語で検索対象にする質問例。日本語の言い方も常に含める。"""
    if lang == "ja":
        return faq.get("questions", [])
    tr = (faq.get("translations") or {}).get(lang) or {}
    return list(tr.get("questions", [])) + list(faq.get("questions", []))


def answer_for(faq: dict, lang: str) -> tuple:
    """(回答文, 日本語で代替したか) を返す。"""
    if lang == "ja":
        return faq.get("answer", ""), False
    tr = (faq.get("translations") or {}).get(lang) or {}
    if tr.get("answer"):
        return tr["answer"], False
    return faq.get("answer", ""), True


COMMON = "共通"


def place_of(faq: dict) -> str:
    return faq.get("place") or COMMON


def search(faqs: list, text: str, lang: str = "ja",
           synonyms: dict | None = None, place: str | None = None) -> MatchResult:
    """
    質問例のスペースは「かつ」を意味する。
    「ごみ どこ」は、ごみ と どこ の両方が含まれるときだけ一致する。

    synonyms を渡すと、言い換え表で入力文を補ってから照合する。

    place（いまいる案内所）を渡すと、その案内所向けの回答を先に探し、
    無ければ「共通」の回答を探す。どこにいるか分からないときは共通だけを見る。
    ロッカーやATMのように、案内所ごとに答えが違うものがあるため。
    """
    t = expand(normalize(text), synonyms or {}, lang)
    if not t:
        return MatchResult(None, 0)

    if place:
        here = [f for f in faqs if place_of(f) == place]
        hit = _search_within(here, t, lang)
        if hit.hit:
            return hit
        return _search_within([f for f in faqs if place_of(f) == COMMON], t, lang)

    if any("place" in f for f in faqs):
        # 場所の情報があるのに現在地が分からない場合は、共通の回答だけを使う
        faqs = [f for f in faqs if place_of(f) == COMMON]
    return _search_within(faqs, t, lang)


def _search_within(faqs: list, t: str, lang: str) -> MatchResult:
    """正規化済みの文 t で、渡されたFAQの中から最も確度の高いものを選ぶ。"""
    best, best_score, best_ex, best_kw = None, 0, "", []

    for faq in faqs:
        for q in questions_for(faq, lang):
            keywords = [normalize(k) for k in re.split(r"[\s　]+", q)]
            keywords = [k for k in keywords if k]
            if not keywords:
                continue
            if not all(contains(k, t) for k in keywords):
                continue
            score = sum(len(k) for k in keywords) + (1 if len(keywords) > 1 else 0)
            if score > best_score:
                best, best_score, best_ex, best_kw = faq, score, q, keywords

    if best_score < SCORE_THRESHOLD:
        return MatchResult(None, best_score)
    return MatchResult(best, best_score, best_ex, best_kw)


def load_faqs(path) -> tuple:
    """(FAQ一覧, 版) を返す。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("faqs", []), data.get("version", "不明")


def load_synonyms(path) -> dict:
    """言い換え表を返す。入っていなければ空。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("synonyms", {})
