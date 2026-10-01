/// 対応言語。追加するときはここに足す。
enum AppLanguage { ja, en, zh, ko, es, fr }

extension AppLanguageInfo on AppLanguage {
  /// faq.json の translations で使うキー
  String get code => name;

  /// 切り替えボタンに出す表示名（その言語の話者が読める表記にする）
  String get label {
    switch (this) {
      case AppLanguage.ja:
        return '日本語';
      case AppLanguage.en:
        return 'English';
      case AppLanguage.zh:
        return '中文';
      case AppLanguage.ko:
        return '한국어';
      case AppLanguage.es:
        return 'Español';
      case AppLanguage.fr:
        return 'Français';
    }
  }

  /// 音声認識に渡すロケール（speech_to_text 用）
  String get speechLocale {
    switch (this) {
      case AppLanguage.ja:
        return 'ja_JP';
      case AppLanguage.en:
        return 'en_US';
      case AppLanguage.zh:
        return 'zh_CN';
      case AppLanguage.ko:
        return 'ko_KR';
      case AppLanguage.es:
        return 'es_ES';
      case AppLanguage.fr:
        return 'fr_FR';
    }
  }

  /// 音声合成に渡す言語コード（flutter_tts 用）
  String get ttsLanguage {
    switch (this) {
      case AppLanguage.ja:
        return 'ja-JP';
      case AppLanguage.en:
        return 'en-US';
      case AppLanguage.zh:
        return 'zh-CN';
      case AppLanguage.ko:
        return 'ko-KR';
      case AppLanguage.es:
        return 'es-ES';
      case AppLanguage.fr:
        return 'fr-FR';
    }
  }
}

/// 画面に出す固定文言。回答文はfaq.jsonが持つが、
/// ボタンや案内はここで管理する。
class UiStrings {
  static const _table = <String, Map<AppLanguage, String>>{
    'prompt': {
      AppLanguage.ja: 'ボタンを押して質問してください',
      AppLanguage.en: 'Tap the button and ask your question',
      AppLanguage.zh: '请点击按钮提问',
      AppLanguage.ko: '버튼을 눌러 질문해 주세요',
      AppLanguage.es: 'Pulse el botón y haga su pregunta',
      AppLanguage.fr: 'Appuyez sur le bouton et posez votre question',
    },
    'pressToTalk': {
      AppLanguage.ja: '話す',
      AppLanguage.en: 'Tap to Speak',
      AppLanguage.zh: '点击说话',
      AppLanguage.ko: '눌러서 말하기',
      AppLanguage.es: 'Pulse para hablar',
      AppLanguage.fr: 'Appuyer pour parler',
    },
    'listening': {
      AppLanguage.ja: '聞き取り中…（もう一度押すと終了）',
      AppLanguage.en: 'Listening… (tap again to finish)',
      AppLanguage.zh: '正在聆听…（再次点击结束）',
      AppLanguage.ko: '듣는 중… (다시 누르면 종료)',
      AppLanguage.es: 'Escuchando… (pulse otra vez para terminar)',
      AppLanguage.fr: 'Écoute… (appuyez à nouveau pour terminer)',
    },
    'question': {
      AppLanguage.ja: '質問',
      AppLanguage.en: 'Question',
      AppLanguage.zh: '提问',
      AppLanguage.ko: '질문',
      AppLanguage.es: 'Pregunta',
      AppLanguage.fr: 'Question',
    },
    'staffReferral': {
      AppLanguage.ja: '申し訳ございません。その質問は案内所の係員にお尋ねください。',
      AppLanguage.en:
          'Sorry, I could not find an answer. Please ask the staff at the information desk.',
      AppLanguage.zh: '很抱歉，未能找到答案。请向服务台的工作人员咨询。',
      AppLanguage.ko: '죄송합니다. 안내소 직원에게 문의해 주세요.',
      AppLanguage.es: 'Lo sentimos, no hemos encontrado una respuesta. Pregunte al personal del centro de información.',
      AppLanguage.fr: 'Désolé, nous n'avons pas trouvé de réponse. Veuillez demander au personnel du centre d'information.',
    },
    'scanForDetails': {
      AppLanguage.ja: '詳しくはこちら',
      AppLanguage.en: 'Scan for details',
      AppLanguage.zh: '扫码查看详情',
      AppLanguage.ko: '자세한 내용은 스캔',
      AppLanguage.es: 'Escanee para más detalles',
      AppLanguage.fr: 'Scannez pour en savoir plus',
    },
    'translationPending': {
      AppLanguage.ja: '',
      AppLanguage.en: 'English text is not ready yet. Showing Japanese.',
      AppLanguage.zh: '该语言的内容正在准备中，暂以日语显示。',
      AppLanguage.ko: '해당 언어는 준비 중입니다. 일본어로 표시합니다.',
      AppLanguage.es: 'El texto en español aún no está disponible. Se muestra en japonés.',
      AppLanguage.fr: 'Le texte français n'est pas encore disponible. Affichage en japonais.',
    },
    'speechUnavailable': {
      AppLanguage.ja: 'この言語の音声認識は、この端末では利用できません',
      AppLanguage.en: 'Voice input is not available for this language on this device.',
      AppLanguage.zh: '本设备不支持该语言的语音识别。',
      AppLanguage.ko: '이 기기에서는 해당 언어의 음성 인식을 사용할 수 없습니다.',
      AppLanguage.es: 'La entrada por voz no está disponible para este idioma en este dispositivo.',
      AppLanguage.fr: 'La saisie vocale n'est pas disponible pour cette langue sur cet appareil.',
    },
  };

  static String of(String key, AppLanguage lang) {
    return _table[key]?[lang] ?? _table[key]?[AppLanguage.ja] ?? '';
  }
}