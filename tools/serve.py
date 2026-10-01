"""手元で案内アプリを開くための簡易サーバ。

`python -m http.server` だと、ブラウザがファイルを取りに来ないことがある。
更新した直後に新しいファイルと古いファイルが混ざり、
「◯◯ is not a function」のような止まり方をする。

このサーバは毎回「変わっていないか」を確かめさせるので、
直したものがそのまま画面に出る。

使い方（リポジトリ直下で）:
    python tools/serve.py
    → http://localhost:8000/webapp/

AIの回答まで試すときは、PHPの簡易サーバを使う（中継が動くのはこちら）:
    php -S 127.0.0.1:8000 -t .
"""
import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NoCacheHandler(SimpleHTTPRequestHandler):
    """毎回ブラウザに確かめさせる。

    no-cache は「毎回ダウンロードし直す」ではなく「毎回確かめてから使う」。
    変わっていなければ中身は送られてこないので、遅くはならない。
    """

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        # 404 の山で見づらくなるのを防ぐ（ブラウザが勝手に探しに来るものがある）
        message = fmt % args
        if "/.well-known/" in message:
            return
        super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--dir", default=str(ROOT),
                    help="配信するフォルダ（既定はリポジトリ直下）")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    handler = partial(NoCacheHandler, directory=args.dir)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)

    print(f"案内アプリ: http://localhost:{args.port}/webapp/")
    print("据え置きとして試す: "
          f"http://localhost:{args.port}/webapp/?place=バスターミナル")
    print("職員用の設定: "
          f"http://localhost:{args.port}/webapp/?setup=1")
    print("\n（AIの回答も試すときは php -S 127.0.0.1:8000 -t . を使ってください）")
    print("止めるには Ctrl+C\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n止めました。")


if __name__ == "__main__":
    main()
