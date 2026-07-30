import 'dart:convert';
import 'package:flutter/services.dart' show rootBundle;

/// 1件のFAQを表すデータクラス（Pythonのクラスに相当）
class Faq {
  final String id;
  final List<String> questions;
  final String answer;
  final String audio;
  final String category;

  Faq({
    required this.id,
    required this.questions,
    required this.answer,
    required this.audio,
    required this.category,
  });

  // JSONの1件をFaqオブジェクトに変換する
  factory Faq.fromJson(Map<String, dynamic> json) {
    return Faq(
      id: json['id'] as String,
      questions: List<String>.from(json['questions']),
      answer: json['answer'] as String,
      audio: json['audio'] as String,
      category: json['category'] as String,
    );
  }
}

/// FAQ検索を担当する部品。
/// 今はキーワード一致だが、将来ここだけを
/// 埋め込みベクトル検索やクラウドLLMに差し替えられる。
class FaqService {
  List<Faq> _faqs = [];

  /// assets/faq.json を読み込む
  Future<void> load() async {
    final raw = await rootBundle.loadString('assets/faq.json');
    final data = jsonDecode(raw) as Map<String, dynamic>;
    _faqs = (data['faqs'] as List)
        .map((e) => Faq.fromJson(e as Map<String, dynamic>))
        .toList();
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
        // 質問例の各文字が入力に含まれていれば加点する簡易スコア
        if (text.contains(q.toLowerCase())) {
          score += 10; // 完全に言い回しが含まれる場合は高得点
        } else {
          // 部分的な単語一致も拾う
          for (final token in q.split(' ')) {
            if (token.isNotEmpty && text.contains(token.toLowerCase())) {
              score += 3;
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
