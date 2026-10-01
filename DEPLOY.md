# 公開の手順

ロリポップ（案内アプリとAIの中継）と GitHub（データの置き場）、
Streamlit（管理画面）の3つを組み合わせる。

## 全体の形

```
          ┌─ 観光客のスマートフォン ─┐   ┌─ 据え置き端末 ─┐
          └───────────┬──────────┘   └───────┬───────┘
                      │                      │
                      ▼                      ▼
        ┌──────────────── ロリポップ ────────────────┐
        │  /webapp/   案内アプリ                      │
        │  /assets/   質問回答集・音声・写真・キャラ画像  │
        │  /api/      AIの中継・記録の受け口            │
        └───────────────┬────────────┬──────────────┘
                        │ 最新の質問回答集 │ 記録
                        ▼            ▼
                 ┌─ GitHub ─┐   ┌─ 管理画面（Streamlit）─┐
                 │ faq.json │◀──│ 職員が質問を足す・設定する │
                 │ Excel    │   └──────────────────────┘
                 └──────────┘
```

**なぜ全部ロリポップに置くか。** AIの中継はPHPが要るのでロリポップになる。
案内アプリを別の場所（GitHub Pagesなど）に置くと、別のサイトからの呼び出しになり、
その許可の設定が増える。同じ場所に置けばその手間が要らない。

**なぜGitHubも使うか。** 職員が質問を足すたびにFTPで上げ直すのは続かない。
管理画面がGitHubへ書き、案内アプリと中継サーバがそこから読むので、
**文章の修正はFTPなしで反映される**（画像と音声を足したときだけFTPが要る）。

---

## 1. GitHub に上げる

### 1-1. APIキーが入っていないことを確かめる

**ここを飛ばさないこと。** 一度公開すると取り消せない。

```
python tools/check_secrets.py
```

```
秘密らしきものは見つかりませんでした。push して大丈夫です。
```

と出れば進んでよい。見つかった場合は、その名前を `.gitignore` に足すか、
ファイルごと消す。**すでに commit してしまったキーは、無効化して作り直す**
（履歴から消してもコピーが残っている可能性があるため）。

使わなくなった設定の控え（`config1.php` など）は、キーごと消しておく。

### 1-2. 上げる

```
git add -A
git commit -m "Webアプリ・管理画面・中継サーバを追加"
git push
```

音声（`assets/audio/`）はmp3に変換済みで13MBほど。そのまま上げてよい。

VOICEVOXで音声を作り足したときは、WAVのままになるので変換する。

```
python tools/convert_audio.py --dry-run   どうなるかだけ見る
python tools/convert_audio.py             変換してExcelも書き換える
```

---

## 2. ロリポップに置く

### 2-1. ファイルを上げる

FTPで、公開フォルダ（`/`）に次の形で置く。

```
/
├── webapp/     ← そのまま
├── assets/     ← そのまま
└── api/        ← server/api/ の中身（名前を api に変える）
```

`server/` ではなく **`api/`** にする。設定の既定値がその形になっている。

`api/data/` フォルダも一緒に上げる。無いと記録が書けない。

### 2-2. 書き込みの許可

`api/data/` に書き込み権限を付ける（ロリポップのFTP画面で属性を `707` か `777`）。
ここに記録と控えが書かれる。

### 2-3. 独自SSL（https）を有効にする

ロリポップの管理画面 →「セキュリティ」→「独自SSL証明書導入」→ 無料SSLを設定。

**httpsでないとマイクが使えない。** ブラウザの決まりなので回避できない。

### 2-4. 設定ファイルを作る

`api/config.sample.php` を `api/config.php` という名前でコピーし、次を埋める。

| 項目 | 入れるもの |
|------|-----------|
| `api_key` | AnthropicのAPIキー（`sk-ant-…`） |
| `faq_url` | `https://raw.githubusercontent.com/＜ユーザ名＞/＜リポジトリ名＞/main/assets/faq.json` |
| `allow_origins` | `https://＜公開したドメイン＞`（1行だけにする） |
| `log_token` | 長い無作為の文字列（下のコマンドで作る） |

```
php -r "echo bin2hex(random_bytes(24));"
```

`faq_path` は見本のまま（`__DIR__ . '/../assets/faq.json'`）でよい。

> `allow_origins` を空にしたり `https://example.com` のままにすると、
> **誰でもAIを呼び出せてしまい、APIの料金を他人に使われる。**

### 2-5. 案内アプリの設定を公開用にする

`webapp/js/config.js` の3行を直す（上げる前に手元で直しておくとよい）。

```js
export const REMOTE_URL = 'https://raw.githubusercontent.com/＜ユーザ名＞/＜リポジトリ名＞/main/assets/faq.json';
export const AI_ENDPOINT = '../api/ask.php';
export const LOG_ENDPOINT = '../api/log.php';
```

`ASSET_BASE` は `'../assets/'` のままでよい。

### 2-6. 動いているか確かめる

ブラウザで `https://＜ドメイン＞/api/ping.php` を開く。

```
1. PHP: 動いています
2. 外部への通信: できます
3. AIへの接続: できます（claude-haiku-4-5）
4. 記録の保存先: 書き込めます
```

4つとも通ったら、**`ping.php` は消す**（設定の様子が外から見えるため）。

---

## 3. 管理画面を置く（Streamlit）

1. share.streamlit.io でアプリを作り、Main file path に `admin/app.py` を指定
2. Settings → Secrets に次を貼る

```toml
[app]
password = "職員に伝える合言葉"

[github]
token      = "GitHubのアクセストークン"
repo       = "＜ユーザ名＞/＜リポジトリ名＞"
excel_path = "tools/faq_master.xlsx"
path       = "assets/faq.json"
branch     = "main"

[anthropic]
api_key = "翻訳用のAPIキー"

[logs]
url   = "https://＜ドメイン＞/api/logs.php"
token = "api/config.php の log_token と同じ文字列"
```

GitHubのトークンは、対象リポジトリの **Contents: Read and write** だけを許した
Fine-grained personal access token を使う。

---

## 4. 端末を設置する

| 端末 | 開くURL |
|------|---------|
| バスターミナル | `https://＜ドメイン＞/webapp/?place=バスターミナル` |
| であいの館 | `https://＜ドメイン＞/webapp/?place=であいの館` |
| 観光客用（QRコードにする） | `https://＜ドメイン＞/webapp/` |
| 職員の設定（ブックマーク） | `https://＜ドメイン＞/webapp/?place=バスターミナル&setup=1` |

据え置きはChromeのキオスクモードで起動する。

```
chrome.exe --kiosk --app=https://＜ドメイン＞/webapp/?place=バスターミナル
```

**掲示を忘れない。** 質問内容を記録して外部のAIへ送るため、
その旨を端末のそばに掲示する（画面の同意と両方）。

---

## 更新するとき

| 変えたもの | やること |
|------------|----------|
| 質問・回答・設定 | 管理画面で直して「案内アプリへ反映する」。**FTPは要らない** |
| 画像・音声を足した | FTPで `assets/` に上げる＋GitHubにも push |
| 画面の作り（js/css） | FTPで `webapp/` を上げ直す |

質問回答集はGitHubから読むので、文章の修正はFTPなしで届く。
中継サーバも同じURLを見ている（`faq_url`）ので、AIの答えも一緒に新しくなる。

案内端末は次に開いたときに新しい内容になる。据え置きは開きっぱなしなので、
**夜に一度閉じて開き直す**運用にしておくとよい。

---

## つまずきやすいところ

| 症状 | 原因 |
|------|------|
| マイクが反応しない | httpsになっていない |
| AIが答えない（`forbidden`） | `allow_origins` が公開ドメインと違う |
| AIが答えない（`no_data`） | `faq_path` の場所が違う。`api/` の1つ上に `assets/` があるか |
| 記録が溜まらない | `api/data/` に書き込み権限が無い／観光客が「同意して使う」を押していない |
| 管理画面で記録が読めない | `log_token` と Secrets の `token` が違う |
| 直したのに画面が変わらない | `.htaccess` を上げ忘れている（`webapp/` と `assets/` の両方に要る） |
