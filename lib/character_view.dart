import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

/// キャラクターの状態。システムの状況に対応する。
enum CharacterState {
  idle,      // 待機中
  listening, // 聞き取り中
  talking,   // 回答中（喋っている）
}

/// 読み込んだ画像の情報
class _Art {
  final String path;
  final double aspect; // 高さ ÷ 幅
  const _Art(this.path, this.aspect);
}

/// キャラクターを表示する部品。
///
/// 立ち絵は切り取らず全身をそのまま使う。
/// ゆっくり上下に動かして、呼吸しているように見せる。
///
/// 画像を差し替えたい・表情を増やしたいときはここだけ直す。
class CharacterView extends StatefulWidget {
  final CharacterState state;

  /// 呼吸の振れ幅（画面の論理ピクセル）。大きくすると動きが目立つ。
  final double breathAmplitude;

  /// 呼吸1往復にかける時間
  final Duration breathPeriod;

  const CharacterView({
    super.key,
    required this.state,
    this.breathAmplitude = 5,
    this.breathPeriod = const Duration(milliseconds: 4200),
  });

  @override
  State<CharacterView> createState() => _CharacterViewState();
}

class _CharacterViewState extends State<CharacterView>
    with SingleTickerProviderStateMixin {
  late final AnimationController _breath;

  /// 一度調べた画像は覚えておく（毎回の読み込みを避ける）
  static final Map<String, _Art?> _cache = {};

  @override
  void initState() {
    super.initState();
    _breath = AnimationController(vsync: this, duration: widget.breathPeriod)
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  String _fileFor(CharacterState s) {
    switch (s) {
      case CharacterState.listening:
        return 'assets/character/listening.png';
      case CharacterState.talking:
        return 'assets/character/talking.png';
      case CharacterState.idle:
        return 'assets/character/idle.png';
    }
  }

  /// 表情の画像が無い場合は idle に落とす。
  /// 立ち絵が1枚しか無い段階でも表示できるようにするため。
  Future<_Art?> _resolve() async {
    for (final path in [_fileFor(widget.state), _fileFor(CharacterState.idle)]) {
      if (_cache.containsKey(path)) {
        final cached = _cache[path];
        if (cached != null) return cached;
        continue;
      }
      try {
        final data = await rootBundle.load(path);
        final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
        final frame = await codec.getNextFrame();
        final art = _Art(path, frame.image.height / frame.image.width);
        frame.image.dispose();
        _cache[path] = art;
        return art;
      } catch (_) {
        _cache[path] = null;
      }
    }
    return null;
  }

  /// 呼吸の動き。等速の往復だと機械的に見えるため、
  /// 端がゆるやかになるよう曲線をかける。
  Widget _breathing({required Widget child}) {
    return AnimatedBuilder(
      animation: _breath,
      builder: (context, inner) {
        final eased = Curves.easeInOut.transform(_breath.value);
        // 中央を基準に上下へ振る
        final dy = (eased - 0.5) * 2 * widget.breathAmplitude;
        return Transform.translate(offset: Offset(0, dy), child: inner);
      },
      child: child,
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_Art?>(
      future: _resolve(),
      builder: (context, snap) {
        final art = snap.data;
        if (art == null) return _placeholder();

        return LayoutBuilder(
          builder: (context, box) {
            // 与えられた高さいっぱいに描き、必要な幅を逆算する。
            // 高さを基準にすることで、画面の縦横比が変わっても
            // 人物の大きさが変わらない。
            final height = box.maxHeight.isFinite
                ? box.maxHeight
                : box.maxWidth * art.aspect;
            final width = height / art.aspect;

            return _breathing(
              child: SizedBox(
                width: width,
                height: height,
                child: Image.asset(
                  art.path,
                  fit: BoxFit.contain,
                  alignment: Alignment.bottomCenter,
                  errorBuilder: (_, __, ___) => _placeholder(),
                ),
              ),
            );
          },
        );
      },
    );
  }

  /// 画像がまだ無いときの仮表示（状態ごとにアイコンを変える）
  Widget _placeholder() {
    final icon = widget.state == CharacterState.talking
        ? Icons.record_voice_over
        : widget.state == CharacterState.listening
            ? Icons.hearing
            : Icons.face;
    return LayoutBuilder(
      builder: (context, box) {
        final height = box.maxHeight.isFinite ? box.maxHeight : 260.0;
        return SizedBox(
          width: height * 0.54,
          height: height,
          child: Align(
            alignment: Alignment.bottomCenter,
            child: _breathing(
              child: Container(
                height: math.min(height, 240),
                width: double.infinity,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0xCCEDF4E6),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(icon, size: 84, color: const Color(0xFF2C5F2D)),
              ),
            ),
          ),
        );
      },
    );
  }
}