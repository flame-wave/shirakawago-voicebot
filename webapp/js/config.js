// 設置先に合わせて変えるのはこのファイルだけで済むようにしている。

/// 素材（faq.json / 音声 / 写真 / キャラクター画像）の置き場所。
/// リポジトリ直下を公開する前提で、webapp/ からの相対パスにしてある。
/// assets/ を webapp/ の中に移すなら './assets/' に変える。
export const ASSET_BASE = '../assets/';

/// 手元のパソコンで試しているかどうか（開いたアドレスで見分ける）。
///
/// 手元と公開先ではファイルの並びが違う（手元は server/api/、公開先は api/）。
/// 以前は公開のたびにこのファイルを書き換えていたが、上書きし忘れ・上書きしすぎで
/// 2度止まったため、開いた場所を見て自動で切り替えるようにした。
/// これで手元のファイルをそのまま公開先へ上げてよい。
const LOCAL = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);

/// FAQデータの配信元URL。ここを設定するとオンライン更新が有効になる。
/// 空文字なら、同梱データ（ASSET_BASE の faq.json）だけで動作する。
/// 手元では、直したばかりの faq.json を試せるよう同梱データを使う。
export const REMOTE_URL = LOCAL ? ''
  : 'https://raw.githubusercontent.com/flame-wave/shirakawago-voicebot/main/assets/faq.json';

/// 画像（キャラクターの絵・写真）が ASSET_BASE に無いときに読みに行く先。
/// 管理画面から足した絵や写真は GitHub にしか無いので、ここから読む（webapp/js/assets.js）。
/// 空なら読みに行かない（手元で試すときは assets/ にそろっているため）。
export const REMOTE_ASSET_BASE = LOCAL ? ''
  : 'https://raw.githubusercontent.com/flame-wave/shirakawago-voicebot/main/assets/';

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
/// 手元か公開先かで、上の LOCAL を見て自動で切り替わる。
export const LOG_ENDPOINT = LOCAL ? '../server/api/log.php' : '../api/log.php';

/// 溜まった記録をまとめて送る間隔。
/// 据え置き端末は電源を入れっぱなしにするため、定期的に送る。
export const LOG_FLUSH_INTERVAL_MS = 5 * 60 * 1000;

/// 据え置き端末で、この時間だれも触らなければ待ち受け（js/attract.js）に戻す。
///
/// 据え置きは次々と別の方が使うので、一度の同意で済ませるわけにいかない。
/// 無操作が続いたら「次の方が来た」とみなして、次に触れられたときに確かめ直す。
/// 短すぎると案内を読んでいる途中で消えてしまうため、余裕を持たせる。
export const CONSENT_IDLE_MS = 5 * 60 * 1000;

/// 据え置き端末の待ち受けで、よくある質問の受け答えを1つ見せる長さ。
export const ATTRACT_STEP_MS = 10 * 1000;

/// 待ち受けで言語を切り替える間隔。英語から始めて、日本語・中国語・韓国語・
/// スペイン語・フランス語の順に回る（通りがかった方の目を引くため）。
/// ATTRACT_STEP_MS の倍数にする（1つの言語で、受け答えを3つ見せてから次へ）。
export const ATTRACT_LANG_MS = 30 * 1000;

/// 据え置き端末の待ち受けを始める言語。
/// 開き直したときに日本語へ戻ると、海外からの方が素通りしてしまうため英語にする。
export const KIOSK_FIRST_LANG = 'en';

/// 管理画面で反映したコミットを教えてくれる所（server/api/version.php）。
/// 反映されたかどうかを、小さな問い合わせで確かめられる。
/// 空なら使わない（下の KIOSK_REFRESH_MS ごとに質問回答集を取りに行くだけになる）。
export const VERSION_URL = LOCAL ? '' : '../api/version.php';

/// 据え置き端末が、反映されたかを確かめる間隔（version.php への小さな問い合わせ）。
/// 反映されていれば、だれも使っていないときに新しい質問回答集に入れ替える。
export const VERSION_CHECK_MS = 60 * 1000;

/// 据え置き端末が、だれも使っていない間に質問回答集そのものを取りに行く間隔。
/// version.php が動いていないときや、管理画面を通さずに直したときの受け皿。
/// 変わっていなければ配信元から「変わっていない」とだけ返るので、通信はほとんど増えない。
export const KIOSK_REFRESH_MS = 5 * 60 * 1000;

/// 「だれも使っていない」とみなすまでの時間。
/// これより長く触られていなければ、使っている途中でも新しい内容に入れ替える
/// （同意画面が出ているときは、すぐ入れ替える）。
export const UPDATE_IDLE_MS = 60 * 1000;

/// 据え置き端末が、自分で画面を開き直す時刻（端末の時計で 0〜23 時。1日に何回でも）。
/// 案内アプリそのもの（js・css）を新しくしたときに、それを読み込ませるため。
///   3時 … 閉館中。だれも使っていないので、確実に開き直せる
///   12時 … 昼のうちに上げ直した分を、その日のうちに出すため。
///          使っている方がいる間は待ち、待ち受けになってから開き直す
///          （12時台ずっと使われていたら、その回は見送って夜の3時に開き直す）
export const DAILY_RELOAD_HOURS = [3, 12];

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
/// 手元か公開先かで、上の LOCAL を見て自動で切り替わる。
/// APIキーはこちらには書かない。中継サーバの中だけに置く。
export const AI_ENDPOINT = LOCAL ? '../server/api/ask.php' : '../api/ask.php';

/// AIの返事をこの時間まで待つ。過ぎたら職員案内に切り替える。
/// 観光客を待たせないことを、答えを得ることより優先する。
/// 中継サーバは、案内で答えられなかった短い話しかけに、雑談としてもう一度AIに聞く
/// （ask.php の small_talk）。2回分でも間に合うよう、少し長めにしてある。
export const AI_TIMEOUT_MS = 12000;

/// 無音がこの時間続いたら聞き取りを終える（実機の pauseFor 相当）
export const SILENCE_TIMEOUT_MS = 10000;

/// 1回の聞き取りの上限（実機の listenFor 相当）
export const LISTEN_TIMEOUT_MS = 60000;
