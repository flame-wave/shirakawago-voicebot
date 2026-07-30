import 'package:flutter/material.dart';

/// キャラクターの状態。システムの状況に対応する。
enum CharacterState {
  idle,      // 待機中
  listening, // 聞き取り中
  talking,   // 回答中（喋っている）
}

/// 状態ごとに表示する画像ファイルを対応づける部品。
/// 画像を差し替えたい・表情を増やしたいときはここだけ直す。
class CharacterView extends StatelessWidget {
  final CharacterState state;

  const CharacterView({super.key, required this.state});

  // 状態 → 画像ファイル名の対応表
  String get _assetPath {
    switch (state) {
      case CharacterState.listening:
        return 'assets/character/listening.png';
      case CharacterState.talking:
        return 'assets/character/talking.png';
      case CharacterState.idle:
        return 'assets/character/idle.png';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFEDF4E6),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Center(
        // 画像がまだ無いときは仮アイコンを出す（用意でき次第自動で絵に）
        child: Image.asset(
          _assetPath,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) {
            return Icon(
              state == CharacterState.talking
                  ? Icons.record_voice_over
                  : state == CharacterState.listening
                      ? Icons.hearing
                      : Icons.face,
              size: 120,
              color: const Color(0xFF2C5F2D),
            );
          },
        ),
      ),
    );
  }
}
