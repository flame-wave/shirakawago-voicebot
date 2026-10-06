// FAQ検索の部品（lib/faq_service.dart の移植。判定はデモ・変換ツールと同じ）。
//
// データの取得元は faq-repository.js が受け持ち、ここは検索だけを行う。
// 将来ここを埋め込みベクトル検索やクラウドLLMに差し替えられる。

// 言い換えで足した語を区切る印。語のまたがり一致を防ぐために挟む。
const SEP = String.fromCharCode(0);

// どの案内所でも使う回答の印
const COMMON = '共通';

function placeOf(faq) {
  return faq.place || COMMON;
}


/// 指定言語での回答。翻訳が無い場合は日本語を返し、isFallback を true にする。
function answerFor(faq, lang) {
  if (lang === 'ja') {
    return { text: faq.answer, audio: faq.audio, isFallback: false };
  }
  const tr = faq.translations[lang];
  if (tr && tr.answer) {
    return { text: tr.answer, audio: tr.audio, isFallback: false };
  }
  // 翻訳が未整備でも、日本語で案内できるだけした方がよい
  return { text: faq.answer, audio: faq.audio, isFallback: true };
}

/// 指定言語で検索対象にする質問例。
/// 日本語以外を選んでいても、日本語の言い方は残す
/// （地名など、言語をまたいで同じ語が使われることがあるため）
function questionsFor(faq, lang) {
  if (lang === 'ja') return faq.questions;
  const tr = faq.translations[lang];
  return [...(tr ? tr.questions : []), ...faq.questions];
}

function parseFaq(json) {
  const raw = json.translations ?? {};
  const translations = {};
  for (const [k, v] of Object.entries(raw)) {
    translations[k] = {
      questions: Array.isArray(v.questions) ? v.questions : [],
      answer: v.answer ?? '',
      audio: v.audio ?? '',
    };
  }
  return {
    id: json.id ?? '',
    questions: Array.isArray(json.questions) ? json.questions : [],
    answer: json.answer ?? '',
    audio: json.audio ?? '',
    photo: json.photo ?? '',
    chip: json.chip ?? '',
    place: json.place ?? '共通',
    link: json.link ?? '',
    category: json.category ?? 'other',
    translations,
  };
}

export class FaqService {
  constructor() {
    this._faqs = [];
    this._synonyms = {};
    this._places = [];
    this._voiceSets = [];
    this._characters = [];
    this._voiceSettings = {};
    this._readings = [];
  }

  /// 用意した音声の種類（話者ごと）。職員用の画面で選ばせるために使う。
  get voiceSets() {
    return this._voiceSets;
  }

  /// 画面に立つキャラクターの一覧。利用者が選べるようにするために使う。
  get characters() {
    return this._characters;
  }

  /// 言語ごとの読み上げの設定（優先する声・速さ・高さ）。
  /// 職員が管理画面で決め、どの端末でも同じになるようにする。
  get voiceSettings() {
    return this._voiceSettings;
  }

  /// 読み上げの読み間違いを直す表（漢字 → カタカナ）。
  get readings() {
    return this._readings;
  }

  /// 案内所の一覧（座標つき）。現在地の判定に使う。
  get places() {
    return this._places;
  }

  get count() {
    return this._faqs.length;
  }

  get all() {
    return this._faqs.slice();
  }

  answerFor(faq, lang) {
    return answerFor(faq, lang);
  }

  /// その言語での質問例。よくある質問の見出しに使う。
  questionsFor(faq, lang) {
    return questionsFor(faq, lang);
  }

  /// JSON文字列（またはパース済みオブジェクト）からFAQを読み込む。
  /// 失敗した場合は false を返し、既存のデータを保持する。
  loadFromJson(raw) {
    try {
      const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
      const list = (data.faqs ?? [])
        .map(parseFaq)
        .filter((f) => f.id !== '' && f.answer !== '');
      if (list.length === 0) return false;
      this._faqs = list;
      this._synonyms = data.synonyms ?? {};
      this._places = data.places ?? [];
      this._voiceSets = data.voice_sets ?? [];
      this._characters = data.characters ?? [];
      this._voiceSettings = data.voice ?? {};
      this._readings = data.readings ?? [];
      return true;
    } catch (_) {
      return false;
    }
  }

  /// 表記の揺れを吸収する。
  /// カタカナ→ひらがな（ゴミ／ごみ）、全角英数→半角、記号と空白の除去。
  /// 音声認識の結果はカタカナ・ひらがなが安定しないため、この正規化が効く。
  static normalize(s) {
    let out = '';
    for (const ch of s) {
      let c = ch.codePointAt(0);
      if (c >= 0xff10 && c <= 0xff5a) c -= 0xfee0; // 全角英数 → 半角
      if (c >= 0x30a1 && c <= 0x30f6) c -= 0x60; // カタカナ → ひらがな
      out += String.fromCodePoint(c);
    }
    return out.toLowerCase().replace(/[\s　、。，．,.!?！？・ー]/g, '');
  }

  /// 言い換え表を使って、入力文に代表語を足す。
  ///
  /// 「銀行ありますか」→ 末尾に atm を足す、というように、
  /// 観光客の言い方を、質問例に書かれている語へ橋渡しする。
  /// 元の文は消さずに足すだけなので、これまで当たっていたものは当たり続ける。
  _expand(text, lang) {
    const table = {
      ...(this._synonyms.ja ?? {}),
      ...(this._synonyms[lang] ?? {}),
    };

    const extra = [];
    for (const [rep, words] of Object.entries(table)) {
      const repN = FaqService.normalize(rep);
      if (!repN || text.includes(repN)) continue; // すでに入っているなら足さない
      for (const w of words) {
        const wn = FaqService.normalize(w);
        if (wn && text.includes(wn)) {
          extra.push(repN);
          break;
        }
      }
    }
    if (extra.length === 0) return text;
    // 足した語が元の文とつながって誤って一致しないよう、印で区切る
    return text + SEP + extra.join(SEP);
  }

  /// 語尾の活用に耐える照合。
  /// 「預ける」が「預けたい」に、「借りる」が「借りられる」に当たるようにする。
  static _contains(keyword, text) {
    if (text.includes(keyword)) return true;
    if (
      keyword.length >= 3 &&
      'るうくすつぬぶむいたてえ'.includes(keyword[keyword.length - 1]) &&
      text.includes(keyword.slice(0, -1))
    ) {
      return true;
    }
    return false;
  }

  /// 入力文に最も近いFAQを返す。見つからなければ null。
  ///
  /// 質問例のスペースは「かつ」を意味する。
  /// 例:「ごみ どこ」は、ごみ と どこ の両方が含まれるときだけ一致する。
  /// どれか1語でも当たれば加点する方式だと、「どこ」「場所」のような
  /// どの質問にも出る語だけで誤って一致してしまうため。
  /// place（いまいる案内所）を渡すと、その案内所向けの回答を先に探し、
  /// 無ければ「共通」の回答を探す。
  /// どこにいるか分からないときは共通の回答だけを見る。
  search(input, lang = 'ja', place = null) {
    const text = this._expand(FaqService.normalize(input ?? ''), lang);
    if (text === '') return null;

    if (place) {
      const here = this._faqs.filter((f) => placeOf(f) === place);
      const hit = this._searchWithin(here, text, lang);
      if (hit) return hit;
      return this._searchWithin(
        this._faqs.filter((f) => placeOf(f) === COMMON), text, lang,
      );
    }
    if (this._faqs.some((f) => 'place' in f)) {
      return this._searchWithin(
        this._faqs.filter((f) => placeOf(f) === COMMON), text, lang,
      );
    }
    return this._searchWithin(this._faqs, text, lang);
  }

  /// 渡されたFAQの中から、最も確度の高いものを選ぶ。
  _searchWithin(faqs, text, lang) {

    let best = null;
    let bestScore = 0;

    for (const faq of faqs) {
      for (const q of questionsFor(faq, lang)) {
        const keywords = q
          .split(/[\s　]+/)
          .map(FaqService.normalize)
          .filter((k) => k !== '');
        if (keywords.length === 0) continue;

        // すべての語が含まれることを条件にする
        if (!keywords.every((k) => FaqService._contains(k, text))) continue;

        // 具体的な語ほど、また語数が多いほど確度が高いとみなす
        let score = keywords.reduce((a, k) => a + k.length, 0);
        if (keywords.length > 1) score += 1;

        if (score > bestScore) {
          bestScore = score;
          best = faq;
        }
      }
    }

    // 1文字だけの一致は弱すぎるため、該当なしとして職員誘導へ
    if (bestScore < 2) return null;
    return best;
  }
}
