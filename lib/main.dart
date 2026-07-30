import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:audioplayers/audioplayers.dart';
import 'faq_service.dart';
import 'faq_repository.dart';
import 'character_view.dart';

void main() {
  runApp(const ShirakawaBotApp());
}

class ShirakawaBotApp extends StatelessWidget {
  const ShirakawaBotApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '白川郷 音声案内',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2C5F2D)),
        useMaterial3: true,
      ),
      home: const BotScreen(),
    );
  }
}

class BotScreen extends StatefulWidget {
  const BotScreen({super.key});

  @override
  State<BotScreen> createState() => _BotScreenState();
}

class _BotScreenState extends State<BotScreen> {
  // --- 部品（前回決めた差し替え可能な単位） ---
  final SpeechToText _speech = SpeechToText();   // 音声認識（第1段階：標準）
  final AudioPlayer _player = AudioPlayer();     // 音声再生
  final FaqService _faqService = FaqService();   // FAQ検索
  final FaqRepository _repo = FaqRepository();   // FAQデータの取得

  // --- 画面の状態 ---
  bool _speechReady = false;   // 音声認識の初期化が済んだか
  bool _listening = false;     // 今「聞き取り中」か
  String _recognized = '';     // 認識された質問文
  String _answer = '';         // 表示する回答（字幕）
  CharacterState _charState = CharacterState.idle; // キャラの表情
  String _dataVersion = '';    // 表示中のFAQデータの版
  String _dataSource = '';     // そのデータの出所

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    // 1. まずローカル（キャッシュ→同梱）を読む。通信を待たずにすぐ使える。
    final local = await _repo.loadLocal();
    _faqService.loadFromJson(local.json);
    if (mounted) {
      setState(() {
        _dataVersion = local.version;
        _dataSource = local.sourceLabel;
      });
    }
    debugPrint('FAQ読み込み: ${_faqService.count}件 (${local.sourceLabel} / ${local.version})');

    // 2. 音声認識を初期化
    _speechReady = await _speech.initialize(
      onError: (e) {
        debugPrint('音声認識エラー: ${e.errorMsg}');
        if (mounted) setState(() => _answer = '認識エラー: ${e.errorMsg}');
      },
      onStatus: (s) => debugPrint('音声認識ステータス: $s'),
    );
    if (!_speechReady && mounted) {
      setState(() => _answer = '音声認識を初期化できませんでした');
    }
    if (mounted) setState(() {});

    // 3. 裏で最新データを取りに行く。失敗しても表示中のデータで動き続ける。
    _refreshInBackground();
  }

  Future<void> _refreshInBackground() async {
    final remote = await _repo.fetchRemote();
    if (remote == null || !mounted) return;
    if (remote.version == _dataVersion) {
      debugPrint('FAQは最新です（${remote.version}）');
      return;
    }
    if (_faqService.loadFromJson(remote.json)) {
      setState(() {
        _dataVersion = remote.version;
        _dataSource = remote.sourceLabel;
      });
      debugPrint('FAQを更新しました: ${_faqService.count}件 (${remote.version})');
    }
  }

  /// 「押して話す」ボタンを押したときの処理
  Future<void> _startListening() async {
    if (!_speechReady) return;
    setState(() {
      _listening = true;
      _recognized = '';
      _answer = '';
      _charState = CharacterState.listening; // 聞き取り中の表情へ
    });
    await _speech.listen(
      localeId: 'ja_JP', // 第1段階は日本語。多言語化は後の段階で切替
      onResult: (result) {
        setState(() => _recognized = result.recognizedWords);
        // 認識が確定したらFAQ検索へ進む
        if (result.finalResult) {
          _handleQuestion(_recognized);
        }
      },
    );
  }

  Future<void> _stopListening() async {
    await _speech.stop();
    setState(() {
      _listening = false;
      // まだ回答に進んでいなければ待機表情へ戻す
      if (_charState == CharacterState.listening) {
        _charState = CharacterState.idle;
      }
    });
  }

  /// 認識した質問文をFAQ検索にかけ、回答表示と音声再生を行う
  Future<void> _handleQuestion(String question) async {
    setState(() => _listening = false);

    final faq = _faqService.search(question);

    if (faq == null) {
      // 該当なし＝ガードレール発動、職員へ誘導
      setState(() {
        _answer = '申し訳ございません。その質問は案内所の係員にお尋ねください。';
        _charState = CharacterState.idle; // 待機表情へ戻す
      });
      return;
    }

    // 回答表示＋喋っている表情へ
    setState(() {
      _answer = faq.answer;
      _charState = CharacterState.talking;
    });

    // 事前生成したテト音声を再生（assets/audio/ に配置）
    try {
      await _player.play(AssetSource('audio/${faq.audio}'));
      // 再生が終わったら待機表情に戻す
      _player.onPlayerComplete.first.then((_) {
        if (mounted) setState(() => _charState = CharacterState.idle);
      });
    } catch (e) {
      // 音声ファイルが無くても字幕は出るので処理は止めない
      debugPrint('音声再生エラー: $e');
      setState(() => _charState = CharacterState.idle);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('白川郷 音声案内'),
        backgroundColor: const Color(0xFF2C5F2D),
        foregroundColor: Colors.white,
        actions: [
          // 職員が更新の反映を確認するための表示
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text('データ $_dataSource',
                    style: const TextStyle(fontSize: 11, color: Colors.white70)),
                Text(_dataVersion,
                    style: const TextStyle(fontSize: 11, color: Colors.white70)),
              ],
            ),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // キャラクター表示エリア（状態に応じて表情が切り替わる）
            // 画像は assets/character/ に idle.png / listening.png / talking.png を配置。
            // 将来Live2Dにする場合も、この CharacterView を差し替えるだけでよい。
            Expanded(
              flex: 3,
              child: CharacterView(state: _charState),
            ),
            const SizedBox(height: 16),

            // 認識した質問の表示
            Text(
              _recognized.isEmpty ? '「押して話す」を押して質問してください' : '質問: $_recognized',
              style: const TextStyle(fontSize: 18, color: Colors.black54),
            ),
            const SizedBox(height: 12),

            // 回答の字幕表示（騒音対策・聴覚配慮）
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                border: Border.all(color: const Color(0xFFC3D2BC)),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _answer.isEmpty ? '　' : _answer,
                style: const TextStyle(fontSize: 22, height: 1.4),
              ),
            ),
            const SizedBox(height: 24),

            // 押して話すボタン（押している間だけ聞き取る方式）
            GestureDetector(
              onTapDown: (_) => _startListening(),
              onTapUp: (_) => _stopListening(),
              onTapCancel: () => _stopListening(),
              child: Container(
                height: 90,
                decoration: BoxDecoration(
                  color: _listening
                      ? const Color(0xFFB85042)
                      : const Color(0xFF2C5F2D),
                  borderRadius: BorderRadius.circular(45),
                ),
                child: Center(
                  child: Text(
                    _listening ? '聞き取り中…（指を離すと終了）' : '押して話す',
                    style: const TextStyle(
                      fontSize: 24,
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
