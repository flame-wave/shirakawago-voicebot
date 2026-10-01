"""キャラクターごとの見え方を、実際のブラウザで測る。

立ち絵は縦横比がまちまちで、横長のものは高さいっぱいに立たせると
画面を覆ってしまう。どれくらいの大きさになるかを数字で確かめる。

使い方（tools/serve.py を動かしておく）:
    python tools/measure_characters.py
    python tools/measure_characters.py --shot    写真も撮る
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ROOT = Path(__file__).resolve().parent.parent

SIZES = [(393, 852, "スマートフォン"), (1280, 800, "ノートPC")]


def render(url, width, height, shot=None):
    with tempfile.TemporaryDirectory() as profile:
        args = [
            CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            "--virtual-time-budget=8000",
            "--dump-dom", url,
        ]
        if shot:
            args[-2:-2] = [f"--screenshot={shot}"]
        res = subprocess.run(args, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=90)
    m = re.search(r'<pre id="measure-result"[^>]*>(.*?)</pre>', res.stdout, re.S)
    return json.loads(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--shot", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "tools" / "_shots"))
    args = ap.parse_args()

    characters = json.loads(
        (ROOT / "assets" / "faq.json").read_text(encoding="utf-8")
    ).get("characters", [])
    out_dir = Path(args.out)
    if args.shot:
        out_dir.mkdir(parents=True, exist_ok=True)

    for width, height, label in SIZES:
        print(f"\n【{label} {width}×{height}】")
        print(f"  {'キャラクター':<12}{'立ち絵の大きさ':<16}{'画面に占める割合':<18}縦横比")
        for c in characters:
            target = f"/webapp/?character={c['id']}"
            if width < 520:
                url = (f"{args.base}/tools/_measure_frame.html"
                       f"?w={width}&h={height}&target={target}")
                win = (width + 160, height + 120)
            else:
                url = f"{args.base}{target}&measure=1"
                win = (width, height)
            shot = str(out_dir / f"{c['id']}_{width}.png") if args.shot else None
            data = render(url, win[0], win[1], shot)
            if not data:
                print(f"  {c['name']:<12}（測れませんでした）")
                continue
            item = data["items"].get("キャラクター")
            view = data["view"]
            if not item:
                print(f"  {c['name']:<12}（画面に無い）")
                continue
            wpct = round(item["w"] / view["w"] * 100)
            hpct = round(item["h"] / view["h"] * 100)
            flag = "  ←大きすぎ★" if wpct > 72 else ""
            print(f"  {c['name']:<12}{item['w']:>4}×{item['h']:<4}px     "
                  f"幅{wpct:>3}% 高さ{hpct:>3}%        {c.get('aspect')}{flag}")


if __name__ == "__main__":
    main()
