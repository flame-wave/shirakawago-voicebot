<?php
/**
 * AI回答の中継（ロリポップなどのレンタルサーバに置く）。
 *
 * 案内アプリ（ブラウザ）から質問を受け取り、質問回答集を資料として添えて
 * AIに聞き、その答えだけを返す。APIキーはこのサーバの中だけにあり、
 * ブラウザ側には出ない。
 *
 * 呼ばれ方:
 *   POST /api/ask.php
 *   {"question": "半日あれば足りますか", "lang": "ja"}
 *
 * 返すもの:
 *   {"answer": "……", "sources": ["shuyu_time"]}      ← 資料から答えられた
 *   {"answer": null, "reason": "not_found"}           ← 答えず職員へ回す
 *
 * 【方針】
 * 資料に書いてあることだけを答えさせ、少しでも怪しければ答えない。
 * 観光客にとって、間違った案内は「答えが得られない」ことより害が大きい。
 */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$config = require __DIR__ . '/config.php';

// ---------------------------------------------------------------- 返し方
function respond(array $body, int $status = 200): void
{
    http_response_code($status);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/** 答えないときの返し方。理由は記録と画面表示の切り分けに使う。 */
function decline(string $reason, int $status = 200): void
{
    respond(['answer' => null, 'reason' => $reason], $status);
}

// ---------------------------------------------------------------- 受け取り
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    decline('method_not_allowed', 405);
}

$request = json_decode((string) file_get_contents('php://input'), true);
if (!is_array($request)) {
    decline('bad_request', 400);
}

$question = trim((string) ($request['question'] ?? ''));
$lang = strtolower(preg_replace('/[^a-zA-Z]/', '', (string) ($request['lang'] ?? 'ja')));
if ($lang === '') {
    $lang = 'ja';
}

// いまいる案内所。ロッカーやATMのように案内所ごとに答えが違うものがあるため、
// 案内アプリ側の検索と同じように、ここでも場所で資料を絞る。
$place = trim((string) ($request['place'] ?? ''));
if (mb_strlen($place) > 40) {
    $place = '';
}

// 極端に長い入力は、料金と悪用の両面で止める
if ($question === '' || mb_strlen($question) > 200) {
    decline('bad_question', 400);
}

// ---------------------------------------------------------------- 呼び出し元の確認
// 案内アプリと同じサイトからの呼び出しだけを受ける。
// 誰でも叩ける状態にしておくと、APIキーの利用料を他人に使われてしまう。
if (!empty($config['allow_origins'])) {
    $from = $_SERVER['HTTP_ORIGIN'] ?? $_SERVER['HTTP_REFERER'] ?? '';
    $ok = false;
    foreach ($config['allow_origins'] as $allowed) {
        if ($from !== '' && strpos($from, $allowed) === 0) {
            $ok = true;
            break;
        }
    }
    if (!$ok) {
        decline('forbidden', 403);
    }
}

// ---------------------------------------------------------------- 使いすぎを止める
/**
 * 1分あたり・1日あたりの回数を数える。
 * 無料枠の上限に当たったり、いたずらで料金が膨らんだりするのを防ぐ。
 */
function within_limits(array $config): bool
{
    $path = $config['counter_path'];
    $fp = @fopen($path, 'c+');
    if (!$fp) {
        return true; // 数えられない環境でも案内は止めない
    }
    flock($fp, LOCK_EX);

    $state = json_decode((string) stream_get_contents($fp), true);
    if (!is_array($state)) {
        $state = [];
    }

    $now = time();
    $minute = (int) floor($now / 60);
    $day = date('Y-m-d', $now);

    if (($state['minute'] ?? null) !== $minute) {
        $state['minute'] = $minute;
        $state['minute_count'] = 0;
    }
    if (($state['day'] ?? null) !== $day) {
        $state['day'] = $day;
        $state['day_count'] = 0;
    }

    $state['minute_count']++;
    $state['day_count']++;
    $ok = $state['minute_count'] <= $config['max_per_minute']
        && $state['day_count'] <= $config['max_per_day'];

    ftruncate($fp, 0);
    rewind($fp);
    fwrite($fp, json_encode($state));
    fflush($fp);
    flock($fp, LOCK_UN);
    fclose($fp);

    return $ok;
}

if (!within_limits($config)) {
    decline('rate_limited', 429);
}

// ---------------------------------------------------------------- 資料を用意する
// 全件をAIに渡すと、料金も待ち時間も無駄にかかり、関係のない回答が混ざって
// 精度も落ちる。質問に近いものだけを選んで渡す。
//
// 「参考資料」が場所によらない回答を毎回すべて渡しているので、
// こちらは「いまいる案内所向けの回答」と「質問に近いものを目立たせる役」を担う。
// 件数を増やすほど同じ内容を二重に送ることになるので、10件にしている。
const CONTEXT_LIMIT = 10;
const COMMON_PLACE = '共通';

/**
 * 表記の揺れを吸収する。
 * カタカナ→ひらがな、全角英数→半角、記号と空白の除去。
 * 案内アプリ側の検索（webapp/js/faq-service.js の normalize）と同じ考え方にしている。
 */
function normalize_text(string $s): string
{
    $out = '';
    foreach (preg_split('//u', $s, -1, PREG_SPLIT_NO_EMPTY) ?: [] as $ch) {
        $c = mb_ord($ch, 'UTF-8');
        if ($c === false) {
            continue;
        }
        if ($c >= 0xff10 && $c <= 0xff5a) {
            $c -= 0xfee0;   // 全角英数 → 半角
        }
        if ($c >= 0x30a1 && $c <= 0x30f6) {
            $c -= 0x60;     // カタカナ → ひらがな
        }
        $out .= mb_chr($c, 'UTF-8');
    }
    $out = mb_strtolower($out, 'UTF-8');
    $out = (string) preg_replace('/[、。，．,.!?！？・ー]+/u', '', $out);

    // 空白は「消す」のではなく1つにまとめる。
    // 英語などは空白が語の切れ目なので、消すと1つの長い語になってしまい、
    // どの資料とも一致しなくなる（日本語は語の中に空白が無いので影響しない）。
    $out = (string) preg_replace('/[\s\x{3000}]+/u', ' ', $out);
    return trim($out);
}

/**
 * 照合に使う語の一覧を返す。
 *
 * 日本語は語の区切りが無いため、2文字の重なりで測る。
 * 英語・スペイン語などは語の区切りがあるので、語をそのまま使う。
 * 英字を2文字ずつに刻むと、どの文にも出る並び（th、in、er など）ばかりが
 * 当たってしまい、まるで関係のない回答が選ばれる。
 */
function terms(string $normalized): array
{
    $out = [];

    // 英字・数字の並びは、語のまとまりとして取り出す
    if (preg_match_all('/[a-z0-9]{2,}/u', $normalized, $m)) {
        foreach ($m[0] as $word) {
            $out[$word] = true;
        }
    }

    // 英字・数字を取り除いた残り（日本語・中国語・韓国語）を2文字ずつに刻む
    $rest = (string) preg_replace('/[a-z0-9]+/u', ' ', $normalized);
    foreach (preg_split('/\s+/u', $rest, -1, PREG_SPLIT_NO_EMPTY) ?: [] as $run) {
        $chars = preg_split('//u', $run, -1, PREG_SPLIT_NO_EMPTY) ?: [];
        $n = count($chars);
        if ($n === 1) {
            $out[$chars[0]] = true;
            continue;
        }
        for ($i = 0; $i < $n - 1; $i++) {
            $out[$chars[$i] . $chars[$i + 1]] = true;
        }
    }

    return array_keys($out);
}

/** その案内所の区別。空欄はどの案内所でも使える回答とみなす。 */
function place_of(array $item): string
{
    $place = trim((string) ($item['place'] ?? ''));
    return $place === '' ? COMMON_PLACE : $place;
}

/** 指定言語の回答。翻訳が無ければ日本語を使う。 */
function answer_of(array $item, string $lang): string
{
    $translated = (string) ($item['translations'][$lang]['answer'] ?? '');
    return $translated !== '' ? $translated : (string) ($item['answer'] ?? '');
}

/** 指定言語の質問例。日本語の言い方も残す（地名などは言語をまたぐため）。 */
function questions_of(array $item, string $lang): array
{
    $ja = is_array($item['questions'] ?? null) ? $item['questions'] : [];
    if ($lang === 'ja') {
        return $ja;
    }
    $tr = $item['translations'][$lang]['questions'] ?? [];
    return array_merge(is_array($tr) ? $tr : [], $ja);
}

/**
 * 「言い換え」表を使って、質問に代表語を足す。
 *
 * 「銀行ありますか」に atm を足す、というように、観光客の言い方を
 * 資料に書かれている語へ橋渡しする。案内アプリ側の検索と同じ表を使う。
 */
function expand_question(array $faq, string $question, string $lang): string
{
    $table = array_merge(
        (array) ($faq['synonyms']['ja'] ?? []),
        (array) ($faq['synonyms'][$lang] ?? []),
    );

    $extra = [];
    foreach ($table as $representative => $words) {
        $rep = normalize_text((string) $representative);
        if ($rep === '' || mb_strpos($question, $rep) !== false) {
            continue;   // すでに入っているなら足さない
        }
        foreach ((array) $words as $word) {
            $w = normalize_text((string) $word);
            if ($w !== '' && mb_strpos($question, $w) !== false) {
                $extra[] = $rep;
                break;
            }
        }
    }

    // 足した語が元の文とつながって誤って一致しないよう、空白で区切る
    return $extra ? $question . ' ' . implode(' ', $extra) : $question;
}

/**
 * 質問に近い回答を、多くても CONTEXT_LIMIT 件だけ選ぶ。
 *
 * いまいる案内所のものと「共通」だけを見る。
 * 別の案内所の回答を混ぜると、ロッカーやATMの場所を取り違えて案内してしまう。
 *
 * 【珍しい語ほど重く見る理由】
 * 「です」「ます」「ここ」のような、どの回答にも出てくる語で点を付けると、
 * 文章の長い回答ばかりが上位に来て、本当に関係のある回答が押し出される。
 * 多くの回答に出てくる語ほど軽く、少しの回答にしか出てこない語ほど重く数える。
 */
function pick_relevant(array $faqs, string $lang, string $question, string $place): array
{
    // $question は正規化と言い換えを済ませたもの。
    // ここで正規化し直すと、言い換えで足した語の区切りが消えてしまう。
    $needle = terms($question);
    if (!$needle) {
        return [];
    }

    // 場所で絞ったうえで、照合に使う文をあらかじめ作っておく
    $pool = [];
    foreach ($faqs as $order => $item) {
        if (($item['id'] ?? '') === '' || answer_of($item, $lang) === '') {
            continue;
        }
        $here = place_of($item);
        if ($here !== COMMON_PLACE && $here !== $place) {
            continue;
        }
        $pool[] = [
            'order' => $order,
            'item' => $item,
            'here' => $here === $place ? 1 : 0,
            // 質問例は手がかりとして強いので、回答文と分けて持つ
            'questions' => normalize_text(implode(' ', questions_of($item, $lang))),
            'answer' => normalize_text(answer_of($item, $lang)),
        ];
    }
    if (!$pool) {
        return [];
    }

    // その語が何件の回答に出てくるかを数える
    $total = count($pool);
    $weight = [];
    foreach ($needle as $term) {
        $found = 0;
        foreach ($pool as $row) {
            if (mb_strpos($row['questions'], $term) !== false
                || mb_strpos($row['answer'], $term) !== false) {
                $found++;
            }
        }
        // どこにも無い語は使わない。全件に出る語はほぼ0点になる。
        $weight[$term] = $found === 0 ? 0.0 : log(1.0 + $total / $found);
    }

    $scored = [];
    foreach ($pool as $row) {
        $score = 0.0;
        foreach ($needle as $term) {
            if ($weight[$term] <= 0.0) {
                continue;
            }
            if (mb_strpos($row['questions'], $term) !== false) {
                $score += $weight[$term] * 3.0;
            } elseif (mb_strpos($row['answer'], $term) !== false) {
                $score += $weight[$term];
            }
        }
        if ($score <= 0.0) {
            continue;
        }
        // 同じ点数なら、いまいる案内所向けのものを先に出す
        $scored[] = ['score' => $score, 'here' => $row['here'],
                     'order' => $row['order'], 'item' => $row['item']];
    }

    usort($scored, function ($a, $b) {
        return [$b['score'], $b['here'], $a['order']] <=> [$a['score'], $a['here'], $b['order']];
    });

    return array_column(array_slice($scored, 0, CONTEXT_LIMIT), 'item');
}

/**
 * 選んだ回答を、AIに渡す資料の形にする。
 * IDを添えるのは、どれを根拠にしたかを答えさせて記録するため。
 */
function build_context(array $picked, string $lang): string
{
    $lines = [];
    foreach ($picked as $item) {
        $answer = str_replace(["\r", "\n"], ' ', answer_of($item, $lang));
        $lines[] = '- [' . $item['id'] . '] ' . $answer;
    }
    return implode("\n", $lines);
}

/**
 * 資料（質問回答集）を読む。
 *
 * 管理画面から反映すると、新しい質問回答集はGitHubに置かれる。
 * 案内アプリはそこから直接読むが、この中継サーバが自分の中の古いファイルを
 * 見ていると、画面とAIで答えが食い違ってしまう。
 * そこで配信URLが設定されていれば、そちらを読んで控えを取っておく。
 *
 * 毎回取りに行くと観光客を待たせるので、控えが新しいうちはそれを使う。
 * 取りに行けなかったときは、控え → 同梱のファイル の順に落とす。
 * 資料が読めないことより、案内が止まることの方が困る。
 */
function load_faq(array $config): ?array
{
    $url = trim((string) ($config['faq_url'] ?? ''));
    $cache = (string) ($config['faq_cache_path'] ?? '');
    $maxAge = (int) ($config['faq_cache_minutes'] ?? 30) * 60;

    // 控えがまだ新しければ、それを使う
    if ($cache !== '' && is_file($cache) && time() - filemtime($cache) < $maxAge) {
        $decoded = json_decode((string) @file_get_contents($cache), true);
        if (is_array($decoded)) {
            return $decoded;
        }
    }

    if ($url !== '') {
        $context = stream_context_create(['http' => [
            'timeout' => 5,
            // 取りに行くのに失敗しても案内は続けるので、短めで切り上げる
            'header' => "User-Agent: shirakawago-voicebot\r\n",
        ]]);
        $raw = @file_get_contents($url, false, $context);
        $decoded = $raw === false ? null : json_decode($raw, true);
        if (is_array($decoded) && !empty($decoded['faqs'])) {
            if ($cache !== '') {
                @file_put_contents($cache, $raw, LOCK_EX);
            }
            return $decoded;
        }
    }

    // 取りに行けなかった場合。古くても控えがあれば使う。
    if ($cache !== '' && is_file($cache)) {
        $decoded = json_decode((string) @file_get_contents($cache), true);
        if (is_array($decoded)) {
            return $decoded;
        }
    }

    $raw = @file_get_contents((string) ($config['faq_path'] ?? ''));
    $decoded = $raw === false ? null : json_decode($raw, true);
    return is_array($decoded) ? $decoded : null;
}

$faq = load_faq($config);
if ($faq === null) {
    decline('no_data', 500);
}

$expanded = expand_question($faq, normalize_text($question), $lang);
$picked = pick_relevant($faq['faqs'] ?? [], $lang, $expanded, $place);
$candidates = array_column($picked, 'id');
// 近いものが1件も無ければ、AIに聞く前に諦める。
// 資料に無いことは答えさせない方針なので、聞いても答えは返らない。
if (!$picked) {
    write_log($config, ['at' => date('c'), 'lang' => $lang, 'place' => $place,
                        'question' => $question, 'result' => 'no_candidate']);
    decline('not_found');
}
$context = build_context($picked, $lang);

/**
 * 参考資料を資料に足す。
 *
 * 質問回答集は「この質問にはこう答える」という形なので、
 * そこに無い聞かれ方には答えられない（雨の日は、冬の靴は、など）。
 * 参考資料は背景の説明で、AIが質問に合わせて言い換えて使う。
 * 件数が少なく短いので、絞らず全部渡す。
 */
function build_reference(array $faq): string
{
    $lines = [];
    foreach ($faq['reference'] ?? [] as $note) {
        $title = trim((string) ($note['title'] ?? ''));
        $text = trim((string) ($note['text'] ?? ''));
        if ($title === '' || $text === '') {
            continue;
        }
        $lines[] = '- ' . $title . ': ' . str_replace(["\r", "\n"], ' ', $text);
    }
    return implode("\n", $lines);
}

$reference = build_reference($faq);

// ---------------------------------------------------------------- AIへの指示
$instructions = <<<'TEXT'
あなたは白川郷（世界遺産の合掌造り集落）の観光案内所の案内係です。
下の「資料」と「参考資料」を使って、観光客の質問に答えてください。

【2種類の材料】
- 「資料」… 職員が確かめた決まった答え。内容をそのまま使えます。
- 「参考資料」… 背景の説明。質問に合わせて言い換えて使ってかまいません。
どちらか一方にしか手がかりが無くても、それだけで答えて構いません。

【絶対に守ること】
- どちらにも書かれていないことは、推測でも一般知識でも答えないでください。
- 時刻・料金・可否（できる/できない）は、明記がある場合のみ答えてください。
  古い情報や推測で答えると、観光客がバスに乗り遅れる等の実害が出ます。
- 危険に関わる質問（けが・急病・事故・熊・川）は answer を null にしてください。
- 手がかりがまったく無いときだけ、answer を null にしてください。
  答えないことは失敗ではありません。職員が対応します。

【答えられるときは答えてください】
- 質問の言い回しが資料と違っても、内容が同じなら答えてください。
- 直接の項目が無くても、複数の資料を組み合わせて答えられるなら答えてください。
- 一部しか分からないときは、分かる範囲だけを答えてください。
  「詳しくは係員にお尋ねください」と添えれば、部分的な回答でも役に立ちます。

【答え方】
- 「答える言語」で示した言語コードの言語で答えてください。
- 読み上げられるため、2〜3文の短い口語にしてください。箇条書きは使わないでください。
- 条件（料金・時間・人数など）は省略しないでください。

出力はJSONのみ。説明や前置きは書かないでください。
sources には使った資料のID、参考資料を使った場合はその見出しを入れてください。
{"answer": "回答文またはnull", "sources": ["根拠にした資料のIDまたは見出し"]}
TEXT;

// 毎回まったく同じになる部分（指示＋参考資料）を先に置く。
// ここを使い回せるようにしておくと、2回目以降の料金が10分の1になる。
// 言語の指定を質問側へ回しているのは、言語ごとに別物にしないため。
$fixed = $instructions;
if ($reference !== '') {
    $fixed .= "\n\n【参考資料】\n" . $reference;
}

// 質問ごとに変わる部分。資料は質問に合わせて選んでいるので、こちら側。
$variable = "【資料】\n" . $context
    . "\n\n【答える言語】\n" . $lang
    . "\n\n【観光客の質問】\n" . $question;

$prompt = $fixed . "\n\n" . $variable;   // 記録に残す長さの計算に使う

// ---------------------------------------------------------------- AIに聞く
/**
 * OpenAI互換の窓口に投げる。
 * Gemini・Groq・OpenRouter などは、設定の base_url と model を変えるだけで使える。
 */
function ask_ai(array $config, string $fixed, string $variable): array
{
    // 毎回同じ部分を system に、質問ごとに変わる部分を messages に分ける。
    // この順でしか使い回しが効かない（前から一致した分までが対象になる）。
    $system = [['type' => 'text', 'text' => $fixed]];
    if (!empty($config['cache'])) {
        $system[0]['cache_control'] = ['type' => 'ephemeral'];
    }

    $payload = [
        'model' => $config['model'],
        'max_tokens' => 600,
        // 案内なので、毎回ぶれないよう低めにする
        'temperature' => 0.2,
        'system' => $system,
        'messages' => [['role' => 'user', 'content' => $variable]],
    ];

    $ch = curl_init(rtrim($config['base_url'], '/') . '/v1/messages');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => $config['timeout'],
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'x-api-key: ' . $config['api_key'],
            'anthropic-version: 2023-06-01',
        ],
        CURLOPT_POSTFIELDS => json_encode($payload, JSON_UNESCAPED_UNICODE),
    ]);

    $body = curl_exec($ch);
    $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);

    if ($body === false) {
        return ['error' => 'connection', 'detail' => $error];
    }
    if ($status !== 200) {
        return ['error' => 'http_' . $status, 'detail' => mb_substr((string) $body, 0, 200)];
    }

    $decoded = json_decode((string) $body, true);

    // 内容によっては答えを断られることがある。異常ではないので職員へ回す。
    if (($decoded['stop_reason'] ?? '') === 'refusal') {
        return ['error' => 'refusal', 'detail' => 'AIが回答を控えました'];
    }

    // 返事は複数のかたまりで来ることがあるので、文章だけをつなぐ
    $text = '';
    foreach ($decoded['content'] ?? [] as $block) {
        if (($block['type'] ?? '') === 'text') {
            $text .= $block['text'] ?? '';
        }
    }

    // 使い回しが効いているかは、ここを見れば分かる
    $usage = $decoded['usage'] ?? [];
    return [
        'text' => $text,
        'usage' => [
            'in' => (int) ($usage['input_tokens'] ?? 0),
            'out' => (int) ($usage['output_tokens'] ?? 0),
            'cache_write' => (int) ($usage['cache_creation_input_tokens'] ?? 0),
            'cache_read' => (int) ($usage['cache_read_input_tokens'] ?? 0),
        ],
    ];
}

/** 返答からJSONを取り出す。前後に説明が付いていても拾う。 */
function parse_answer(string $text): ?array
{
    if (preg_match('/```(?:json)?\s*(.+?)\s*```/s', $text, $m)) {
        $text = $m[1];
    }
    $start = strpos($text, '{');
    $end = strrpos($text, '}');
    if ($start === false || $end === false) {
        return null;
    }
    $decoded = json_decode(substr($text, $start, $end - $start + 1), true);
    return is_array($decoded) ? $decoded : null;
}

$result = ask_ai($config, $fixed, $variable);

// ---------------------------------------------------------------- 記録
/**
 * 何を聞かれ、AIが何と答えたかを残す。
 * 職員が後から確認し、良い回答は質問回答集へ移すために使う。
 */
function write_log(array $config, array $row): void
{
    if (empty($config['log_path'])) {
        return;
    }
    @file_put_contents(
        $config['log_path'],
        json_encode($row, JSON_UNESCAPED_UNICODE) . "\n",
        FILE_APPEND | LOCK_EX
    );
}

$base = [
    'at' => date('c'),
    'lang' => $lang,
    'place' => $place,
    'question' => $question,
    'model' => $config['model'],
    // AIに渡した資料。的外れな候補しか出ていないなら、言い換え表の見直しに使う。
    'candidates' => $candidates,
    // 送った文の長さ。利用料金の見積りと、上限に当たっていないかの確認に使う。
    'prompt_chars' => mb_strlen($prompt),
];

if (isset($result['error'])) {
    write_log($config, $base + ['result' => 'error', 'detail' => $result['detail'] ?? '']);
    decline('ai_error');
}

$parsed = parse_answer($result['text'] ?? '');
$answer = $parsed['answer'] ?? null;
if (!is_string($answer) || trim($answer) === '' || strtolower(trim($answer)) === 'null') {
    write_log($config, $base + ['result' => 'not_found']);
    decline('not_found');
}

$sources = [];
foreach ((array) ($parsed['sources'] ?? []) as $id) {
    if (is_string($id)) {
        $sources[] = $id;
    }
}

write_log($config, $base + [
    'result' => 'answered', 'answer' => $answer, 'sources' => $sources,
    // 使い回し（キャッシュ）が効いているかの確認に使う
    'usage' => $result['usage'] ?? null,
]);
respond(['answer' => trim($answer), 'sources' => $sources]);
