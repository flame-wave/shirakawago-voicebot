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


def search(faqs: list, text: str, lang: str = "ja") -> MatchResult:
    """
    質問例のスペースは「かつ」を意味する。
    「ごみ どこ」は、ごみ と どこ の両方が含まれるときだけ一致する。
    """
    t = normalize(text)
    if not t:
        return MatchResult(None, 0)

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
