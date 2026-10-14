<?php
/**
 * いま公開している質問回答集の版を伝える。
 *
 * 呼ばれ方:
 *   GET  /api/version.php
 *        … {"ref": "＜GitHubのコミット＞", "version": "2026-10-14 13:44", "at": "…"}
 *          案内端末が1分ごとに見に来る（小さな返事なので負担はほとんど無い）。
 *   POST /api/version.php   {"token": "…", "ref": "＜コミット＞", "version": "…"}
 *        … 管理画面が「案内アプリへ反映する」のあとに呼ぶ。合言葉は logs.php と同じ。
 *
 * 【なぜ要るのか】
 * 質問回答集は GitHub の raw から配っている。raw は5分間、古い写しを返すことがあり、
 * 反映してもすぐには届かなかった。コミットを指定した URL（…/＜コミット＞/assets/faq.json）
 * なら古い写しは返らないので、案内端末とAIの中継（ask.php）は、ここで知った
 * コミットを指定して読む。これで反映から1分ほどで届く。
 *
 * ここが動いていない・まだ反映していないときは ref が空になり、
 * 案内端末はこれまでどおり数分ごとに確かめる形に戻る。
 */

declare(strict_types=1);

$config = require __DIR__ . '/config.php';
$path = (string) ($config['version_path'] ?? (__DIR__ . '/data/version.json'));

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    $body = json_decode((string) file_get_contents('php://input'), true);
    $token = (string) ($config['log_token'] ?? '');
    $given = is_array($body) ? (string) ($body['token'] ?? '') : '';
    // 合言葉を決めていない場合は受け付けない（空を「制限なし」にしない）
    if ($token === '' || !hash_equals($token, $given)) {
        http_response_code(403);
        echo json_encode(['ok' => false, 'reason' => 'forbidden']);
        exit;
    }
    $ref = strtolower((string) ($body['ref'] ?? ''));
    if (!preg_match('/^[0-9a-f]{40}$/', $ref)) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'reason' => 'bad_ref']);
        exit;
    }
    $version = mb_substr(trim((string) ($body['version'] ?? '')), 0, 40);
    $row = ['ref' => $ref, 'version' => $version, 'at' => date('c')];
    $ok = @file_put_contents($path, json_encode($row, JSON_UNESCAPED_UNICODE), LOCK_EX) !== false;
    if (!$ok) {
        http_response_code(500);
    }
    echo json_encode(['ok' => $ok], JSON_UNESCAPED_UNICODE);
    exit;
}

$row = is_file($path) ? json_decode((string) @file_get_contents($path), true) : null;
if (!is_array($row) || !preg_match('/^[0-9a-f]{40}$/', (string) ($row['ref'] ?? ''))) {
    $row = ['ref' => '', 'version' => '', 'at' => ''];
}
echo json_encode([
    'ref' => (string) $row['ref'],
    'version' => (string) ($row['version'] ?? ''),
    'at' => (string) ($row['at'] ?? ''),
], JSON_UNESCAPED_UNICODE);
