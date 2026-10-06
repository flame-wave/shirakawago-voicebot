"""GitHubのトークンで、管理画面と同じことができるかを確かめる。

管理画面は2つのファイルを読み書きする。どちらかができないと
「保存に失敗しました（403）」になる。どこで止まっているかを切り分ける。

トークンは画面に出さず、保存もしない（入力中も表示されない）。

使い方:
    python tools/check_github_token.py
    python tools/check_github_token.py --write-test   書き込みも実際に試す
"""
import argparse
import getpass
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://api.github.com"
REPO = "flame-wave/shirakawago-voicebot"
BRANCH = "main"
FILES = ["tools/faq_master.xlsx", "assets/faq.json"]

# 書き込みを試すときに作る、使い捨てのファイル
TEST_PATH = ".github/write-test.txt"


def headers(token):
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"}


def needed(res):
    """GitHubが「この権限が要る」と教えてくれるヘッダ。"""
    return res.headers.get("x-accepted-github-permissions", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--write-test", action="store_true",
                    help="書き込みも実際に試す（使い捨てのファイルを作って消す）")
    args = ap.parse_args()

    print(f"対象: {args.repo}（{args.branch}）\n")
    token = getpass.getpass("GitHubのトークンを貼ってください（画面には出ません）: ")
    if not token.strip():
        print("入力がありませんでした。")
        sys.exit(1)
    token = token.strip()

    kind = ("Fine-grained" if token.startswith("github_pat_")
            else "Classic" if token.startswith(("ghp_", "gho_"))
            else "不明な形式")
    print(f"\n種類: {kind}")

    # ---- 1. リポジトリが見えるか
    res = requests.get(f"{API}/repos/{args.repo}", headers=headers(token), timeout=30)
    if res.status_code == 404:
        print("\n★ リポジトリが見えません。")
        print("  トークンの Repository access で、このリポジトリを選んでいますか。")
        sys.exit(1)
    if res.status_code == 401:
        print("\n★ トークンが無効です（期限切れか、貼り間違い）。")
        sys.exit(1)
    if res.status_code != 200:
        print(f"\n★ リポジトリを見られません（{res.status_code}）: {res.text[:200]}")
        sys.exit(1)
    print("1. リポジトリが見える: はい")

    # ---- 2. ファイルが読めるか
    shas = {}
    for path in FILES:
        res = requests.get(f"{API}/repos/{args.repo}/contents/{path}",
                           headers=headers(token), params={"ref": args.branch},
                           timeout=30)
        if res.status_code == 200:
            shas[path] = res.json().get("sha")
            print(f"2. 読める: {path}")
        elif res.status_code == 404:
            print(f"★ 2. ファイルがありません: {path}（先に push してください）")
        else:
            print(f"★ 2. 読めません: {path}（{res.status_code}）")
            if needed(res):
                print(f"     要る権限: {needed(res)}")

    # ---- 3. 書けるか
    if not args.write_test:
        print("\n3. 書き込み: 試していません（--write-test を付けると試します）")
        print("   「保存に失敗しました（403）」が出ている場合は、付けて実行してください。")
        return

    body = {"message": "書き込みの確認（すぐ消します）",
            "content": "dGVzdA==", "branch": args.branch}
    res = requests.put(f"{API}/repos/{args.repo}/contents/{TEST_PATH}",
                       headers=headers(token), json=body, timeout=30)

    if res.status_code in (200, 201):
        print("3. 書き込み: できます")
        sha = res.json()["content"]["sha"]
        requests.delete(f"{API}/repos/{args.repo}/contents/{TEST_PATH}",
                        headers=headers(token), timeout=30,
                        json={"message": "確認用ファイルを削除",
                              "sha": sha, "branch": args.branch})
        print("   （確認用のファイルは消しました）")
        print("\nすべて通りました。管理画面から保存できるはずです。")
        return

    print(f"★ 3. 書き込めません（{res.status_code}）")
    print(f"     {res.json().get('message', res.text[:200])}")
    if needed(res):
        print(f"     GitHubが要ると言っている権限: {needed(res)}")
    print("\n直し方:")
    print("  GitHub → Settings → Developer settings → Personal access tokens")
    print("  → Fine-grained tokens → 該当のトークン → Edit")
    print("    ・Repository access … Only select repositories に"
          f" {args.repo} を入れる")
    print("    ・Repository permissions → Contents … Read and write にする")
    print("  直したら Update token を押し、管理画面のSecretsも貼り直す。")


if __name__ == "__main__":
    main()
