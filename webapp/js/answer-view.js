// 回答の表示（lib/answer_view.dart の移植）。
// 吹き出しの中に文章、外に写真とQRコードを置く。
//
// 写真やQRを吹き出しに入れると、文章が押し出されて読みにくくなるため、
// 「話した内容」と「見て確認するもの」を分けている。

import { ASSET_BASE } from './config.js';
import { showQr } from './deployment.js';
import { uiString } from './app-language.js';

export class AnswerView {
  constructor(root) {
    this.root = root;
    this.pending = root.querySelector('.answer-pending');
    this.text = root.querySelector('.answer-text');
    this.aiNote = root.querySelector('.answer-ai');
    // 写真とQRは吹き出しの外（会話領域の下側）に置いてあるので、画面全体から探す
    this.media = document.querySelector('.answer-media');
    this.photoBox = document.querySelector('.answer-photo-box');
    this.photo = document.querySelector('.answer-photo');
    this.photoHint = document.querySelector('.answer-photo-hint');
    this.qrBox = document.querySelector('.answer-qr-box');
    this.qr = document.querySelector('.answer-qr');
    this.qrCaption = document.querySelector('.answer-qr-caption');
    this.link = document.querySelector('.answer-link');

    // 必ず別のタブで開く。
    //
    // target="_blank" は書いてあるが、キオスクモード（--app=）や
    // ホーム画面に追加したときは無視され、案内アプリ自体が
    // 外部サイトに置き換わってしまう。そうなると観光客は戻り方が分からず、
    // 据え置き端末では次の方が外部サイトを見ることになる。
    // 自分で新しい窓を開き、開けたときだけ元の遷移を止める。
    this.link.addEventListener('click', (e) => {
      const url = this.link.getAttribute('href');
      if (!url) return;
      const opened = window.open(url, '_blank', 'noopener,noreferrer');
      if (opened) e.preventDefault();   // 開けなかったときは普通の遷移に任せる
    });

    // 写真が無くても表示は崩さない
    this.photo.addEventListener('error', () => {
      this.photoBox.hidden = true;
      this._syncMedia();
    });
  }

  /// answer が空のときは placeholder（案内文）を薄く出す
  update({ answer, photo, link, lang, isFallback, placeholder, isAi }) {
    const empty = !answer;
    this.text.textContent = empty ? placeholder : answer;
    this.text.classList.toggle('empty', empty);

    // 翻訳が未整備のときは、日本語表示であることを断る
    const pending = !empty && isFallback ? uiString('translationPending', lang) : '';
    this.pending.textContent = pending;
    this.pending.hidden = pending === '';

    // AIが作った回答であることは、必ず画面に出す（職員の回答と見分けられるように）
    this.aiNote.textContent = isAi ? uiString('aiNote', lang) : '';
    this.aiNote.hidden = !isAi;

    if (photo) {
      this.photoBox.hidden = false;
      this.photo.src = `${ASSET_BASE}photo/${photo}`;
      this.photoHint.textContent = uiString('tapToEnlarge', lang);
    } else {
      this.photoBox.hidden = true;
      this.photo.removeAttribute('src');
    }

    // 据え置き端末はQRコード、観光客の端末は押せるリンク。
    // 据え置きの画面でリンクを出しても持ち帰れず、
    // 手元の端末にQRコードを出しても自分では読み取れない。
    if (link && showQr) {
      this.qrBox.hidden = false;
      this.qr.hidden = false;
      this.qr.innerHTML = qrSvg(link);
      this.qrCaption.textContent = uiString('scanForDetails', lang);
      this.qrCaption.hidden = false;
      this.link.hidden = true;
    } else if (link) {
      this.qrBox.hidden = false;
      this.qr.hidden = true;
      this.qr.innerHTML = '';
      this.qrCaption.hidden = true;
      this.link.hidden = false;
      this.link.href = link;
      this.link.textContent = uiString('openLink', lang);
    } else {
      this.qrBox.hidden = true;
      this.qr.hidden = true;
      this.qr.innerHTML = '';
      this.qrCaption.hidden = true;
      this.link.hidden = true;
      this.link.removeAttribute('href');
    }

    this._syncMedia();
  }

  _syncMedia() {
    this.media.hidden = this.photoBox.hidden && this.qrBox.hidden;
  }
}

/// QRコードをSVGで描く。
/// 汚れや反射に強くするため、誤り訂正は高め（H）にする。
function qrSvg(url) {
  if (typeof window.qrcode !== 'function') {
    console.warn('QRコードの生成ライブラリが読み込まれていません');
    return '';
  }
  try {
    const qr = window.qrcode(0, 'H'); // 0 = 文字数に合わせて自動
    qr.addData(url);
    qr.make();
    return qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
  } catch (e) {
    console.warn('QRコードを作れません:', e);
    return '';
  }
}
