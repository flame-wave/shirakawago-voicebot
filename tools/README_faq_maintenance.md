# 質問回答集のメンテナンス手順

編集 → 検証 → 配信 の3段階。編集する場所だけ職員が触り、
検証と配信はコマンド1つで行う。

## ファイル

| ファイル | 役割 |
|----------|------|
| `faq_master.xlsx` | 質問回答集の原本。ここだけを編集する |
| `build_faq.py` | 記入内容をチェックして `faq.json` を書き出す |

## Excel運用の場合

1. `faq_master.xlsx` を共有フォルダに置き、職員が直接編集する
2. 変換する

```
python build_faq.py --source faq_master.xlsx --out assets/faq.json --assets assets
```

## Googleスプレッドシート運用の場合

1. `faq_master.xlsx` をGoogleドライブにアップロードし、スプレッドシートとして開く
2. 共有設定を「リンクを知っている全員が閲覧可」にする
3. URLを指定して変換する（内部でxlsxとして取得するので処理は同じ）

```
python build_faq.py --source "https://docs.google.com/spreadsheets/d/XXXX/edit" --out assets/faq.json --assets assets
```

いつでも相互に移行できる。Excelで始めてGoogleに移す場合はアップロードするだけ、
逆の場合はスプレッドシートを .xlsx でダウンロードするだけ。

## 検証でチェックされる内容

**エラー（書き出しを中止）**
- IDの重複、IDの書式違反、IDの空欄
- カテゴリが未定義
- 質問例・回答が空
- 参考リンクがURLの形式でない
- 多言語シートの言語コードが不正

**確認（書き出しは実行）**
- 回答が120字を超える（読み上げが長い）
- 質問例が1つだけ（認識精度が下がる）
- 写真・音声ファイルが見つからない
- 多言語シートのIDがFAQシートに無い

`--assets` を付けると写真・音声の実在確認まで行う。
`--force` でエラーを無視して強制書き出しもできる（原則使わない）。

## 運用上の約束

- 不要になった質問は行を削除せず「有効」を FALSE にする（履歴が残る）
- IDは一度決めたら変更しない（音声・写真のファイル名と紐づいているため）
- 変更したら「更新日」を記入する

## 必要なもの

Python と以下のライブラリ。

```
pip install pandas openpyxl
pip install requests   # GoogleスプレッドシートのURLを使う場合のみ
```
