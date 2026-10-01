<?php
/**
 * 質問の記録を受け取る。
 *
 * 案内端末（ブラウザ）から、聞かれた質問と答えられたかどうかを受け取り、
 * 1行1件で書き溜める。職員は管理者画面からこれを見る。
 *
 * 案内端末の側には記録を見る画面を置いていない。
 * 観光客が触る端末に閲覧口があると、いつか開かれてしまうため。
 *
 * 呼ばれ方:
 *   POST /api/log.php
 *   {"client": "バスターミナル", "entries": [{...}, {...}]}
 *
 * 返すもの:
 *   {"ok": true, "saved": 12}
 *
 * 【方針】
 * 記録が取れないことより、案内が止まることの方が困る。
 * 受け取れないときも短く断るだけにして、端末側は黙って次の機会に送り直す。
 */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$config = require __DIR__ . '/config.php';

function respond(array $body, int $status = 200): void
{
    http_response_code($status);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function refuse(string $reason, int $status): void
{
    respond(['ok' => false, 'reason' => $reason], $status);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    refuse('method_not_allowed', 405);
}

// 案内アプリと同じサイトからの呼び出しだけを受ける。
// 誰でも書き込める状態だと、記録が荒らされて統計が使えなくなる。
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
        refuse('forbidden', 403);
    }
}

$request = json_decode((string) file_get_contents('php://input'), true);
if (!is_array($request) || !is_array($request['entries'] ?? null)) {
    refuse('bad_request', 400);
}

// どの端末から来たか。統計を案内所ごとに分けるために使う。
$client = trim((string) ($request['client'] ?? ''));
if ($client === '' || mb_strlen($client) > 40) {
    $client = '不明';
}

/// 1回に受け取る件数の上限。これを超える分は次の機会に送られてくる。
const MAX_ENTRIES = 300;

/// 記録して良い項目だけを取り出す。
/// 端末から送られてきたものをそのまま書くと、細工された値が混ざる。
function clean(array $entry, string $client): ?array
{
    $text = trim((string) ($entry['recognized'] ?? ''));
    if ($text === '') {
        return null;
    }

    $source = (string) ($entry['source'] ?? '');
    if (!in_array($source, ['faq', 'ai', 'none'], true)) {
        $source = 'none';
    }

    $at = (string) ($entry['at'] ?? '');
    // 端末の時計が狂っていることがあるので、読めない値は受け取った時刻にする
    if ($at === '' || strtotime($at) === false) {
        $at = date('c');
    }

    return [
        'at' => $at,
        'client' => $client,
        'place' => mb_substr(trim((string) ($entry['place'] ?? '')), 0, 40),
        'lang' => mb_substr(preg_replace('/[^a-zA-Z]/', '', (string) ($entry['lang'] ?? '')), 0, 8),
        'recognized' => mb_substr($text, 0, 200),
        'faq_id' => mb_substr(trim((string) ($entry['faq_id'] ?? '')), 0, 60),
        'source' => $source,
        'category' => mb_substr(trim((string) ($entry['category'] ?? '')), 0, 40),
        'voice' => mb_substr(trim((string) ($entry['voice'] ?? '')), 0, 20),
        'received' => date('c'),
    ];
}

$lines = [];
foreach (array_slice($request['entries'], 0, MAX_ENTRIES) as $entry) {
    if (!is_array($entry)) {
        continue;
    }
    $row = clean($entry, $client);
    if ($row !== null) {
        $lines[] = json_encode($row, JSON_UNESCAPED_UNICODE);
    }
}

if ($lines === []) {
    respond(['ok' => true, 'saved' => 0]);
}

$path = $config['question_log_path'] ?? (__DIR__ . '/data/question_log.jsonl');
$written = @file_put_contents(
    $path,
    implode("\n", $lines) . "\n",
    FILE_APPEND | LOCK_EX
);
if ($written === false) {
    // 端末側は次の機会に送り直すので、ここで詳しく返す必要はない
    refuse('cannot_write', 500);
}

respond(['ok' => true, 'saved' => count($lines)]);
