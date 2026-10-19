// 据え置き端末の夜間（画面を真っ黒にする）。
//
// 案内所が閉まったあとも画面が明るいと、夜に虫（カメムシなど）が集まってくる。
// 電源を切ると、朝に立ち上げ直す手間がかかる（ピン止めや許可の確認もやり直しになる）。
// そこで、管理画面の「画面レイアウト」で決めた消灯の時刻から点灯の時刻までは、
// 案内アプリが画面を真っ黒にするだけにする（app.js の checkNight）。
//
// 【明るさについて】
// ブラウザからは、端末の画面の明るさ（バックライト）そのものは変えられない。
// 真っ黒にすれば、ほとんど光らなくなる（液晶はうっすら光が漏れる）。
// さらに抑えたいときは、端末の明るさを下げておく。

import { uiString } from './app-language.js';

const minutes = (hhmm) => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm || '');
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
};

/// いまが消灯の時間か。hours は { off: "18:00", on: "8:00" }。どちらかが無ければ消さない。
export function isNight(hours, now = new Date()) {
  const off = minutes(hours?.off);
  const on = minutes(hours?.on);
  if (off === null || on === null || off === on) return false;
  const t = now.getHours() * 60 + now.getMinutes();
  // ふつうは夜をまたぐ（18:00〜翌8:00）。またがない書き方（1:00〜5:00）にも対応する
  return off > on ? t >= off || t < on : t >= off && t < on;
}

export class NightMode {
  constructor(root) {
    this.root = root;
    this.note = root.querySelector('.night-note');
    this._hide = null;
    this._lang = 'ja';
    this._on = '';
    // 触れたら、暗い文字で「本日は終了」とだけ出す（しばらくすると消える）
    root.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.note.textContent = uiString('nightClosed', this._lang).replace('{on}', this._on);
      if (this._lang !== 'en') {
        this.note.textContent += `\n${uiString('nightClosed', 'en').replace('{on}', this._on)}`;
      }
      this.note.style.whiteSpace = 'pre-line';
      this.note.hidden = false;
      clearTimeout(this._hide);
      this._hide = setTimeout(() => { this.note.hidden = true; }, 5000);
    });
  }

  get on() {
    return !this.root.hidden;
  }

  enter(lang, onTime) {
    this._lang = lang;
    this._on = onTime || '';
    this.note.hidden = true;
    this.root.hidden = false;
  }

  leave() {
    clearTimeout(this._hide);
    this.note.hidden = true;
    this.root.hidden = true;
  }
}
