import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'app_language.dart';
import 'speech_bubble.dart';

/// 回答の表示。吹き出しの中に文章、外に写真とQRコードを置く。
///
/// 写真やQRを吹き出しに入れると、文章が押し出されて読みにくくなるため、
/// 「話した内容」と「見て確認するもの」を分けている。
class AnswerView extends StatelessWidget {
  final String answer;
  final String photo; // 例: shuttle_stop.jpg（空なら表示しない）
  final String link;  // 例: https://...（空なら表示しない）
  final AppLanguage lang;
  final bool isFallback; // 翻訳が未整備で日本語を表示しているか
  final String placeholder; // 回答がまだ無いときに出す案内

  const AnswerView({
    super.key,
    required this.answer,
    this.photo = '',
    this.link = '',
    this.lang = AppLanguage.ja,
    this.isFallback = false,
    this.placeholder = '',
  });

  bool get _hasMedia => photo.isNotEmpty || link.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    final empty = answer.isEmpty;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 吹き出し（回答の文章）
        Flexible(
          child: SpeechBubble(
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  // 翻訳が未整備のときは、日本語表示であることを断る
                  if (isFallback && !empty) ...[
                    Text(
                      UiStrings.of('translationPending', lang),
                      style: const TextStyle(
                          fontSize: 13, color: Color(0xFFB85042)),
                    ),
                    const SizedBox(height: 8),
                  ],
                  Text(
                    empty ? placeholder : answer,
                    style: TextStyle(
                      fontSize: empty ? 19 : 23,
                      height: 1.6,
                      color: empty ? Colors.black45 : const Color(0xFF2B2B2B),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),

        // 吹き出しの外：写真とQRコード
        if (_hasMedia) ...[
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (photo.isNotEmpty)
                Flexible(child: _photo(photo)),
              if (photo.isNotEmpty && link.isNotEmpty)
                const SizedBox(width: 14),
              if (link.isNotEmpty) _qr(link),
            ],
          ),
        ],
      ],
    );
  }

  Widget _photo(String name) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: Image.asset(
        'assets/photo/$name',
        height: 150,
        fit: BoxFit.cover,
        // 写真が無くても表示は崩さない
        errorBuilder: (_, __, ___) => const SizedBox.shrink(),
      ),
    );
  }

  Widget _qr(String url) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: const Color(0xFFC3D2BC)),
            borderRadius: BorderRadius.circular(10),
          ),
          child: QrImageView(
            data: url,
            size: 108,
            // 汚れや反射に強くするため誤り訂正を高めにする
            errorCorrectionLevel: QrErrorCorrectLevel.H,
          ),
        ),
        const SizedBox(height: 4),
        SizedBox(
          width: 124,
          child: Text(
            UiStrings.of('scanForDetails', lang),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12, color: Colors.black54),
          ),
        ),
      ],
    );
  }
}