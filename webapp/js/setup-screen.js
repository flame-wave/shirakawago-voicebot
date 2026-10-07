// 職員用の設定画面（この端末だけの設定）。
//
// 以前はここで質問の記録も見られるようにしていたが、
// 観光客が触る端末に閲覧口があると、いつか開かれてしまう。
// 記録の閲覧と集計は管理者画面（admin/）に一本化し、
// この画面には「その端末でしか決められないこと」だけを残した。
//
// 開き方は URL に ?setup=1 を足す（画面の操作では開けない）。
//   webapp/?place=バスターミナル&setup=1

import { TTS_ONLY } from './voice-service.js';
import { LANGUAGES, LABEL, uiString } from './app-language.js';
import { clientId, isKiosk } from './deployment.js';

const escape = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);

export class SetupScreen {
  constructor(root, log, voice) {
    this.root = root;
    this.log = log;
    this.voice = voice;
  }

  open() {
    this.root.hidden = false;
    this.render();
  }

  close() {
    this.root.hidden = true;
    this.root.innerHTML = '';
    // 閉じたあとにすること（据え置き端末では、次の方のために同意画面を出す）
    if (this.onClose) this.onClose();
  }

  render() {
    this.root.innerHTML = `
      <div class="log-bar">
        <button class="log-back" type="button">← 戻る</button>
        <h2>この端末の設定（職員用）</h2>
      </div>
      <div class="log-body">
        ${this._roleSection()}
        ${this._voiceSetSection()}
        ${this._voiceSection()}
      </div>`;

    this.root.querySelector('.log-back').onclick = () => this.close();

    const send = this.root.querySelector('.log-send');
    if (send) {
      send.onclick = async () => {
        send.disabled = true;
        send.textContent = '送っています…';
        while (await this.log.flush()) {
          // まだ残っていれば続けて送る
        }
        this.render();
      };
    }

    const clear = this.root.querySelector('.log-clear');
    if (clear) {
      clear.onclick = () => {
        // 押し間違いで消えないよう、一度確かめる
        if (!window.confirm('この端末に残っている記録を消します。元に戻せません。よろしいですか？')) {
          return;
        }
        this.log.clearLocal();
        this.render();
      };
    }

    const setSelect = this.root.querySelector('.voice-set-select');
    if (setSelect) {
      setSelect.onchange = () => this.voice.chooseSet(setSelect.value);
    }

    for (const select of this.root.querySelectorAll('.voice-select')) {
      select.onchange = () => {
        this.voice.chooseVoice(select.dataset.lang, select.value);
        this.voice.setLanguage(select.dataset.lang);
      };
    }
    for (const button of this.root.querySelectorAll('.voice-test')) {
      button.onclick = () => {
        const lang = button.dataset.lang;
        // その言語の文を、その言語の声で読む（食い違うと鳴らない）
        this.voice.speakSample(lang, uiString('voiceSample', lang));
      };
    }
  }

  /// この端末がどの役割で動いているか。設置のときの確認に使う。
  _roleSection() {
    const pending = this.log.pendingCount;
    const role = isKiosk
      ? `据え置き（${escape(clientId)}）`
      : '観光客のスマートフォン';
    const sending = pending === 0
      ? '未送信の記録はありません'
      : `未送信の記録 ${pending} 件`
        + ' <button class="log-send" type="button">いま送る</button>';

    const local = this.log.localCount;
    return `<section class="log-section">
      <h3>この端末</h3>
      <p class="log-sub">役割: ${role}</p>
      <p class="log-sub">${sending}</p>
      <p class="log-sub">質問の記録は中継サーバへ送られ、管理者画面で見られます。
      この画面からは見られません。</p>
      <p class="log-sub">この端末に残っている記録 ${local + pending} 件
        <button class="log-clear" type="button" ${local + pending === 0 ? 'disabled' : ''}>この端末の記録を消す</button></p>
      <p class="log-sub">本番を始める前に押します。試しの頃の質問で、
      「よくある質問」の並び順が偏らないようにするためです。</p>
    </section>`;
  }

  /// 用意した音声（VOICEVOXなどで作ったもの）の選択。
  _voiceSetSection() {
    if (!this.voice) return '';
    const sets = this.voice.sets;
    if (sets.length === 0) return '';

    const current = this.voice.currentSet;
    const options = sets
      .map((v) =>
        `<option value="${escape(v.id)}"${v.id === current ? ' selected' : ''}>`
        + `${escape(v.label)}</option>`)
      .concat([
        `<option value="${TTS_ONLY}"${current === TTS_ONLY ? ' selected' : ''}>`
        + '使わない（ブラウザの声で読む）</option>',
      ])
      .join('');

    return `<section class="log-section">
      <h3>用意した音声</h3>
      <p class="log-sub">回答ごとに用意した音声のうち、どれを鳴らすかを選べます。
      ここで選ぶとこの端末だけが変わります。
      全部の端末をまとめて変えるときは管理者画面で選んでください。</p>
      <div class="voice-row">
        <select class="voice-set-select">${options}</select>
      </div>
      <p class="log-sub">選んだ音声が無い回答は、ブラウザの声で読み上げます。</p>
    </section>`;
  }

  /// ブラウザの声の選択。対応言語すべてを並べる。
  ///
  /// 言語ごとに別々の声を使うため、いま選んでいる言語だけを出すと
  /// 「他の言語はどうなっているのか」が職員から見えない。
  /// 声が入っていない言語もその場で分かるようにしている。
  _voiceSection() {
    if (!this.voice) return '';

    const rows = LANGUAGES.map((lang) => {
      const voices = this.voice.voicesFor(lang);
      const name = escape(LABEL[lang]);
      if (voices.length === 0) {
        return `<div class="voice-lang voice-lang-missing">
          <span class="voice-lang-name">${name}</span>
          <span class="voice-lang-none">この端末に声が入っていません</span>
        </div>`;
      }
      const current = this.voice.currentVoiceName(lang);
      const options = ['<option value="">自動（おすすめの声）</option>']
        .concat(voices.map((v) =>
          `<option value="${escape(v.name)}"${v.name === current ? ' selected' : ''}>`
          + `${escape(v.name)}（${escape(v.lang)}）</option>`))
        .join('');
      return `<div class="voice-lang">
        <span class="voice-lang-name">${name}</span>
        <select class="voice-select" data-lang="${lang}">${options}</select>
        <button class="voice-test" type="button" data-lang="${lang}">試しに読む</button>
      </div>`;
    }).join('');

    const missing = LANGUAGES.filter((l) => this.voice.voicesFor(l).length === 0);
    const note = missing.length === 0 ? '' :
      `<p class="log-sub">声が入っていない言語は、読み上げだけができません（字幕は出ます）。
       Windowsの「設定 → 時刻と言語 → 言語と地域」でその言語を追加すると使えるようになります。</p>`;

    return `<section class="log-section">
      <h3>読み上げの声</h3>
      <p class="log-sub">言語ごとに、この端末で使う声を選べます。
      <strong>この一覧はこの端末に入っている声です</strong>（端末ごとに違います）。
      管理者画面では「どれを優先するか」と速さ・高さを決められます。</p>
      ${rows}
      ${note}
      <p class="log-sub">用意した音声ファイル（VOICEVOXなど）がある回答では、そちらが優先されます。</p>
    </section>`;
  }
}
