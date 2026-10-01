"""翻訳した回答から、固有名詞のあやしい箇所を洗い出す。

使い方:
    python tools/check_translations.py [assets/faq.json]

観光客は、地名を手がかりに地図や看板と突き合わせる。
地名が違うと、案内として成り立たない。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets" / "faq.json"
FAQ = json.loads(SOURCE.read_text(encoding="utf-8"))

# 見つけたら必ず直すもの。（あやしい表記, 説明）
SUSPECT = [
    (r'백가와고|백가고|백천향', '白川郷の韓国語は「시라카와고」。漢字を韓国語読みした形になっている'),
    (r'\bShiroyama\b', '白山は Hakusan。Shiroyama（城山）は別の山'),
    (r'백산(?!맥)', '白山の韓国語は「하쿠산」。漢字読みでは通じない'),
    (r'도로역', '道の駅は「미치노에키」。「도로역」では通じない'),
    (r'Roadside Station', '道の駅は Michi-no-Eki（道の駅 roadside station）と書く方が通じる'),
]

# 日本語以外の文に日本語の文字が残っていないか（読めない）
JA_CHARS = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')

# 表記のゆれ
VARIANTS = [
    (r'Shirakawago\b', 'Shirakawa-go に揃える'),
    (r'Shirakawa-gō', 'Shirakawa-go に揃える（長音記号なし）'),
]

found = 0
for f in FAQ['faqs']:
    for lang, tr in (f.get('translations') or {}).items():
        text = (tr.get('answer') or '') + ' ' + ' '.join(tr.get('questions') or [])
        hits = []
        for pattern, why in SUSPECT:
            for m in re.finditer(pattern, text):
                hits.append(f'「{m.group(0)}」… {why}')
        for pattern, why in VARIANTS:
            if re.search(pattern, text):
                hits.append(f'表記ゆれ: {why}')
        if lang != 'ja' and lang in ('en', 'es', 'fr', 'ko'):
            # 中国語は漢字を使うので対象外
            for m in JA_CHARS.finditer(text):
                hits.append(f'日本語の文字が残っている: …{text[max(0, m.start()-8):m.start()+10]}…')
                break
        if hits:
            found += 1
            print(f'{f["id"]} / {lang}')
            for h in dict.fromkeys(hits):
                print('   ', h)

print()
print(f'あやしい箇所のある翻訳: {found} 組')
