import 'dart:convert';

/// 1件のFAQ
class Faq {
  final String id;
  final List<String> questions;
  final String answer;
  final String audio;
  final String photo;
  final String link;
  final String category;

  Faq({
    required this.id,
    required this.questions,
    required this.answer,
    required this.audio,
    required this.photo,
    required this.link,
    required this.category,
  });

  /// 項目が欠けていても落ちないよう、既定値を用意しておく
  factory Faq.fromJson(Map<String, dynamic> json) {
    return Faq(
      id: json['id'] as String? ?? '',
      questions: List<String>.from(json['questions'] as List? ?? const []),
      answer: json['answer'] as String? ?? '',
      audio: json['audio'] as String? ?? '',
      photo: json['photo'] as String? ?? '',
      link: json['link'] as String? ?? '',
      category: json['category'] as String? ?? 'other',
    );
  }
}

/// FAQ検索を担当する部品。
///
/// データの取得元は FaqRepository が受け持ち、ここは検索だけを行う。
/// 将来ここを埋め込みベクトル検索やクラウドLLMに差し替えられる。
class FaqService {
  List<Faq> _faqs = [];

  int get count => _faqs.length;
  List<Faq> get all => List.unmodifiable(_faqs);

  /// JSON文字列からFAQを読み込む。
  /// 失敗した場合は false を返し、既存のデータを保持する。
  bool loadFromJson(String raw) {
    try {
      final data = jsonDecode(raw) as Map<String, dynamic>;
      final list = (data['faqs'] as List)
          .map((e) => Faq.fromJson(e as Map<String, dynamic>))
          .where((f) => f.id.isNotEmpty && f.answer.isNotEmpty)
          .toList();
      if (list.isEmpty) return false;
      _faqs = list;
      return true;
    } catch (_) {
      return false;
    }
  }

  /// 入力文に最も近いFAQを返す。見つからなければ null。
  /// 【第1段階】単純なキーワード一致でスコアリング
  Faq? search(String input) {
    final text = input.toLowerCase();
    Faq? best;
    int bestScore = 0;

    for (final faq in _faqs) {
      int score = 0;
      for (final q in faq.questions) {
        if (text.contains(q.toLowerCase())) {
          score += 10; // 言い回しがそのまま含まれる
        } else {
          for (final token in q.split(' ')) {
            if (token.isNotEmpty && text.contains(token.toLowerCase())) {
              score += 3; // 部分的な単語一致
            }
          }
        }
      }
      if (score > bestScore) {
        bestScore = score;
        best = faq;
      }
    }

    // スコアが低すぎる＝該当なしとみなし、職員誘導へ
    if (bestScore < 3) return null;
    return best;
  }
}
