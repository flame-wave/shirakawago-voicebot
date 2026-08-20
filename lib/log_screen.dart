import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'question_log.dart';

/// 職員向けの確認画面。観光客の目に触れないよう、通常のUIからは辿れない。
///
/// 「答えられなかった質問」の一覧が、FAQに何を追加すべきかの
/// そのままの根拠になる。
class LogScreen extends StatefulWidget {
  final QuestionLog log;

  const LogScreen({super.key, required this.log});

  @override
  State<LogScreen> createState() => _LogScreenState();
}

class _LogScreenState extends State<LogScreen> {
  LogStats? _stats;
  List<LogEntry> _entries = [];
  String _filePath = '';
  bool _loading = true;

  /// 一度に描画する件数。多すぎると開いたときに固まるため区切る。
  int _shownCount = 200;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final entries = await widget.log.readAll();
    String path = '';
    try {
      path = (await widget.log.logFile()).path;
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _stats = LogStats.from(entries);
      // 一覧は新しいものから見たいので逆順にしておく
      _entries = entries.reversed.toList();
      _shownCount = 200;
      _filePath = path;
      _loading = false;
    });
  }

  Future<void> _confirmClear() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('記録を削除しますか'),
        content: const Text('これまでの質問記録がすべて消えます。元に戻せません。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('やめる'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('削除する'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await widget.log.clear();
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _stats;

    return Scaffold(
      appBar: AppBar(
        title: const Text('質問の記録（職員用）'),
        backgroundColor: const Color(0xFF2C5F2D),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _load,
            tooltip: '再読み込み',
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: _confirmClear,
            tooltip: '記録を削除',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : s == null || s.total == 0
              ? const Center(
                  child: Text('まだ記録がありません',
                      style: TextStyle(fontSize: 16, color: Colors.black54)),
                )
              : ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    _summary(s),
                    const SizedBox(height: 24),
                    _section(
                      '答えられなかった質問',
                      'FAQに追加する候補です',
                      s.topUnmatched,
                      empty: 'すべての質問に回答できています',
                      highlight: true,
                    ),
                    const SizedBox(height: 24),
                    _section(
                      'よく聞かれた質問',
                      '音声を優先して用意すると効果的です',
                      s.topMatched,
                      empty: '記録がありません',
                    ),
                    const SizedBox(height: 24),
                    _section('言語別の利用', '', s.byLanguage, empty: ''),
                    const SizedBox(height: 24),
                    _allEntries(),
                    const SizedBox(height: 24),
                    if (_filePath.isNotEmpty)
                      SelectableText(
                        '記録の保存先:\n$_filePath',
                        style: const TextStyle(
                            fontSize: 11, color: Colors.black45),
                      ),
                  ],
                ),
    );
  }

  /// すべての記録の一覧。既定では閉じておく（普段は集計だけ見れば足りるため）。
  Widget _allEntries() {
    final shown = _entries.take(_shownCount).toList();
    final rest = _entries.length - shown.length;

    return Theme(
      // 折りたたみ時の区切り線を消す
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0xFFC3D2BC)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14),
          title: const Text(
            'すべての記録',
            style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: Color(0xFF1F3D20)),
          ),
          subtitle: Text(
            '新しい順に表示します（全 ${_entries.length} 件）',
            style: const TextStyle(fontSize: 12, color: Color(0xFF5A6B58)),
          ),
          children: [
            const Divider(height: 1, color: Color(0xFFE3EADF)),
            ...shown.map(_entryRow),
            if (rest > 0)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: TextButton(
                  onPressed: () => setState(() => _shownCount += 200),
                  child: Text('さらに表示（残り $rest 件）'),
                ),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _entryRow(LogEntry e) {
    final t = e.at;
    final stamp = '${t.month}/${t.day} '
        '${t.hour.toString().padLeft(2, '0')}:'
        '${t.minute.toString().padLeft(2, '0')}';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFF0F3EE))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 74,
            child: Text(stamp,
                style: const TextStyle(
                    fontSize: 12, color: Color(0xFF5A6B58))),
          ),
          Container(
            margin: const EdgeInsets.only(right: 10),
            padding:
                const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: const Color(0xFFEDF4E6),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(e.lang,
                style: const TextStyle(
                    fontSize: 11, color: Color(0xFF2C5F2D))),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  e.recognized.isEmpty ? '（認識できず）' : e.recognized,
                  style: const TextStyle(fontSize: 14),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Icon(
                      e.matched ? Icons.check_circle : Icons.help_outline,
                      size: 13,
                      color: e.matched
                          ? const Color(0xFF2C5F2D)
                          : const Color(0xFFB85042),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      e.matched ? e.faqId! : '該当なし',
                      style: TextStyle(
                        fontSize: 12,
                        color: e.matched
                            ? const Color(0xFF5A6B58)
                            : const Color(0xFFB85042),
                      ),
                    ),
                    if (e.translationFallback) ...[
                      const SizedBox(width: 8),
                      const Text('日本語で代替',
                          style: TextStyle(
                              fontSize: 11, color: Color(0xFFB85042))),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _summary(LogStats s) {
    final rate = (s.matchRate * 100).toStringAsFixed(1);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFFEDF4E6),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          _stat('質問の総数', '${s.total}'),
          _stat('回答できた', '${s.matched}'),
          _stat('回答率', '$rate%'),
        ],
      ),
    );
  }

  Widget _stat(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(label,
              style: const TextStyle(fontSize: 12, color: Color(0xFF5A6B58))),
          const SizedBox(height: 4),
          Text(value,
              style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF1F3D20))),
        ],
      ),
    );
  }

  Widget _section(String title, String note, Map<String, int> data,
      {required String empty, bool highlight = false}) {
    final items = data.entries.take(20).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: Color(0xFF1F3D20))),
        if (note.isNotEmpty) ...[
          const SizedBox(height: 2),
          Text(note,
              style: const TextStyle(fontSize: 12, color: Color(0xFF5A6B58))),
        ],
        const SizedBox(height: 8),
        if (items.isEmpty)
          Text(empty,
              style: const TextStyle(fontSize: 14, color: Colors.black45))
        else
          ...items.map((e) => Container(
                margin: const EdgeInsets.only(bottom: 4),
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: highlight ? const Color(0xFFFFF6F5) : Colors.white,
                  border: Border.all(
                      color: highlight
                          ? const Color(0xFFE8C4C0)
                          : const Color(0xFFC3D2BC)),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(e.key,
                          style: const TextStyle(fontSize: 14)),
                    ),
                    const SizedBox(width: 12),
                    Text('${e.value} 件',
                        style: const TextStyle(
                            fontSize: 13, color: Color(0xFF5A6B58))),
                    if (highlight) ...[
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.copy, size: 16),
                        tooltip: 'コピー',
                        visualDensity: VisualDensity.compact,
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: e.key));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text('コピーしました'),
                                duration: Duration(seconds: 1)),
                          );
                        },
                      ),
                    ],
                  ],
                ),
              )),
      ],
    );
  }
}