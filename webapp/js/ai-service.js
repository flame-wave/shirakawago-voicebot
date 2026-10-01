// AI回答の問い合わせ（第3段）。
//
// 質問回答集で答えられなかったときだけ使う。
// 中継サーバ（server/api/ask.php）に質問を送り、資料をもとにした回答を受け取る。
// APIキーはこちらには無く、中継サーバの中だけにある。
//
// 【考え方】
// ここは「答えられれば助かる」補助であって、頼るものではない。
// 通信が遅い・止まっている・答えが出ない、のどれでも静かに諦めて、
// 呼び出し側は職員案内に切り替える。観光客を待たせないことを優先する。

import { AI_ENDPOINT, AI_TIMEOUT_MS } from './config.js';

export class AiService {
  get available() {
    return AI_ENDPOINT !== '';
  }

  /// 回答が得られれば { answer, sources }、駄目なら null を返す。
  /// 例外は投げない（案内を止めないため）。
  /// place はいまいる案内所。中継サーバ側で渡す資料を絞るのに使う。
  async ask(question, lang, place = '') {
    if (!this.available) return null;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), AI_TIMEOUT_MS);

    try {
      const res = await fetch(AI_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, lang, place: place ?? '' }),
        signal: controller.signal,
      });
      if (!res.ok) {
        console.warn('AI回答の中継が応答しません:', res.status);
        return null;
      }
      const data = await res.json();
      if (!data || typeof data.answer !== 'string' || data.answer.trim() === '') {
        // 資料から答えられなかった場合。これは異常ではない。
        console.info('AIは答えませんでした:', data?.reason ?? 'not_found');
        return null;
      }
      return {
        answer: data.answer.trim(),
        sources: Array.isArray(data.sources) ? data.sources : [],
      };
    } catch (e) {
      // 時間切れ・通信断。どちらも職員案内に回せばよい。
      console.warn('AI回答を受け取れません:', e?.name ?? e);
      return null;
    } finally {
      clearTimeout(timer);
    }
  }
}
