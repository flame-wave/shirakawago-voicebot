import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'app_language.dart';

/// 回答の表示部分。
/// 字幕・写真・QRコードをまとめて扱う。
///
/// 写真は「シャトルバス乗り場はどこ」のように、言葉より画像の方が
/// 早く伝わる質問のために用意する。言語が通じない相手にも有効。
/// QRコードは、音声で伝えきれない詳細（時刻表など）への導線。
class AnswerView extends StatelessWidget {
  final String answer;
  final String photo; // 例: shuttle_stop.jpg（空なら表示しない）
  final String link;  // 例: https://...（空なら表示しない）
  final AppLanguage lang;
  final bool isFallback; // 翻訳が未整備で日本語を表示しているか

  const AnswerView({
    super.key,
    required this.answer,
    this.photo = '',
    this.link = '',
    this.lang = AppLanguage.ja,
    this.isFallback = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xFFC3D2BC)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 左：字幕（騒音対策・聴覚への配慮）
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                // 翻訳が未整備のときは、日本語表示であることを断る
                if (isFallback && answer.isNotEmpty) ...[
                  Text(
                    UiStrings.of('translationPending', lang),
                    style: const TextStyle(
                        fontSize: 13, color: Color(0xFFB85042)),
                  ),
                  const SizedBox(height: 6),
                ],
                Text(
                  answer.isEmpty ? '　' : answer,
                  style: const TextStyle(fontSize: 22, height: 1.5),
                ),
              ],
            ),
          ),

          // 右：詳細ページへのQRコード
          if (link.isNotEmpty) ...[
            const SizedBox(width: 16),
            Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  color: Colors.white,
                  child: QrImageView(
                    data: link,
                    size: 110,
                    backgroundColor: Colors.white,
                    // 汚れや反射があっても読めるよう誤り訂正を高めに
                    errorCorrectionLevel: QrErrorCorrectLevel.H,
                  ),
                ),
                const SizedBox(height: 4),
                SizedBox(
                  width: 120,
                  child: Text(
                    UiStrings.of('scanForDetails', lang),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 12, color: Colors.black54),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  /// 写真部分は上部に大きく出したいので、別のウィジェットとして提供する。
  /// 写真が無い場合や読み込めない場合は null を返し、呼び出し側で表示を省略する。
  static Widget? photoWidget(String photo) {
    if (photo.isEmpty) return null;
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: Image.asset(
        'assets/photo/$photo',
        fit: BoxFit.contain,
        errorBuilder: (context, error, stackTrace) {
          // ファイルが無くても落ちない。字幕と音声だけで案内は成立する。
          return const SizedBox.shrink();
        },
      ),
    );
  }
}
