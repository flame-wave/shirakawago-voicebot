<?php
/**
 * 溜まった質問の記録を渡す（管理者画面が読みに来る）。
 *
 * 呼ばれ方:
 *   GET /api/logs.php?token=＜合言葉＞
 *   GET /api/logs.php?token=＜合言葉＞&kind=ai   … AIが答えた分の記録
 *
 * 返すもの: 1行1件のJSONL
 *
 * 【方針】
 * 質問の内容は観光客の声そのものなので、合言葉を知っている人だけが読める。
 * 合言葉は config.php にだけ置き、案内アプリ側には持たせない。
 */

declare(strict_types=1);

$config = require __DIR__ . '/config.php';

$token = (string) ($config['log_token'] ?? '');
$given = (string) ($_GET['token'] ?? '');

// 合言葉を決めていない場合は、誰にも渡さない。
// 空を「制限なし」にすると、設定し忘れがそのまま公開になる。
if ($token === '' || !hash_equals($token, $given)) {
    http_response_code(403);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'reason' => 'forbidden'], JSON_UNESCAPED_UNICODE);
    exit;
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
