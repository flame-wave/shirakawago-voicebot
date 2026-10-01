// 利用前の同意画面。
//
// 質問した内容を記録して外部へ送るため、使い始める前にそのことを伝える。
//
// 【「記録せずに使う」を用意している理由】
// 同意しないと使えない作りにすると、断った人は案内そのものを受けられない。
// 観光案内は本来だれでも受けられるべきもので、記録はこちらの都合である。
// 断っても案内はすべて使えるようにし、記録だけを止める。
//
// 【据え置き端末と観光客の端末で出し方が違う】
//   観光客の端末 … 初回だけ出す。一度決めればその端末で覚える。
//   据え置き端末 … しばらく誰も触っていなければまた出す。
//                  次の方にとっては「初めて」なので、その人に確かめる必要がある。

import { LANGUAGES, LABEL } from './app-language.js';
import { CONSENT } from './consent-text.js';

const KEY = 'shirakawa_consent';

/// 同意の状態。'agreed'（記録してよい）／'declined'（記録しない）／''（未回答）
export function consentState() {
  try {
    return localStorage.getItem(KEY) || '';
  } catch (_) {
    // 保存できない設定のときは、毎回たずねる（黙って記録しない）
    return '';
  }
}

/// 記録してよいか。未回答のうちは記録しない。
export function mayRecord() {
  return consentState() === 'agreed';
}

function remember(value) {
  try {
    localStorage.setItem(KEY, value);
  } catch (_) {
    // 覚えられなくても、その場の選択は効く
  }
}

const escape = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);

const list = (items) =>
  '<ul>' + items.map((t) => `<li>${escape(t)}</li>`).join('') + '</ul>';

export class ConsentScreen {
  constructor(root) {
    this.root = root;
    this.lang = 'ja';
    this.onDone = null;
    /// 言語を選び直したときに呼ばれる（本編の表示も合わせるため）
    this.onLanguage = null;
  }

  get open() {
    return !this.root.hidden;
  }

  /// たずねる。答えが出たら onDone(agreed) を呼ぶ。
  ask(lang, onDone) {
    this.lang = lang;
    this.onDone = onDone;
    this.root.hidden = false;
    this.render();
  }

  close() {
    this.root.hidden = true;
    this.root.innerHTML = '';
  }

  render() {
    const t = CONSENT[this.lang] ?? CONSENT.ja;

    // 読める言語に切り替えられないと、そもそも同意の意味がない
    const langs = LANGUAGES.map((code) =>
      `<button class="consent-lang${code === this.lang ? ' on' : ''}"`
      + ` type="button" data-lang="${code}">${escape(LABEL[code])}</button>`).join('');

    this.root.innerHTML = `
      <div class="consent-box" role="dialog" aria-modal="true">
        <div class="consent-langs">${langs}</div>
        <div class="consent-body">
          <h2>${escape(t.title)}</h2>
          <p class="consent-provider">${escape(t.provider)}</p>
          <p>${escape(t.purpose)}</p>

          <h3>${escape(t.recordTitle)}</h3>
          ${list(t.record)}

          <h3>${escape(t.keepTitle)}</h3>
          ${list(t.keep)}

          <h3>${escape(t.noteTitle)}</h3>
          ${list(t.note)}

          <p class="consent-closing">${escape(t.closing)}</p>
        </div>
        <div class="consent-actions">
          <button class="consent-agree" type="button">${escape(t.agree)}</button>
          <button class="consent-decline" type="button">${escape(t.decline)}</button>
          <p class="consent-hint">${escape(t.declineHint)}</p>
        </div>
      </div>`;

    for (const button of this.root.querySelectorAll('.consent-lang')) {
      button.onclick = () => {
        this.lang = button.dataset.lang;
        if (this.onLanguage) this.onLanguage(this.lang);
        this.render();
      };
    }

    this.root.querySelector('.consent-agree').onclick = () => this._answer('agreed');
    this.root.querySelector('.consent-decline').onclick = () => this._answer('declined');

    // 長い文章なので、言語を変えたときは先頭から読めるようにする
    this.root.querySelector('.consent-body').scrollTop = 0;
  }

  _answer(value) {
    remember(value);
    this.close();
    if (this.onDone) this.onDone(value === 'agreed');
  }
}
