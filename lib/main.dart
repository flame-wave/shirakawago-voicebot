import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'faq_service.dart';
import 'faq_repository.dart';
import 'character_view.dart';
import 'voice_service.dart';
import 'answer_view.dart';
import 'app_language.dart';
import 'language_selector.dart';
import 'background_view.dart';
import 'question_log.dart';
import 'log_screen.dart';

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
  // --- 部品（差し替え可能な単位） ---
  final SpeechToText _speech = SpeechToText();   // 音声認識
  final FaqService _faqService = FaqService();   // FAQ検索
  final FaqRepository _repo = FaqRepository();   // FAQデータの取得
  final VoiceService _voice = VoiceService();    // 読み上げ（音声ファイル／端末音声）
  final QuestionLog _log = QuestionLog();       // 質問の記録

  // --- 画面の状態 ---
  bool _speechReady = false;
  bool _listening = false;
  String _recognized = '';
  String _answer = '';
  String _photo = '';   // 表示中の回答の写真
  String _link = '';    // 表示中の回答のリンク（QRコード）
  CharacterState _charState = CharacterState.idle;
  String _dataVersion = '';
  String _dataSource = '';
  AppLanguage _lang = AppLanguage.ja;      // 選択中の言語
  bool _isFallback = false;                // 翻訳未整備で日本語を表示中か
  Set<String> _speechLocales = {};         // 端末が対応する認識ロケール

  @override
  void initState() {
    super.initState();
    _init();
  }

  @override
  void dispose() {
    _voice.dispose();
    super.dispose();
  }

  Future<void> _init() async {
    // 読み上げ終了で待機表情に戻す
    _voice.onComplete = () {
      if (mounted) setState(() => _charState = CharacterState.idle);
    };
    await _voice.init();

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
      onStatus: (s) {
        debugPrint('音声認識ステータス: $s');
        // 無音が続いて自動終了した場合も、ボタンの表示を戻す
        if ((s == 'notListening' || s == 'done') && mounted && _listening) {
          setState(() {
            _listening = false;
            if (_charState == CharacterState.listening) {
              _charState = CharacterState.idle;
            }
          });
        }
      },
    );
    if (!_speechReady && mounted) {
      setState(() => _answer = '音声認識を初期化できませんでした');
    }

    // 端末がどの言語の音声認識に対応しているかを調べておく
    if (_speechReady) {
      try {
        final locales = await _speech.locales();
        _speechLocales = locales.map((l) => l.localeId).toSet();
        debugPrint('認識可能なロケール: ${_speechLocales.length}件');
        for (final lang in AppLanguage.values) {
          if (!_supportsSpeech(lang)) {
            debugPrint('  ${lang.label} (${lang.speechLocale}) は非対応');
          }
        }
      } catch (e) {
        debugPrint('ロケール一覧の取得に失敗: $e');
      }
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

  /// 端末がその言語の音声認識に対応しているか
  bool _supportsSpeech(AppLanguage lang) {
    if (_speechLocales.isEmpty) return true; // 取得できていないときは試させる
    final target = lang.speechLocale.toLowerCase().replaceAll('-', '_');
    final prefix = target.split('_').first;
    return _speechLocales.any((id) {
      final normalized = id.toLowerCase().replaceAll('-', '_');
      return normalized == target || normalized.startsWith('${prefix}_');
    });
  }

  /// 言語ボタンが押されたときの処理
  Future<void> _changeLanguage(AppLanguage lang) async {
    if (lang == _lang) return;
    await _speech.stop();
    await _voice.stop();
    await _voice.setLanguage(lang);
    setState(() {
      _lang = lang;
      _listening = false;
      _recognized = '';
      _photo = '';
      _link = '';
      _isFallback = false;
      _charState = CharacterState.idle;
      // その言語で音声が使えない場合は、その旨を先に伝える
      _answer = _supportsSpeech(lang)
          ? ''
          : UiStrings.of('speechUnavailable', lang);
    });
    debugPrint('言語を切り替え: ${lang.label}');
  }

  /// 「押して話す」を押したときの処理
  Future<void> _startListening() async {
    if (!_speechReady) return;
    await _voice.stop(); // 読み上げ中なら止めて質問を優先する
    setState(() {
      _listening = true;
      _recognized = '';
      _answer = '';
      _photo = '';
      _link = '';
      _isFallback = false;
      _charState = CharacterState.listening;
    });
    await _speech.listen(
      localeId: _lang.speechLocale,
      // もう一度押すまで待つ方式なので、自動で切れるまでの時間を長めにとる
      listenFor: const Duration(seconds: 60),
      pauseFor: const Duration(seconds: 10),
      onResult: (result) {
        setState(() => _recognized = result.recognizedWords);
        if (result.finalResult) {
          _handleQuestion(_recognized);
        }
      },
    );
  }

  Future<void> _stopListening() async {
    await _speech.stop();
    if (!mounted) return;
    setState(() {
      _listening = false;
      if (_charState == CharacterState.listening) {
        _charState = CharacterState.idle;
      }
    });
  }

  /// ボタンを押すたびに開始と終了を切り替える。
  /// 押し続ける方式だと、指が少し離れただけで録音が切れてしまうため。
  Future<void> _toggleListening() async {
    if (_listening) {
      await _stopListening();
    } else {
      await _startListening();
    }
  }

  /// 認識した質問をFAQ検索にかけ、表示と読み上げを行う
  Future<void> _handleQuestion(String question) async {
    setState(() => _listening = false);

    // 何も聞き取れていない場合は、案内も記録もせずに待機に戻す
    if (question.trim().isEmpty) {
      setState(() => _charState = CharacterState.idle);
      return;
    }

    final faq = _faqService.search(question, _lang);

    if (faq == null) {
      // 該当なし＝ガードレール発動、職員へ誘導
      final fallback = UiStrings.of('staffReferral', _lang);
      setState(() {
        _answer = fallback;
        _photo = '';
        _link = '';
        _isFallback = false;
        _charState = CharacterState.talking;
      });
      // 画面が見えない方にも伝わるよう、この案内も読み上げる
      final mode = await _voice.speakText(fallback);
      // 答えられなかった質問こそ、FAQ拡充の材料になる
      await _log.add(LogEntry(
        at: DateTime.now(),
        lang: _lang.code,
        recognized: question,
        faqId: null,
        category: '',
        translationFallback: false,
        voiceMode: mode.name,
      ));
      return;
    }

    final localized = faq.answerFor(_lang);
    setState(() {
      _answer = localized.text;
      _photo = faq.photo;
      _link = faq.link;
      _isFallback = localized.isFallback;
      _charState = CharacterState.talking;
    });

    // 音声ファイルがあればそれを、無ければ端末音声で読み上げる
    final mode = await _voice.speak(faq, _lang);
    final note = localized.isFallback ? ' (日本語で代替)' : '';
    debugPrint('読み上げ方法: $mode / 言語: ${_lang.label}$note');

    await _log.add(LogEntry(
      at: DateTime.now(),
      lang: _lang.code,
      recognized: question,
      faqId: faq.id,
      category: faq.category,
      translationFallback: localized.isFallback,
      voiceMode: mode.name,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('白川郷 音声案内'),
        backgroundColor: const Color(0xFF2C5F2D),
        foregroundColor: Colors.white,
        actions: [
          // 職員が更新の反映を確認するための表示。
          // 長押しで質問記録の画面を開く（観光客には見えない導線）。
          GestureDetector(
            onLongPress: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => LogScreen(log: _log)),
              );
            },
            child: Padding(
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
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 会話の領域。キャラクターを大きく置き、その左に吹き出しを重ねる。
            Expanded(
              child: LayoutBuilder(
                builder: (context, box) {
                  return ClipRRect(
                    borderRadius: BorderRadius.circular(18),
                    child: Stack(
                    clipBehavior: Clip.hardEdge,
                    children: [
                      // 背景（白川郷の集落＋近未来的な意匠）
                      const Positioned.fill(child: BackgroundView()),

                      // キャラクター（右寄せ・下端に立たせる）
                      // 全身をそのまま使い、ゆっくり上下させて呼吸を表す
                      Positioned(
                        right: -20,
                        bottom: -6,
                        height: box.maxHeight * 1.02,
                        child: CharacterView(state: _charState),
                      ),

                      // 左：質問・回答の吹き出しと、その下の写真・QR
                      Positioned(
                        left: 16,
                        top: 16,
                        width: box.maxWidth * 0.54,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            // 聞き取った質問（観光客側の発話）
                            if (_recognized.isNotEmpty)
                              Container(
                                margin: const EdgeInsets.only(bottom: 10),
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 14, vertical: 8),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFEDF4E6),
                                  borderRadius: BorderRadius.circular(14),
                                ),
                                child: Text(
                                  '${UiStrings.of('question', _lang)}: $_recognized',
                                  style: const TextStyle(
                                      fontSize: 16, color: Color(0xFF2C5F2D)),
                                ),
                              ),
                            // 回答（吹き出し）と、その下の写真・QR
                            ConstrainedBox(
                              constraints: BoxConstraints(
                                maxHeight: box.maxHeight * 0.72,
                              ),
                              child: AnswerView(
                                answer: _answer,
                                photo: _photo,
                                link: _link,
                                lang: _lang,
                                isFallback: _isFallback,
                                placeholder: UiStrings.of('prompt', _lang),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 14),

            // 押して話すボタン（1回押すと開始、もう1回で終了）
            GestureDetector(
              onTap: _toggleListening,
              child: Container(
                height: 92,
                decoration: BoxDecoration(
                  color: _listening
                      ? const Color(0xFFB85042)
                      : const Color(0xFF2C5F2D),
                  borderRadius: BorderRadius.circular(46),
                ),
                child: Center(
                  child: Text(
                    _listening
                        ? UiStrings.of('listening', _lang)
                        : UiStrings.of('pressToTalk', _lang),
                    style: const TextStyle(
                      fontSize: 24,
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),

            // 言語切り替え（ボタンのすぐ下に置き、迷わないようにする）
            LanguageSelector(current: _lang, onChanged: _changeLanguage),
          ],
        ),
      ),
    );
  }
}