// この端末がどの役割で使われているかを決める。
//
// 同じファイルを3通りの使い方で共有する。開く URL だけで切り替わるので、
// 置くファイルは1組でよい（別々に作ると、片方だけ更新し忘れる）。
//
//   webapp/?place=バスターミナル … バスターミナルの据え置き端末
//   webapp/?place=であいの館     … であいの館の据え置き端末
//   webapp/                      … 観光客が自分のスマートフォンで開く
//
// 据え置きと観光客で違うのは、主に次の2点。
//
//   |              | 据え置き           | 観光客のスマートフォン |
//   |--------------|--------------------|------------------------|
//   | 詳しい案内   | QRコード（読み取る）| リンク（押して開く）   |
//   | 現在地       | URLで固定          | 位置情報で判定         |
//
// 据え置きの画面でリンクを出しても押せる端末が無く、
// 観光客の手元でQRコードを出しても自分の画面は読み取れない。

import { PLACE } from './config.js';

/// 据え置き端末の役割を覚えておく場所。
/// キオスク端末が何かの拍子にURLを見失っても、役割が変わらないようにする。
const ROLE_KEY = 'shirakawa_role';

/// 観光客の端末を、統計の上でこう呼ぶ
export const VISITOR = '観光客';

function saved() {
  try {
    return localStorage.getItem(ROLE_KEY) || '';
  } catch (_) {
    return '';
  }
}

function remember(place) {
  try {
    localStorage.setItem(ROLE_KEY, place);
  } catch (_) {
    // 保存できない設定でも、その場の動作は変わらない
  }
}

const params = new URLSearchParams(window.location.search);
const fromUrl = (params.get('place') || '').trim();

// URLの指定が最優先。次に前回の役割、最後に config.js の既定。
let place = fromUrl || saved();
if (!place && PLACE && PLACE !== 'auto') place = PLACE;
if (fromUrl) remember(fromUrl);

/// 据え置き端末かどうか。場所が決まっていれば据え置きとみなす。
export const isKiosk = place !== '';

/// 据え置き端末の設置場所。観光客の端末では ''（位置情報で判定する）。
export const fixedPlace = place;

/// 統計をこの名前で分ける。据え置きは設置場所、それ以外は「観光客」。
export const clientId = isKiosk ? place : VISITOR;

/// 詳しい案内の出し方。据え置きはQRコード、手元の端末はリンク。
export const showQr = isKiosk;
export const showLink = !isKiosk;

/// URLで指定されたキャラクター。
///
///   webapp/?place=バスターミナル&character=yuru
///
/// 据え置きを2台置いて別々のキャラクターにしたいときや、
/// 見え方を確かめたいときに使う。指定が無ければ空。
export const fixedCharacter = (params.get('character') || '').trim();

/// 職員用の設定（読み上げの声の選択）を出すかどうか。
///
/// 画面の長押しのような隠し操作にすると、観光客に偶然見つかる。
/// URLを知っている人だけが開ける形にして、端末にブックマークしておく。
///   webapp/?place=バスターミナル&setup=1
export const showSetup = params.get('setup') === '1';
