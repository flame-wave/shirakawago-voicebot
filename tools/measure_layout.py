"""画面の寸法を実際のブラウザで測る。

目で見て「大きい」「小さい」と直すと、別の画面幅で崩れる。
Chromeに描かせて、幅と高さを数字で確かめるための道具。

使い方（リポジトリ直下で tools/serve.py を動かしておく）:
    python tools/measure_layout.py
    python tools/measure_layout.py --shot   画面の写真も撮る
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

# 確かめる画面の大きさ（幅, 高さ, 呼び名）
SIZES = [
    (393, 852, "スマートフォン"),
    (768, 1024, "タブレット縦"),
    (1280, 800, "ノートPC"),
    (1920, 1080, "設置端末"),
]

def measure(url, width, height, shot=None):
    with tempfile.TemporaryDirectory() as profile:
        args = [
            CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            "--virtual-time-budget=8000",
            "--dump-dom", url,
        ]
        if shot:
            args[-2:-2] = [f"--screenshot={shot}"]
        res = subprocess.run(args, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=90)
    return res.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8010/webapp/")
    ap.add_argument("--shot", action="store_true", help="画面の写真も撮る")
    ap.add_argument("--out", default=str(ROOT / "tools" / "_shots"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    if args.shot:
        out_dir.mkdir(parents=True, exist_ok=True)

    # 測る対象は案内アプリ側（app.js の MEASURE_TARGETS）が持っている。
    # 画面の作りが変わったとき、直す場所が1か所で済む。
    #
    # ヘッドレスのブラウザは窓を500pxより狭くできないため、
    # スマートフォンの幅は枠（tools/_measure_frame.html）の中で測る。
    base = args.url.split("/webapp/")[0]

    for width, height, label in SIZES:
        shot = str(out_dir / f"{width}x{height}.png") if args.shot else None
        if width < 520:
            probe = (f"{base}/tools/_measure_frame.html"
                     f"?w={width}&h={height}&target=/webapp/")
            # 窓は枠より大きくしておく（枠が切れないように）
            dom = measure(probe, width + 160, height + 120, shot)
        else:
            probe = args.url + ("&" if "?" in args.url else "?") + "measure=1"
            dom = measure(probe, width, height, shot)
        m = re.search(r'<pre id="measure-result"[^>]*>(.*?)</pre>', dom, re.S)
        if not m:
            print(f"[{label} {width}x{height}] 測れませんでした"
                  "（webapp/js/app.js の計測用の出力を確認してください）")
            continue
        data = json.loads(m.group(1))
        view = data["view"]["w"]
        over = data["doc"]["w"] > view
        hami = ("あり★ 内容" + str(data["doc"]["w"]) + "px") if over else "なし"
        print(f"\n【{label} 指定{width}×{height} / 実際の表示幅 {view}px】  横のはみ出し={hami}")
        for name, v in data["items"].items():
            if v is None:
                print(f"  {name:<12} （画面に無い）")
            elif v["hidden"]:
                print(f"  {name:<12} （隠れている）")
            else:
                pct = round(v["w"] / data["view"]["w"] * 100)
                flag = "  ←はみ出し★" if v["x"] + v["w"] > data["view"]["w"] + 1 else ""
                print(f"  {name:<12} {v['w']:>5}×{v['h']:<5}px "
                      f"(幅の{pct:>3}%) 文字{v['font']:<7} x={v['x']}{flag}")
        if shot:
            print(f"  写真: {shot}")


if __name__ == "__main__":
    main()
