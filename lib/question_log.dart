import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

/// 1件の質問記録。
///
/// 音声そのものは保存しない（プライバシー配慮・容量）。
/// 認識されたテキストは、頻出質問の分析に必要なため保存する。
/// 設置時は「音声を認識し、質問内容を記録します」の掲示が必要。
class LogEntry {
  final DateTime at;
  final String lang;          // ja / en / zh / ko
  final String recognized;    // 認識された質問文
  final String? faqId;        // ヒットしたFAQのID。null なら該当なし
  final String category;      // ヒットしたFAQの分類
  final bool translationFallback; // 翻訳が無く日本語で答えたか
  final String voiceMode;     // recorded / synthesized / failed

  const LogEntry({
    required this.at,
    required this.lang,
    required this.recognized,
    required this.faqId,
    required this.category,
    required this.translationFallback,
    required this.voiceMode,
  });

  bool get matched => faqId != null;

  Map<String, dynamic> toJson() => {
        'at': at.toIso8601String(),
        'lang': lang,
        'recognized': recognized,
        'faq_id': faqId,
        'category': category,
        'fallback': translationFallback,
        'voice': voiceMode,
      };

  factory LogEntry.fromJson(Map<String, dynamic> j) => LogEntry(
        at: DateTime.tryParse(j['at'] as String? ?? '') ?? DateTime(2000),
        lang: j['lang'] as String? ?? '',
        recognized: j['recognized'] as String? ?? '',
        faqId: j['faq_id'] as String?,
        category: j['category'] as String? ?? '',
        translationFallback: j['fallback'] as bool? ?? false,
        voiceMode: j['voice'] as String? ?? '',
      );
}

/// 質問の記録を担当する部品。
///
/// 記録先は端末内のファイル（1行1件のJSONL形式）。
/// 追記方式なので、途中で電源が切れても既存の行は壊れない。
///
/// 将来クラウドに送る場合も、この部品の中だけを変えればよい。
class QuestionLog {
  static const String _fileName = 'question_log.jsonl';

  /// 端末に保存できない環境（Web）では、この場に貯めるだけにする
  final List<LogEntry> _memory = [];

  Future<File> logFile() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/$_fileName');
  }

  /// 1件記録する。失敗しても案内の動作は止めない。
  Future<void> add(LogEntry entry) async {
    _memory.add(entry);
    if (kIsWeb) return;
    try {
      final file = await logFile();
      await file.writeAsString(
        '${jsonEncode(entry.toJson())}\n',
        mode: FileMode.append,
        flush: true,
      );
    } catch (e) {
      debugPrint('質問ログの記録に失敗（動作は継続）: $e');
    }
  }

  /// 保存済みの記録を読み出す。壊れた行は飛ばす。
  Future<List<LogEntry>> readAll() async {
    if (kIsWeb) return List.unmodifiable(_memory);
    try {
      final file = await logFile();
      if (!await file.exists()) return const [];
      final lines = await file.readAsLines();
      final entries = <LogEntry>[];
      for (final line in lines) {
        if (line.trim().isEmpty) continue;
        try {
          entries.add(
              LogEntry.fromJson(jsonDecode(line) as Map<String, dynamic>));
        } catch (_) {
          // 1行壊れていても他は読める
        }
      }
      return entries;
    } catch (e) {
      debugPrint('質問ログの読み込みに失敗: $e');
      return const [];
    }
  }

  Future<void> clear() async {
    _memory.clear();
    if (kIsWeb) return;
    try {
      final file = await logFile();
      if (await file.exists()) await file.delete();
    } catch (e) {
      debugPrint('質問ログの削除に失敗: $e');
    }
  }
}

/// 集計結果。職員向け画面と分析の両方で使う。
class LogStats {
  final int total;
  final int matched;
  final Map<String, int> byLanguage;
  final Map<String, int> topMatched;    // FAQ ID → 件数
  final Map<String, int> topUnmatched;  // 認識文 → 件数

  const LogStats({
    required this.total,
    required this.matched,
    required this.byLanguage,
    required this.topMatched,
    required this.topUnmatched,
  });

  /// FAQで答えられた割合。職員に回さず完結できた割合の目安。
  double get matchRate => total == 0 ? 0 : matched / total;

  factory LogStats.from(List<LogEntry> entries) {
    final byLang = <String, int>{};
    final matchedCount = <String, int>{};
    final unmatchedCount = <String, int>{};
    var matched = 0;

    for (final e in entries) {
      byLang[e.lang] = (byLang[e.lang] ?? 0) + 1;
      if (e.matched) {
        matched++;
        matchedCount[e.faqId!] = (matchedCount[e.faqId!] ?? 0) + 1;
      } else if (e.recognized.isNotEmpty) {
        final key = e.recognized.trim();
        unmatchedCount[key] = (unmatchedCount[key] ?? 0) + 1;
      }
    }

    List<MapEntry<String, int>> sorted(Map<String, int> m) =>
        m.entries.toList()..sort((a, b) => b.value.compareTo(a.value));

    return LogStats(
      total: entries.length,
      matched: matched,
      byLanguage: byLang,
      topMatched: Map.fromEntries(sorted(matchedCount)),
      topUnmatched: Map.fromEntries(sorted(unmatchedCount)),
    );
  }
}
