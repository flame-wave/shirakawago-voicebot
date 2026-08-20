# デモ版（Streamlit）

外部の方に内容を確認していただくためのデモ。
実機アプリと**同じ判定**でFAQを選ぶが、音声入力の代わりにテキスト入力を使う。

## 構成

| ファイル | 役割 |
|----------|------|
| `app.py` | デモ画面 |
| `faq_engine.py` | 検索ロジック（`lib/faq_service.dart` と同じ判定をPythonで再現） |
| `requirements.txt` | 必要なライブラリ |

`assets/faq.json` をそのまま読むため、質問回答集を更新すればデモにも反映される。

## 手元で動かす

```
pip install -r demo/requirements.txt
streamlit run demo/app.py
```

## 公開する（Streamlit Community Cloud）

1. このリポジトリをGitHubにpush
2. share.streamlit.io でアプリを新規作成
3. Main file path に `demo/app.py` を指定

公開URLができるので、そのまま共有できる。
`assets/faq.json` を更新してpushすれば、デモも自動で新しくなる。

## 画面

- **試す**: 質問を入力して回答を確認。「なぜこの回答が選ばれたか」で判定根拠も見られる
- **質問回答集の一覧**: 登録されている全件を分類別に確認
- **動作の確認**: 複数の質問をまとめて試し、回答できた割合を出す

## 注意

- 検索ロジックを `lib/faq_service.dart` で変更したら、`faq_engine.py` も必ず合わせること
- 音声認識・読み上げ・キャラクター表示は含まない（実機で確認する部分）
