<?php
/**
 * 中継の設定。
 *
 * このファイルを config.php という名前でコピーし、値を入れて使う。
 * config.php はAPIキーを含むため、リポジトリに入れないこと（.gitignore 済み）。
 *
 * ここは公開時（api/ と assets/ と webapp/ を並べて置く）の書き方。
 * 手元のリポジトリで動かすときだけ、faq_path を1つ上に変える。
 */

return [
    // ---- AIの窓口（Anthropic の Messages API）
    'base_url' => 'https://api.anthropic.com',
    'model' => 'claude-haiku-4-5',   // 速くて安い。賢さが要るなら claude-sonnet-5-5
    'api_key' => 'ここにAnthropicのAPIキー（sk-ant-…）',

    // ---- 同じ資料を毎回送るので、使い回し（プロンプトキャッシュ）を効かせる。
    // 2回目以降、指示文と参考資料の分が10分の1の料金になる。
    // 効くのは直前の質問から5分以内。閑散期は効かないが、損にはならない。
    'cache' => true,

    // ---- 参照する資料（案内アプリが読むものと同じファイル）
    'faq_path' => __DIR__ . '/../assets/faq.json',
    // 手元のリポジトリで動かすときは __DIR__ . '/../../assets/faq.json'

    // ---- 配信URL（管理画面から反映した最新の質問回答集）。
    // 設定すると、こちらを読んで控えを取る。案内アプリの REMOTE_URL と同じURLにする。
    // 空なら上の faq_path だけを見る。
    //   例: https://raw.githubusercontent.com/ユーザ名/リポジトリ名/main/assets/faq.json
    'faq_url' => '',
    'faq_cache_path' => __DIR__ . '/data/faq_cache.json',
    'faq_cache_minutes' => 30,

    // ---- 呼び出しを許す元（案内アプリを置いた場所）
    // 空にすると誰でも叩けてしまうため、必ず設定する。
    'allow_origins' => [
        'https://example.com',
    ],

    // ---- 使いすぎを止める上限
    'max_per_minute' => 10,
    'max_per_day' => 500,
    'counter_path' => __DIR__ . '/data/counter.json',

    // ---- AIの回答を残す場所（職員が後から確認する）
    'log_path' => __DIR__ . '/data/ai_log.jsonl',

    // ---- 質問の記録を残す場所（案内端末から送られてくる）
    'question_log_path' => __DIR__ . '/data/question_log.jsonl',

    // ---- 記録を読み出すときの合言葉（管理者画面がこれを使う）
    // 決めないと誰も読めない。長い無作為の文字列にすること。
    //   例: php -r "echo bin2hex(random_bytes(24));"
    'log_token' => 'ここに長い無作為の文字列',

    // ---- 待ち時間（秒）。これを超えたら案内アプリは職員案内に切り替える
    'timeout' => 8,
];
