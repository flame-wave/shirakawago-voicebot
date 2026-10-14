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
//   観光客の端末 … 開くたびに出す（同じ端末を連れの方が使うこともあるため）。
//   据え置き端末 … 開いたときと、しばらく誰も触っていなかったときに出す。
//                  次の方にとっては「初めて」なので、その人に確かめる必要がある。
//
// 【据え置き端末では、待っている間の「呼び込み」も兼ねる】
// 同意画面は、だれも使っていない間ずっと出ている。そこで上に大きく
// 「何ができるか」を出し、言語を順に切り替えて、通りがかった方の目を引く。
// だれかが画面に触れたら、切り替えは止める（読んでいる途中で変わらないように）。
//
// 【スマートフォンでは詰めて出す】
// 幅の狭い画面に全部を並べると、肝心の説明が1行ぶんしか見えなかった。
// スマートフォンでは（styles.css の max-width: 600px）
//   ・見出しはタイトルと一言だけ（呼び込みは要らない。自分でQRから開いた方なので）
//   ・言語は「🌐 日本語 ▾」の1つのボタンにまとめ、押すと一覧が開く
//   ・説明は3行の要約にし、全文は「詳しく見る」で開く（説明そのものは省かない）
//   ・画面全体を1枚で流し、同意のボタンは常に下に見えるようにする

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
    /// 上の見出しの横に出すキャラクターの絵（無ければ出さない）
    this.image = '';
    this._rotation = null;
    this._rotTimer = null;
    /// スマートフォンで、言語の一覧・説明の全文を開いているか
    this._langsOpen = false;
    this._more = false;
    // 画面に触れたら、言語の切り替えを止める
    root.addEventListener('pointerdown', () => this._stopRotation());
  }

  get open() {
    return !this.root.hidden;
  }

  /// たずねる。答えが出たら onDone(agreed) を呼ぶ。
  ask(lang, onDone) {
    this.lang = lang;
    this.onDone = onDone;
    this._langsOpen = false;
    this._more = false;
    this.root.hidden = false;
    this.render();
    this._schedule();
  }

  close() {
    this._stopRotation();
    this.root.hidden = true;
    this.root.innerHTML = '';
  }

  /// 待っている間、言語を順に切り替える（据え置き端末の呼び込み）。
  /// langs の順に、ms ごとに次の言語へ。画面に触れると止まり、次に出したときにまた始める。
  rotate(langs, ms) {
    this._rotation = langs.length > 1 && ms > 0 ? { langs, ms } : null;
    this._schedule();
  }

  _schedule() {
    clearTimeout(this._rotTimer);
    if (!this._rotation || !this.open) return;
    this._rotTimer = setTimeout(() => {
      const { langs } = this._rotation;
      this.lang = langs[(langs.indexOf(this.lang) + 1) % langs.length];
      if (this.onLanguage) this.onLanguage(this.lang);
      this.render();
      this._schedule();
    }, this._rotation.ms);
  }

  _stopRotation() {
    clearTimeout(this._rotTimer);
    this._rotTimer = null;
  }

  render() {
    const t = CONSENT[this.lang] ?? CONSENT.ja;

    // 読める言語に切り替えられないと、そもそも同意の意味がない
    const langs = LANGUAGES.map((code) =>
      `<button class="consent-lang${code === this.lang ? ' on' : ''}"`
      + ` type="button" data-lang="${code}">${escape(LABEL[code])}</button>`).join('');

    // 上の大きな見出し。何ができるかを、読まなくても分かるようにする。
    const examples = (t.examples ?? []).map((e) => `<li>${escape(e)}</li>`).join('');
    const hero = `
        <div class="consent-hero">
          <div class="consent-hero-text">
            <h2 class="consent-title">${escape(t.title)}</h2>
            <p class="consent-lead">${escape(t.lead ?? '')}</p>
            <ul class="consent-examples">${examples}</ul>
            <p class="consent-tags">🌐 ${escape(t.languages ?? '')}</p>
          </div>
          ${this.image ? `<img class="consent-hero-char" src="${escape(this.image)}" alt="">` : ''}
          <button class="consent-lang-toggle" type="button" aria-expanded="${this._langsOpen}"
            aria-label="Language">🌐 ${escape(LABEL[this.lang] ?? this.lang)} ▾</button>
        </div>`;

    // スマートフォンで本文の代わりに出す要約
    const marks = ['✅', '❌', 'ℹ️'];
    const summary = (t.summary ?? []).map((line, i) =>
      `<li><span class="consent-mark" aria-hidden="true">${marks[i] ?? '・'}</span>`
      + `<span>${escape(line)}</span></li>`).join('');

    this.root.innerHTML = `
      <div class="consent-box${this._more ? ' more' : ''}" role="dialog" aria-modal="true"
        aria-label="${escape(t.title)}">
        ${hero}
        <div class="consent-langs${this._langsOpen ? ' open' : ''}">${langs}</div>
        <div class="consent-summary">
          <ul>${summary}</ul>
          <p class="consent-provider">${escape(t.provider)}</p>
          <button class="consent-more" type="button" aria-expanded="${this._more}">
            ${this._more ? '▾' : '▸'} ${escape(this._more ? (t.less ?? '') : (t.more ?? ''))}</button>
        </div>
        <div class="consent-body">
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
          <p class="consent-start">${escape(t.start ?? '')}</p>
          <button class="consent-agree" type="button">${escape(t.agree)}</button>
          <button class="consent-decline" type="button">${escape(t.decline)}</button>
          <p class="consent-hint">${escape(t.declineHint)}</p>
        </div>
      </div>`;

    for (const button of this.root.querySelectorAll('.consent-lang')) {
      button.onclick = () => {
        this.lang = button.dataset.lang;
        this._langsOpen = false;   // 選んだら一覧は閉じる（スマートフォン）
        if (this.onLanguage) this.onLanguage(this.lang);
        this.render();
      };
    }
    this.root.querySelector('.consent-lang-toggle').onclick = () => {
      this._langsOpen = !this._langsOpen;
      this.render();
    };
    this.root.querySelector('.consent-more').onclick = () => {
      this._more = !this._more;
      this.render();
    };

    this.root.querySelector('.consent-agree').onclick = () => this._answer('agreed');
    this.root.querySelector('.consent-decline').onclick = () => this._answer('declined');

    // 長い文章なので、言語を変えたときは先頭から読めるようにする
    // （「詳しく見る」を開いたときは、読み進めた位置のままにする）
    if (!this._more) {
      this.root.querySelector('.consent-body').scrollTop = 0;
      this.root.querySelector('.consent-box').scrollTop = 0;
    }
  }

  _answer(value) {
    remember(value);
    this.close();
    if (this.onDone) this.onDone(value === 'agreed');
  }
}
