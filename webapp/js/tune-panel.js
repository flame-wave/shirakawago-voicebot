// キャラクターの見え方を、画面を見ながら合わせる道具（職員用）。
//
// これまでは Excel に数値を入れ → 書き出し → 読み込み直して確かめる、
// という手順だった。1つ直すたびに3手かかるので、合わせ込みが進まない。
//
// この画面はつまみを動かすと立ち絵と吹き出しがその場で動く。
// 決まったら数値を書き写して、管理画面の「キャラクター」に入れる。
//
// 【保存はしない】
// 案内アプリから質問回答集へ書き込む道は用意していない（観光客の端末から
// 設定が書き換わると困る）。ここは「数値を決めるため」だけの画面。
//
// 開き方: webapp/?tune=1

import { LANGUAGES, LABEL } from './app-language.js';
import { TuneHandles } from './tune-handles.js';

/// つまみの定義。名前は「キャラクター」シートの列と同じにしてある
/// （書き写すときに迷わないようにするため）。
const KNOBS = [
  {
    key: 'scale', label: '大きさ', min: 0.1, max: 1.5, step: 0.01,
    hint: '1.0が基準。横長のキャラクターは小さめに',
  },
  {
    key: 'rise', label: '高さ位置', min: 0, max: 1, step: 0.01,
    hint: '0は下端に立たせる、1は上端まで持ち上げる',
  },
  {
    key: 'mouth', label: '口の高さ', min: 0.02, max: 0.9, step: 0.01,
    hint: '立ち絵の上から口までの割合。尻尾の向く先',
  },
  {
    key: 'face', label: '顔の広さ', min: 0.05, max: 1.2, step: 0.01,
    hint: '右端から顔の左端まで。吹き出しが顔にかぶらない位置',
  },
];

const escape = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);

export class TunePanel {
  /// character … CharacterView、onLanguage … 言語を変えたいときに呼ぶ
  constructor(root, character, onLanguage) {
    this.root = root;
    this.character = character;
    this.onLanguage = onLanguage;
    this.values = null;
    // 立ち絵を直接つまんで動かすための取っ手
    this.handles = new TuneHandles(
      character.stage, character.root, (values) => this._fromHandles(values),
    );
  }

  open() {
    this.values = { ...this.character.shape };
    this.root.hidden = false;
    this.render();
    this.handles.attach(this.values);
  }

  close() {
    this.handles.detach();
    this.character.preview(null);   // 合わせた値は残さない
    this.root.hidden = true;
    this.root.innerHTML = '';
  }

  /// 取っ手を動かしたとき。つまみの表示も合わせる。
  _fromHandles(values) {
    this.values = { ...values };
    this.character.preview(this.values);
    for (const k of KNOBS) {
      const slider = this.root.querySelector(`input[data-key="${k.key}"]`);
      if (slider) slider.value = String(this.values[k.key]);
      const out = this.root.querySelector(`output[data-out="${k.key}"]`);
      if (out) out.textContent = this.values[k.key].toFixed(2);
    }
    this._writeCopyLine();
  }

  _writeCopyLine() {
    const line = KNOBS.map((k) => `${k.label} ${this.values[k.key].toFixed(2)}`)
      .join(' / ');
    const box = this.root.querySelector('.tune-copy');
    if (box) box.value = line;
  }

  render() {
    const current = this.character.current;

    const characters = this.character.list.map((c) =>
      `<option value="${escape(c.id)}"${c.id === current.id ? ' selected' : ''}>`
      + `${escape(c.name)}</option>`).join('');

    const langs = LANGUAGES.map((code) =>
      `<option value="${code}">${escape(LABEL[code])}</option>`).join('');

    const knobs = KNOBS.map((k) => `
      <label class="tune-knob">
        <span class="tune-knob-name">${k.label}</span>
        <input type="range" data-key="${k.key}"
               min="${k.min}" max="${k.max}" step="${k.step}"
               value="${this.values[k.key]}">
        <output data-out="${k.key}">${this.values[k.key].toFixed(2)}</output>
        <span class="tune-knob-hint">${escape(k.hint)}</span>
      </label>`).join('');

    this.root.innerHTML = `
      <div class="tune-box">
        <div class="tune-head">
          <strong>見え方の調整</strong>
          <button class="tune-close" type="button">閉じる</button>
        </div>

        <div class="tune-row">
          <select class="tune-character">${characters}</select>
          <select class="tune-language">${langs}</select>
          <button class="tune-say" type="button">長い回答で試す</button>
        </div>

        ${knobs}

        <p class="tune-note">立ち絵そのものをつまんで上下に動かせます。
        左上の四角で大きさ、丸い印で口の位置、縦の点線で吹き出しの右端。</p>

        <p class="tune-copy-label">この数値を管理画面の「キャラクター」に書き写します</p>
        <div class="tune-row">
          <input class="tune-copy" type="text" readonly value="">
          <button class="tune-copy-button" type="button">写す</button>
          <button class="tune-reset" type="button">戻す</button>
        </div>
        <p class="tune-note">ここで動かしても保存はされません。
        閉じると元の見え方に戻ります。</p>
      </div>`;

    this._wire();
    this._apply();
  }

  _wire() {
    this.root.querySelector('.tune-close').onclick = () => this.close();

    this.root.querySelector('.tune-character').onchange = (e) => {
      this.character.preview(null);          // 先に上書きを外してから
      this.character.choose(e.target.value); // 別のキャラクターへ
      this.values = { ...this.character.shape };
      this.render();
      this.handles.attach(this.values);
    };

    const lang = this.root.querySelector('.tune-language');
    if (this.onLanguage) lang.onchange = () => this.onLanguage(lang.value);

    for (const slider of this.root.querySelectorAll('input[type="range"]')) {
      // input は「つまみを動かしている間ずっと」なので、その場で反映される
      slider.oninput = () => {
        this.values[slider.dataset.key] = Number(slider.value);
        this._apply();
      };
    }

    this.root.querySelector('.tune-reset').onclick = () => {
      this.values = { ...this.character.current };
      this.values = {
        scale: this.character.current.scale ?? 1,
        rise: this.character.current.rise ?? 0,
        mouth: this.character.current.mouth ?? 0.14,
        face: this.character.current.face ?? 0.31,
      };
      this.render();
    };

    this.root.querySelector('.tune-copy-button').onclick = () => {
      const box = this.root.querySelector('.tune-copy');
      box.select();
      try {
        navigator.clipboard.writeText(box.value);
      } catch (_) {
        document.execCommand('copy');   // 古いブラウザ向け
      }
    };

    this.root.querySelector('.tune-say').onclick = () => {
      // 文章が長いときに吹き出しがどう伸びるかを見るための試し表示
      if (this.onLongText) this.onLongText();
    };
  }

  _apply() {
    this.character.preview(this.values);
    for (const k of KNOBS) {
      const out = this.root.querySelector(`output[data-out="${k.key}"]`);
      if (out) out.textContent = this.values[k.key].toFixed(2);
    }
    this._writeCopyLine();
    // 立ち絵が動いたあとに取っ手を置き直す（描画が終わってから測る）
    requestAnimationFrame(() => this.handles.update(this.values));
  }
}
