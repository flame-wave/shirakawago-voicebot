// 画像（キャラクターの絵・回答の写真）を読む。
//
// ふだんはロリポップ（ASSET_BASE）から読む。そこに無ければ GitHub（REMOTE_ASSET_BASE）から読む。
// 管理画面から足した絵や写真は GitHub にしか無いので、FTP で上げ直さなくても案内端末に出る。
// 管理画面は差し替えのたびに新しいファイル名を付けるので、古い絵が残って見えることも無い。

import { ASSET_BASE, REMOTE_ASSET_BASE } from './config.js';

/// img に画像を読ませる。path は assets/ から先（例: 'character/main.png'）。
export function loadImage(img, path) {
  img.dataset.asset = path;
  img.dataset.remote = '';
  img.src = `${ASSET_BASE}${path}`;
}

/// 読めなかったときに呼ぶ。まだ GitHub を試していなければ試して true を返す。
/// false が返ったら、どちらにも無い（呼び出し側で代わりの表示をする）。
export function retryRemote(img) {
  const path = img.dataset.asset;
  if (!REMOTE_ASSET_BASE || !path || img.dataset.remote) return false;
  img.dataset.remote = '1';
  img.src = `${REMOTE_ASSET_BASE}${path}`;
  return true;
}
