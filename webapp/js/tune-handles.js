// 立ち絵を直接つまんで動かすための取っ手（職員用・調整モードの一部）。
//
// つまみ（スライダー）だけだと「どの数字が何に効くのか」を覚える必要がある。
// 動かしたいものを直接つまめれば、覚えることが無くなる。
//
// つまめるのは4つ。どれも「キャラクター」シートの値に対応している。
//
//   立ち絵そのもの … 上下に動かす           → 高さ位置
//   左上の四角     … 斜めに引くと大きさが変わる → 大きさ
//   丸い印         … 口の位置               → 口の高さ
//   縦の点線       … 吹き出しが来てよい右端    → 顔の広さ
//
// 【画面の上に重ねるだけ】
// 立ち絵そのものには触らない。取っ手は会話領域に重ねて置き、
// 動かした結果は数値として呼び出し側へ返す。

/// つまんだ量が小さすぎると、押しただけで動いてしまう
const DEAD_ZONE = 2;

export class TuneHandles {
  /// stage … 会話領域、characterEl … 立ち絵、onChange … 値が変わったときに呼ぶ
  constructor(stage, characterEl, onChange) {
    this.stage = stage;
    this.characterEl = characterEl;
    this.onChange = onChange;
    this.root = null;
    this.values = null;
    this._onResize = () => this.sync();
  }

  /// 取っ手を出す。values は { scale, rise, mouth, face }。
  attach(values) {
    this.values = { ...values };
    if (!this.root) {
      this.root = document.createElement('div');
      this.root.className = 'tune-handles';
      this.root.innerHTML = `
        <div class="tune-h tune-h-move" data-kind="move" title="上下に動かす（高さ位置）">
          <span class="tune-h-label">動かす</span>
        </div>
        <div class="tune-h tune-h-size" data-kind="size" title="引くと大きさが変わる"></div>
        <div class="tune-h tune-h-mouth" data-kind="mouth" title="口の位置"></div>
        <div class="tune-h tune-h-face" data-kind="face" title="吹き出しが来てよい右端"></div>`;
      this.stage.appendChild(this.root);
      for (const el of this.root.querySelectorAll('.tune-h')) {
        el.addEventListener('pointerdown', (e) => this._start(e, el.dataset.kind));
      }
    }
    // 呼吸の上下運動があると、つまむ位置がずれて見える
    this.characterEl.style.animationPlayState = 'paused';
    window.addEventListener('resize', this._onResize);
    this.sync();
  }

  detach() {
    if (this.root) {
      this.root.remove();
      this.root = null;
    }
    this.characterEl.style.removeProperty('animation-play-state');
    window.removeEventListener('resize', this._onResize);
  }

  /// 外から値が変わったとき（スライダーを動かしたときなど）に呼ぶ
  update(values) {
    this.values = { ...values };
    this.sync();
  }

  /// 取っ手を、いまの立ち絵の位置に合わせて置き直す
  sync() {
    if (!this.root) return;
    const stage = this.stage.getBoundingClientRect();
    const ch = this.characterEl.getBoundingClientRect();
    const top = ch.top - stage.top;
    const left = ch.left - stage.left;

    const place = (sel, style) => {
      const el = this.root.querySelector(sel);
      if (el) Object.assign(el.style, style);
    };

    place('.tune-h-move', {
      top: `${top}px`, left: `${left}px`,
      width: `${ch.width}px`, height: `${ch.height}px`,
    });
    place('.tune-h-size', { top: `${top - 7}px`, left: `${left - 7}px` });
    // 口の印は、立ち絵の左端あたりの高さに置く（顔そのものを隠さないため）
    place('.tune-h-mouth', {
      top: `${top + ch.height * this.values.mouth - 9}px`,
      left: `${left - 9}px`,
    });
    // 顔の広さは「右端から顔の左端まで」。立ち絵の右端から測る。
    place('.tune-h-face', {
      top: `${top}px`,
      left: `${ch.right - stage.left - ch.height * this.values.face}px`,
      height: `${ch.height}px`,
    });
  }

  _start(event, kind) {
    event.preventDefault();
    event.stopPropagation();

    const stage = this.stage.getBoundingClientRect();
    const ch = this.characterEl.getBoundingClientRect();
    const from = { x: event.clientX, y: event.clientY };
    const base = { ...this.values };
    let moved = false;

    const target = event.currentTarget;
    target.setPointerCapture?.(event.pointerId);

    const move = (e) => {
      const dx = e.clientX - from.x;
      const dy = e.clientY - from.y;
      if (!moved && Math.abs(dx) < DEAD_ZONE && Math.abs(dy) < DEAD_ZONE) return;
      moved = true;

      const next = { ...base };
      if (kind === 'move') {
        // 上へ引くほど持ち上がる。動かせる幅は「会話領域の高さ − 立ち絵の高さ」。
        const room = stage.height - ch.height;
        if (room > 1) next.rise = base.rise - dy / room;
      } else if (kind === 'size') {
        // 左上の角を外へ引くほど大きくなる。縦の動きを基準にする。
        if (ch.height > 1) {
          next.scale = base.scale * (1 - dy / ch.height);
        }
      } else if (kind === 'mouth') {
        if (ch.height > 1) next.mouth = base.mouth + dy / ch.height;
      } else if (kind === 'face') {
        // 右端から左へ広げるほど、吹き出しが遠ざかる
        if (ch.height > 1) next.face = base.face - dx / ch.height;
      }

      this.values = {
        scale: clamp(next.scale, 0.1, 1.5),
        rise: clamp(next.rise, 0, 1),
        mouth: clamp(next.mouth, 0.02, 0.9),
        face: clamp(next.face, 0.05, 1.2),
      };
      this.onChange(this.values);
      // 立ち絵が動いたあとに取っ手を置き直す（描画が終わってから測る）
      requestAnimationFrame(() => this.sync());
    };

    const end = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
    };

    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
  }
}

function clamp(value, low, high) {
  if (!Number.isFinite(value)) return low;
  return Math.min(high, Math.max(low, value));
}
