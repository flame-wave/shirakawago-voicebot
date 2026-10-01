import 'dart:math' as math;

import 'package:flutter/material.dart';

/// 背景。白川郷の合掌造り集落を、キャラクターの近未来的な意匠に合わせて描く。
///
/// 画像ファイルではなくコードで描いているのは、
/// どの画面サイズでも破綻せず、素材の管理も要らないため。
///
/// 前面に白い吹き出しと文字が載るので、全体を淡くして可読性を優先している。
class BackgroundView extends StatelessWidget {
  const BackgroundView({super.key});

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: CustomPaint(
        painter: _ScenePainter(),
        size: Size.infinite,
      ),
    );
  }
}

class _ScenePainter extends CustomPainter {
  // 空
  static const _skyTop = Color(0xFFF4F9FB);
  static const _skyMid = Color(0xFFE9F3F2);
  static const _skyBottom = Color(0xFFDFEEE9);
  // 地形
  static const _ridgeFar = Color(0xC6CBDACE);
  static const _ridgeNear = Color(0xCDB0C6B5);
  static const _ground = Color(0x78C6DACC);
  // 建物と発光
  static const _house = Color(0xEB78907F);
  static const _windowGlow = Color(0xAF68DEDA);
  static const _tech = Color(0xFF56BEC4);

  /// 雪は毎フレーム位置が変わらないよう、固定の種から作る
  static final List<Offset> _snow = _makeSnow();
  static List<Offset> _makeSnow() {
    final rnd = math.Random(5);
    return List.generate(80, (_) => Offset(rnd.nextDouble(), rnd.nextDouble() * 0.85));
  }

  static final List<double> _snowSize =
      List.generate(80, (i) => 1.0 + math.Random(100 + i).nextDouble() * 1.6);

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final horizon = h * 0.60;
    canvas.clipRect(Offset.zero & size);

    _paintSky(canvas, size);
    _paintGlow(canvas, w, horizon);
    _paintRidge(canvas, w, horizon, 0.0055, 0.019, 34, 52, _ridgeFar);
    _paintRidge(canvas, w, horizon, 0.0092, 0.028, 10, 34, _ridgeNear);
    _paintGround(canvas, w, h, horizon);
    _paintGrid(canvas, w, h, horizon);
    _paintVillage(canvas, w, horizon);
    _paintScanlines(canvas, w, h);
    _paintRings(canvas, w, h);
    _paintHorizonLine(canvas, w, horizon);
    _paintSnow(canvas, w, h);
  }

  void _paintSky(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [_skyTop, _skyMid, _skyBottom],
          stops: [0.0, 0.6, 1.0],
        ).createShader(rect),
    );
  }

  /// 朝もやのような滲んだ光
  void _paintGlow(Canvas canvas, double w, double horizon) {
    final center = Offset(w * 0.58, horizon - 20);
    final rect = Rect.fromCenter(center: center, width: 520, height: 260);
    canvas.drawOval(
      rect,
      Paint()
        ..shader = RadialGradient(
          colors: [const Color(0x4096EBE4), const Color(0x0096EBE4)],
        ).createShader(rect)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 40),
    );
  }

  /// 山の稜線
  void _paintRidge(Canvas canvas, double w, double horizon, double a, double b,
      double dy, double amp, Color color) {
    final path = Path()..moveTo(0, horizon - dy);
    for (double x = 0; x <= w; x += 26) {
      final y = horizon - dy - amp * (math.sin(x * a)).abs() - amp * 0.35 * math.sin(x * b);
      path.lineTo(x, y);
    }
    path
      ..lineTo(w, horizon - dy)
      ..lineTo(w, horizon + 2)
      ..lineTo(0, horizon + 2)
      ..close();
    canvas.drawPath(path, Paint()..color = color);
  }

  void _paintGround(Canvas canvas, double w, double h, double horizon) {
    canvas.drawRect(
      Rect.fromLTRB(0, horizon, w, h),
      Paint()..color = _ground,
    );
  }

  /// 奥に収束するグリッド（近未来的な地面）
  void _paintGrid(Canvas canvas, double w, double h, double horizon) {
    final vp = Offset(w * 0.52, horizon);
    final line = Paint()
      ..color = _tech.withValues(alpha: 0.12)
      ..strokeWidth = 1;

    for (int i = -10; i <= 10; i++) {
      canvas.drawLine(vp, Offset(vp.dx + i * w * 0.19, h), line);
    }
    final across = Paint()
      ..color = _tech.withValues(alpha: 0.10)
      ..strokeWidth = 1;
    for (int j = 1; j < 14; j++) {
      final t = j / 14;
      final y = horizon + (h - horizon) * math.pow(t, 2.0);
      canvas.drawLine(Offset(0, y), Offset(w, y), across);
    }
  }

  /// 合掌造りの集落。急勾配の切妻屋根と、妻面の窓明かり。
  void _paintVillage(Canvas canvas, double w, double horizon) {
    // 画面幅に対する比率で配置し、どの端末でも同じ並びになるようにする
    const layout = [
      [0.076, 0.076, 26.0],
      [0.197, 0.061, 18.0],
      [0.339, 0.089, 34.0],
      [0.516, 0.068, 22.0],
      [0.658, 0.082, 30.0],
      [0.805, 0.058, 16.0],
      [0.926, 0.071, 24.0],
    ];
    for (final it in layout) {
      _paintGassho(canvas, w * it[0], w * it[1], horizon + it[2]);
    }
  }

  void _paintGassho(Canvas canvas, double cx, double width, double base) {
    final roofH = width * 1.15;
    final wallH = width * 0.26;
    final body = Paint()..color = _house;

    canvas.drawRect(
      Rect.fromLTRB(cx - width * 0.40, base - wallH, cx + width * 0.40, base),
      body,
    );
    final roof = Path()
      ..moveTo(cx, base - wallH - roofH)
      ..lineTo(cx - width / 2, base - wallH)
      ..lineTo(cx + width / 2, base - wallH)
      ..close();
    canvas.drawPath(roof, body);

    final glow = Paint()..color = _windowGlow;
    for (final win in [
      [0.60, 0.11, 0.085],
      [0.40, 0.10, 0.070],
    ]) {
      canvas.drawRect(
        Rect.fromLTRB(
          cx - width * win[2],
          base - wallH - roofH * win[0],
          cx + width * win[2],
          base - wallH - roofH * (win[0] - win[1]),
        ),
        glow,
      );
    }
  }

  /// 走査線（画面全体にうっすら）
  void _paintScanlines(Canvas canvas, double w, double h) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.06)
      ..strokeWidth = 1;
    for (double y = 0; y < h; y += 6) {
      canvas.drawLine(Offset(0, y), Offset(w, y), paint);
    }
  }

  /// 浮遊するリング
  void _paintRings(Canvas canvas, double w, double h) {
    const rings = [
      [0.16, 0.16, 52.0, 0.13],
      [0.82, 0.10, 34.0, 0.12],
      [0.70, 0.30, 20.0, 0.10],
    ];
    for (final r in rings) {
      final center = Offset(w * r[0], h * r[1]);
      final outer = Paint()
        ..color = _tech.withValues(alpha: r[3])
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2;
      final inner = Paint()
        ..color = _tech.withValues(alpha: r[3] * 0.7)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1;
      canvas.drawCircle(center, r[2], outer);
      canvas.drawCircle(center, r[2] * 0.58, inner);
    }
  }

  void _paintHorizonLine(Canvas canvas, double w, double horizon) {
    canvas.drawLine(
      Offset(0, horizon),
      Offset(w, horizon),
      Paint()
        ..color = _tech.withValues(alpha: 0.42)
        ..strokeWidth = 2,
    );
  }

  void _paintSnow(Canvas canvas, double w, double h) {
    final paint = Paint()..color = Colors.white.withValues(alpha: 0.5);
    for (int i = 0; i < _snow.length; i++) {
      canvas.drawCircle(
        Offset(_snow[i].dx * w, _snow[i].dy * h),
        _snowSize[i],
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_ScenePainter oldDelegate) => false;
}
