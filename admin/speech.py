"""管理画面で「聞いてみる」ための部品。

職員さんのパソコンのブラウザの声で読む。案内端末と同じ仕組み（Web Speech API）なので、
声の高さ・速さ・読み方の直しが、案内端末でどう聞こえるかをその場で確かめられる。

【端末ごとに声が違う】
ブラウザの声は、パソコンやタブレットに入っているものを使う。
ここで聞こえる声と、案内端末で聞こえる声は同じとは限らないので、
「この端末では○○の声で読みます」と、実際に使った声の名前を出す。

【ボタンは枠（iframe）の中に置く】
ブラウザは、人が押したボタンからでないと読み上げを始めない決まりがある。
Streamlit のボタンを押してから読ませると、この決まりに引っかかって鳴らないことがある。
そのため、読み上げのボタンそのものを枠の中に置いている。
"""
import json

import streamlit.components.v1 as components

# 言語ごとの読み上げの言葉の指定（案内アプリの TTS_LANGUAGE と同じ）
TTS_LANG = {"ja": "ja-JP", "en": "en-US", "zh": "zh-CN", "ko": "ko-KR",
            "es": "es-ES", "fr": "fr-FR"}

# 試しに読む文。地名が入っていると、読み方の直しや声の違いが分かりやすい。
SAMPLES = {
    "ja": "白川郷へようこそ。展望台行きのシャトルバスは、荻町の和田家の前から出ています。",
    "en": "Welcome to Shirakawa-go. The shuttle bus to the observatory leaves from in front of Wada House.",
    "zh": "欢迎来到白川乡。前往观景台的接驳巴士从和田家门前出发。",
    "ko": "시라카와고에 오신 것을 환영합니다. 전망대행 셔틀버스는 와다가 앞에서 출발합니다.",
    "es": "Bienvenido a Shirakawa-go. El autobús lanzadera al mirador sale frente a la casa Wada.",
    "fr": "Bienvenue à Shirakawa-go. La navette pour l'observatoire part devant la maison Wada.",
}

STYLE = """
<style>
  body { margin: 0; font-family: "BIZ UDPGothic", sans-serif; color: #1F2A1F; }
  button {
    min-height: 44px; border-radius: 10px; cursor: pointer; padding: 0 16px;
    border: 1px solid #2C5F2D; background: #fff; color: #2C5F2D;
    font: 700 15px "BIZ UDPGothic", sans-serif;
  }
  button:hover { background: #E8F1E4; }
  button.wide { width: 100%; }
  button:disabled { color: #8A9A88; border-color: #DDE3D8; cursor: default; background: #fff; }
  .who { font-size: 13px; color: #4A5648; margin-top: 6px; min-height: 18px; }
</style>
"""

# 声を選ぶ処理（案内アプリの voice-service.js と同じ考え方）
PICK_JS = """
function pickVoice(lang, want) {
  const all = speechSynthesis.getVoices().filter(v => v.lang.replace('_','-').startsWith(lang.slice(0, 2)));
  for (const name of want) {
    const v = all.find(x => x.name.includes(name));
    if (v) return v;
  }
  return all[0] || null;
}
function speak(text, lang, want, rate, pitch, onEnd, who) {
  if (speechSynthesis.speaking) { speechSynthesis.cancel(); onEnd && onEnd(); return false; }
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang; u.rate = rate; u.pitch = pitch;
  const v = pickVoice(lang, want);
  if (v) u.voice = v;
  if (who) who.textContent = v ? `この端末では「${v.name}」で読みます。`
                               : 'この端末には、この言語の声が入っていません。';
  u.onend = () => onEnd && onEnd();
  u.onerror = () => onEnd && onEnd();
  speechSynthesis.speak(u);
  return true;
}
"""


def voice_of(settings_row):
    """「読み上げ」シートの1行から、優先する声の並び・速さ・高さを取り出す。"""
    row = settings_row or {}
    voices = row.get("voices", [])
    if isinstance(voices, str):
        voices = [v.strip() for v in voices.split(",") if v.strip()]
    try:
        rate = float(row.get("rate", 0.95))
    except (TypeError, ValueError):
        rate = 0.95
    try:
        pitch = float(row.get("pitch", 1.0))
    except (TypeError, ValueError):
        pitch = 1.0
    return voices, rate, pitch


def apply_readings(text, readings):
    """読み方の直しを当てる（長い語から先に。案内アプリと同じ）。

    readings … [(表記, 読み)]
    """
    for src, yomi in sorted(readings, key=lambda x: -len(x[0])):
        if src and yomi:
            text = text.replace(src, yomi)
    return text


def listen_button(text, lang="ja", voices=(), rate=0.95, pitch=1.0,
                  label="🔈 聞いてみる", height=72):
    """1つの文を読む「聞いてみる」ボタン。押すと止めるボタンに変わる。"""
    tts = TTS_LANG.get(lang, lang)
    components.html(STYLE + f"""
<button class="wide" id="b" {"disabled" if not text else ""}>{label}</button>
<div class="who" id="who"></div>
<script>
{PICK_JS}
const b = document.getElementById("b"), who = document.getElementById("who");
const label = {json.dumps(label, ensure_ascii=False)};
speechSynthesis.getVoices();   // 声の一覧を先に読み込ませる（最初の1回は空のことがある）
b.onclick = () => {{
  const started = speak({json.dumps(text, ensure_ascii=False)}, {json.dumps(tts)},
                        {json.dumps(list(voices), ensure_ascii=False)}, {rate}, {pitch},
                        () => b.textContent = label, who);
  if (started) b.textContent = "■ 止める";
}};
</script>""", height=height)


def readings_player(rows, voices=(), rate=0.95, pitch=1.0, sample=SAMPLES["ja"]):
    """読み方の表を、1行ずつ聞き比べる部品。

    rows … [(表記, 読み, 有効)]。「そのまま」は直す前（表記をそのまま読ませる）、
    「直したあと」は読みに差し替えて読む。下には、文で試す欄も置く。
    """
    data = [{"src": s, "yomi": y, "on": bool(on)} for s, y, on in rows if s or y]
    # 行が多いと縦に長くなりすぎるので、上限を決めて中で巻き取る
    height = min(640, 120 + 46 * len(data) + 150)
    components.html(STYLE + """
<style>
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th { text-align: left; font-size: 13px; color: #4A5648; padding: 4px 8px;
       border-bottom: 1px solid #DDE3D8; }
  td { padding: 4px 8px; border-bottom: 1px solid #EEF1EC; vertical-align: middle; }
  td.off { color: #8A9A88; text-decoration: line-through; }
  td button { min-height: 36px; font-size: 14px; padding: 0 12px; }
  .tester { margin-top: 14px; }
  textarea { width: 100%; box-sizing: border-box; font: 15px "BIZ UDPGothic", sans-serif;
             border: 1px solid #DDE3D8; border-radius: 10px; padding: 8px 10px; }
  .row2 { display: flex; gap: 8px; margin-top: 6px; }
  .row2 button { flex: 1; }
</style>
<table><thead><tr><th>表記</th><th>読み</th><th>直す前</th><th>直したあと</th></tr></thead>
<tbody id="rows"></tbody></table>
<div class="tester">
  <div style="font-size:15px;font-weight:700;margin-bottom:4px">文で試す</div>
  <textarea id="t" rows="2"></textarea>
  <div class="row2">
    <button id="raw">🔈 そのまま読む</button>
    <button id="fix">🔈 読み方を直して読む</button>
  </div>
</div>
<div class="who" id="who"></div>
<script>
""" + PICK_JS + f"""
const DATA = {json.dumps(data, ensure_ascii=False)};
const WANT = {json.dumps(list(voices), ensure_ascii=False)};
const RATE = {rate}, PITCH = {pitch};
const who = document.getElementById("who");
speechSynthesis.getVoices();
function say(text, btn) {{
  const label = btn.textContent;
  if (speak(text, "ja-JP", WANT, RATE, PITCH, () => btn.textContent = label, who))
    btn.textContent = "■ 止める";
}}
function fixAll(text) {{
  const pairs = DATA.filter(d => d.on && d.src && d.yomi)
                    .sort((a, b) => b.src.length - a.src.length);
  for (const d of pairs) text = text.split(d.src).join(d.yomi);
  return text;
}}
const tbody = document.getElementById("rows");
DATA.forEach(d => {{
  const tr = document.createElement("tr");
  const cls = d.on ? "" : ' class="off"';
  tr.innerHTML = `<td${{cls}}></td><td${{cls}}></td><td></td><td></td>`;
  tr.children[0].textContent = d.src; tr.children[1].textContent = d.yomi;
  const b1 = document.createElement("button"); b1.textContent = "🔈 そのまま";
  b1.disabled = !d.src; b1.onclick = () => say(d.src, b1);
  const b2 = document.createElement("button"); b2.textContent = "🔈 直したあと";
  b2.disabled = !d.yomi; b2.onclick = () => say(d.yomi, b2);
  tr.children[2].appendChild(b1); tr.children[3].appendChild(b2);
  tbody.appendChild(tr);
}});
document.getElementById("t").value = {json.dumps(sample, ensure_ascii=False)};
document.getElementById("raw").onclick = (e) => say(document.getElementById("t").value, e.target);
document.getElementById("fix").onclick = (e) => say(fixAll(document.getElementById("t").value), e.target);
</script>""", height=height, scrolling=True)


def clean_reading_rows(records):
    """表（data_editor の行）から (表記, 読み, 有効) を取り出す。"""
    out = []
    for r in records:
        src = str(r.get("表記") or "").strip()
        yomi = str(r.get("読み") or "").strip()
        on = str(r.get("有効") or "").strip().upper() not in ("FALSE", "0", "×", "NO")
        if src in ("nan", "None"):
            src = ""
        if yomi in ("nan", "None"):
            yomi = ""
        if src.startswith("※"):
            continue
        out.append((src, yomi, on))
    return out
