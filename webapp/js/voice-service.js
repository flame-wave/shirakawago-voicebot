// 読み上げの部品（lib/voice_service.dart の移植）。
//
// 「専用の音声ファイルがあればそれを使い、無ければブラウザの音声で読む」
// という判断をここに閉じ込める。
// 職員がFAQを追加しても、音声ファイルが無いまま読み上げられるようにするための仕組み。

import { ASSET_BASE, PREFERRED_VOICES, AVOID_VOICES, VOICE_RATE, VOICE_PITCH } from './config.js';
import { TTS_LANGUAGE } from './app-language.js';

/// 職員が選んだ声を覚えておく場所（言語ごと）
const VOICE_KEY = 'shirakawa_voice';

/// 用意した音声のうち、どれを使うかを覚えておく場所
const SET_KEY = 'shirakawa_voice_set';

/// 「用意した音声を使わず、ブラウザの声で読む」を表す印
export const TTS_ONLY = '__tts__';

/// どの方法で喋ったか
export const VoiceMode = {
  recorded: 'recorded', // 用意された音声ファイル
  synthesized: 'synthesized', // ブラウザの音声合成
  failed: 'failed', // どちらも使えなかった
};

export class VoiceService {
  constructor() {
    this._audio = new Audio();
    this._sets = []; // 用意した音声の種類（faq.json から渡される）
    this._settings = {}; // 言語ごとの読み上げの設定（faq.json から渡される）
    this._readings = []; // 読み間違いの直し（faq.json から渡される）
    this._lang = 'ja';
    this._voices = [];
    /// 読み上げが終わったときに呼ばれる（表情を待機に戻すために使う）
    this.onComplete = null;

    this._audio.addEventListener('ended', () => this._done());
    this._audio.addEventListener('error', () => this._done());
  }

  _done() {
    if (this.onComplete) this.onComplete();
  }

  get available() {
    return 'speechSynthesis' in window;
  }

  /// 用意した音声の一覧を受け取る
  setSets(sets) {
    this._sets = Array.isArray(sets) ? sets : [];
  }

  /// 言語ごとの読み上げの設定を受け取る（管理画面で決めたもの）。
  ///
  /// 端末に入っている声は端末ごとに違うので、ここで決められるのは
  /// 「どれを優先するか」まで。実際にどれを使うかは _voiceFor が、
  /// その端末に入っている声と突き合わせて決める。
  setSettings(settings) {
    this._settings = (settings && typeof settings === 'object') ? settings : {};
  }

  /// 読み間違いの直しを受け取る（管理画面の「読み方」）。
  ///
  /// 合成音声は「荻町」を「はぎまち」、「朴葉味噌」を「ぼくようみそ」のように
  /// 読み間違える。地名や料理名は観光案内でいちばん大事な語なので、
  /// 読み上げに回す直前だけカタカナに差し替える。
  /// 画面に出る文字は差し替えない（漢字のままの方が読みやすい）。
  setReadings(readings) {
    const list = Array.isArray(readings) ? readings : [];
    // 長い語から先に直す。「八幡神社」を直してから「白川八幡神社」を直すと、
    // 前半だけ差し替わって「しらかわハチマンジンジャ」のように半端になる。
    this._readings = list
      .filter((r) => r && r.text && r.reading)
      .slice()
      .sort((a, b) => b.text.length - a.text.length);
  }

  get readings() {
    return this._readings;
  }

  /// 読み上げる文章に、読み方の直しを当てる（日本語のときだけ）。
  applyReadings(text, lang = this._lang) {
    if (lang !== 'ja' || !text) return text;
    let out = String(text);
    for (const r of this._readings) out = out.split(r.text).join(r.reading);
    return out;
  }

  /// その言語で優先する声の並び。設定が無ければ config.js の既定を使う。
  _preferred(lang) {
    const fromData = this._settings[lang]?.voices;
    if (Array.isArray(fromData) && fromData.length > 0) return fromData;
    return PREFERRED_VOICES[lang] ?? [];
  }

  /// 読み上げの速さ・高さ。設定が無ければ config.js の既定を使う。
  _tone(lang) {
    const row = this._settings[lang] ?? {};
    return {
      rate: typeof row.rate === 'number' ? row.rate : VOICE_RATE,
      pitch: typeof row.pitch === 'number' ? row.pitch : VOICE_PITCH,
    };
  }

  get sets() {
    return this._sets;
  }

  /// いま使う音声の置き場所。'' は assets/audio 直下。
  get currentSet() {
    try {
      const saved = localStorage.getItem(SET_KEY);
      if (saved !== null) return saved;
    } catch (_) {
      // 読めないときは既定に従う
    }
    if (this._sets.length === 0) return '';
    const marked = this._sets.find((v) => v.default);
    return (marked ?? this._sets[0]).id;
  }

  /// 使う音声を選ぶ。TTS_ONLY を渡すと、用意した音声を使わずブラウザの声で読む。
  chooseSet(id) {
    try {
      localStorage.setItem(SET_KEY, id);
    } catch (_) {
      // 保存できなくても、その場の選択は効く
    }
  }

  async init() {
    if (!this.available) {
      console.warn('このブラウザは音声合成に対応していません');
      return;
    }
    await this._loadVoices();
    await this.setLanguage('ja');
  }

  /// 音声一覧は非同期に揃うブラウザがあるため、イベントを待つ
  _loadVoices() {
    return new Promise((resolve) => {
      const read = () => {
        this._voices = window.speechSynthesis.getVoices();
        return this._voices.length > 0;
      };
      if (read()) return resolve();
      const timer = setTimeout(() => resolve(), 1500); // 揃わなくても先に進む
      window.speechSynthesis.addEventListener(
        'voiceschanged',
        () => {
          read();
          clearTimeout(timer);
          resolve();
        },
        { once: true },
      );
    });
  }

  /// 読み上げの言語を切り替える。
  /// ブラウザにその言語の音声が入っていない場合もあるため、結果を返す。
  async setLanguage(lang) {
    this._lang = lang;
    if (!this.available) return false;
    if (this._voices.length === 0) this._voices = window.speechSynthesis.getVoices();
    const voice = this._voiceFor(lang);
    if (!voice) {
      console.warn(`ブラウザに ${TTS_LANGUAGE[lang]} の音声がありません`);
    } else {
      console.info(`読み上げの声: ${voice.name}（${voice.lang}）`);
    }
    return voice != null;
  }

  /// その言語で使える声を返す（職員用の画面で選ばせるため）
  voicesFor(lang) {
    const prefix = TTS_LANGUAGE[lang].toLowerCase().split('-')[0];
    return this._voices.filter((v) =>
      v.lang.toLowerCase().replace('_', '-').startsWith(prefix),
    );
  }

  /// 職員が選んだ声を覚える。'' を渡すと自動選択に戻す。
  chooseVoice(lang, name) {
    const saved = this._savedVoices();
    if (name) saved[lang] = name;
    else delete saved[lang];
    try {
      localStorage.setItem(VOICE_KEY, JSON.stringify(saved));
    } catch (_) {
      // 保存できなくても、その場の選択は効く
    }
  }

  _savedVoices() {
    try {
      return JSON.parse(localStorage.getItem(VOICE_KEY) || '{}');
    } catch (_) {
      return {};
    }
  }

  /// 使う声を決める。
  ///
  /// 1. 職員が選んだ声
  /// 2. 設定した優先順位（Androidアプリと同じ「Google 日本語」など）
  /// 3. その言語で使える声のどれか
  _voiceFor(lang) {
    const candidates = this.voicesFor(lang);
    if (candidates.length === 0) return null;

    const chosen = this._savedVoices()[lang];
    if (chosen) {
      const found = candidates.find((v) => v.name === chosen || v.voiceURI === chosen);
      if (found) return found;
    }

    for (const wanted of this._preferred(lang)) {
      const needle = wanted.toLowerCase();
      const found = candidates.find((v) => v.name.toLowerCase().includes(needle));
      if (found) return found;
    }

    // 同じ言語でも国違いがあるため、完全一致を先に探す。
    // また、名前から男性と分かる声は最後に回す（キャラクターに合わないため）。
    const target = TTS_LANGUAGE[lang].toLowerCase();
    const sameCountry = (v) => v.lang.toLowerCase().replace('_', '-') === target;
    const looksFemale = (v) => {
      const name = v.name.toLowerCase();
      return !AVOID_VOICES.some((n) => name.includes(n));
    };
    return (
      candidates.find((v) => sameCountry(v) && looksFemale(v)) ??
      candidates.find(looksFemale) ??
      candidates.find(sameCountry) ??
      candidates[0]
    );
  }

  /// いま使う声の名前（職員用の画面に出す）
  currentVoiceName(lang) {
    return this._voiceFor(lang)?.name ?? '';
  }

  /// 回答を読み上げる。使った方法を返す。
  async speak(faq, lang, localized) {
    await this.stop();

    // 1. その言語の専用音声ファイルを試す
    if (localized.audio && this.currentSet !== TTS_ONLY) {
      const played = await this._playFile(localized.audio);
      if (played) return VoiceMode.recorded;
      // ファイルが無い場合はここに来る（職員が追加したFAQなど）
      console.info(`音声ファイル ${localized.audio} を再生できないため、ブラウザ音声に切り替えます`);
    }

    // 2. ブラウザの音声合成で読む
    return this.speakText(localized.text);
  }

  /// 選ばれている音声セットの中から再生する。
  /// そのセットに無ければ、直下（既定の音声）も試す。
  async _playFile(name) {
    const folder = this.currentSet;
    if (folder && folder !== TTS_ONLY) {
      if (await this._playPath(`${ASSET_BASE}audio/${folder}/${name}`)) return true;
    }
    return this._playPath(`${ASSET_BASE}audio/${name}`);
  }

  _playPath(url) {
    return new Promise((resolve) => {
      this._audio.src = url;
      const onError = () => resolve(false);
      this._audio.addEventListener('error', onError, { once: true });
      this._audio
        .play()
        .then(() => {
          this._audio.removeEventListener('error', onError);
          resolve(true);
        })
        .catch(() => resolve(false));
    });
  }

  /// 指定した言語で試しに読み上げる（職員用の画面の「試しに読む」）。
  ///
  /// 読む言語と声の言語が食い違うと、多くのブラウザは何も鳴らさずに終わる。
  /// そのため、いま案内に使っている言語とは関係なく、その言語へ切り替えて読む。
  async speakSample(lang, text) {
    await this.stop();
    const previous = this._lang;
    this._lang = lang;
    const mode = await this.speakText(text);
    this._lang = previous;
    return mode;
  }

  /// 文章をそのままブラウザ音声で読み上げる（FAQに紐づかない案内文など）
  speakText(text) {
    if (!text || !this.available) {
      this._done();
      return Promise.resolve(VoiceMode.failed);
    }
    try {
      // 読み間違いを直してから渡す（画面の文字はそのまま）
      const u = new SpeechSynthesisUtterance(this.applyReadings(text));
      u.lang = TTS_LANGUAGE[this._lang];
      const voice = this._voiceFor(this._lang);
      if (voice) u.voice = voice;
      // 速さ・高さは言語ごとに決められる（管理画面の「読み上げ」）
      const tone = this._tone(this._lang);
      u.rate = tone.rate;   // 案内なので少しゆっくり
      u.pitch = tone.pitch;
      u.volume = 1.0;
      u.onend = () => this._done();
      u.onerror = () => this._done(); // 表情が固まらないよう必ず戻す
      window.speechSynthesis.speak(u);
      return Promise.resolve(VoiceMode.synthesized);
    } catch (e) {
      console.warn('読み上げに失敗:', e);
      this._done();
      return Promise.resolve(VoiceMode.failed);
    }
  }

  async stop() {
    try {
      this._audio.pause();
      this._audio.currentTime = 0;
    } catch (_) {}
    try {
      if (this.available) window.speechSynthesis.cancel();
    } catch (_) {}
  }
}
