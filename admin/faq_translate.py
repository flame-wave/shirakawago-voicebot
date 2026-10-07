"""
日本語の質問回答を、他の言語へ翻訳する。

翻訳の指示には、これまでの検証で分かった注意点を埋め込んである。
（質問例のスペースは「かつ」、韓国語の活用、英語の綴り違い、
  料金や条件を省略しない、など）
"""

import json
import re

LANGS = {
    "en": "英語",
    "zh": "中国語（簡体字）",
    "ko": "韓国語",
    "es": "スペイン語",
    "fr": "フランス語",
}

# 翻訳に使うモデル。
#
# 翻訳は年に数百円の世界なので、ここは料金より品質で選んでよい。
# 一番こわいのは固有名詞の間違いで、観光客は地名を手がかりに
# 地図や看板と突き合わせるため、「白山」を Shiroyama と訳されると
# 別の山を探しに行ってしまう。安いモデルほどこの種の間違いが出る。
#
# 2026年10月、料金を抑えるため Haiku に切り替えた（運用者の判断）。
# 安いモデルほど固有名詞を間違えやすいので、自動翻訳には「要確認」の印を付け、
# 管理画面の「まとめて翻訳する」で日本語と並べて確かめてから印を外す運用にしている。
# 地名の訳し間違いが目立つようなら "claude-sonnet-5-5" に戻す。
# まとめて確かめるときは tools/check_translations.py も使える。
MODEL = "claude-haiku-4-5"

# オープンなモデル（gpt-oss、Qwen など）を代わりに使うときの既定。
# Groq の無料枠で動く。安く済ませるなら "openai/gpt-oss-20b"。
#
# 提供されるモデルは入れ替わる（Groq では 2026年8月に Llama 3.3 70B が
# 法人契約専用へ移った）。使えなくなったら Secrets の model を書き換える。
OPEN_MODEL = "openai/gpt-oss-120b"

# 1回の依頼に入れる項目数。多すぎると返答が途中で切れる。
CHUNK = 5

INSTRUCTIONS = """\
あなたは観光案内の翻訳者です。日本の白川郷（世界遺産の合掌造り集落）の
観光案内所に置く音声案内システムの、質問回答集を翻訳します。

各項目について、次の2つを作ってください。

1. answer（回答文）
   - 観光客に読み上げられる案内文です。丁寧で簡潔な口語にしてください。
   - 数字は読み上げやすい表記にしてください。
   - 料金・時間・条件（例「小学生は半額」「当日のみ」）は絶対に省略・要約しないでください。
     条件を落とすと料金トラブルの原因になります。
   - 危険を知らせる文（川、山、熊など）は、やわらげずにはっきり伝えてください。
   - 施設名・地名は、その言語圏の観光客が地図と照合できる表記にしてください。

2. questions（想定される聞かれ方）
   - その言語の観光客が実際に口にしそうな言い方を4〜6個。
   - 【重要】1行が1つの言い方です。行内の半角スペースは「かつ」を意味します。
     例「trash bin」は trash と bin の両方が含まれるときだけ一致します。
   - 一般的すぎる語（where, time, どこ に相当する語）だけの行は作らないでください。
     内容を表す語を必ず含めてください。
   - 2文字未満の語だけの行は作らないでください（短すぎて判定に使えません）。
   - 韓国語は活用形が一致しないことがあるため、
     「맡기」と「맡길」のように語幹の異なる形を複数入れてください。
   - 英語は英式・米式の綴り（tyre / tire）の両方を入れてください。

出力は次の形式のJSONのみ。説明や前置きは一切書かないでください。

{
  "項目のID": {
    "言語コード": {
      "questions": ["言い方1", "言い方2"],
      "answer": "回答文"
    }
  }
}
"""


def build_prompt(items, langs):
    """items: {id: {"questions": [...], "answer": "..."}}"""
    payload = {
        fid: {
            "日本語の質問例": v["questions"],
            "日本語の回答": v["answer"],
            "翻訳する言語": list(langs),
        }
        for fid, v in items.items()
    }
    names = "、".join(f"{l}（{LANGS.get(l, l)}）" for l in langs)
    return (
        INSTRUCTIONS
        + f"\n翻訳する言語コード: {names}\n\n以下が翻訳対象です。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


class TooLong(RuntimeError):
    """まとめて頼みすぎた合図。件数を減らせば通る見込みがある。

    返答が途中で切れた場合と、返答がJSONとして読めなかった場合の両方で使う。
    どちらも、一度に頼む量を減らすと通ることが多い。
    """


def parse_result(text):
    """返答からJSONを取り出す。前後に説明が付いていても拾う。"""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("翻訳結果からJSONを読み取れませんでした")
    return json.loads(text[start:end + 1])


def translate(items, langs, engine, progress=None):
    """翻訳する。戻り値は {id: {lang: {questions, answer}}}

    engine は使う翻訳の設定（下の describe_engine 参照）。
    どちらの方式でも、職員のパソコンには何も入れなくてよい
    （処理はクラウド側で行われ、管理画面はその結果を受け取るだけ）。

    件数が多いと返答が長くなるため、少しずつに分けて依頼する。
    progress … 1回頼み終えるたびに progress(終わった件数, 全件数, それまでの結果) を呼ぶ。
               画面に進み具合を出すため。途中で止まっても、それまでの結果は残せる。
    """
    once = {"open_model": _open_model_once, "fake": _fake_once}.get(
        engine["kind"], _claude_once)

    merged = {}
    total = len(items)
    for chunk in chunked(items, CHUNK):
        merged.update(_once_splitting(once, chunk, langs, engine))
        if progress:
            progress(len(merged), total, merged)
    return merged


# ---------------------------------------------------------------- 試し用
def fake_engine():
    """決まった訳を返す、試し用の翻訳。

    本物の翻訳（AIのキー）が無い状態で、画面と保存の流れを確かめるために使う。
    管理画面を CHAATBOT_FAKE_TRANSLATE=1 を付けて起動したときだけ有効になる。
    職員が使う画面で有効になることは無い。
    """
    return {"kind": "fake", "model": "fake", "label": "試し用の翻訳（本物ではありません）"}


def _fake_once(items, langs, engine):
    return {
        fid: {
            lang: {"questions": [f"{lang} {q}" for q in v["questions"]],
                   "answer": f"[{lang}] {v['answer']}"}
            for lang in langs
        }
        for fid, v in items.items()
    }


# ---------------------------------------------------------------- 費用の目安
# Claude Haiku の料金（1ドルあたり、100万トークンごと）。
# 料金が変わったらここだけ直す。画面の「費用の目安」はこの値で計算する。
PRICE_IN = 1.00     # 入力
PRICE_OUT = 5.00    # 出力
YEN_PER_USD = 150   # 円に直すときの目安


def estimate(items, langs):
    """翻訳にかかるおおよその費用（円）を返す。(少なめ, 多め)

    日本語は1文字がおよそ1トークン。訳文は言語ごとに日本語の1.5倍ほどの
    長さになる。毎回付ける指示文のぶんも足す。幅を持たせて出す。
    """
    if not items or not langs:
        return 0.0, 0.0
    ja = sum(len(v["answer"]) + sum(len(q) for q in v["questions"]) for v in items.values())
    chunks = (len(items) + CHUNK - 1) // CHUNK
    tokens_in = ja * 1.2 + chunks * (len(INSTRUCTIONS) * 1.1 + 200)
    tokens_out = ja * 1.5 * len(langs) + len(items) * len(langs) * 40
    usd = tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT
    yen = usd * YEN_PER_USD
    return yen * 0.7, yen * 1.5


def _once_splitting(once, items, langs, engine):
    """返答が途中で切れたら、半分に分けてやり直す。

    1回に何件まで入るかは、回答文の長さとモデルによって変わる。
    職員に「件数を減らしてください」と伝えても加減が分からないので、
    こちらで分けて通す。
    """
    try:
        return once(items, langs, engine)
    except TooLong as e:
        if len(items) <= 1:
            fid = next(iter(items), "（不明）")
            raise RuntimeError(
                f"「{fid}」を1件だけで頼んでも受け取れませんでした（{e}）。"
                "回答文を短くするか、翻訳する言語を減らしてお試しください。"
            )
    keys = list(items)
    half = len(keys) // 2
    merged = {}
    for part in (keys[:half], keys[half:]):
        merged.update(
            _once_splitting(once, {k: items[k] for k in part}, langs, engine)
        )
    return merged


def describe_engine(anthropic_key=None, open_model=None, prefer=None):
    """設定から、どの方式で翻訳するかを決める。

    anthropic_key … Claudeを使う場合のAPIキー
    open_model    … {"base_url", "api_key", "model"}
                    Groq / OpenRouter など、オープンなモデルを動かすサービス
    prefer        … "claude" / "open_model"（両方設定されているときの優先）

    戻り値は engine（使えないときは None）。
    """
    claude = {"kind": "claude", "api_key": anthropic_key, "model": MODEL,
              "label": f"Claude（{MODEL}）"} if anthropic_key else None

    openm = None
    if open_model and open_model.get("base_url") and open_model.get("api_key"):
        name = open_model.get("model") or OPEN_MODEL
        openm = {
            "kind": "open_model",
            "base_url": open_model["base_url"].rstrip("/"),
            "api_key": open_model["api_key"],
            "model": name,
            "label": f"オープンモデル（{name}）",
        }

    if prefer == "open_model" and openm:
        return openm
    if prefer == "claude" and claude:
        return claude
    return claude or openm


def chunked(items: dict, size: int):
    """辞書を size 件ずつに分ける。"""
    keys = list(items)
    for i in range(0, len(keys), size):
        yield {k: items[k] for k in keys[i:i + size]}


def _claude_once(items, langs, engine):
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic パッケージが入っていません。"
            "requirements.txt を確認してください。"
        )
    client = anthropic.Anthropic(api_key=engine["api_key"])

    # 返答が長くなるので、途中で時間切れにならないよう受け取りながら読む
    with client.messages.stream(
        model=engine["model"],
        max_tokens=16000,
        messages=[{"role": "user", "content": build_prompt(items, langs)}],
    ) as stream:
        res = stream.get_final_message()

    # 安全側の判断で断られた場合は、中身を読む前に知らせる
    if getattr(res, "stop_reason", "") == "refusal":
        raise RuntimeError(
            "翻訳を断られました。内容を確認するか、手作業で翻訳してください。"
        )
    if getattr(res, "stop_reason", "") == "max_tokens":
        raise TooLong("翻訳結果が長すぎて途中で切れました")

    text = "".join(b.text for b in res.content if getattr(b, "type", "") == "text")
    try:
        return parse_result(text)
    except ValueError as e:
        raise TooLong(f"返答を読み取れませんでした（{e}）") from e


# 1分あたりの上限に当たったときに待つ回数。
# 無料枠は上限が低く（Groqは1分8,000トークン）、まとめて翻訳すると必ず当たる。
# 職員には待つ以外にできることが無いので、こちらで待って続ける。
RETRY_LIMIT = 4


def _max_tokens(items, langs):
    """受け取る長さの上限を、件数と言語数から見積もる。

    固定で大きく取ると、無料枠では「1分の上限より大きい依頼」として
    そもそも受け付けてもらえない（Groqは依頼したこの数もその分に数える）。
    考えてから答えるモデル（gpt-oss など）は考えた分も使うので、少し余裕を持たせる。
    """
    per_item = 900 * max(1, len(langs)) / 5
    return int(min(16000, 1200 + per_item * max(1, len(items))))


def _open_model_once(items, langs, engine):
    """オープンなモデルを動かすサービスに依頼する。

    Groq・OpenRouter・Together など、OpenAI互換の窓口を持つサービスなら
    設定を変えるだけでそのまま使える。動かすのは相手のサーバなので、
    職員のパソコンにモデルを入れる必要はない。
    """
    import time

    import requests

    body = {
        "model": engine["model"],
        "messages": [{"role": "user", "content": build_prompt(items, langs)}],
        "max_tokens": _max_tokens(items, langs),
        # 翻訳なので、毎回ぶれないよう低めにする
        "temperature": 0.2,
        # 考えてから答えるモデル（gpt-oss など）では、考える量を控えめにする。
        # 翻訳は筋道を立てて解く仕事ではないので、深く考えても質は上がらず、
        # 考えた分の枠と料金だけがかかる（実測で出力が半分以下になる）。
        # この指定を知らないサービスもあるため、断られたら外して送り直す。
        "reasoning_effort": "low",
    }

    for attempt in range(RETRY_LIMIT + 1):
        res = requests.post(
            f"{engine['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {engine['api_key']}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=300,
        )
        if res.status_code == 400 and "reasoning_effort" in body:
            del body["reasoning_effort"]
            continue
        if res.status_code != 429:
            break
        if attempt == RETRY_LIMIT:
            raise RuntimeError(
                "1分あたりの上限に当たり続けています。"
                "しばらく待ってからお試しください"
                "（無料枠の上限です。有料に切り替えると解消します）。"
            )
        # サービスが待ち時間を教えてくれるならそれに従う
        try:
            wait = float(res.headers.get("retry-after", ""))
        except ValueError:
            wait = 0.0
        time.sleep(min(max(wait, 5.0), 65.0))

    # 無料枠では「1分の上限より大きい依頼」そのものが断られる。
    # 件数を減らせば通るので、切れた場合と同じ扱いにする。
    if res.status_code == 413:
        raise TooLong("依頼が1分あたりの上限より大きいため受け付けられませんでした")
    if res.status_code != 200:
        raise RuntimeError(f"翻訳に失敗しました（{res.status_code}）: {res.text[:200]}")

    body = res.json()
    choice = (body.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length":
        raise TooLong("翻訳結果が長すぎて途中で切れました")
    text = (choice.get("message") or {}).get("content", "")
    try:
        return parse_result(text)
    except ValueError as e:
        # まとめて頼むほど、途中で形が崩れやすい。件数を減らせば通ることが多い。
        raise TooLong(f"返答を読み取れませんでした（{e}）") from e


# ---------------------------------------------------------------- 点検
GENERIC = {
    "どこ", "場所", "時間", "いつ", "何時", "料金", "値段", "ある", "教えて",
    "where", "when", "what", "how", "time", "place", "is", "the", "a",
    "哪里", "什么", "多少", "时间",
    "어디", "언제", "얼마", "시간",
    "donde", "cuando", "que", "hora",
    "ou", "quand", "quoi", "heure",
}


def check_questions(questions):
    """質問例が判定に使えるかを見る。問題があれば説明を返す。"""
    problems = []
    for q in questions:
        words = [w for w in q.split() if w]
        if not words:
            continue
        if all(w.lower() in GENERIC for w in words):
            problems.append(f"「{q}」は一般的な語だけのため、関係ない質問にも反応する恐れがあります")
        if max((len(w) for w in words), default=0) < 2:
            problems.append(f"「{q}」は語が短すぎて判定に使えません")
    return problems


# ---------------------------------------------------------------- 小さな頼みごと
# 翻訳と同じ設定（engine）を使って、短い返事をもらう。
# 管理用の名前を付ける・聞き方の案を出す、といった用途。
def ask_text(engine, prompt: str, max_tokens: int = 400) -> str:
    """短い返事を文字で受け取る。設定が無ければ RuntimeError。"""
    if not engine:
        raise RuntimeError("AIの設定がされていません")
    if engine["kind"] == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=engine["api_key"])
        res = client.messages.create(
            model=engine["model"], max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in res.content if getattr(b, "type", "") == "text")

    import requests
    res = requests.post(
        f"{engine['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {engine['api_key']}",
                 "Content-Type": "application/json"},
        json={"model": engine["model"], "max_tokens": max_tokens, "temperature": 0.2,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    if res.status_code != 200:
        raise RuntimeError(f"AIに頼めませんでした（{res.status_code}）")
    choice = (res.json().get("choices") or [{}])[0]
    return (choice.get("message") or {}).get("content", "")


def make_slug(answer: str, engine) -> str:
    """回答の内容から、管理用の名前（英小文字と _ だけ）を作る。

    例: 喫煙所の案内 → smoking_area
    名前は職員には見せないが、Excel と記録で同じ項目を指すのに使う。
    """
    text = ask_text(engine, (
        "次の観光案内の回答を表す、短い英語の名前を1つだけ作ってください。\n"
        "・英小文字と _ だけ、2〜3語（例: smoking_area, bus_timetable）\n"
        "・説明や記号は付けず、名前だけを1行で返す\n\n"
        f"回答: {answer[:300]}"
    ), max_tokens=40)
    slug = re.sub(r"[^a-z0-9_]+", "_", text.strip().lower().split("\n")[0]).strip("_")
    slug = re.sub(r"_+", "_", slug)[:32].strip("_")
    return slug


def suggest_questions(answer: str, existing, engine, count: int = 6) -> list:
    """回答に合う聞き方の案を出す。

    案内アプリは「質問例の語が全部入っていたら当たる」決め方なので、
    文ではなく、空白でつないだ短い語の組（例: たばこ 吸える）で出してもらう。
    """
    have = "、".join(existing) or "（まだない）"
    text = ask_text(engine, (
        "白川郷の観光案内で、観光客がこの回答を聞きたいときの言い方を考えてください。\n"
        f"・{count}個、1行に1つ\n"
        "・文ではなく、空白でつないだ短い語の組にする（例: たばこ 吸える／喫煙所）\n"
        "・語は2〜3個まで。「どこ」「時間」のような一般的な語だけの組にはしない\n"
        "・すでにある言い方と同じものは出さない\n"
        "・番号や記号、説明は付けない\n\n"
        f"回答: {answer[:400]}\n"
        f"すでにある言い方: {have}"
    ), max_tokens=300)
    out = []
    for line in text.splitlines():
        q = re.sub(r"^[\s\-・*0-9.)、]+", "", line).replace("　", " ").strip()
        q = re.sub(r"\s+", " ", q)
        if q and q not in existing and q not in out and len(q) <= 30:
            out.append(q)
    return out[:count]
