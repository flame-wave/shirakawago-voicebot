// FAQデータの取得（lib/faq_repository.dart の移植）。
//
// 方針は「オフライン優先」:
//   1. 起動時はローカル（キャッシュ→同梱）を即座に読み、すぐ使える状態にする
//   2. その裏で通信を試み、成功したら差し替える
// 通信が遅い・繋がらない場合でも、起動が止まることはない。
//
// 端末内ファイルの代わりに localStorage を使う。
// ブラウザを閉じても残るので、次回以降も通信なしで最新版から始められる。

import { ASSET_BASE, REMOTE_URL, FETCH_TIMEOUT_MS } from './config.js';

const CACHE_KEY = 'shirakawa_faq_cache';

const SOURCE_LABEL = {
  remote: '最新',
  cache: '保存済み',
  bundled: '初期データ',
};

function versionOf(raw) {
  try {
    return JSON.parse(raw).version ?? '不明';
  } catch (_) {
    return '不明';
  }
}

/// 最低限の妥当性チェック。faqs が配列で1件以上あること。
function isValid(raw) {
  try {
    const decoded = JSON.parse(raw);
    if (typeof decoded !== 'object' || decoded === null) return false;
    return Array.isArray(decoded.faqs) && decoded.faqs.length > 0;
  } catch (_) {
    return false;
  }
}

function data(raw, source) {
  return { json: raw, source, version: versionOf(raw), sourceLabel: SOURCE_LABEL[source] };
}

export class FaqRepository {
  /// 起動時に呼ぶ。キャッシュがあればそれを、無ければ同梱データを返す。
  async loadLocal() {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        if (isValid(cached)) return data(cached, 'cache');
        console.warn('キャッシュが壊れているため無視します');
        localStorage.removeItem(CACHE_KEY);
      }
    } catch (e) {
      console.warn('キャッシュ読み込みエラー:', e);
    }

    const res = await fetch(`${ASSET_BASE}faq.json`, { cache: 'no-cache' });
    const raw = await res.text();
    return data(raw, 'bundled');
  }

  /// 裏で呼ぶ。取得できなければ null を返すだけで、例外は投げない。
  async fetchRemote() {
    if (REMOTE_URL === '') {
      console.info('配信URLが未設定のため、オンライン更新はしません');
      return null;
    }

    let raw;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
      const res = await fetch(REMOTE_URL, { signal: controller.signal, cache: 'no-cache' });
      clearTimeout(timer);
      if (!res.ok) {
        console.warn(`取得失敗: HTTP ${res.status}`);
        return null;
      }
      raw = await res.text();
    } catch (e) {
      console.warn('オンライン取得に失敗（オフラインで継続）:', e);
      return null;
    }

    // 壊れたデータでキャッシュを上書きしないよう、保存前に検査する
    if (!isValid(raw)) {
      console.warn('取得したデータが不正な形式のため破棄します');
      return null;
    }

    // 保存の失敗は取得の失敗とは別扱いにする。
    // 保存できなくても今回取得したデータは使えるため、ここで捨てない。
    this._saveCache(raw);

    return data(raw, 'remote');
  }

  _saveCache(raw) {
    try {
      localStorage.setItem(CACHE_KEY, raw);
    } catch (e) {
      console.warn('キャッシュ保存に失敗（動作は継続）:', e);
    }
  }
}
