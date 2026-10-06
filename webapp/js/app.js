// 画面と一連の流れの組み立て（lib/main.dart の移植）。
//
// 「押して話す → 音声認識 → FAQ検索 → 回答表示＆音声再生」の流れを
// ブラウザ内で完結させる。各処理は差し替え可能な部品として分離してある。

import { LOG_FLUSH_INTERVAL_MS, CONSENT_IDLE_MS, ASSET_BASE } from './config.js';
import { LANGUAGES, LABEL, uiString } from './app-language.js';
import { FaqService } from './faq-service.js';
import { FaqRepository } from './faq-repository.js';
import { VoiceService } from './voice-service.js';
import { SpeechService } from './speech-service.js';
import { AiService } from './ai-service.js';
import { PlaceService, NOWHERE } from './place-service.js';
import { BackgroundView } from './background.js';
import { CharacterView, CharacterState } from './character.js';
import { AnswerView } from './answer-view.js';
import { QuestionLog, logStats } from './question-log.js';
import { SetupScreen } from './setup-screen.js';
import { TunePanel } from './tune-panel.js';
import { ConsentScreen, consentState } from './consent.js';
import { fixedPlace, isKiosk, showSetup, showTune } from './deployment.js';

// --- 部品（差し替え可能な単位） ---
const speech = new SpeechService(); // 音声認識
const faqService = new FaqService(); // FAQ検索
const repo = new FaqRepository(); // FAQデータの取得
const voice = new VoiceService(); // 読み上げ（音声ファイル／ブラウザ音声）
const ai = new AiService(); // 質問回答集で答えられないときの補助
const places = new PlaceService(); // いまどの案内所の近くにいるか
const log = new QuestionLog(); // 質問の記録

const el = {
  dataSource: document.getElementById('dataSource'),
  dataVersion: document.getElementById('dataVersion'),
  dataStatus: document.getElementById('dataStatus'),
  questionBubble: document.getElementById('questionBubble'),
  talkButton: document.getElementById('talkButton'),
  languages: document.getElementById('languages'),
  placeButton: document.getElementById('placeButton'),
  placeMenu: document.getElementById('placeMenu'),
  placeMenuTitle: document.getElementById('placeMenuTitle'),
  placeMenuList: document.getElementById('placeMenuList'),
  placeMenuClose: document.getElementById('placeMenuClose'),
  characterButton: document.getElementById('characterButton'),
  characterMenu: document.getElementById('characterMenu'),
  characterMenuTitle: document.getElementById('characterMenuTitle'),
  characterMenuList: document.getElementById('characterMenuList'),
  characterMenuClose: document.getElementById('characterMenuClose'),
  faqStrip: document.getElementById('faqStrip'),
  faqTrack: document.getElementById('faqTrack'),
  answerPhoto: document.querySelector('.answer-photo'),
  photoView: document.getElementById('photoView'),
  photoViewImg: document.getElementById('photoViewImg'),
  photoViewClose: document.getElementById('photoViewClose'),
  typedForm: document.getElementById('typedForm'),
  typedInput: document.getElementById('typedInput'),
  typedSend: document.getElementById('typedSend'),
};

const background = new BackgroundView(document.getElementById('background'));
const character = new CharacterView(
  document.getElementById('character'), document.getElementById('stage'));
const answerView = new AnswerView(document.getElementById('answer'));
const setupScreen = new SetupScreen(document.getElementById('setupScreen'), log, voice);
const consentScreen = new ConsentScreen(document.getElementById('consentScreen'));
const tunePanel = new TunePanel(
  document.getElementById('tunePanel'), character,
  (lang) => changeLanguage(lang));

// --- 画面の状態 ---
const state = {
  listening: false,
  recognized: '',
  answer: '',
  photo: '',
  link: '',
  isFallback: false, // 翻訳未整備で日本語を表示中か
  isAi: false, // AIが資料から作った回答を表示中か
  lang: 'ja', // 選択中の言語
  place: null, // いまいる案内所（null なら共通の回答だけを使う）
  dataVersion: '',
  dataSource: '',
};

function render() {
  renderPlacePill();
  el.dataSource.textContent = state.dataSource;
  el.dataVersion.textContent = state.dataVersion;

  // 聞き取った質問（観光客側の発話）
  const hasQuestion = state.recognized !== '';
  el.questionBubble.hidden = !hasQuestion;
  if (hasQuestion) {
    el.questionBubble.textContent = `${uiString('question', state.lang)}: ${state.recognized}`;
  }

  answerView.update({
    answer: state.answer,
    photo: state.photo,
    link: state.link,
    lang: state.lang,
    isFallback: state.isFallback,
    isAi: state.isAi,
    placeholder: uiString('prompt', state.lang),
  });

  el.talkButton.textContent = state.listening
    ? uiString('listening', state.lang)
    : uiString('pressToTalk', state.lang);
  el.talkButton.classList.toggle('listening', state.listening);
  el.talkButton.disabled = !speech.available;

  el.typedInput.placeholder = uiString('typeInstead', state.lang);
  el.typedSend.textContent = uiString('send', state.lang);

  for (const button of el.languages.children) {
    button.classList.toggle('selected', button.dataset.lang === state.lang);
  }
}

function buildLanguageButtons() {
  // 言語の切り替えは自動判定ではなく手動にしている。音声認識は
  // 「これから何語が話されるか」を先に指定する必要があるため。
  // 騒音下では自動判定が誤りやすく、観光客が自分で選ぶ方が確実。
  el.languages.innerHTML = '';
  for (const lang of LANGUAGES) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'lang-button';
    button.dataset.lang = lang;
    button.textContent = LABEL[lang];
    button.addEventListener('click', () => changeLanguage(lang));
    el.languages.appendChild(button);
  }
}

/// 現在地の表示。押すと選び直せる。
///
/// 観光客のスマートフォンでは、開いた瞬間に位置情報を求めると驚かせるため、
/// すでに許可されている場合だけ自動で調べ、そうでなければ
/// この表示を押したときに求める。
function renderPlacePill() {
  if (!el.placeButton || isKiosk) return; // 据え置きは場所を固定しているので出さない
  const how = places.how;
  let label;
  if (how === 'checking') {
    label = uiString('placeChecking', state.lang);
  } else if (state.place) {
    label = `📍 ${places.labelFor(state.place, state.lang)}`;
  } else if (how === 'manual' || how === 'far') {
    label = `📍 ${uiString('placeFar', state.lang)}`;
  } else {
    label = `📍 ${uiString('placeUnset', state.lang)}`;
  }
  el.placeButton.textContent = label;
}

function openPlaceMenu() {
  el.placeMenuTitle.textContent = uiString('placeTitle', state.lang);
  el.placeMenuClose.textContent = uiString('close', state.lang);
  el.placeMenuList.innerHTML = '';

  const choices = [
    { value: 'auto', label: uiString('placeAuto', state.lang) },
    // 選んだ結果は日本語の名前で覚える（FAQとの突き合わせに使うため）が、
    // 画面に出すのはその言語の名前にする
    ...places.names.map((name) => ({
      value: name,
      label: places.labelFor(name, state.lang),
    })),
    { value: NOWHERE, label: uiString('placeNone', state.lang) },
  ];
  const saved = places.saved || 'auto';

  for (const choice of choices) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = choice.label;
    if (choice.value === saved) button.classList.add('selected');
    button.addEventListener('click', () => choosePlace(choice.value));
    el.placeMenuList.appendChild(button);
  }

  const hint = document.createElement('p');
  hint.className = 'hint-line';
  hint.textContent = uiString('placeHint', state.lang);
  el.placeMenuList.appendChild(hint);

  el.placeMenu.hidden = false;
}

function renderCharacterPill() {
  if (!el.characterButton) return;
  el.characterButton.textContent = `🧑 ${character.current.name}`;
}

function openCharacterMenu() {
  el.characterMenuTitle.textContent = uiString('characterTitle', state.lang);
  el.characterMenuClose.textContent = uiString('close', state.lang);
  el.characterMenuList.innerHTML = '';

  for (const item of character.list) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'char-choice';
    if (item.id === character.current.id) button.classList.add('selected');

    // 絵を見せないと選べない（名前だけでは、どれが誰か分からない）
    const img = document.createElement('img');
    img.src = `${ASSET_BASE}character/${item.idle}`;
    img.alt = '';
    img.loading = 'lazy';
    const label = document.createElement('span');
    label.textContent = item.name;
    button.append(img, label);

    button.addEventListener('click', () => {
      character.choose(item.id, true);
      renderCharacterPill();
      el.characterMenu.hidden = true;
      // 選んだ人がすぐ分かるよう、その場で喋っている表情にはしない
      character.setState(CharacterState.idle);
      background.draw();
    });
    el.characterMenuList.appendChild(button);
  }

  el.characterMenu.hidden = false;
}

function wireCharacter() {
  if (!el.characterButton || !el.characterMenu) return;
  renderCharacterPill();
  el.characterButton.addEventListener('click', openCharacterMenu);
  el.characterMenuClose.addEventListener('click', () => {
    el.characterMenu.hidden = true;
  });
  // 外側を押しても閉じる
  el.characterMenu.addEventListener('click', (e) => {
    if (e.target === el.characterMenu) el.characterMenu.hidden = true;
  });
}

async function choosePlace(value) {
  el.placeMenu.hidden = true;

  if (value === 'auto') {
    places.remember('');
    places.how = 'checking';
    renderPlacePill();
    await places.resolve({ ask: true }); // ここで初めて位置情報を求める
  } else {
    places.remember(value);
  }

  state.place = places.current;
  buildChips();
  render();
  console.info('現在地:', state.place ?? '（共通のみ）');
}

/// 歩いて移動している人のために、現在地が古ければ静かに取り直す。
/// 結果が変わったときだけ画面を更新する。
async function refreshPlace() {
  const changed = await places.refreshIfStale();
  if (!changed) return;
  state.place = places.current;
  renderPlacePill();
  buildChips();
  render();
  console.info('現在地が変わりました:', state.place ?? '（共通のみ）');
}

function wirePlace() {
  if (!el.placeButton || !el.placeMenu) {
    console.warn('現在地の表示が見つかりません（画面の更新が古い可能性があります）');
    return;
  }

  // 据え置き端末は場所が動かない。
  // 観光客が押して変えられると、その案内所と違う回答が出てしまう。
  if (isKiosk) {
    el.placeButton.hidden = true;
    return;
  }

  el.placeButton.addEventListener('click', openPlaceMenu);

  // 画面に戻ってきたとき（別のアプリから戻ったときなど）に取り直す
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshPlace();
  });
  el.placeMenuClose.addEventListener('click', () => {
    el.placeMenu.hidden = true;
  });
  // 外側を押しても閉じる
  el.placeMenu.addEventListener('click', (e) => {
    if (e.target === el.placeMenu) el.placeMenu.hidden = true;
  });
}

/// よくある質問（押すだけで聞ける入口）。
///
/// 並べるものは、質問回答集のExcelで「よくある質問」に文言を入れた項目。
/// 職員がそこを直せば、この列も変わる。
///
/// 並び順は、その端末でよく聞かれた順を先にする（記録が無ければExcelの順）。
/// 日本語以外では、その言語の質問例に置き換える。
function chipLabel(faq) {
  if (state.lang === 'ja') return faq.chip;
  return (faqService.questionsFor(faq, state.lang)[0] ?? faq.chip).trim();
}

function buildChips() {
  const asked = Object.keys(logStats(log.readAll()).topMatched);
  const all = faqService.all.filter(
    (f) => f.chip && (!f.place || f.place === '共通' || f.place === state.place),
  );
  const byId = new Map(all.map((f) => [f.id, f]));

  const picked = [];
  for (const id of asked) {
    const faq = byId.get(id);
    if (faq) picked.push(faq);
  }
  for (const faq of all) {
    if (!picked.includes(faq)) picked.push(faq);
  }

  // 同じ文言が場所ごとの項目と共通版で重なることがあるので、1つにまとめる
  const chips = [];
  for (const faq of picked) {
    const text = chipLabel(faq);
    if (text !== '' && !chips.includes(text)) chips.push(text);
  }

  el.faqTrack.innerHTML = '';
  if (chips.length === 0) {
    el.faqStrip.hidden = true;
    return;
  }
  el.faqStrip.hidden = false;

  // 同じ並びを2回置き、端まで流れたら先頭に戻しても途切れないようにする
  for (let pass = 0; pass < 2; pass++) {
    for (const text of chips) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'chip';
      button.textContent = text;
      if (pass === 1) button.setAttribute('aria-hidden', 'true');
      button.addEventListener('click', () => askChip(text));
      el.faqTrack.appendChild(button);
    }
  }
  // 数が多いほどゆっくり流す（読み取れる速さを保つ）
  el.faqTrack.style.setProperty('--marquee-duration', `${Math.max(24, chips.length * 4)}s`);
}

/// よくある質問を押したとき。声で聞いたときと同じ流れにする。
async function askChip(text) {
  speech.stop(true);
  await voice.stop();
  handleQuestion(text);
}

/// 言語ボタンが押されたときの処理
async function changeLanguage(lang) {
  if (lang === state.lang) return;
  speech.stop(true); // 聞き取り中なら、その内容は前の言語のものなので捨てる
  await voice.stop();
  await voice.setLanguage(lang);
  state.lang = lang;
  state.listening = false;
  state.recognized = '';
  state.answer = '';
  state.photo = '';
  state.link = '';
  state.isFallback = false;
  state.isAi = false;
  character.setState(CharacterState.idle);
  renderPlacePill(); // 表示をその言語にする
  renderCharacterPill();
  buildChips(); // その言語の言い方に入れ替える
  render();
  console.info('言語を切り替え:', LABEL[lang]);
}

/// ボタンを押すたびに開始と終了を切り替える。
/// 押し続ける方式だと、指が少し離れただけで録音が切れてしまうため。
async function toggleListening() {
  if (state.listening) {
    speech.stop();
    return;
  }
  if (!speech.available) return;

  await voice.stop(); // 読み上げ中なら止めて質問を優先する
  state.listening = true;
  state.recognized = '';
  state.answer = '';
  state.photo = '';
  state.link = '';
  state.isFallback = false;
  state.isAi = false;
  character.setState(CharacterState.listening);
  render();
  speech.start(state.lang);
}

/// 認識した質問をFAQ検索にかけ、表示と読み上げを行う
async function handleQuestion(question) {
  state.listening = false;

  // 何も聞き取れていない場合は、案内も記録もせずに待機に戻す
  if (!question || question.trim() === '') {
    character.setState(CharacterState.idle);
    render();
    return;
  }

  state.recognized = question;
  const faq = faqService.search(question, state.lang, state.place);

  // 次の質問に備えて、現在地が古ければ裏で取り直す（この回答は待たせない）
  refreshPlace();

  if (faq == null) {
    await answerWithoutFaq(question);
    return;
  }

  const localized = faqService.answerFor(faq, state.lang);
  state.answer = localized.text;
  state.isAi = false;
  state.photo = faq.photo;
  state.link = faq.link;
  state.isFallback = localized.isFallback;
  character.setState(CharacterState.talking);
  render();

  // 音声ファイルがあればそれを、無ければブラウザ音声で読み上げる
  const mode = await voice.speak(faq, state.lang, localized);
  const note = localized.isFallback ? ' (日本語で代替)' : '';
  console.info(`読み上げ方法: ${mode} / 言語: ${LABEL[state.lang]}${note}`);

  log.add({
    at: new Date(),
    lang: state.lang,
    recognized: question,
    faqId: faq.id,
    category: faq.category,
    translationFallback: localized.isFallback,
    voiceMode: mode,
    place: state.place,
    source: 'faq',
  });
}

/// 質問回答集で答えられなかったときの流れ。
///
/// AIの中継が設定されていれば、案内資料をもとにした回答を試みる。
/// 答えが得られなければ、これまでどおり職員へ案内する。
/// 待たせないことを優先し、時間切れ・通信断はすべて職員案内に倒す。
async function answerWithoutFaq(question) {
  let result = null;

  if (ai.available) {
    state.answer = uiString('aiThinking', state.lang);
    state.photo = '';
    state.link = '';
    state.isFallback = false;
    state.isAi = false;
    character.setState(CharacterState.listening);
    render();

    result = await ai.ask(question, state.lang, state.place);
  }

  if (result) {
    state.answer = result.answer;
    state.isAi = true; // 画面に「AIが作成した回答」と断りを出す
    character.setState(CharacterState.talking);
    render();

    const mode = await voice.speakText(result.answer);
    console.info('AIが回答（根拠）:', result.sources.join(', ') || 'なし');
    log.add({
      at: new Date(),
      lang: state.lang,
      recognized: question,
      faqId: null,
      category: '',
      translationFallback: false,
      voiceMode: mode,
      place: state.place,
      source: 'ai',
    });
    return;
  }

  // 該当なし＝ガードレール発動、職員へ誘導
  const fallback = uiString('staffReferral', state.lang);
  state.answer = fallback;
  state.photo = '';
  state.link = '';
  state.isFallback = false;
  state.isAi = false;
  character.setState(CharacterState.talking);
  render();

  // 画面が見えない方にも伝わるよう、この案内も読み上げる
  const mode = await voice.speakText(fallback);
  // 答えられなかった質問こそ、FAQ拡充の材料になる
  log.add({
    at: new Date(),
    lang: state.lang,
    recognized: question,
    faqId: null,
    category: '',
    translationFallback: false,
    voiceMode: mode,
    place: state.place,
    source: 'none',
  });
}

function wireSpeech() {
  speech.onPartial = (text) => {
    state.recognized = text;
    render();
  };
  speech.onStop = () => {
    // 無音が続いて自動終了した場合も、ボタンの表示を戻す
    state.listening = false;
    render();
  };
  speech.onResult = (text) => {
    handleQuestion(text);
  };
  speech.onError = (kind) => {
    state.listening = false;
    character.setState(CharacterState.idle);
    state.answer = uiString(kind === 'denied' ? 'micDenied' : 'speechUnavailable', state.lang);
    render();
  };
}

/// 写真を押したら大きく表示する。
/// 案内図のように細かい写真は、小さいままでは読めないため。
function wirePhoto() {
  if (!el.answerPhoto || !el.photoView) return;

  const close = () => {
    el.photoView.hidden = true;
    el.photoViewImg.removeAttribute('src');
  };

  el.answerPhoto.addEventListener('click', () => {
    if (!el.answerPhoto.getAttribute('src')) return;
    el.photoViewImg.src = el.answerPhoto.src;
    el.photoViewClose.textContent = uiString('close', state.lang);
    el.photoView.hidden = false;
  });
  el.photoViewClose.addEventListener('click', close);
  // 写真の外側を押しても閉じる
  el.photoView.addEventListener('click', (e) => {
    if (e.target !== el.photoViewImg) close();
  });
}

function wireInput() {
  el.talkButton.addEventListener('click', toggleListening);

  // 音声が使えないブラウザでも案内が止まらないよう、入力欄を出す
  el.typedForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = el.typedInput.value.trim();
    if (text === '') return;
    el.typedInput.value = '';
    handleQuestion(text);
  });

  // 以前はここを長押しすると職員用の画面が開いたが、
  // 観光客が触る端末では、隠した導線もいずれ見つかる。
  // 設定画面は URL に ?setup=1 を足したときだけ開く。
}

async function refreshInBackground() {
  const remote = await repo.fetchRemote();
  if (remote == null) return;
  if (remote.version === state.dataVersion) {
    console.info(`FAQは最新です（${remote.version}）`);
    return;
  }
  if (faqService.loadFromJson(remote.json)) {
    state.dataVersion = remote.version;
    state.dataSource = remote.sourceLabel;
    render();
    console.info(`FAQを更新しました: ${faqService.count}件 (${remote.version})`);
  }
}

async function init() {
  buildLanguageButtons();
  wireSpeech();
  wireInput();
  wirePhoto();
  render();

  // 読み上げ終了で待機表情に戻す
  voice.onComplete = () => character.setState(CharacterState.idle);
  await voice.init();

  // 1. まずローカル（キャッシュ→同梱）を読む。通信を待たずにすぐ使える。
  try {
    const local = await repo.loadLocal();
    faqService.loadFromJson(local.json);
    state.dataVersion = local.version;
    state.dataSource = local.sourceLabel;
    console.info(`FAQ読み込み: ${faqService.count}件 (${local.sourceLabel} / ${local.version})`);
  } catch (e) {
    console.error('FAQデータを読み込めません:', e);
    state.dataSource = '読込エラー';
  }

  // 用意した音声の一覧（話者ごと）と、言語ごとの読み上げの設定を渡す
  voice.setSets(faqService.voiceSets);
  voice.setSettings(faqService.voiceSettings);
  voice.setReadings(faqService.readings);

  // 立つキャラクターの一覧。職員が決めた既定を立て、利用者は選び直せる。
  character.setList(faqService.characters);
  wireCharacter();

  // 現在地の判定（案内所の一覧は質問回答集に入っている）
  // ここで失敗しても、案内そのものは続けられるようにする
  try {
    places.setPlaces(faqService.places);
    wirePlace();
    renderPlacePill();

    if (isKiosk) {
      // 据え置き端末は場所が動かないので、位置情報を使わずURLの指定に従う。
      // 観光客に位置情報の許可を求めずに済む。
      places.remember(fixedPlace);
      state.place = places.current;
      renderPlacePill();
    } else {
      // 位置情報の取得は時間がかかることがあるので、待たずに画面を使える状態にする
      places.resolve().then(() => {
        state.place = places.current;
        renderPlacePill();
        buildChips();
        render();
      });
    }
  } catch (e) {
    console.error('現在地の準備に失敗しました:', e);
  }

  // よくある質問を並べる（FAQを読み込んだ後でないと作れない）
  buildChips();

  // 2. 音声が使えないブラウザでは、文字で聞けることを伝える
  //    （入力欄は常に出しているので、案内を出すだけでよい）
  if (!speech.available) {
    state.answer = uiString('speechUnsupported', state.lang);
  }
  render();

  // 3. 裏で最新データを取りに行く。失敗しても表示中のデータで動き続ける。
  refreshInBackground();

  // 4. 溜まっている質問の記録を送る。失敗しても案内は止めない。
  startLogSending();

  // 5. 職員が ?setup=1 を付けて開いたときだけ、設定画面を出す
  if (showSetup) setupScreen.open();

  // 6. ?tune=1 なら、見え方を合わせる画面を出す
  if (showTune) {
    // 文章が長いときの伸び方も見られるようにしておく
    tunePanel.onLongText = showLongSample;
    tunePanel.open();
  }

  // 6. 記録することをお伝えし、同意をいただく
  wireConsent();
}

/// 使い始める前に、記録することをお伝えする。
///
/// 観光客の端末は初回だけ。据え置き端末は、しばらく誰も触っていなければまた出す。
/// 据え置きは次々と別の方が使うので、一度の同意で済ませるわけにいかない。
function wireConsent() {
  // 同意画面で言語を選べる。選んだ言語はそのまま案内にも引き継ぐ。
  consentScreen.onLanguage = (lang) => changeLanguage(lang);

  const ask = () => {
    if (consentScreen.open) return;
    voice.stop();
    consentScreen.ask(state.lang, () => {
      // 断られた場合もここへ来る（案内はそのまま使える）
      touch();
    });
  };

  if (isKiosk) {
    startIdleWatch(ask);
    ask();          // 起動直後は、次に来た方のために出しておく
  } else if (consentState() === '') {
    ask();          // 一度お答えいただいた端末では、もう出さない
  }
}

/// 据え置き端末で、無操作が続いたら同意画面に戻す。
let lastTouch = Date.now();

function touch() {
  lastTouch = Date.now();
}

function startIdleWatch(ask) {
  for (const ev of ['pointerdown', 'keydown']) {
    window.addEventListener(ev, touch, { passive: true });
  }
  setInterval(() => {
    if (consentScreen.open) {
      // 出ている間は数えない（読んでいる途中で作り直すと読めなくなる）
      touch();
      return;
    }
    if (Date.now() - lastTouch >= CONSENT_IDLE_MS) {
      resetForNextVisitor();
      ask();
    }
  }, 10000);
}

/// 次の方のために、画面を最初の状態へ戻す。
/// 前の方の質問と回答が残っていると、その方の質問が他人に見えてしまう。
function resetForNextVisitor() {
  state.recognized = '';
  state.answer = '';
  state.photo = '';
  state.link = '';
  state.isAi = false;
  state.isFallback = false;
  character.setState(CharacterState.idle);
  render();
}

/// 吹き出しが長文でどう伸びるかを見るための試し表示（調整画面から使う）。
/// 短い文だけで合わせると、本番の長い回答で顔にかぶることがある。
function showLongSample() {
  const faq = faqService.all.find((f) => (f.answer || '').length > 90)
    ?? faqService.all[0];
  if (!faq) return;
  const localized = faqService.answerFor(faq, state.lang);
  state.recognized = faqService.questionsFor(faq, state.lang)[0] ?? '';
  state.answer = localized.text;
  state.photo = '';
  state.link = '';
  state.isAi = false;
  state.isFallback = localized.isFallback;
  character.setState(CharacterState.talking);
  render();
}

/// 質問の記録を中継サーバへ送り続ける。
///
/// 1件ごとに送ると通信が細切れになるので、少し間を置いてまとめて送る。
/// 据え置き端末は電源を入れっぱなしにするため、定期的にも送る。
function startLogSending() {
  const send = async () => {
    // 残りがあるうちは続けて送る（溜まっていた分を一度に片付ける）
    while (await log.flush()) {
      // flush が false を返すまで繰り返す
    }
  };
  send();
  setInterval(send, LOG_FLUSH_INTERVAL_MS);
  // 閉じる直前にも送っておく（観光客の端末は見終わるとすぐ閉じられる）
  window.addEventListener('pagehide', () => log.flush());
}

// 画面の向きが変わったときに背景を描き直す（ResizeObserver で拾えない場合の保険）
window.addEventListener('orientationchange', () => background.draw());

/// 寸法を測るための出口（tools/measure_layout.py から使う）。
///
/// URLに ?measure=1 が付いているときだけ、各部の大きさをページに書き出す。
/// 目分量で直すと別の画面幅で崩れるため、数字で確かめられるようにしている。
const MEASURE_TARGETS = {
  '同意画面の箱': '.consent-box',
  '同意の本文': '.consent-body',
  '上のバー': '.appbar',
  '題字': '.appbar h1',
  '現在地ボタン': '.place-pill',
  'キャラボタン': '.char-pill',
  'データ表示': '.data-status',
  '会話領域': '.stage',
  'キャラクター': '.character',
  '吹き出し': '.bubble',
  'よくある質問': '.faq-strip',
  '質問の帯の中身': '.faq-track',
  '入力欄': '.typed',
  '話すボタン': '.talk-button',
  '言語の列': '.languages',
  '画面全体': '.screen',
};

function writeMeasurement() {
  const out = {
    view: { w: innerWidth, h: innerHeight },
    doc: { w: document.documentElement.scrollWidth },
    items: {},
  };
  for (const [name, sel] of Object.entries(MEASURE_TARGETS)) {
    const el = document.querySelector(sel);
    if (!el) {
      out.items[name] = null;
      continue;
    }
    const r = el.getBoundingClientRect();
    out.items[name] = {
      w: Math.round(r.width), h: Math.round(r.height),
      x: Math.round(r.left), y: Math.round(r.top),
      font: getComputedStyle(el).fontSize,
      hidden: el.hidden || getComputedStyle(el).display === 'none',
    };
  }
  const pre = document.createElement('pre');
  pre.id = 'measure-result';
  pre.textContent = JSON.stringify(out);
  pre.style.display = 'none';
  document.body.appendChild(pre);
}

if (new URLSearchParams(window.location.search).get('measure') === '1') {
  window.addEventListener('load', () => setTimeout(() => {
    // 同意画面が出ていると後ろが測れない。
    // 仕組みを迂回せず、「記録せずに使う」を押して先へ進める
    // （記録は始まらないので、測定のために同意したことにはならない）。
    const decline = document.querySelector('.consent-decline');
    if (decline) decline.click();
    // 押したあとの配置が落ち着いてから測る
    setTimeout(writeMeasurement, 500);
  }, 600));
}


init();
