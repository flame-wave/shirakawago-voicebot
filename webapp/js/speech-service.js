// 音声認識の部品（実機の speech_to_text に相当）。
//
// ブラウザ標準の Web Speech API を使う。Chrome / Edge / Safari が対象で、
// 対応していないブラウザでは available が false になり、
// 画面側がキーボード入力に切り替える。
//
// 第2段階で whisper.cpp（WebAssembly）に差し替えるときは、この部品だけを直す。

import { SPEECH_LOCALE } from './app-language.js';
import { SILENCE_TIMEOUT_MS, LISTEN_TIMEOUT_MS } from './config.js';

const Recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;

export class SpeechService {
  constructor() {
    this._recognition = null;
    this._silenceTimer = null;
    this._limitTimer = null;
    this._finalText = '';
    this._listening = false;
    this._discard = false; // 打ち切った聞き取りの結果を捨てるか

    /// 聞き取り途中の文字（画面にそのまま出す）
    this.onPartial = null;
    /// 聞き取りが確定したとき
    this.onResult = null;
    /// 認識が止まったとき（無音での自動終了を含む）
    this.onStop = null;
    /// 使えなかったとき（'denied' / 'error'）
    this.onError = null;
  }

  get available() {
    return Recognition != null;
  }

  get listening() {
    return this._listening;
  }

  start(lang) {
    if (!this.available || this._listening) return;

    const rec = new Recognition();
    rec.lang = SPEECH_LOCALE[lang];
    // もう一度押すまで待つ方式なので、区切られても続けて聞く
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    let partial = '';

    rec.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          this._finalText += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }
      partial = (this._finalText + interim).trim();
      if (this.onPartial) this.onPartial(partial);
      this._restartSilenceTimer();
      // 文として確定したらそこで打ち切る（実機の finalResult と同じ扱い）
      if (this._finalText.trim() !== '') this.stop();
    };

    rec.onerror = (event) => {
      console.warn('音声認識エラー:', event.error);
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      const kind =
        event.error === 'not-allowed' || event.error === 'service-not-allowed'
          ? 'denied'
          : 'error';
      if (this.onError) this.onError(kind, event.error);
    };

    rec.onend = () => {
      this._clearTimers();
      this._listening = false;
      this._recognition = null;
      const text = this._finalText.trim() || partial;
      const discard = this._discard;
      this._finalText = '';
      this._discard = false;
      if (this.onStop) this.onStop();
      // 言語切り替えなどで打ち切った場合は、聞き取れていた分も捨てる
      if (!discard && this.onResult) this.onResult(text);
    };

    this._recognition = rec;
    this._finalText = '';
    this._listening = true;

    try {
      rec.start();
    } catch (e) {
      console.warn('音声認識を開始できません:', e);
      this._listening = false;
      this._recognition = null;
      if (this.onError) this.onError('error', String(e));
      return;
    }

    this._restartSilenceTimer();
    this._limitTimer = setTimeout(() => this.stop(), LISTEN_TIMEOUT_MS);
  }

  /// discard = true なら、そこまで聞き取れていた分も使わずに捨てる
  stop(discard = false) {
    this._discard = discard;
    this._clearTimers();
    if (!this._recognition) return;
    try {
      this._recognition.stop(); // onend で後始末する
    } catch (_) {
      this._listening = false;
      this._recognition = null;
      if (this.onStop) this.onStop();
    }
  }

  /// 無音が続いたときは自分から終える。
  /// ブラウザ任せだと切れる条件がまちまちで、待たされることがあるため。
  _restartSilenceTimer() {
    clearTimeout(this._silenceTimer);
    this._silenceTimer = setTimeout(() => this.stop(), SILENCE_TIMEOUT_MS);
  }

  _clearTimers() {
    clearTimeout(this._silenceTimer);
    clearTimeout(this._limitTimer);
    this._silenceTimer = null;
    this._limitTimer = null;
  }
}
