// あいさつなどの短い会話（「こんにちは」「ありがとう」「お名前は？」）。
//
// 質問回答集は案内のための表なので、あいさつは入れていない。
// 返事はキャラクターごとに持っている（質問回答集の「会話」シート →
// faq.json の characters[].talk）。どんな言い方をどの種類とみなすかは、ここで決める。
//
// 【質問の邪魔をしない】
// 質問回答集で見つからなかったときだけ使う。さらに、言い方の語が入っていても
// 文が長いとき（「こんにちは、猫は入れますか」など）は会話とみなさず、AIに回す。
// あいさつに続けて本当の質問をしている場合に、あいさつだけ返してしまわないため。

import { FaqService } from './faq-service.js';
import { nameIn } from './character.js';

/// 種類ごとの言い方と、言い方の語以外に許す文字数。
/// 言い方は FaqService.normalize を通した形で比べる（空白・記号を除き、カタカナはひらがな）。
const KINDS = {
  greeting: {
    slack: 6,
    words: ['こんにちは', 'こんにちわ', 'こんばんは', 'こんばんわ', 'おはよう', 'はじめまして',
            'やあ', 'どうも', 'hello', 'hi', 'hey', 'hithere', 'heythere', 'hieveryone',
            'goodmorning', 'goodafternoon',
            'goodevening', '你好', '您好', '大家好', '안녕하세요', '안녕', 'hola',
            'buenosdías', 'buenosdias', 'buenastardes', 'buenasnoches', 'bonjour',
            'bonsoir', 'salut'],
  },
  thanks: {
    slack: 8,
    words: ['ありがとう', 'さんきゅう', 'thankyou', 'thanks', '谢谢', '感谢', '감사합니다',
            '고마워요', '고맙습니다', 'gracias', 'merci'],
  },
  name: {
    slack: 10,
    // 「名前」「誰」だけだと「この料理の名前は」「誰でも入れますか」にも当たるので、
    // 相手に向けた言い方だけにする。頭に ^ がある語は、文の頭にあるときだけ当てる。
    words: ['あなたの名前', 'あなたのなまえ', '君の名前', 'きみの名前', 'お名前', 'おなまえ',
            'あなたは誰', 'あなたはだれ', '君は誰', 'きみはだれ', '^名前は', '^なまえは',
            '^誰ですか', '^だれですか', '^どなたですか', 'whoareyou', 'yourname', 'whatisyourname',
            '你叫什么', '你是谁', '이름', '누구', 'cómotellamas', 'comotellamas', 'quiéneres',
            'quieneres', 'tunombre', "comment tu t'appelles", "comment t'appelles-tu",
            'comment vous appelez-vous', 'qui es-tu', 'qui êtes-vous', 'quiestu', 'quietesvous'],
  },
  howareyou: {
    slack: 6,
    words: ['げんき', '元気', 'ちょうしどう', 'howareyou', 'howareyoudoing', '你好吗',
            '잘지내', '잘 지내', 'cómoestás', 'comoestas', 'quétal', 'quetal',
            'commentçava', 'commentcava', 'çava', 'cava'],
  },
  bye: {
    slack: 6,
    words: ['さようなら', 'さよなら', 'ばいばい', 'またね', 'じゃあね', 'goodbye', 'bye', 'byebye',
            'seeyou', '再见', '拜拜', '안녕히계세요', '안녕히가세요', '잘가요', 'adiós',
            'adios', 'hastaluego', 'aurevoir', 'àbientôt', 'abientot'],
  },
};

// 言い方の語を正規化しておく（比べる側と同じ形にする）
const NORMALIZED = Object.fromEntries(Object.entries(KINDS).map(([kind, def]) => [
  kind, {
    slack: def.slack,
    words: def.words.map((w) => ({
      atStart: w.startsWith('^'),
      text: FaqService.normalize(w.replace(/^\^/, '')),
    })),
  },
]));

/// これが入っていたら会話ではなく質問（「ありがとうの言い方」「こんにちはの意味」など）
const QUESTION_WORDS = ['言い方', 'いいかた', '意味', 'いみ', 'とは', 'どこ', 'いくら', '何時',
  'ありますか', '売って', '買え', '行き方', '営業',
  'where', 'when', 'howmuch', 'howto', 'howdoisay', 'meaning', 'whatdoes', 'isthere']
  .map((w) => FaqService.normalize(w));

/// 自分で足した種類（「好きな食べ物」など）の、言い方の語以外に許す文字数。
/// 「かわいい」のような語は「かわいいお土産ある」にもまぎれるので、決まった5つより狭くする。
const CUSTOM_SLACK = 4;

/// 1つの言い方が、この文に当たるか。当たれば、当たった語の長さを返す（当たらなければ 0）。
function hit(t, word, atStart, slack) {
  if (!word || !t.includes(word)) return 0;
  if (atStart && !t.startsWith(word)) return 0;
  // 言い方の語のほかに、長い文が付いていたら会話ではない（本当の質問かもしれない）
  if (t.length - word.length > slack) return 0;
  // 「hi」「bye」のような短い英字の語は、ほかの語の中にもまぎれる
  // （「shiro」の中の hi など）。文の頭にあって、ほぼそれだけのときに限る。
  // 日本語の「名前」「元気」は、まぎれる心配が少ないので、この決まりは当てない。
  if (/^[a-z]{1,3}$/.test(word) && !(t.startsWith(word) && t.length - word.length <= 2)) return 0;
  return word.length;
}

/// 聞き取った文が、どの種類の会話か。会話でなければ null。
///
/// character … いま立っているキャラクター。管理画面で足した種類（「好きな食べ物」など）と
///             その言い方は、キャラクターの会話（character.talk）に入っている。
/// いくつかの種類に当たるときは、文の中で長く当たった方を選ぶ。
export function talkKind(text, character = null) {
  const t = FaqService.normalize(text ?? '');
  if (t === '') return null;
  if (QUESTION_WORDS.some((w) => t.includes(w))) return null;
  let best = null;
  let bestLen = 0;
  const consider = (kind, len) => {
    if (len > bestLen) {
      best = kind;
      bestLen = len;
    }
  };
  for (const [kind, def] of Object.entries(NORMALIZED)) {
    for (const { atStart, text: word } of def.words) consider(kind, hit(t, word, atStart, def.slack));
  }
  // 管理画面で足した言い方（決まった5つの種類に足した言い方も含む）
  for (const [kind, entry] of Object.entries(character?.talk ?? {})) {
    for (const phrase of entry.phrases ?? []) {
      const word = FaqService.normalize(phrase);
      // 長い言い方（英語など）は、前後に付く語も長くなりやすいので、少し広めに許す
      const slack = NORMALIZED[kind]?.slack ?? Math.max(CUSTOM_SLACK, Math.floor(word.length / 2));
      consider(kind, hit(t, word, false, slack));
    }
  }
  return best;
}

/// 種類ごとに、前に使った返事（続けて同じ返事にならないように）
const lastUsed = {};

/// そのキャラクターの返事（その言語）。無ければ null。
///
/// 返事が何通りかあれば、その中から選ぶ（続けて同じものは避ける）。
/// その言語の返事が無ければ「共通」の返事（fallback）から、それも無ければ日本語で答える。
/// {名前} は、そのキャラクターのその言語での名前に置き換える。
export function talkReply(character, kind, lang) {
  const entry = character?.talk?.[kind];
  if (!entry) return null;
  const pick = (list) => (list ?? []).map((r) => r[lang]).filter(Boolean);
  let options = pick(entry.replies);
  if (options.length === 0) options = pick(entry.fallback);
  if (options.length === 0) options = (entry.replies ?? []).map((r) => r.ja).filter(Boolean);
  if (options.length === 0) return null;

  const key = `${character.id}:${kind}:${lang}`;
  let choices = options.filter((o) => o !== lastUsed[key]);
  if (choices.length === 0) choices = options;
  const text = choices[Math.floor(Math.random() * choices.length)];
  lastUsed[key] = text;
  return text.replaceAll('{名前}', nameIn(character, lang));
}
