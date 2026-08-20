# 白川郷 音声案内チャットボット（Flutter プロトタイプ）

「押して話す → 音声認識 → FAQ検索 → 回答表示＆音声再生」の流れを端末内で完結させる。
各処理は差し替え可能な部品として分離してある。

## ファイル構成

| ファイル | 役割 |
|----------|------|
| `lib/main.dart` | 画面と一連の流れの組み立て |
| `lib/faq_repository.dart` | FAQデータの取得（オンライン更新・キャッシュ・同梱の3段構え） |
| `lib/faq_service.dart` | FAQ検索の部品（← 将来ここだけ差し替える） |
| `lib/voice_service.dart` | 読み上げの部品（音声ファイル → 無ければ端末音声） |
| `lib/answer_view.dart` | 回答表示の部品（字幕・写真・QRコード） |
| `lib/app_language.dart` | 対応言語の定義と画面文言（← 言語追加はここから） |
| `lib/question_log.dart` | 質問の記録（1行1件のJSONL形式で端末内に保存） |
| `lib/log_screen.dart` | 職員向けの記録確認画面 |
| `lib/language_selector.dart` | 言語切り替えボタン |
| `lib/character_view.dart` | キャラクター表情の表示部品（← Live2D化もここを差替） |
| `assets/faq.json` | 質問・回答データ（変換ツールが生成） |
| `assets/audio/` | 用意した音声（*.wav）。無い項目は端末音声で読み上げ |
| `assets/photo/` | 回答に添える写真 |
| `assets/character/` | idle / listening / talking の3表情画像 |
| `tools/` | 質問回答集の原本と変換ツール、ログ分析（アプリには同梱されない） |

## FAQデータの更新の流れ

```
Excel / Googleスプレッドシート  ←  職員が編集
        ↓  tools/build_faq.py（検証つき変換）
     faq.json
        ↓  GitHub等にアップロード
   配信URL
        ↓  起動時に自動取得
   タブレット
```

### 端末側の動作（オフライン優先）

1. 起動時、ローカルを即座に読む（キャッシュ → 無ければ同梱データ）
2. 画面が使える状態になった後、裏で配信URLを取得
3. 取得できて版が新しければ差し替え、キャッシュに保存
4. 通信が失敗しても、前回のデータで動き続ける

配信URLは `lib/faq_repository.dart` の `remoteUrl` に設定する。
空のままなら同梱データのみで動作する（オフライン専用運用）。

画面右上に「データ 最新 / 保存済み / 初期データ」と版が表示されるので、
職員が更新の反映を確認できる。

## セットアップ

```
flutter pub get
flutter run
```

`android/app/src/main/AndroidManifest.xml` に以下が必要:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.INTERNET"/>
<queries>
    <intent>
        <action android:name="android.speech.RecognitionService" />
    </intent>
</queries>
```

## 段階的な発展計画

- 第1段階（現在）: 端末標準の音声認識 ＋ キーワード一致 ＋ 音声ファイル/端末音声の併用
  ＋ 写真・QRコード表示 ＋ オンライン更新 ＋ 多言語（手動切替）

## 多言語対応

日本語・English・中文・한국어の4言語。画面上部のボタンで手動切り替え。

自動判定にしていないのは、音声認識が「これから何語が話されるか」を事前に
指定する必要があるため。騒音下では自動判定が誤りやすく、観光客が自分で
選ぶ方が確実になる。どの言語が選ばれたかは利用統計としても使える。

翻訳は `tools/faq_master.xlsx` の「多言語」シートに記入する。
未記入の項目は日本語で表示し、画面にその旨を断り書きとして出す
（翻訳が揃うまで案内が止まらないようにするため）。

音声は、その言語の音声ファイルがあれば再生し、無ければ端末の音声合成が
その言語で読み上げる。端末がその言語の音声認識に対応していない場合は、
言語を選んだ時点で画面に表示される。
- 第2段階: 音声認識を whisper.cpp でオフライン化、FAQ検索を埋め込みベクトル化
- 第3段階: FAQ検索・AI返答をクラウド（Python側）へ、質問ログを蓄積して分析


## 質問ログ

何を聞かれ、答えられたかを端末内に記録する。
頻出質問の把握とFAQ拡充の根拠になり、研究データとしても使う。

### 記録する内容

日時 / 言語 / 認識された質問文 / ヒットしたFAQのID / 分類 /
翻訳を日本語で代替したか / 読み上げの方法

音声そのものは保存しない。

### 確認する

画面右上のデータ表示を**長押し**すると職員用の画面が開く。
観光客の目に触れないよう、通常のUIからは辿れない導線にしてある。

- 回答率（職員に回さず完結できた割合の目安）
- 答えられなかった質問の一覧 ← FAQに追加する候補
- よく聞かれた質問 ← 音声を優先して用意すべきもの
- 言語別の利用

### PCで分析する

職員用画面に表示される保存先から `question_log.jsonl` を取り出し、

```
python tools/analyze_log.py question_log.jsonl
python tools/analyze_log.py question_log.jsonl --csv out.csv
```

時間帯別の利用状況まで集計される。`--csv` を付けるとExcelで開ける形式で出力する。

### 設置時の注意

質問内容を記録するため、**「音声を認識し、質問内容を記録します」の掲示が必要**。
保存期間と匿名化の方針もあわせて決めておく。大学の研究として設置する場合は
倫理審査の対象になる可能性がある。
