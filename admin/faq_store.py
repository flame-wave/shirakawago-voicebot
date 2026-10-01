"""
質問回答集（faq.json）の読み書き。

保存先は2通り。
  local  … 手元のファイル。PCで動かして試すとき用。
  github … リポジトリに直接コミットする。公開した管理画面はこちら。

GitHubに保存すると、配信URL（raw）の中身がそのまま新しくなるので、
タブレット側は何もしなくても次の起動で最新になる。
"""

import base64
import json
from datetime import datetime
from pathlib import Path

import requests

API = "https://api.github.com"


class StoreError(Exception):
    pass


# ---------------------------------------------------------------- 手元のファイル
class LocalStore:
    label = "この端末のファイル"

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return {"version": "", "count": 0, "faqs": []}, None
        return json.loads(self.path.read_text(encoding="utf-8")), None

    def save(self, data, message, sha=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return None


# ---------------------------------------------------------------- GitHub
class GitHubStore:
    label = "GitHub（配信元）"

    def __init__(self, token, repo, path="assets/faq.json", branch="main"):
        self.token = token
        self.repo = repo          # 例: flame-wave/shirakawago-voicebot
        self.path = path
        self.branch = branch

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def load(self):
        """(データ, sha) を返す。sha は保存時の衝突検出に使う。"""
        url = f"{API}/repos/{self.repo}/contents/{self.path}"
        res = requests.get(url, headers=self._headers,
                           params={"ref": self.branch}, timeout=20)
        if res.status_code == 404:
            return {"version": "", "count": 0, "faqs": []}, None
        if res.status_code != 200:
            raise StoreError(f"読み込みに失敗しました（{res.status_code}）: {res.text[:200]}")
        body = res.json()
        raw = base64.b64decode(body["content"]).decode("utf-8")
        return json.loads(raw), body["sha"]

    def save(self, data, message, sha=None):
        url = f"{API}/repos/{self.repo}/contents/{self.path}"
        content = json.dumps(data, ensure_ascii=False, indent=2)
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": self.branch,
        }
        if sha:
            payload["sha"] = sha
        res = requests.put(url, headers=self._headers, json=payload, timeout=20)
        if res.status_code == 409:
            raise StoreError(
                "ほかの人が先に保存したため、保存できませんでした。"
                "画面を再読み込みして、もう一度お試しください。"
            )
        if res.status_code not in (200, 201):
            raise StoreError(f"保存に失敗しました（{res.status_code}）: {res.text[:200]}")
        return res.json()["content"]["sha"]


# ---------------------------------------------------------------- 共通の操作
VALID_CATEGORIES = {
    "bus": "バス・交通",
    "facility": "施設・設備",
    "sightseeing": "観光・見学",
    "food": "食事",
    "season": "季節・天候",
    "accessibility": "バリアフリー",
    "manner": "マナー・お願い",
    "emergency": "緊急・注意喚起",
    "event": "催し・期間限定",
    "other": "その他",
}


def new_version():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def find(data, fid):
    for f in data["faqs"]:
        if f["id"] == fid:
            return f
    return None


def upsert(data, item):
    """同じIDがあれば置き換え、無ければ追加する。"""
    for i, f in enumerate(data["faqs"]):
        if f["id"] == item["id"]:
            data["faqs"][i] = item
            break
    else:
        data["faqs"].append(item)
    data["version"] = new_version()
    data["count"] = len(data["faqs"])
    return data


def blank_item():
    return {
        "id": "",
        "category": "other",
        "questions": [],
        "answer": "",
        "audio": "",
        "photo": "",
        "link": "",
        "enabled": True,
        "show_from": "",
        "show_until": "",
        "note": "",
        "translations": {},
    }
