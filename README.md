# 白川郷 音声案内チャットボット（Flutter プロトタイプ）

「押して話す → 音声認識 → FAQ検索 → 回答表示＆音声再生」の一連の流れを
端末内で通す最小構成。各処理は差し替え可能な部品として分離してある。

## ファイル構成

| ファイル | 役割 |
|----------|------|
| `lib/main.dart` | 画面と一連の流れの組み立て |
| `lib/faq_service.dart` | FAQ検索の部品（← 将来ここだけ差し替える） |
| `lib/character_view.dart` | キャラクター表情の表示部品（← Live2D化もここを差替） |
| `assets/faq.json` | 質問・回答データ |
| `assets/audio/` | 事前生成したテト音声（*.wav）を置く |
| `assets/character/` | idle / listening / talking の3表情画像を置く |
| `pubspec.yaml` | 使用ライブラリと素材の宣言 |

## キャラクター表示について

システムの状態に応じて3つの表情が自動で切り替わる:

- `idle`（待機中）→ `listening`（押して話す中）→ `talking`（回答中）→ `idle`

`assets/character/` に `idle.png` / `listening.png` / `talking.png` を置けば表示される。
画像が無い間は状態ごとの仮アイコンが出るので、絵の完成前でも動作確認できる。
Live2Dにする場合は `CharacterView` を差し替える（静止画方式と同じ状態を渡せばよい）。

## セットアップ手順

1. Flutter SDK をインストール（Windows可）
2. このフォルダで `flutter pub get`
3. `assets/audio/` に、PCのVOICEPEAKで生成したテト音声を
   faq.json の "audio" 名（例 `toilet.wav`）で配置
4. Androidタブレットを接続して `flutter run`

※ マイク権限が必要（初回起動時に許可を求められる）

## 段階的な発展計画

- 第1段階（現在）: 端末標準の音声認識 ＋ キーワード一致 ＋ 事前生成音声
- 第2段階: 音声認識を whisper.cpp でオフライン化、FAQ検索を埋め込みベクトル化、多言語対応
- 第3段階: FAQ検索・AI返答をクラウド（Python側）へ、質問ログをクラウドに蓄積して分析
