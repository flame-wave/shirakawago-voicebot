<?php
/**
 * 溜まった質問の記録を渡す（管理者画面が読みに来る）。
 *
 * 呼ばれ方:
 *   GET /api/logs.php?token=＜合言葉＞
 *   GET /api/logs.php?token=＜合言葉＞&kind=ai   … AIが答えた分の記録
 *
 *   POST /api/logs.php   {"token": "…", "action": "clear"}
 *   POST /api/logs.php   {"token": "…", "action": "clear", "before": "2026-11-01"}
 *        … 記録を消す（本番を始める前に、試しの記録を消すため）。
 *          before を付けると、その日より前の分だけを消す（日付は日本時間）。
 *
 * 返すもの: GET は1行1件のJSONL、POST は {"ok": true, "deleted": 件数, ...}
 *
 * 【消したあとに古い記録が戻ってこないように】
 * 案内端末は、送れなかった記録をブラウザに溜めておき、あとでまとめて送る。
 * 記録を消しても、端末に残っていた試しの頃の記録が届くと元に戻ってしまう。
 * そこで、消した時点（または指定の日）を data/log_since.txt に残し、
 * log.php はそれより前の時刻の記録を受け取らないようにしている。
 * こうすれば、端末を1台ずつ回って消さなくてよい。
 *
 * 【方針】
 * 質問の内容は観光客の声そのものなので、合言葉を知っている人だけが読める。
 * 合言葉は config.php にだけ置き、案内アプリ側には持たせない。
 */

declare(strict_types=1);

$config = require __DIR__ . '/config.php';

$token = (string) ($config['log_token'] ?? '');

// 消すときは POST で受ける（GET だとリンクを開いただけ・先読みだけで消えかねないため）
$isPost = ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST';
$body = $isPost ? json_decode((string) file_get_contents('php://input'), true) : null;
$given = $isPost ? (string) ($body['token'] ?? '') : (string) ($_GET['token'] ?? '');

// 合言葉を決めていない場合は、誰にも渡さない。
// 空を「制限なし」にすると、設定し忘れがそのまま公開になる。
if ($token === '' || !hash_equals($token, $given)) {
    http_response_code(403);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'reason' => 'forbidden'], JSON_UNESCAPED_UNICODE);
    exit;
}

if ($isPost) {
    clear_logs($config, is_array($body) ? $body : []);
    exit;
}

/**
 * 記録を消す。before が無ければすべて、あればその日（日本時間の0時）より前を消す。
 */
function clear_logs(array $config, array $body): void
{
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');

    if (($body['action'] ?? '') !== 'clear') {
        http_response_code(400);
        echo json_encode(['ok' => false, 'reason' => 'bad_request'], JSON_UNESCAPED_UNICODE);
        return;
    }

    $before = trim((string) ($body['before'] ?? ''));
    if ($before !== '' && !preg_match('/^\d{4}-\d{2}-\d{2}$/', $before)) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'reason' => 'bad_date'], JSON_UNESCAPED_UNICODE);
        return;
    }
    // 消す境目。日付だけなら日本時間のその日の0時。指定が無ければ「いま」。
    $cutoff = $before === ''
        ? time()
        : (new DateTimeImmutable($before . 'T00:00:00', new DateTimeZone('Asia/Tokyo')))->getTimestamp();

    $paths = [
        $config['question_log_path'] ?? (__DIR__ . '/data/question_log.jsonl'),
        $config['log_path'] ?? (__DIR__ . '/data/ai_log.jsonl'),
    ];
    $deleted = 0;
    $kept = 0;
    foreach ($paths as $path) {
        if (!is_file($path)) {
            continue;
        }
        $fp = fopen($path, 'c+');
        if ($fp === false || !flock($fp, LOCK_EX)) {
            http_response_code(500);
            echo json_encode(['ok' => false, 'reason' => 'cannot_open'], JSON_UNESCAPED_UNICODE);
            return;
        }
        $keep = [];
        while (($line = fgets($fp)) !== false) {
            $line = rtrim($line, "\r\n");
            if ($line === '') {
                continue;
            }
            $row = json_decode($line, true);
            $at = is_array($row) ? strtotime((string) ($row['at'] ?? '')) : false;
            // 時刻が読めない行は、消す側に入れる（いつの記録か分からないため）
            if ($before !== '' && $at !== false && $at >= $cutoff) {
                $keep[] = $line;
                $kept++;
            } else {
                $deleted++;
            }
        }
        ftruncate($fp, 0);
        rewind($fp);
        if ($keep !== []) {
            fwrite($fp, implode("\n", $keep) . "\n");
        }
        fflush($fp);
        flock($fp, LOCK_UN);
        fclose($fp);
    }

    // 境目を残す（あとで届く古い記録を受け取らないため）。前より新しいときだけ進める。
    $sincePath = $config['log_since_path'] ?? (__DIR__ . '/data/log_since.txt');
    $old = is_file($sincePath) ? strtotime(trim((string) file_get_contents($sincePath))) : false;
    if ($old === false || $cutoff > $old) {
        @file_put_contents($sincePath, date('c', $cutoff), LOCK_EX);
    }

    echo json_encode([
        'ok' => true, 'deleted' => $deleted, 'kept' => $kept, 'since' => date('c', $cutoff),
    ], JSON_UNESCAPED_UNICODE);
}

$kind = (string) ($_GET['kind'] ?? 'question');
$path = $kind === 'ai'
    ? ($config['log_path'] ?? (__DIR__ . '/data/ai_log.jsonl'))
    : ($config['question_log_path'] ?? (__DIR__ . '/data/question_log.jsonl'));

header('Content-Type: application/x-ndjson; charset=utf-8');
header('Cache-Control: no-store');

if (!is_file($path)) {
    exit;   // まだ1件も無い。空で返すのが正しい。
}

// 件数が増えても memory を使い切らないよう、読みながら流す
$fp = fopen($path, 'rb');
if ($fp === false) {
    http_response_code(500);
    exit;
}
while (!feof($fp)) {
    echo fread($fp, 65536);
}
fclose($fp);
