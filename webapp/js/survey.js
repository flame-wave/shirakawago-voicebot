// かんたんなアンケート（「AI観光ガイドの体験はどうでしたか？」に 〇△× で答える）。
//
// 最初の答えを出し終えたあと、画面の下の言語の列と入れ替えて出す。
// 言語の列はいつも同じ場所・同じ大きさなので、答えの領域を狭めずに済む。
// 画面全体をふさぐと案内のじゃまになるので、答えなくても使い続けられるようにする
// （「答えない」を押すと、すぐ言語の列に戻る）。
//
// 1人に1回だけ聞く。据え置き端末では、次の方に替わったら（同意画面に戻ったら）また聞く。
// 記録は質問の記録とは別に送る（question-log.js の addSurvey）。

import { uiString } from './app-language.js';

const VOTES = [
  { vote: 'good', mark: '〇', label: 'surveyGood' },
  { vote: 'ok', mark: '△', label: 'surveyOk' },
  { vote: 'bad', mark: '×', label: 'surveyBad' },
];

export class SurveyView {
  /// root … アンケートを入れる場所（言語の列と同じ並びに置いた箱）
  constructor(root) {
    this.root = root;
    this.done = false;     // この方にはもう聞いた（答えた・答えないを選んだ）
    this.onVote = null;    // onVote('good' | 'ok' | 'bad')
    this._lang = 'ja';
    this._thanksTimer = null;
  }

  get open() {
    return !this.root.hidden;
  }

  /// まだ聞いていなければ出す
  ask(lang) {
    if (this.done || this.open) return;
    this._lang = lang;
    this._render();
    this._show(true);
  }

  /// 出す・隠す。出ている間は、言語の列を隠す（.screen に印を付ける）。
  _show(open) {
    this.root.hidden = !open;
    this.root.closest('.screen')?.classList.toggle('survey-open', open);
    if (!open) this.root.innerHTML = '';
  }

  /// 言語を変えたときに、出ている文を入れ替える
  setLanguage(lang) {
    this._lang = lang;
    if (this.open && !this._thanking) this._render();
  }

  /// 次の方のために、また聞けるようにする
  reset() {
    clearTimeout(this._thanksTimer);
    this._thanking = false;
    this.done = false;
    this._show(false);
  }

  _render() {
    const t = (key) => uiString(key, this._lang);
    this.root.innerHTML = '';
    const q = document.createElement('p');
    q.className = 'survey-q';
    q.textContent = t('surveyQuestion');
    const row = document.createElement('div');
    row.className = 'survey-row';
    for (const v of VOTES) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `survey-vote survey-${v.vote}`;
      b.innerHTML = `<span class="survey-mark" aria-hidden="true">${v.mark}</span>`
        + `<span class="survey-label">${t(v.label)}</span>`;
      b.addEventListener('click', () => this._choose(v.vote));
      row.appendChild(b);
    }
    const skip = document.createElement('button');
    skip.type = 'button';
    skip.className = 'survey-skip';
    skip.textContent = t('surveySkip');
    skip.addEventListener('click', () => this._close());
    this.root.append(q, row, skip);
  }

  _choose(vote) {
    this.done = true;
    if (this.onVote) this.onVote(vote);
    // お礼を少しだけ出して閉じる
    this._thanking = true;
    this.root.innerHTML = '';
    const thanks = document.createElement('p');
    thanks.className = 'survey-thanks';
    thanks.textContent = uiString('surveyThanks', this._lang);
    this.root.appendChild(thanks);
    this._thanksTimer = setTimeout(() => {
      this._thanking = false;
      this._show(false);
    }, 2500);
  }

  _close() {
    this.done = true;
    this._show(false);
  }
}
