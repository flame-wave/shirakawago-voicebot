// 質問の記録（lib/question_log.dart の移植）。
//
// 音声そのものは保存しない（プライバシー配慮・容量）。
// 認識されたテキストは、頻出質問の分析に必要なため保存する。
// 設置時は「音声を認識し、質問内容を記録します」の掲示が必要。
//
// 記録には2つの役目がある。
//
//   1. この端末でよく聞かれた質問の順を決める（よくある質問の並び）
//      → ブラウザ内（localStorage）に持つ。送れなくても案内は成り立つ。
//   2. 職員が管理者画面で全体の傾向を見る
//      → 中継サーバへ送る。案内端末の側からは見られないようにしてある。
//
// 2つを分けているのは、観光客が触る端末に記録の閲覧口を作らないため。
// 送れなかった分は溜めておき、次に通信できたときにまとめて送る。

import { LOG_ENDPOINT } from './config.js';
import { clientId } from './deployment.js';
import { mayRecord } from './consent.js';

const KEY = 'shirakawa_question_log';

/// まだ送れていない分の置き場所
const OUTBOX_KEY = 'shirakawa_log_outbox';

/// 溜めすぎるとブラウザの保存領域を圧迫するため、古いものから捨てる
const MAX_ENTRIES = 5000;

/// 送れないまま溜まった分の上限。ここを超えたら古いものから諦める。
const MAX_OUTBOX = 2000;

/// 1回に送る件数。多すぎるとサーバ側で受け取りきれない。
const BATCH = 200;

/// 行の区切り。
/// 以前の版は区切りに文字としての「\n」（円記号とn）を書き込んでいたため、
/// 読むときだけは両方を受け付ける。書くときは本来の改行にする。
const SPLIT = /\\n|\n/;

export class QuestionLog {
  /// 1件記録する。失敗しても案内の動作は止めない。
  add(entry) {
    const line = JSON.stringify({
      at: entry.at.toISOString(),
      lang: entry.lang,
      recognized: entry.recognized,
      faq_id: entry.faqId ?? null,
      source: entry.source ?? (entry.faqId ? 'faq' : 'none'), // faq / ai / none
      category: entry.category,
      fallback: entry.translationFallback,
      voice: entry.voiceMode,
      place: entry.place ?? null,
    });
    this._append(KEY, line, MAX_ENTRIES);
    // 同意をいただけていない間は送らない。
    // この端末の中の記録（よくある質問の並び順に使う）だけを残す。
    if (LOG_ENDPOINT && mayRecord()) this._append(OUTBOX_KEY, line, MAX_OUTBOX);
  }

  _append(key, line, limit) {
    try {
      const lines = this._lines(key);
      lines.push(line);
      while (lines.length > limit) lines.shift();
      localStorage.setItem(key, lines.join('\n'));
    } catch (e) {
      console.warn('質問ログの記録に失敗（動作は継続）:', e);
    }
  }

  /// 溜まっている分を中継サーバへ送る。まだ残っていれば true を返す。
  ///
  /// 案内の邪魔をしないよう、失敗しても黙って諦める（次の機会に送り直す）。
  /// 送れた分だけを消すので、送っている間に増えた分を取りこぼさない。
  async flush() {
    if (!LOG_ENDPOINT || !mayRecord()) return false;
    const lines = this._lines(OUTBOX_KEY);
    if (lines.length === 0) return false;

    const batch = lines.slice(0, BATCH);
    const entries = [];
    for (const line of batch) {
      try {
        entries.push(JSON.parse(line));
      } catch (_) {
        // 壊れた行は送らずに捨てる
      }
    }

    try {
      const res = await fetch(LOG_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client: clientId, entries }),
      });
      if (!res.ok) {
        console.info('質問記録を送れませんでした（後でやり直します）:', res.status);
        return false;
      }
    } catch (e) {
      console.info('質問記録を送れませんでした（後でやり直します）:', e?.name ?? e);
      return false;
    }

    const rest = this._lines(OUTBOX_KEY).slice(batch.length);
    try {
      localStorage.setItem(OUTBOX_KEY, rest.join('\n'));
    } catch (_) {
      // 消せなかった場合は同じものを再び送るが、集計側で取り除ける
    }
    return rest.length > 0;
  }

  /// まだ送れていない件数（職員用の設定画面に出す）
  get pendingCount() {
    return this._lines(OUTBOX_KEY).length;
  }

  /// この端末の記録の件数（よくある質問の並び順に使っているもの）
  get localCount() {
    return this._lines(KEY).length;
  }

  /// この端末に残っている記録を消す（本番を始める前に、試しの頃の記録を消すため）。
  ///
  /// 消すのは2つ。
  ///   ・この端末の記録 … よくある質問の並び順に使っている。試しの頃の質問で
  ///                     並び順が偏らないように消す
  ///   ・送れていない記録 … 中継サーバも、消した日より前の記録は受け取らない
  ///                     ようになっているが、端末にも残さない方が分かりやすい
  clearLocal() {
    try {
      localStorage.removeItem(KEY);
      localStorage.removeItem(OUTBOX_KEY);
    } catch (_) {
      // 消せなくても案内は続けられる
    }
  }

  _lines(key = KEY) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return [];
      return raw.split(SPLIT).filter((l) => l.trim() !== '');
    } catch (_) {
      return [];
    }
  }

  /// この端末の記録を読み出す（よくある質問の並び順に使う）。壊れた行は飛ばす。
  readAll() {
    const entries = [];
    for (const line of this._lines()) {
      try {
        const j = JSON.parse(line);
        entries.push({
          at: new Date(j.at ?? 0),
          lang: j.lang ?? '',
          recognized: j.recognized ?? '',
          faqId: j.faq_id ?? null,
          source: j.source ?? (j.faq_id ? 'faq' : 'none'),
          category: j.category ?? '',
          translationFallback: j.fallback ?? false,
          voiceMode: j.voice ?? '',
          place: j.place ?? null,
        });
      } catch (_) {
        // 1行壊れていても他は読める
      }
    }
    return entries;
  }
}

/// 集計結果。よくある質問の並び順に使う。
/// 職員向けの集計は管理者画面（admin/）が中継サーバの記録から作る。
export function logStats(entries) {
  const byLanguage = {};
  const matchedCount = {};
  const unmatchedCount = {};
  let matched = 0;

  for (const e of entries) {
    byLanguage[e.lang] = (byLanguage[e.lang] ?? 0) + 1;
    if (e.faqId) {
      matched++;
      matchedCount[e.faqId] = (matchedCount[e.faqId] ?? 0) + 1;
    } else if (e.recognized !== '') {
      const key = e.recognized.trim();
      unmatchedCount[key] = (unmatchedCount[key] ?? 0) + 1;
    }
  }

  const sorted = (m) =>
    Object.fromEntries(Object.entries(m).sort((a, b) => b[1] - a[1]));

  return {
    total: entries.length,
    matched,
    /// FAQで答えられた割合。職員に回さず完結できた割合の目安。
    matchRate: entries.length === 0 ? 0 : matched / entries.length,
    byLanguage,
    topMatched: sorted(matchedCount),
    topUnmatched: sorted(unmatchedCount),
  };
}
