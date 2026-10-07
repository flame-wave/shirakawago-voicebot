"""回答に付ける写真の置き場所。

写真は2か所に置く必要がある。
  ・GitHub（または手元）の assets/photo … 質問回答集と一緒に残すため
  ・ロリポップの assets/photo         … 案内アプリはここから写真を読む

管理画面からできるのは前者まで。後者（FTP）は管理者の作業として残る。
そのため、新しく追加した写真には「案内端末に出すにはもう一手間」と知らせる。
"""
import base64
import re
from pathlib import Path

import requests

API = "https://api.github.com"
FOLDER = "assets/photo"
KINDS = (".jpg", ".jpeg", ".png", ".webp")


def safe_name(name: str) -> str:
    """ファイル名を、どの端末でも扱える形にする（英数字・_・- と拡張子）。

    日本語や空白の入った名前は、FTP やURLで化けることがある。
    """
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, "jpg"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_").lower() or "photo"
    ext = ext.lower()
    if f".{ext}" not in KINDS:
        ext = "jpg"
    return f"{stem[:40]}.{ext}"


class LocalPhotoStore:
    label = "この端末"

    def __init__(self, root):
        self.dir = Path(root) / FOLDER

    def list(self) -> list:
        if not self.dir.exists():
            return []
        return sorted(p.name for p in self.dir.iterdir()
                      if p.suffix.lower() in KINDS)

    def read(self, name: str):
        path = self.dir / name
        return path.read_bytes() if path.exists() else None

    def save(self, name: str, data: bytes) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / name).write_bytes(data)
        return name


class GitHubPhotoStore:
    label = "GitHub"

    def __init__(self, token, repo, branch="main", root=None):
        self.token, self.repo, self.branch = token, repo, branch
        # 管理画面を置いた時点の写し。GitHub に聞けないときの予備に使う。
        self.local = LocalPhotoStore(root) if root else None

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json"}

    def list(self) -> list:
        try:
            res = requests.get(f"{API}/repos/{self.repo}/contents/{FOLDER}",
                               headers=self._headers, params={"ref": self.branch},
                               timeout=20)
            if res.status_code == 200:
                return sorted(x["name"] for x in res.json()
                              if x.get("type") == "file"
                              and Path(x["name"]).suffix.lower() in KINDS)
        except requests.RequestException:
            pass
        return self.local.list() if self.local else []

    def read(self, name: str):
        if self.local:
            data = self.local.read(name)
            if data:
                return data
        try:
            res = requests.get(f"{API}/repos/{self.repo}/contents/{FOLDER}/{name}",
                               headers=self._headers, params={"ref": self.branch},
                               timeout=20)
            if res.status_code == 200 and res.json().get("content"):
                return base64.b64decode(res.json()["content"])
        except requests.RequestException:
            pass
        return None

    def save(self, name: str, data: bytes) -> str:
        url = f"{API}/repos/{self.repo}/contents/{FOLDER}/{name}"
        # 同じ名前があれば上書きする（目印 sha が要る）
        sha = None
        res = requests.get(url, headers=self._headers,
                           params={"ref": self.branch}, timeout=20)
        if res.status_code == 200:
            sha = res.json().get("sha")
        body = {"message": f"写真を追加: {name}（管理画面より）",
                "content": base64.b64encode(data).decode("ascii"),
                "branch": self.branch}
        if sha:
            body["sha"] = sha
        res = requests.put(url, headers=self._headers, json=body, timeout=60)
        if res.status_code not in (200, 201):
            raise RuntimeError(f"写真を保存できませんでした（{res.status_code}）")
        return name
