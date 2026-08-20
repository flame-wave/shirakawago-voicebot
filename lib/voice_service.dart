import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

import 'faq_service.dart';
import 'app_language.dart';

/// どの方法で喋ったか
enum VoiceMode {
  recorded,     // 用意された音声ファイル（テトなど）
  synthesized,  // 端末の音声合成
  failed,       // どちらも使えなかった
}

/// 回答の読み上げを担当する部品。
///
/// 「専用の音声ファイルがあればそれを使い、無ければ端末の音声で読む」
/// という判断をここに閉じ込める。
/// 職員がFAQを追加しても、音声ファイルが無いまま読み上げられるようにするための仕組み。
class VoiceService {
  final AudioPlayer _player = AudioPlayer();
  final FlutterTts _tts = FlutterTts();

  StreamSubscription<void>? _playerSub;

  /// 読み上げが終わったときに呼ばれる（表情を待機に戻すために使う）
  VoidCallback? onComplete;

  Future<void> init() async {
    await setLanguage(AppLanguage.ja);

    _tts.setCompletionHandler(() => onComplete?.call());
    _tts.setCancelHandler(() => onComplete?.call());
    _tts.setErrorHandler((msg) {
      debugPrint('音声合成エラー: $msg');
      onComplete?.call();
    });

    _playerSub = _player.onPlayerComplete.listen((_) => onComplete?.call());
  }

  /// 読み上げの言語を切り替える。
  /// 端末にその言語の音声が入っていない場合もあるため、結果を返す。
  Future<bool> setLanguage(AppLanguage lang) async {
    try {
      final available = await _tts.isLanguageAvailable(lang.ttsLanguage);
      if (available != true) {
        debugPrint('端末に ${lang.ttsLanguage} の音声がありません');
      }
      await _tts.setLanguage(lang.ttsLanguage);
      await _tts.setSpeechRate(0.5); // 案内なので少しゆっくり
      await _tts.setVolume(1.0);
      await _tts.awaitSpeakCompletion(true);
      return available == true;
    } catch (e) {
      debugPrint('音声合成の言語設定に失敗: $e');
      return false;
    }
  }

  /// 回答を読み上げる。使った方法を返す。
  Future<VoiceMode> speak(Faq faq, AppLanguage lang) async {
    await stop();

    final localized = faq.answerFor(lang);

    // 1. その言語の専用音声ファイルを試す
    if (localized.audio.isNotEmpty) {
      try {
        await _player.play(AssetSource('audio/${localized.audio}'));
        return VoiceMode.recorded;
      } catch (e) {
        // ファイルが無い場合はここに来る（職員が追加したFAQなど）
        debugPrint('音声ファイル ${localized.audio} を再生できないため、端末音声に切り替えます');
      }
    }

    // 2. 端末の音声合成で読む
    return speakText(localized.text);
  }

  /// 文章をそのまま端末音声で読み上げる（FAQに紐づかない案内文など）
  Future<VoiceMode> speakText(String text) async {
    if (text.isEmpty) {
      onComplete?.call();
      return VoiceMode.failed;
    }
    try {
      await _tts.speak(text);
      return VoiceMode.synthesized;
    } catch (e) {
      debugPrint('読み上げに失敗: $e');
      onComplete?.call(); // 表情が固まらないよう必ず戻す
      return VoiceMode.failed;
    }
  }

  Future<void> stop() async {
    try {
      await _player.stop();
    } catch (_) {}
    try {
      await _tts.stop();
    } catch (_) {}
  }

  void dispose() {
    _playerSub?.cancel();
    _player.dispose();
    _tts.stop();
  }
}
