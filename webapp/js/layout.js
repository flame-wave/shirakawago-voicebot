// 設置形態ごとの画面の形（管理画面の「画面レイアウト」で決めたもの）。
//
// 据え置きのタブレットと、観光客のスマートフォンでは、同じ並びが使えない。
//
//   据え置き … 立ったまま、少し離れて使う。指は大きく動かせるので
//               話すボタンは大きい方がよい。一方で「文字で質問する」欄は、
//               公共の端末ではほとんど使われない。
//   観光客   … 手元で見る。画面が小さいので、出すものを絞りたい。
//
// これまでは1つの並びをどの端末でも使い回していたので、
// どちらかに合わせるともう一方が使いにくくなっていた。
//
// 【崩れない形で持つ】
// 位置を px で覚えると、別の大きさの画面に移したとたんに重なるか外へ出る。
// ここでは高さを「画面の高さに対する割合」、立ち位置を「0〜1の割合」で持つ。
// 7インチでも13インチでも、同じ見え方になる。

import { clientId } from './deployment.js';

/// 画面の中で動かせるブロック。管理画面の編集画面と同じ並び。
export const BLOCKS = {
  stage: '.stage',
  faq: '.faq-strip',
  typed: '.typed',
  talk: '.talk-button',
  languages: '.languages',
};

/// 高さを決められるブロック（会話領域は残り全部を使うので入らない）
const SIZED = ['faq', 'typed', 'talk', 'languages'];

/// 設定が無いときの並び（これまでと同じ）
const DEFAULT_ORDER = ['stage', 'faq', 'typed', 'talk', 'languages'];

export class LayoutView {
  /// screen … .screen、stage … .stage
  constructor(screen, stage) {
    this.screen = screen;
    this.stage = stage;
    this._all = [];
  }

  /// 質問回答集から受け取った一覧を覚え、この端末のものを当てる
  setList(layouts) {
    this._all = Array.isArray(layouts) ? layouts : [];
    this.apply(this.forPlace(clientId));
  }

  /// その設置場所の設定。無ければ「共通」、それも無ければ null。
  forPlace(place) {
    return this._all.find((l) => l.place === place)
      ?? this._all.find((l) => l.place === '共通')
      ?? null;
  }

  /// 画面に当てる。null を渡すと、CSSの既定（これまでの見え方）に戻す。
  apply(layout) {
    this._layout = layout;

    const order = layout?.order?.length ? layout.order : DEFAULT_ORDER;

    // 並び順。一覧に無いブロックは「出さない」。
    for (const [key, selector] of Object.entries(BLOCKS)) {
      const el = this.screen.querySelector(selector);
      if (!el) continue;
      const at = order.indexOf(key);
      if (at < 0) {
        el.dataset.off = '1';
      } else {
        delete el.dataset.off;
        this.screen.style.setProperty(`--order-${key}`, String(at + 1));
      }
    }

    // 高さ。0（未設定）なら中身なりの高さに戻す。
    for (const key of SIZED) {
      const value = Number(layout?.heights?.[key] ?? 0);
      if (value > 0) {
        this.screen.style.setProperty(`--h-${key}`, `${(value * 100).toFixed(2)}cqh`);
      } else {
        this.screen.style.removeProperty(`--h-${key}`);
      }
    }

    this.applyStage();
  }

  /// 会話領域の中（立ち絵と吹き出し）。
  /// 立ち絵を選び直したあとにも呼ぶ（CharacterView が変数を入れ直すため）。
  applyStage() {
    const layout = this._layout;
    const set = (name, value) => {
      if (value === null || value === undefined) {
        this.stage.style.removeProperty(name);
      } else {
        this.stage.style.setProperty(name, String(value));
      }
    };

    const c = layout?.character ?? {};
    // 大きさは倍率。「キャラクター」シートの絵ごとの大きさに掛ける
    // （絵ごとの違いは残したまま、場所ごとに一律で大小を変えられる）。
    set('--place-char-scale', c.scale > 0 ? c.scale : null);
    // 立ち位置は割合そのもの。0＝下端、1＝上端。
    set('--place-char-rise', typeof c.rise === 'number' ? c.rise : null);
    // 左右は 0＝右端、1＝左端。立ち絵の幅を引いて動ける範囲にする。
    set('--place-char-right', typeof c.side === 'number'
      ? `calc(${c.side} * (100cqw - var(--char-w)))` : null);

    const b = layout?.bubble ?? {};
    set('--place-bubble', b.width > 0 ? b.width : null);
    set('--place-text', b.text > 0 ? b.text : null);
  }
}
