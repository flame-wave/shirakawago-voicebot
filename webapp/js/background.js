// 背景（lib/background_view.dart の移植）。
// 白川郷の合掌造り集落を、キャラクターの近未来的な意匠に合わせて描く。
//
// 画像ファイルではなく canvas に描いているのは、
// どの画面サイズでも破綻せず、素材の管理も要らないため。
//
// 前面に白い吹き出しと文字が載るので、全体を淡くして可読性を優先している。

const SKY_TOP = '#F4F9FB';
const SKY_MID = '#E9F3F2';
const SKY_BOTTOM = '#DFEEE9';
const RIDGE_FAR = 'rgba(203,218,206,0.776)';
const RIDGE_NEAR = 'rgba(176,198,181,0.804)';
const GROUND = 'rgba(198,218,204,0.471)';
const HOUSE = 'rgba(120,144,127,0.922)';
const WINDOW_GLOW = 'rgba(104,222,218,0.686)';
const TECH = '86,190,196'; // rgb（濃さを変えて何度も使う）

/// 乱数の種を固定する（描き直しても雪の位置が変わらないように）
function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const SNOW = (() => {
  const rnd = seeded(5);
  return Array.from({ length: 80 }, () => ({
    x: rnd(),
    y: rnd() * 0.85,
    r: 1.0 + rnd() * 1.6,
  }));
})();

export class BackgroundView {
  constructor(canvas) {
    this.canvas = canvas;
    this._observer = new ResizeObserver(() => this.draw());
    this._observer.observe(canvas.parentElement ?? canvas);
    this.draw();
  }

  draw() {
    const canvas = this.canvas;
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);

    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const w = rect.width;
    const h = rect.height;
    const horizon = h * 0.6;

    ctx.clearRect(0, 0, w, h);
    this._sky(ctx, w, h);
    this._glow(ctx, w, horizon);
    this._ridge(ctx, w, horizon, 0.0055, 0.019, 34, 52, RIDGE_FAR);
    this._ridge(ctx, w, horizon, 0.0092, 0.028, 10, 34, RIDGE_NEAR);
    this._ground(ctx, w, h, horizon);
    this._grid(ctx, w, h, horizon);
    this._village(ctx, w, horizon);
    this._scanlines(ctx, w, h);
    this._rings(ctx, w, h);
    this._horizonLine(ctx, w, horizon);
    this._snow(ctx, w, h);
  }

  _sky(ctx, w, h) {
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, SKY_TOP);
    g.addColorStop(0.6, SKY_MID);
    g.addColorStop(1, SKY_BOTTOM);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  }

  /// 朝もやのような滲んだ光
  _glow(ctx, w, horizon) {
    const cx = w * 0.58;
    const cy = horizon - 20;
    ctx.save();
    ctx.filter = 'blur(40px)';
    ctx.translate(cx, cy);
    ctx.scale(1, 0.5);
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 260);
    g.addColorStop(0, 'rgba(150,235,228,0.25)');
    g.addColorStop(1, 'rgba(150,235,228,0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(0, 0, 260, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  /// 山の稜線
  _ridge(ctx, w, horizon, a, b, dy, amp, color) {
    ctx.beginPath();
    ctx.moveTo(0, horizon - dy);
    for (let x = 0; x <= w; x += 26) {
      const y =
        horizon - dy - amp * Math.abs(Math.sin(x * a)) - amp * 0.35 * Math.sin(x * b);
      ctx.lineTo(x, y);
    }
    ctx.lineTo(w, horizon - dy);
    ctx.lineTo(w, horizon + 2);
    ctx.lineTo(0, horizon + 2);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  _ground(ctx, w, h, horizon) {
    ctx.fillStyle = GROUND;
    ctx.fillRect(0, horizon, w, h - horizon);
  }

  /// 奥に収束するグリッド（近未来的な地面）
  _grid(ctx, w, h, horizon) {
    const vpx = w * 0.52;
    ctx.lineWidth = 1;
    ctx.strokeStyle = `rgba(${TECH},0.12)`;
    for (let i = -10; i <= 10; i++) {
      ctx.beginPath();
      ctx.moveTo(vpx, horizon);
      ctx.lineTo(vpx + i * w * 0.19, h);
      ctx.stroke();
    }
    ctx.strokeStyle = `rgba(${TECH},0.10)`;
    for (let j = 1; j < 14; j++) {
      const t = j / 14;
      const y = horizon + (h - horizon) * Math.pow(t, 2.0);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
  }

  /// 合掌造りの集落。画面幅に対する比率で配置し、どの画面でも同じ並びになるようにする
  _village(ctx, w, horizon) {
    const layout = [
      [0.076, 0.076, 26.0],
      [0.197, 0.061, 18.0],
      [0.339, 0.089, 34.0],
      [0.516, 0.068, 22.0],
      [0.658, 0.082, 30.0],
      [0.805, 0.058, 16.0],
      [0.926, 0.071, 24.0],
    ];
    for (const it of layout) {
      this._gassho(ctx, w * it[0], w * it[1], horizon + it[2]);
    }
  }

  /// 急勾配の切妻屋根と、妻面の窓明かり
  _gassho(ctx, cx, width, base) {
    const roofH = width * 1.15;
    const wallH = width * 0.26;

    ctx.fillStyle = HOUSE;
    ctx.fillRect(cx - width * 0.4, base - wallH, width * 0.8, wallH);

    ctx.beginPath();
    ctx.moveTo(cx, base - wallH - roofH);
    ctx.lineTo(cx - width / 2, base - wallH);
    ctx.lineTo(cx + width / 2, base - wallH);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = WINDOW_GLOW;
    for (const win of [
      [0.6, 0.11, 0.085],
      [0.4, 0.1, 0.07],
    ]) {
      const top = base - wallH - roofH * win[0];
      const bottom = base - wallH - roofH * (win[0] - win[1]);
      ctx.fillRect(cx - width * win[2], top, width * win[2] * 2, bottom - top);
    }
  }

  /// 走査線（画面全体にうっすら）
  _scanlines(ctx, w, h) {
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    for (let y = 0; y < h; y += 6) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
  }

  /// 浮遊するリング
  _rings(ctx, w, h) {
    const rings = [
      [0.16, 0.16, 52.0, 0.13],
      [0.82, 0.1, 34.0, 0.12],
      [0.7, 0.3, 20.0, 0.1],
    ];
    for (const r of rings) {
      const cx = w * r[0];
      const cy = h * r[1];
      ctx.strokeStyle = `rgba(${TECH},${r[3]})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r[2], 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeStyle = `rgba(${TECH},${r[3] * 0.7})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r[2] * 0.58, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  _horizonLine(ctx, w, horizon) {
    ctx.strokeStyle = `rgba(${TECH},0.42)`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, horizon);
    ctx.lineTo(w, horizon);
    ctx.stroke();
  }

  _snow(ctx, w, h) {
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    for (const s of SNOW) {
      ctx.beginPath();
      ctx.arc(s.x * w, s.y * h, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}
