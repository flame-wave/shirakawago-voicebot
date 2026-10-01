// いまどの案内所の近くにいるかを決める部品。
//
// ロッカーやATMのように、案内所ごとに答えが違う質問がある。
// 近くの案内所が分かればその回答を、どちらからも離れていれば
// 場所に依存しない「共通」の回答を出すために使う。
//
// 判定の順番:
//   1. 職員が選んだ場所（この端末に覚えさせたもの）
//   2. 設定で決め打ちした場所（据え置きの案内端末はこれ）
//   3. 位置情報から、範囲内で最も近い案内所
//   4. どれも分からなければ「共通」だけで案内する
//
// 位置情報は判定にしか使わず、送信も保存もしない。

import { PLACE, PLACE_TIMEOUT_MS } from './config.js';

const SAVED_KEY = 'shirakawa_place';

/// 「どちらでもない」を選んだときに覚えておく印
export const NOWHERE = 'どちらでもない';

/// 2点間のおおよその距離（メートル）
function distance(lat1, lon1, lat2, lon2) {
  const R = 6371000; // 地球の半径
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export class PlaceService {
  constructor() {
    this.places = []; // faq.json から渡される
    this.current = null; // 判定できた案内所の名前。null なら共通のみ
    this.how = 'unknown'; // checking / gps / manual / config / far / denied / pending
    this._denied = false; // 位置情報を断られたか
    this.fixedAt = 0; // 最後に位置情報で判定した時刻
  }

  setPlaces(places) {
    this.places = Array.isArray(places) ? places : [];
  }

  get names() {
    return this.places.map((p) => p.name);
  }

  /// その言語で画面に出す名前。
  ///
  /// 日本語の名前は、FAQの「設置場所」と突き合わせるための鍵として使う。
  /// 画面にはその言語の名前を出さないと、読めない方には選びようがない。
  /// 質問回答集に名前が入っていない言語は、日本語のまま出す。
  labelFor(name, lang) {
    if (!name || lang === 'ja') return name;
    const place = this.places.find((p) => p.name === name);
    return place?.labels?.[lang] || name;
  }

  /// 職員が選んだ場所を覚える。'' を渡すと自動判定に戻す。
  remember(name) {
    try {
      if (name) localStorage.setItem(SAVED_KEY, name);
      else localStorage.removeItem(SAVED_KEY);
    } catch (_) {
      // 保存できない環境でも、その場の選択は効く
    }
    this.current = name === NOWHERE ? null : (name || null);
    this.how = name ? 'manual' : 'pending';
  }

  get saved() {
    try {
      return localStorage.getItem(SAVED_KEY) || '';
    } catch (_) {
      return '';
    }
  }

  /// 位置情報が既に許可されているかを調べる。
  ///
  /// 開くなり許可を求めると驚かせてしまうので、
  /// まだ許可されていない場合は、利用者が押したときに求める。
  async permissionGranted() {
    try {
      const status = await navigator.permissions?.query({ name: 'geolocation' });
      return status?.state === 'granted';
    } catch (_) {
      return false; // 調べられないブラウザでは、押されるまで待つ
    }
  }

  /// 現在地を決める。時間がかかることがあるので、呼び出し側は待たずに進めてよい。
  ///
  /// ask を true にすると、まだ許可されていなくても位置情報を求める
  /// （利用者が「現在地を使う」を押したとき）。
  async resolve({ ask = false } = {}) {
    const saved = this.saved;
    if (saved) {
      this.current = saved === NOWHERE ? null : saved;
      this.how = 'manual';
      return this.current;
    }

    if (PLACE && PLACE !== 'auto') {
      this.current = PLACE;
      this.how = 'config';
      return this.current;
    }

    if (!ask && !(await this.permissionGranted())) {
      this.current = null;
      this.how = 'pending'; // 利用者が押すまで待つ
      return null;
    }

    const near = await this._byLocation();
    this.current = near;
    this.how = near ? 'gps' : this._denied ? 'denied' : 'far';
    this.fixedAt = Date.now();
    return this.current;
  }

  /// 歩いて移動している人のために、古くなった判定を取り直す。
  ///
  /// 案内所を選んで固定している場合や、位置情報が使えない場合は何もしない。
  /// 時間がかかるので、呼び出し側は待たずに進めてよい。
  async refreshIfStale(maxAgeMs = 120000) {
    if (this.saved || (PLACE && PLACE !== 'auto')) return false;
    if (this.how !== 'gps' && this.how !== 'far') return false;
    if (Date.now() - this.fixedAt < maxAgeMs) return false;

    const before = this.current;
    await this.resolve({ ask: true }); // 一度許可されているので確認は出ない
    return this.current !== before;
  }

  /// 位置情報から、範囲内で最も近い案内所を返す。無ければ null。
  async _byLocation() {
    this._denied = false;
    if (this.places.length === 0 || !navigator.geolocation) return null;

    let position;
    try {
      position = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: false, // 案内所の判別には十分で、電池にも優しい
          timeout: PLACE_TIMEOUT_MS,
          maximumAge: 5 * 60 * 1000,
        });
      });
    } catch (e) {
      // 許可されなかった・取得できなかった。共通の回答で案内する。
      console.info('現在地を取得できません:', e?.message ?? e);
      this._denied = true;
      return null;
    }

    const { latitude, longitude, accuracy } = position.coords;
    let best = null;
    let bestDistance = Infinity;
    for (const place of this.places) {
      const d = distance(latitude, longitude, place.lat, place.lon);
      // 測定誤差のぶんだけ範囲を広げて判定する
      const limit = (place.radius ?? 250) + Math.min(accuracy ?? 0, 200);
      if (d <= limit && d < bestDistance) {
        best = place.name;
        bestDistance = d;
      }
    }
    if (best) {
      console.info(`現在地: ${best}（約${Math.round(bestDistance)}m）`);
    } else {
      console.info('どの案内所からも離れているため、共通の案内をします');
    }
    return best;
  }
}
