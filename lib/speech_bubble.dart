import 'package:flutter/material.dart';

/// 回答を表示する吹き出し。
/// 右側にいるキャラクターに向けて尻尾を出し、話しかけられている印象にする。
class SpeechBubble extends StatelessWidget {
  final Widget child;
  final Color background;
  final Color border;

  /// 尻尾の縦位置（0.0 が上端、1.0 が下端）。
  /// キャラクターの口の高さに合わせて調整する。
  final double tailPosition;

  const SpeechBubble({
    super.key,
    required this.child,
    this.background = Colors.white,
    this.border = const Color(0xFFC3D2BC),
    this.tailPosition = 0.28,
  });

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _BubblePainter(
        background: background,
        border: border,
        tailPosition: tailPosition,
      ),
      child: Padding(
        // 右側は尻尾のぶん余白を広くとる
        padding: const EdgeInsets.fromLTRB(24, 22, 40, 22),
        child: child,
      ),
    );
  }
}

class _BubblePainter extends CustomPainter {
  final Color background;
  final Color border;
  final double tailPosition;

  static const double _radius = 18;
  static const double _tailWidth = 18;  // 尻尾の出っ張り
  static const double _tailHeight = 26; // 尻尾の根元の高さ

  _BubblePainter({
    required this.background,
    required this.border,
    required this.tailPosition,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final bodyWidth = size.width - _tailWidth;
    final body = RRect.fromRectAndRadius(
      Rect.fromLTWH(0, 0, bodyWidth, size.height),
      const Radius.circular(_radius),
    );

    // 尻尾は本体の右辺から生やす。位置は上下にはみ出さないよう収める
    final centerY = (size.height * tailPosition)
        .clamp(_radius + _tailHeight / 2, size.height - _radius - _tailHeight / 2);

    final path = Path()..addRRect(body);
    final tail = Path()
      ..moveTo(bodyWidth - 1, centerY - _tailHeight / 2)
      ..lineTo(size.width, centerY)
      ..lineTo(bodyWidth - 1, centerY + _tailHeight / 2)
      ..close();
    final combined = Path.combine(PathOperation.union, path, tail);

    canvas.drawShadow(combined, Colors.black26, 3, false);
    canvas.drawPath(combined, Paint()..color = background);
    canvas.drawPath(
      combined,
      Paint()
        ..color = border
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );
  }

  @override
  bool shouldRepaint(_BubblePainter old) =>
      old.background != background ||
      old.border != border ||
      old.tailPosition != tailPosition;
}
