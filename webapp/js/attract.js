// 据え置き端末の待ち受け（だれも使っていない間の画面）。
//
// 以前は、だれも使っていない間ずっと同意画面を出していた。
// しかし説明の文章が並んだ画面では、通りがかった方に「何ができるか」が伝わらない。
// そこで待っている間は、ふだんの案内画面のまま、よくある質問の受け答えを
// 実演として流し（音は出さない）、言語も順に切り替える。
// 画面のどこかに触れたら実演を止め、同意画面を出す（app.js の startAttract）。
//
// 触れた指で、下にあるボタン（話す・言語など）が押されないよう、
// 待ち受けの間は画面全体を透明な覆いで受け止める。

import { uiString } from './app-language.js';

export class AttractMode {
  /// root は画面全体を覆う透明な要素（index.html の #attract）
  constructor(root) {
    this.root = root;
    this.running = false;
    /// 触れられたときに呼ばれる
    this.onTouch = null;
    /// 実演の1こま（n は0から数える）。表示は app.js が受け持つ
    this.onStep = null;
    this.stepMs = 10000;
    /// 呼びかけの帯を重ねる要素（話すボタン）。無ければ画面の下の方に出す
    this.anchor = null;
    this._timer = null;
    this._step = 0;
    window.addEventListener('resize', () => this.running && this._place());

    root.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!this.running || this._ending) return;
      // 指の下に言語のボタンがあれば、その言語で同意画面を出す
      const under = document.elementsFromPoint(e.clientX, e.clientY)
        .map((el) => el.closest?.('.lang-button')).find(Boolean);
      this._end(under?.dataset.lang || '');
    });
  }

  /// 触れられたあとの片付け。
  ///
  /// 指を置いた瞬間に覆いを消すと、指を離したときの「クリック」が、
  /// そのとき指の下にある部品（すぐに出てくる同意画面の「記録せずに使う」など）に届き、
  /// 同意画面が勝手に閉じてしまった（タッチの画面でだけ起きる）。
  /// そこで、クリックが覆いに届くまで覆いを残し、それから同意画面を出す。
  _end(lang) {
    this._ending = true;
    this._halt();
    const finish = () => {
      if (!this._ending) return;
      this._ending = false;
      clearTimeout(wait);
      this.root.removeEventListener('click', swallow, true);
      this.root.hidden = true;
      if (this.onTouch) this.onTouch(lang);
    };
    const swallow = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      setTimeout(finish, 60);
    };
    this.root.addEventListener('click', swallow, true);
    // 長押しなどでクリックが来ないときも、少し待てば出す
    const wait = setTimeout(finish, 700);
  }

  /// 実演を止める（覆いは残す）
  _halt() {
    this.running = false;
    clearTimeout(this._timer);
    this._timer = null;
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.root.hidden = false;
    this._step = 0;
    this._place();
    this._tick();
  }

  stop() {
    this._ending = false;
    this._halt();
    this.root.hidden = true;
  }

  /// 「画面にタッチしてはじめてください」をその言語で出す。
  /// 英語以外のときは、英語も小さく添える（読めない言語のときでも分かるように）。
  setLanguage(lang) {
    this.root.querySelector('.attract-text').textContent = uiString('touchToStart', lang);
    const sub = this.root.querySelector('.attract-sub');
    sub.textContent = lang === 'en' ? '' : uiString('touchToStart', 'en');
    sub.hidden = lang === 'en';
  }

  /// 呼びかけの帯を、話すボタンの上にちょうど重ねる。
  /// 会話領域に重ねると、長い答えの文章が隠れてしまう。
  /// 待ち受けの間は話すボタンを押せない（触れると同意画面になる）ので、そこに出すのが自然。
  _place() {
    const call = this.root.querySelector('.attract-call');
    const r = this.anchor?.getBoundingClientRect();
    if (!r || !r.height) {
      call.style.top = '';
      return;
    }
    call.style.top = `${Math.round(r.top + r.height / 2 - call.offsetHeight / 2)}px`;
  }

  _tick() {
    if (!this.running) return;
    this._place();   // 言語が変わると帯の大きさも変わるので、置き直す
    if (this.onStep) this.onStep(this._step);
    this._step += 1;
    this._timer = setTimeout(() => this._tick(), this.stepMs);
  }
}
