// キャラクターの表示（lib/character_view.dart の移植）。
//
// 立ち絵は切り取らず全身をそのまま使い、
// ゆっくり上下に動かして呼吸しているように見せる（動きはCSS側）。
//
// 【複数のキャラクターを切り替えられる】
// どのキャラクターを使うかは「キャラクター」シートで決める。
// 職員は既定を決め、利用者は画面で選び直せる。選んだものはその端末に残る。
//
// 【表情が1枚しかなくても動く】
// 聞き取り中・話している間の絵が無ければ、通常の絵をそのまま使う。
// 立ち絵が1枚だけのキャラクターでも、そのまま案内に使える。
//
// 【立ち絵ごとに吹き出しの位置が変わる】
// 縦長の人物と、横長のゆるキャラでは、口の位置も体の幅も違う。
// 同じ数字のままだと吹き出しの尻尾が口から外れるので、
// キャラクターを変えるたびにCSSの変数を書き換えている。

import { ASSET_BASE } from './config.js';
import { fixedCharacter } from './deployment.js';

/// キャラクターの状態。システムの状況に対応する。
export const CharacterState = {
  idle: 'idle', // 待機中
  listening: 'listening', // 聞き取り中
  talking: 'talking', // 回答中（喋っている）
};

/// 選んだキャラクターを覚えておく場所
const CHOICE_KEY = 'shirakawa_character';

/// それを覚えたときに「職員が決めた既定」が何だったかを控えておく場所。
///
/// 利用者の選択をそのまま優先すると、職員が管理画面で既定を変えても、
/// 一度でも画面で選んだ端末には永久に古いキャラクターが立ち続ける。
/// 据え置き端末は同じブラウザを使い続けるので、これが起きると直せない。
/// そこで「職員が既定を変えたら、覚えている選択は捨てる」ことにする。
const CHOICE_BASE_KEY = 'shirakawa_character_base';

/// 「キャラクター」シートがまだ無いときに使うもの。
/// これまでの3枚組をそのまま既定にしてある。
const FALLBACK = {
  id: 'navi',
  name: 'ナビ',
  idle: 'idle.png',
  listening: 'listening.png',
  talking: 'talking.png',
  aspect: 0.538,
  mouth: 0.14,
  face: 0.31,
  scale: 1,
  rise: 0,
};

const PLACEHOLDER_ICON = {
  idle: '🙂',
  listening: '👂',
  talking: '💬',
};

export class CharacterView {
  constructor(root, stage) {
    this.root = root;
    /// 吹き出しの位置を決める変数を書き込む先
    this.stage = stage ?? root.closest('.stage') ?? document.documentElement;
    this.img = root.querySelector('.character-img');
    this.placeholder = root.querySelector('.character-placeholder');
    /// 表情の画像が無い場合は通常の絵に落とす。
    /// 立ち絵が1枚しか無い段階でも表示できるようにするため。
    this.img.addEventListener('error', () => this._onMissing());
    this._state = CharacterState.idle;
    this._missing = new Set();
    this._list = [FALLBACK];
    this._current = FALLBACK;
    this._preview = null;   // 調整中の一時的な上書き
    this._applyShape();
    this.setState(CharacterState.idle);
  }

  /// 選べるキャラクターの一覧（質問回答集から渡される）
  get list() {
    return this._list;
  }

  get current() {
    return this._current;
  }

  /// 一覧を受け取り、覚えている選択か既定のものを立てる。
  setList(characters) {
    const list = (Array.isArray(characters) ? characters : [])
      .filter((c) => c && c.id && c.idle);
    this._list = list.length > 0 ? list : [FALLBACK];
    // URLの指定 → その端末で選ばれたもの → 職員が決めた既定、の順。
    // ただし職員が既定を変えていれば、その端末の記憶より職員の設定を通す。
    const base = this._defaultId();
    this.choose(fixedCharacter || this._savedFor(base) || base);
  }

  /// 覚えている選択。職員が既定を変えていれば忘れて '' を返す。
  _savedFor(defaultId) {
    const saved = this.saved;
    if (!saved) return '';
    let base = '';
    try {
      base = localStorage.getItem(CHOICE_BASE_KEY) || '';
    } catch (_) {
      // 読めないときは、職員の設定を通す側に倒す
    }
    if (base === defaultId) return saved;
    this._forget();
    return '';
  }

  _forget() {
    try {
      localStorage.removeItem(CHOICE_KEY);
      localStorage.removeItem(CHOICE_BASE_KEY);
    } catch (_) {
      // 消せなくても、この回は職員の設定が通る
    }
  }

  _defaultId() {
    const marked = this._list.find((c) => c.default);
    return (marked ?? this._list[0]).id;
  }

  get saved() {
    try {
      return localStorage.getItem(CHOICE_KEY) || '';
    } catch (_) {
      return '';
    }
  }

  /// キャラクターを選ぶ。覚えていないIDなら既定に戻す。
  choose(id, remember = false) {
    const found = this._list.find((c) => c.id === id);
    this._current = found ?? this._list.find((c) => c.default) ?? this._list[0];
    this._missing.clear();   // 別のキャラクターなので、欠けている絵の記憶は捨てる

    if (remember) {
      try {
        localStorage.setItem(CHOICE_KEY, this._current.id);
        // 「どの既定のときに選んだのか」も一緒に控える
        localStorage.setItem(CHOICE_BASE_KEY, this._defaultId());
      } catch (_) {
        // 保存できなくても、その場の選択は効く
      }
    }

    this._applyShape();
    this.setState(this._state);
  }

  /// 調整中だけ、値を一時的に上書きする（画面を見ながら合わせるため）。
  /// null を渡すと、質問回答集の値に戻す。保存はしない。
  preview(values) {
    this._preview = values || null;
    this._applyShape();
    this.setState(this._state);
  }

  /// いま効いている値（調整中なら上書きした値）
  get shape() {
    const c = this._current;
    return {
      scale: this._preview?.scale ?? c.scale ?? 1,
      rise: this._preview?.rise ?? c.rise ?? 0,
      mouth: this._preview?.mouth ?? c.mouth ?? 0.14,
      face: this._preview?.face ?? c.face ?? 0.31,
    };
  }

  /// 立ち絵の形を、吹き出しの位置を決める変数に反映する
  _applyShape() {
    const c = { ...this._current, ...(this._preview ?? {}) };
    const set = (name, value) => {
      if (typeof value === 'number' && value > 0) {
        this.stage.style.setProperty(name, String(value));
      } else {
        this.stage.style.removeProperty(name);   // 既定値（CSS側）に戻す
      }
    };
    set('--char-aspect', c.aspect);
    set('--mouth-ratio', c.mouth);
    set('--face-ratio', c.face);
    set('--char-scale', c.scale);

    // 以前は縦長の立ち絵を画面の端から少しはみ出させて大きく見せていたが、
    // 細身のキャラクター（ゆい＝縦横比0.36）では切り落とす幅が体の2割を超え、
    // 腕や裾が画面の外に消えてしまった。見せたいものを切ってしまうので、
    // はみ出しはやめて必ず全身が入るようにする。
    // 変数は残してある（CSS側で位置の式に使っているため）。
    this.stage.style.setProperty('--char-bleed', '0');

    // 立ち位置の高さ。0 は下端（人物が地面に立つ）、1 は上端。
    // 0 も意味のある値なので、set（0 を「未設定」とみなす）は使わない。
    this.stage.style.setProperty('--char-rise', String(c.rise ?? 0));
  }

  setState(state) {
    this._state = state;
    this.placeholder.textContent = PLACEHOLDER_ICON[state];

    // 欠けている表情は通常の絵で代える
    const name = this._missing.has(state)
      ? this._current.idle
      : (this._current[state] || this._current.idle);

    if (this._missing.has(CharacterState.idle) && this._missing.has(state)) {
      this._showPlaceholder();
      return;
    }
    this.img.hidden = false;
    this.placeholder.hidden = true;
    this.img.src = `${ASSET_BASE}character/${name}`;
  }

  _onMissing() {
    this._missing.add(this._state);
    if (this._state !== CharacterState.idle && !this._missing.has(CharacterState.idle)) {
      // 通常の絵に落として表示を続ける
      this.img.src = `${ASSET_BASE}character/${this._current.idle}`;
      return;
    }
    this._missing.add(CharacterState.idle);
    this._showPlaceholder();
  }

  /// 画像がまだ無いときの仮表示（状態ごとにしるしを変える）
  _showPlaceholder() {
    this.img.hidden = true;
    this.placeholder.hidden = false;
  }
}
