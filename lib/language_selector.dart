import 'package:flutter/material.dart';

import 'app_language.dart';

/// 言語の切り替えボタン。
///
/// 自動判定ではなく手動にしているのは、音声認識が
/// 「これから何語が話されるか」を事前に指定する必要があるため。
/// 騒音下では自動判定が誤りやすく、観光客が自分で選ぶ方が確実。
///
/// どの言語が何回選ばれたかは、案内所の多言語対応を考える資料にもなる。
class LanguageSelector extends StatelessWidget {
  final AppLanguage current;
  final ValueChanged<AppLanguage> onChanged;

  const LanguageSelector({
    super.key,
    required this.current,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: AppLanguage.values.map((lang) {
        final selected = lang == current;
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Material(
              color: selected ? const Color(0xFF2C5F2D) : Colors.white,
              borderRadius: BorderRadius.circular(10),
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => onChanged(lang),
                child: Container(
                  height: 52,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: selected
                          ? const Color(0xFF2C5F2D)
                          : const Color(0xFFC3D2BC),
                      width: selected ? 2 : 1,
                    ),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    lang.label,
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight:
                          selected ? FontWeight.bold : FontWeight.normal,
                      color: selected ? Colors.white : const Color(0xFF2B2B2B),
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}
