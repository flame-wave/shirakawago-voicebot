<?php
/**
 * 設置の確認用。ブラウザでこのファイルを開くと、次の3つを順に調べる。
 *
 *   1. PHPが動くか
 *   2. このサーバから外部へ通信できるか（レンタルサーバによっては塞がれている）
 *   3. APIキーでAIに接続できるか
 *
 * 確認が済んだら、このファイルは消しておくこと。
 * 置いたままだと、誰でもAPIの疎通を試せてしまう。
 */

declare(strict_types=1);
header('Content-Type: text/plain; charset=utf-8');

echo "1. PHP: 動いています（" . PHP_VERSION . "）\n";

if (!function_exists('curl_init')) {
    echo "   × cURLが使えません。サーバの設定を確認してください。\n";
    exit;
}

$configPath = __DIR__ . '/config.php';
if (!is_file($configPath)) {
    echo "   × config.php がありません。config.sample.php をコピーして作ってください。\n";
    exit;
}
$config = require $configPath;

// ---- 2. 外部へ出られるか
$ch = curl_init('https://www.google.com/generate_204');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 8,
    CURLOPT_NOBODY => true,
]);
curl_exec($ch);
$status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
$error = curl_error($ch);
curl_close($ch);

if ($status === 0) {
    echo "2. 外部への通信: × できません（{$error}）\n";
    echo "   このサーバでは外部APIを呼べないため、中継を別の場所に置く必要があります。\n";
    exit;
}
echo "2. 外部への通信: できます\n";

// ---- 3. AIにつながるか
$ch = curl_init(rtrim($config['base_url'], '/') . '/v1/messages');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 20,
    CURLOPT_HTTPHEADER => [
        'Content-Type: application/json',
        'x-api-key: ' . $config['api_key'],
        'anthropic-version: 2023-06-01',
    ],
    CURLOPT_POSTFIELDS => json_encode([
        'model' => $config['model'],
        'messages' => [['role' => 'user', 'content' => '「接続できました」とだけ答えてください。']],
        'max_tokens' => 100,
    ], JSON_UNESCAPED_UNICODE),
]);
$body = curl_exec($ch);
$status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($status !== 200) {
    echo "3. AIへの接続: × 失敗（HTTP {$status}）\n";
    echo "   返答: " . mb_substr((string) $body, 0, 300) . "\n";
    echo "   APIキー・モデル名・base_url を確認してください。\n";
    exit;
}

$decoded = json_decode((string) $body, true);
$text = $decoded['content'][0]['text'] ?? '(空の返答)';
echo "3. AIへの接続: できます（{$config['model']}）\n";
echo "   返答: " . trim((string) $text) . "\n\n";

// ---- 書き込み先の確認
$dir = dirname($config['counter_path']);
echo "4. 記録の保存先: " . (is_writable($dir) ? "書き込めます（{$dir}）" : "× 書き込めません（{$dir}）") . "\n";

echo "\nすべて問題なければ、このファイル（ping.php）は削除してください。\n";
