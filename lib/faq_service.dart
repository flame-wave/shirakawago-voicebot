import 'dart:convert';

import 'app_language.dart';

/// ある言語での質問例・回答・音声
class FaqTranslation {
  final List<String> questions;
  final String answer;
  final String audio;

  const FaqTranslation({
    required this.questions,
    required this.answer,
    required this.audio,
  });

  factory FaqTranslation.fromJson(Map<String, dynamic> json) {
    return FaqTranslation(
      questions: List<String>.from(json['questions'] as List? ?? const []),
      answer: json['answer'] as String? ?? '',
      audio: json['audio'] as String? ?? '',
    );
  }
}

/// 実際に読み上げ・表示する内容。
/// 翻訳が無い場合は日本語で返し、[isFallback] を true にする。
class LocalizedAnswer {
  final String text;
  final String audio;
  final bool isFallback;

  const LocalizedAnswer({
    required this.text,
    required this.audio,
    required this.isFallback,
  });
}

/// 1件のFAQ（日本語＋各言語の翻訳）
class Faq {
  final String id;
  final List<String> questions;
  final String answer;
  final String audio;
  final String photo;
  final String link;
  final String category;
  final Map<String, FaqTranslation> translations;

  Faq({
    required this.id,
    required this.questions,
    required this.answer,
    required this.audio,
    required this.photo,
    required this.link,
    required this.category,
    required this.translations,
  });

  factory Faq.fromJson(Map<String, dynamic> json) {
    final raw = json['translations'] as Map<String, dynamic>? ?? const {};
    return Faq(
      id: json['id'] as String? ?? '',
      questions: List<String>.from(json['questions'] as List? ?? const []),
      answer: json['answer'] as String? ?? '',
      audio: json['audio'] as String? ?? '',
      photo: json['photo'] as String? ?? '',
      link: json['link'] as String? ?? '',
      category: json['category'] as String? ?? 'other',
      translations: raw.map((k, v) =>
          MapEntry(k, FaqTranslation.fromJson(v as Map<String, dynamic>))),
    );
  }

  /// 指定言語での回答。無ければ日本語を返す。
  LocalizedAnswer answerFor(AppLanguage lang) {
    if (lang == AppLanguage.ja) {
      return LocalizedAnswer(text: answer, audio: audio, isFallback: false);
    }
    final tr = translations[lang.code];
    if (tr != null && tr.answer.isNotEmpty) {
      return LocalizedAnswer(text: tr.answer, audio: tr.audio, isFallback: false);
    }
    // 翻訳が未整備でも、日本語で案内できるだけした方がよい
    return LocalizedAnswer(text: answer, audio: audio, isFallback: true);
  }

  /// 指定言語で検索対象にする質問例。
  /// 日本語以外を選んでいても、日本語の言い方は残す
  /// （地名など、言語をまたいで同じ語が使われることがあるため）
  List<String> questionsFor(AppLanguage lang) {
    if (lang == AppLanguage.ja) return questions;
    final tr = translations[lang.code];
    return [...?tr?.questions, ...questions];
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

  /// その言語の翻訳が1件でも入っているか（未整備の案内を出すために使う）
  bool hasTranslations(AppLanguage lang) {
    if (lang == AppLanguage.ja) return true;
    return _faqs.any((f) {
      final tr = f.translations[lang.code];
      return tr != null && tr.answer.isNotEmpty;
    });
  }

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

  /// 表記の揺れを吸収する。
  /// カタカナ→ひらがな（ゴミ／ごみ）、全角英数→半角、記号と空白の除去。
  /// 音声認識の結果はカタカナ・ひらがなが安定しないため、この正規化が効く。
  static String _normalize(String s) {
    final buf = StringBuffer();
    for (final r in s.runes) {
      var c = r;
      if (c >= 0xFF10 && c <= 0xFF5A) c -= 0xFEE0; // 全角英数 → 半角
      if (c >= 0x30A1 && c <= 0x30F6) c -= 0x60;   // カタカナ → ひらがな
      buf.writeCharCode(c);
    }
    return buf
        .toString()
        .toLowerCase()
        .replaceAll(RegExp(r'[\s　、。，．,\.!?！？・ー]'), '');
  }

  /// 語尾の活用に耐える照合。
  /// 「預ける」が「預けたい」に、「借りる」が「借りられる」に当たるようにする。
  static bool _contains(String keyword, String text) {
    if (text.contains(keyword)) return true;
    if (keyword.length >= 3 &&
        'るうくすつぬぶむいたてえ'.contains(keyword[keyword.length - 1]) &&
        text.contains(keyword.substring(0, keyword.length - 1))) {
      return true;
    }
    return false;
  }

  /// 入力文に最も近いFAQを返す。見つからなければ null。
  ///
  /// 質問例のスペースは「かつ」を意味する。
  /// 例:「ごみ どこ」は、ごみ と どこ の両方が含まれるときだけ一致する。
  /// どれか1語でも当たれば加点する方式だと、「どこ」「場所」のような
  /// どの質問にも出る語だけで誤って一致してしまうため。
  Faq? search(String input, [AppLanguage lang = AppLanguage.ja]) {
    final text = _normalize(input);
    if (text.isEmpty) return null;

    Faq? best;
    int bestScore = 0;

    for (final faq in _faqs) {
      for (final q in faq.questionsFor(lang)) {
        final keywords = q
            .split(RegExp(r'[\s　]+'))
            .map(_normalize)
            .where((k) => k.isNotEmpty)
            .toList();
        if (keywords.isEmpty) continue;

        // すべての語が含まれることを条件にする
        if (!keywords.every((k) => _contains(k, text))) continue;

        // 具体的な語ほど、また語数が多いほど確度が高いとみなす
        var score = keywords.fold<int>(0, (a, k) => a + k.length);
        if (keywords.length > 1) score += 1;

        if (score > bestScore) {
          bestScore = score;
          best = faq;
        }
      }
    }

    // 1文字だけの一致は弱すぎるため、該当なしとして職員誘導へ
    if (bestScore < 2) return null;
    return best;
  }
}