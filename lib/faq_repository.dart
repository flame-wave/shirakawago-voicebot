import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

/// データがどこから来たか
enum FaqSource {
  bundled, // アプリに同梱されたもの（初回起動時など）
  cache,   // 前回オンライン時に取得して保存したもの
  remote,  // 今回オンラインで取得した最新のもの
}

/// 読み込んだFAQデータと、その出所・更新日
class FaqData {
  final String json;
  final FaqSource source;
  final String version;

  const FaqData(this.json, this.source, this.version);

  String get sourceLabel {
    switch (source) {
      case FaqSource.remote:
        return '最新';
      case FaqSource.cache:
        return '保存済み';
      case FaqSource.bundled:
        return '初期データ';
    }
  }
}

/// FAQデータの取得を担当する。
///
/// 方針は「オフライン優先」:
///   1. 起動時はローカル（キャッシュ→同梱）を即座に読み、すぐ使える状態にする
///   2. その裏で通信を試み、成功したら差し替える
/// 通信が遅い・繋がらない場合でも、起動が止まることはない。
class FaqRepository {
  /// 配信元のURL。ここを設定するとオンライン更新が有効になる。
  /// 空文字のままなら、同梱データだけで動作する。
  ///
  /// 例（GitHubで配信する場合）:
  ///   https://raw.githubusercontent.com/ユーザ名/リポジトリ名/main/assets/faq.json
  static const String remoteUrl = 'https://raw.githubusercontent.com/flame-wave/shirakawago-voicebot/main/assets/faq.json';

  /// 通信の待ち時間。現地の回線が遅い場合を考えて短めにする。
  static const Duration fetchTimeout = Duration(seconds: 8);

  static const String _cacheFileName = 'faq_cache.json';

  Future<File> _cacheFile() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/$_cacheFileName');
  }

  /// 起動時に呼ぶ。キャッシュがあればそれを、無ければ同梱データを返す。
  Future<FaqData> loadLocal() async {
    try {
      final file = await _cacheFile();
      if (await file.exists()) {
        final raw = await file.readAsString();
        if (_isValid(raw)) {
          return FaqData(raw, FaqSource.cache, _versionOf(raw));
        }
        debugPrint('キャッシュが壊れているため無視します');
      }
    } catch (e) {
      debugPrint('キャッシュ読み込みエラー: $e');
    }

    final raw = await rootBundle.loadString('assets/faq.json');
    return FaqData(raw, FaqSource.bundled, _versionOf(raw));
  }

  /// 裏で呼ぶ。取得できなければ null を返すだけで、例外は投げない。
  Future<FaqData?> fetchRemote() async {
    if (remoteUrl.isEmpty) {
      debugPrint('配信URLが未設定のため、オンライン更新はしません');
      return null;
    }

    try {
      final res =
          await http.get(Uri.parse(remoteUrl)).timeout(fetchTimeout);

      if (res.statusCode != 200) {
        debugPrint('取得失敗: HTTP ${res.statusCode}');
        return null;
      }

      // 文字化けを避けるため、明示的にUTF-8として解釈する
      final raw = utf8.decode(res.bodyBytes);

      // 壊れたデータでキャッシュを上書きしないよう、保存前に検査する
      if (!_isValid(raw)) {
        debugPrint('取得したデータが不正な形式のため破棄します');
        return null;
      }

      final file = await _cacheFile();
      await file.writeAsString(raw);

      return FaqData(raw, FaqSource.remote, _versionOf(raw));
    } catch (e) {
      debugPrint('オンライン更新に失敗（オフラインで継続）: $e');
      return null;
    }
  }

  /// 最低限の妥当性チェック。faqs が配列で1件以上あること。
  bool _isValid(String raw) {
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) return false;
      final faqs = decoded['faqs'];
      return faqs is List && faqs.isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  String _versionOf(String raw) {
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return (decoded['version'] as String?) ?? '不明';
    } catch (_) {
      return '不明';
    }
  }
}
