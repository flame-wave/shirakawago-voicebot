"""管理画面を実際に開いて、各ページの写真を撮る。

Streamlit は読み込んだあとに通信してから中身を描くので、
ヘッドレスのChromeに `--screenshot` を渡すだけでは、まだ何も無い画面が写る。
描き終わるのを待ってから撮るために、ブラウザを操作して撮る。

使い方（別の窓で管理画面を起動しておく）:
    streamlit run admin/app.py --server.port 8502 --server.headless true
    python tools/shoot_admin.py
"""
import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# 撮るページ。URLの末尾は app.py の st.Page に合わせてある。
PAGES = [
    ("", "ホーム"),
    ("page_add", "質問を追加・修正する"),
    ("page_list", "登録されている質問"),
    ("page_bulk", "まとめて翻訳する"),
    ("screen?tab=layout", "画面・キャラクター・声：画面レイアウト"),
    ("screen?tab=character", "画面・キャラクター・声：キャラクター"),
    ("screen?tab=voice", "画面・キャラクター・声：読み上げの声"),
    ("screen?tab=yomikata", "画面・キャラクター・声：読み方"),
    ("local?tab=sanko", "現地の情報：参考資料"),
    ("local?tab=basho", "現地の情報：設置場所"),
    ("local?tab=iikae", "現地の情報：言い換え"),
    ("page_publish", "案内アプリへ反映する"),
    ("page_stats", "利用状況"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8502")
    ap.add_argument("--out", default=str(ROOT / "tools" / "_shots" / "admin"))
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--only", nargs="*", help="撮るページのURL（省略すると全部）")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        for path, label in PAGES:
            if args.only and path not in args.only:
                continue
            url = f"{args.base}/{path}"
            # Streamlitは通信をつなぎっぱなしにするので networkidle には
            # ならない。中身が描かれたことを目印にして待つ。
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("[data-testid='stMain']", timeout=60000)
            try:
                # 骨組み（読み込み中の薄い帯）が消えるまで
                page.wait_for_function(
                    "document.querySelectorAll('[class*=skeleton]').length === 0",
                    timeout=30000)
                # 画面の題（共通の部品 ui.page_header）が出るまで待つ
                page.wait_for_selector("[data-testid='stMain'] .ui-title, "
                                       "[data-testid='stMain'] h3", timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(1500)

            shown = page.inner_text("[data-testid='stMain']")[:60].replace("\n", " ")
            shot = out / f"{(path or 'home').replace('?tab=', '_')}.png"
            page.screenshot(path=str(shot), full_page=True)
            # 画面のどこかに Python のエラーの箱が出ていないか（先頭だけ見ると見逃す）
            crashed = page.query_selector("[data-testid='stException']") is not None
            if crashed:
                errors.append(f"{label}: 画面の中にエラーの箱があります")
            bad = "★" if crashed or "Traceback" in shown else " "
            print(f" {bad} {label:<20} {shot.name:<20} {shown}")

        browser.close()

    if errors:
        print("\n画面側のエラー:")
        for e in errors[:10]:
            print("  ・" + e)
    else:
        print("\n画面側のエラーはありません。")


if __name__ == "__main__":
    main()
