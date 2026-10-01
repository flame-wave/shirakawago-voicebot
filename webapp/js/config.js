// 設置先に合わせて変えるのはこのファイルだけで済むようにしている。

/// 素材（faq.json / 音声 / 写真 / キャラクター画像）の置き場所。
/// リポジトリ直下を公開する前提で、webapp/ からの相対パスにしてある。
/// assets/ を webapp/ の中に移すなら './assets/' に変える。
export const ASSET_BASE = '../assets/';

/// FAQデータの配信元URL。ここを設定するとオンライン更新が有効になる。
/// 空文字のままなら、同梱データ（ASSET_BASE の faq.json）だけで動作する。
///
/// 例（GitHubで配信する場合）:
///   https://raw.githubusercontent.com/ユーザ名/リポジトリ名/main/assets/faq.json
export const REMOTE_URL = '';

/// 通信の待ち時間。現地の回線が遅い場合を考えて短めにする。
export const FETCH_TIMEOUT_MS = 8000;

/// 読み上げに使う声の優先順位。
///
/// ブラウザによって入っている声が違うため、上から順に探して最初に見つかったものを使う。
/// Androidアプリで使っていたのは「Google 日本語」なので、それを先頭にしている。
/// Chrome（PC・Android）ならこの声が使える。名前の一部が一致すれば採用する。
/// キャラクターは若い女性なので、どの言語も女性の声を先に挙げている。
/// Windows・macOS・Chrome で名前が違うため、同じ声を複数の表記で並べてある。
export const PREFERRED_VOICES = {
  ja: ['Google 日本語', 'Microsoft Nanami', 'Microsoft Ayumi', 'Microsoft Haruka',
       'Kyoko', 'O-ren'],
  en: ['Google US English', 'Microsoft Aria', 'Microsoft Jenny', 'Microsoft Michelle',
       'Microsoft Zira', 'Samantha'],
  zh: ['Google 普通话', 'Microsoft Xiaoxiao', 'Microsoft Xiaoyi', 'Microsoft Huihui',
       'Tingting', 'Ting-Ting'],
  ko: ['Google 한국의', 'Microsoft SunHi', 'Microsoft Heami', 'Yuna'],
  es: ['Google español', 'Microsoft Elvira', 'Microsoft Helena', 'Microsoft Laura',
       'Mónica', 'Monica', 'Paulina'],
  fr: ['Google français', 'Microsoft Denise', 'Microsoft Vivienne', 'Microsoft Hortense',
       'Amélie', 'Amelie', 'Audrey'],
};

/// 最後の手段で声を選ぶときに、避けたい名前。
///
/// 上の優先順位にある声がどれも入っていない端末では、その言語の声を
/// 上から順に使うことになる。そこで男性の声を引くと、キャラクターの
/// 見た目と合わない（例: 英語で Microsoft David が選ばれる）。
/// Web Speech API は声の性別を教えてくれないため、名前で避けている。
export const AVOID_VOICES = [
  'david', 'mark', 'george', 'guy', 'ryan', 'brian', 'christopher', 'eric', 'roger',
  'steffan', 'thomas', 'daniel', 'alex', 'fred', 'paul', 'rishi', 'liam',
  'ichiro', 'keita', 'kangkang', 'yunxi', 'yunyang', 'yunjhe', 'injoon',
  'jorge', 'pablo', 'diego', 'juan', 'henri', 'claude', 'rémy', 'remy', 'nicolas',
];

/// 読み上げの速さと高さ。案内なので少しゆっくりめにする。
/// キャラクターの印象に合わせるなら、高さを 1.1〜1.2 に上げる。
export const VOICE_RATE = 0.95;
export const VOICE_PITCH = 1.0;

/// 質問の記録を送る先（server/api/log.php を置いた場所）。
/// 空にすると送らず、その端末の中だけに残る（管理者画面では見られない）。
///
///   手元で試すとき … '../server/api/log.php'
///   公開するとき   … '../api/log.php'
export const LOG_ENDPOINT = '../server/api/log.php';

/// 溜まった記録をまとめて送る間隔。
/// 据え置き端末は電源を入れっぱなしにするため、定期的に送る。
export const LOG_FLUSH_INTERVAL_MS = 5 * 60 * 1000;

/// 据え置き端末で、この時間だれも触らなければ同意画面に戻す。
///
/// 据え置きは次々と別の方が使うので、一度の同意で済ませるわけにいかない。
/// 無操作が続いたら「次の方が来た」とみなして、確かめ直す。
/// 短すぎると案内を読んでいる途中で消えてしまうため、余裕を持たせる。
export const CONSENT_IDLE_MS = 10 * 60 * 1000;

/// この端末がどの案内所にあるか。
///
/// 通常は URL で決める（1組のファイルを3通りの端末で共有できる）。
///   webapp/?place=バスターミナル … その案内所の据え置き端末
///   webapp/                      … 観光客のスマートフォン（位置情報で判定）
///
/// ここに書くのは、URLを固定できない場合の既定。
///   'auto'          … 位置情報で判定する
///   'バスターミナル' … 常にその案内所として動かす
///   ''              … 場所を使わず、共通の回答だけで案内する
/// 名前は質問回答集の「設置場所」シートと同じ文字にする。
export const PLACE = 'auto';

/// 位置情報の取得をこの時間まで待つ（過ぎたら共通の回答で案内する）
export const PLACE_TIMEOUT_MS = 6000;

/// AI回答の中継（server/api/ask.php を置いた場所）。
/// 空のままなら、質問回答集で答えられないときは職員案内だけになる。
///
/// 置き場所によって書き分ける。
///   手元で試すとき（リポジトリ直下で php -S を動かす）… '../server/api/ask.php'
///   公開するとき（api/ を assets/ と並べて置く）    … '../api/ask.php'
/// APIキーはこちらには書かない。中継サーバの中だけに置く。
export const AI_ENDPOINT = '../server/api/ask.php';

/// AIの返事をこの時間まで待つ。過ぎたら職員案内に切り替える。
/// 観光客を待たせないことを、答えを得ることより優先する。
export const AI_TIMEOUT_MS = 8000;

/// 無音がこの時間続いたら聞き取りを終える（実機の pauseFor 相当）
export const SILENCE_TIMEOUT_MS = 10000;

/// 1回の聞き取りの上限（実機の listenFor 相当）
export const LISTEN_TIMEOUT_MS = 60000;
