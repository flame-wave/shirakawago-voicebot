"""まだ案内アプリに反映していない変更を数える。

管理画面で保存しただけでは、案内端末には届かない（「案内アプリへ反映する」で
書き出して初めて届く）。以前、キャラクターを変えたのに書き出しを忘れ、
古いまま公開され続けたことがあった。

そこで「いまの Excel を書き出したらどうなるか」を、反映のときと同じ変換
（build_faq）で作り、いま公開されているものと1件ずつ比べる。
同じ変換を通すので、掲載期間を過ぎたものが外れる・翻訳が入る、といった
書き出しのときの動きもそのまま反映される（見かけだけの差が出ない）。
"""
import hashlib
import json

import build_faq

# 比べる設定。左が faq.json の中の名前、右が職員に見せる名前。
SETTINGS = [
    ("characters", "キャラクター"),
    ("layouts", "画面レイアウト"),
    ("voice", "読み上げの声"),
    ("voice_sets", "用意した音声"),
    ("readings", "読み方"),
    ("reference", "参考資料"),
    ("places", "設置場所"),
    ("synonyms", "言い換え"),
]


def build(raw: bytes, assets_dir):
    """Excel から、書き出したときと同じ中身を作る。

    戻り値: (中身, 止めるべきエラー, 注意)
    """
    (faqs, errors, warnings, _pending, synonyms, places, voice_sets, reference,
     characters, voice, readings, layouts) = build_faq.build_from_bytes(raw, assets_dir)
    payload = {
        "count": len(faqs),
        "faqs": faqs,
        "synonyms": synonyms,
        "places": places,
        "voice_sets": voice_sets,
        "reference": reference,
        "characters": characters,
        "voice": voice,
        "readings": readings,
        "layouts": layouts,
    }
    return payload, errors, warnings


def _same(a, b) -> bool:
    """中身が同じか。並び順や小数の書き方の違いで「変わった」と言わないように、
    いったん同じ形の文字にしてから比べる。"""
    return (json.dumps(a, ensure_ascii=False, sort_keys=True)
            == json.dumps(b, ensure_ascii=False, sort_keys=True))


def _label(faq) -> str:
    """職員に見せる名前。管理用の名前（ID）ではなく、回答の書き出しを使う。"""
    text = (faq.get("answer") or "").strip().replace("\n", " ")
    return text[:28] + ("…" if len(text) > 28 else "") or faq.get("id", "")


def compare(built: dict, live: dict | None) -> list:
    """書き出したら変わるものの一覧。空なら反映済み。

    1件は {"kind": 追加／修正／案内から外れる／設定, "label": 名前, "id": 管理用の名前}
    """
    live = live or {}
    changes = []

    mine = {f["id"]: f for f in built.get("faqs", [])}
    theirs = {f["id"]: f for f in live.get("faqs", [])}
    for fid, faq in mine.items():
        if fid not in theirs:
            changes.append({"kind": "追加", "label": _label(faq), "id": fid})
        elif not _same(faq, theirs[fid]):
            changes.append({"kind": "修正", "label": _label(faq), "id": fid})
    for fid, faq in theirs.items():
        if fid not in mine:
            changes.append({"kind": "案内から外れる", "label": _label(faq), "id": fid})

    for key, name in SETTINGS:
        if not _same(built.get(key) or [], live.get(key) or []):
            changes.append({"kind": "設定", "label": name, "id": ""})
    return changes


def cached(session, raw: bytes, live: dict | None, assets_dir):
    """compare の結果を、Excel と公開中の版が変わるまで使い回す。

    書き出しと同じ変換は表の読み込みを伴うので、画面を作るたびに
    行うと遅い。Excel の中身と公開中の版が同じなら、結果も同じ。
    """
    stamp = (hashlib.sha1(raw).hexdigest(), (live or {}).get("version", ""))
    hit = session.get("publish_diff")
    if hit and hit[0] == stamp:
        return hit[1]
    try:
        built, _errors, _warnings = build(raw, assets_dir)
        result = compare(built, live)
    except Exception:
        result = None   # 読み取れないときは数えない（画面は止めない）
    session["publish_diff"] = (stamp, result)
    return result
