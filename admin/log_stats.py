"""
案内端末から送られてきた質問の記録を読み、職員向けの集計にする。

記録は中継サーバ（server/api/log.php）が書き溜めている。
案内端末の画面からは見られないようにしてあるので、見るのはここだけ。

設置場所ごとに分けて見られるようにしているのは、
「バスターミナルでだけよく聞かれる」質問があるため。
その質問は、その案内所向けの回答を用意すれば解決する。
"""

import json
from collections import Counter
from datetime import datetime, timezone

import requests

# 端末の区別。管理者画面ではこの順に並べる。
CLIENTS = ["バスターミナル", "であいの館", "観光客"]

# 端末ごとの色。グラフでは、どの画面でも同じ場所に同じ色を使う（色は場所に付ける）。
# 色覚の違いがあっても3つが見分けられることを確かめた組み合わせ
# （dataviz の validate_palette で、白地・3系列すべての組で合格）。
# 水色は白地との差が小さめなので、グラフには必ず数の表を添える。
CLIENT_COLORS = {"バスターミナル": "#2a78d6", "であいの館": "#eb6834", "観光客": "#1baf7a"}
OTHER_COLOR = "#8A9A88"

# 回答できた経路
SOURCES = {
    "faq": "質問回答集",
    "ai": "AIが作成",
    "none": "答えられず職員へ",
}


def fetch(url, token, kind="question", timeout=30):
    """中継サーバから記録を取ってくる。1行1件のJSONL。"""
    res = requests.get(url, params={"token": token, "kind": kind}, timeout=timeout)
    if res.status_code == 403:
        raise RuntimeError(
            "記録を読み出せませんでした。合言葉（log_token）が"
            "中継サーバの config.php と一致しているか確認してください。"
        )
    if res.status_code != 200:
        raise RuntimeError(f"記録を読み出せませんでした（{res.status_code}）")
    return parse(res.text)


def clear(url, token, before=None, timeout=30):
    """中継サーバの記録を消す。before（"2026-11-01"）を渡すと、その日より前だけを消す。

    戻り値: {"deleted": 消した件数, "kept": 残した件数, "since": 境目}
    消したあと、それより前の時刻の記録は中継サーバが受け取らなくなる
    （案内端末に残っていた古い記録が届いても戻らない）。
    """
    body = {"token": token, "action": "clear"}
    if before:
        body["before"] = before
    res = requests.post(url, json=body, timeout=timeout)
    if res.status_code == 403:
        raise RuntimeError("記録を消せませんでした。合言葉（log_token）が"
                           "中継サーバの config.php と一致しているか確認してください。")
    if res.status_code != 200:
        raise RuntimeError(f"記録を消せませんでした（{res.status_code}）。"
                           "中継サーバの logs.php が新しいものか確認してください。")
    data = res.json()
    if not data.get("ok"):
        raise RuntimeError(f"記録を消せませんでした（{data.get('reason', '理由不明')}）")
    return data


def parse(text):
    """JSONLを読む。壊れた行は飛ばす（1行壊れても他は読める）。"""
    rows = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _when(row):
    """記録の時刻。読めなければ None。"""
    value = str(row.get("at") or "")
    try:
        at = datetime.fromisoformat(value)
    except ValueError:
        return None
    # 時刻帯の有無が混ざると比較できないため、揃えておく
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at


def within(rows, days):
    """直近 days 日ぶんに絞る。days が None なら全件。"""
    if not days:
        return rows
    now = datetime.now(timezone.utc)
    kept = []
    for row in rows:
        at = _when(row)
        if at is None or (now - at).days < days:
            kept.append(row)
    return kept


def clients_in(rows):
    """記録に出てくる端末の一覧。決めてある順を先に、知らないものは後ろに。"""
    found = {str(r.get("client") or "不明") for r in rows}
    ordered = [c for c in CLIENTS if c in found]
    return ordered + sorted(found - set(ordered))


def summarize(rows):
    """1つの端末（またはまとめて全部）の集計。

    answered は「その場で答えられた」割合。
    職員に回さずに済んだ割合なので、設置の効果はこの数字で見る。
    """
    total = len(rows)
    by_source = Counter(str(r.get("source") or "none") for r in rows)
    answered = by_source["faq"] + by_source["ai"]

    unmatched = Counter()
    for row in rows:
        if str(row.get("source") or "none") == "none":
            text = str(row.get("recognized") or "").strip()
            if text:
                unmatched[text] += 1

    return {
        "total": total,
        "answered": answered,
        "answered_rate": 0.0 if total == 0 else answered / total,
        "by_source": dict(by_source),
        "by_lang": dict(Counter(str(r.get("lang") or "?") for r in rows)),
        "by_day": dict(Counter(
            (_when(r) or datetime.now(timezone.utc)).strftime("%Y-%m-%d") for r in rows
        )),
        "top_faq": Counter(
            str(r.get("faq_id")) for r in rows if r.get("faq_id")
        ).most_common(20),
        # 答えられなかった質問こそ、次に何を足すべきかの答えになる
        "unmatched": unmatched.most_common(50),
    }


def by_client(rows):
    """端末ごとの集計。{端末名: summarize(...)}"""
    groups = {}
    for row in rows:
        groups.setdefault(str(row.get("client") or "不明"), []).append(row)
    return {name: summarize(groups[name]) for name in clients_in(rows)}


def only_here(rows, client):
    """その端末でだけ聞かれた質問を探す。

    ほかの案内所では出ていない質問は、その場所ならではの困りごとである
    ことが多い（「ここからバスに乗れますか」など）。
    設置場所ごとの回答を足す候補になる。
    """
    here = Counter()
    elsewhere = set()
    for row in rows:
        text = str(row.get("recognized") or "").strip()
        if not text:
            continue
        if str(row.get("client") or "") == client:
            here[text] += 1
        else:
            elsewhere.add(text)
    return [(t, n) for t, n in here.most_common(30) if t not in elsewhere]
