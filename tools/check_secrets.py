"""GitHubへ上げる前に、APIキーなどが混ざっていないかを調べる。

一度公開すると取り消せない。push の前に必ず通す。

使い方:
    python tools/check_secrets.py
"""
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# 本物のキーだけを拾う形にする。
# 説明文の「sk-ant-…」のような書き方に引っかからないよう、
# 鍵として成り立つ長さの英数字が続くものだけを見る。
PATTERNS = [
    (r"sk-ant-[A-Za-z0-9_\-]{30,}", "AnthropicのAPIキー"),
    (r"gsk_[A-Za-z0-9]{40,}", "GroqのAPIキー"),
    (r"AIza[A-Za-z0-9_\-]{30,}", "GoogleのAPIキー"),
    (r"gh[ps]_[A-Za-z0-9]{30,}", "GitHubのトークン"),
    (r"github_pat_[A-Za-z0-9_]{40,}", "GitHubのトークン"),
    (r"sk-[A-Za-z0-9]{40,}", "OpenAI系のAPIキー"),
]

# 中身を見る拡張子。画像や音声は見ても意味がない。
READABLE = {".php", ".js", ".py", ".md", ".json", ".toml", ".txt",
            ".html", ".css", ".yaml", ".yml", ".dart", ".sh"}

# 設定ファイルは名前だけで判断する（中身を見るまでもない）
CONFIG_LIKE = re.compile(r"config.*\.php$|secrets\.toml$|\.env$")


def tracked_files():
    """Gitが上げる対象のファイル（除外設定を効かせたもの）。"""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("build/", ".venv/")):
            yield line


def main():
    problems = []
    checked = 0

    for name in tracked_files():
        path = ROOT / name

        # 設定ファイルの名前のものは、中身にかかわらず止める
        if CONFIG_LIKE.search(name) and not name.endswith("config.sample.php"):
            problems.append((name, 0, "設定ファイルが除外されていません"))
            continue

        if path.suffix.lower() not in READABLE or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        checked += 1

        for i, line in enumerate(text.splitlines(), start=1):
            for pattern, label in PATTERNS:
                if re.search(pattern, line):
                    problems.append((name, i, label))

    print(f"調べたファイル: {checked} 件")
    if not problems:
        print("\n秘密らしきものは見つかりませんでした。push して大丈夫です。")
        return

    print(f"\n★ {len(problems)} 件見つかりました。push しないでください。\n")
    for name, line, label in problems:
        where = f"{name}:{line}" if line else name
        print(f"  {where}  … {label}")
    print("\n対処:")
    print("  ・設定ファイルなら .gitignore に足す")
    print("  ・すでに commit 済みなら、そのキーは無効化して作り直す")
    sys.exit(1)


if __name__ == "__main__":
    main()
