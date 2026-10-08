// 同意画面に出す文言。
//
// 【書くときの約束】
// ここに書いてあることと、実際に送っているものを必ず一致させる。
// 実装を変えたら、この文言も必ず見直すこと。
//
// いま実際に起きていること（2026-09-30 時点）:
//   送る     … 質問の内容（文字）／答えられたか／言語／日時／どの案内所か
//   送らない … 声そのもの・氏名や連絡先・現在地の座標
//   ただし   … 音声認識のため、声はブラウザの音声認識サービスへ送られる
//              （Chromeの場合はGoogle。こちらでは受け取らず、保存もしない）
//              質問集で答えられない質問は、文字にした内容を外部のAIへ送る

/// 提供者の表示。日本語の画面にはこれがそのまま出る。
export const PROVIDER = '名古屋大学 情報学部／大学院情報学研究科　遠藤・浦田研究室';

export const CONSENT = {
  ja: {
    title: '白川郷AI観光ガイド',
    provider: PROVIDER + ' が提供しています。',
    purpose: 'このアプリは、観光案内をよりよくするための研究として運用しています。'
      + 'ご利用の記録は、案内の改善と研究にのみ使います。',
    recordTitle: '記録すること',
    record: [
      '質問された内容（文字にしたもの）',
      '答えられたかどうか・選ばれた言語・日時',
      'どちらの案内所で使われたか',
    ],
    keepTitle: '記録しないこと',
    keep: [
      'お声そのもの',
      'お名前・連絡先など、どなたかが分かる情報',
      '現在地の座標（近い案内所を選ぶためだけに使います）',
    ],
    noteTitle: 'ご承知おきください',
    note: [
      '声で質問されるときは、聞き取りのためにブラウザの音声認識サービス'
        + '（Chromeの場合はGoogle）へお声が送られます。',
      '質問集にない質問は、文字にした内容を外部のAIサービスへ送って回答を作ります。',
    ],
    closing: '記録は統計としてのみ扱い、どなたかが分かる形で公表することはありません。',
    agree: '同意して使う',
    decline: '記録せずに使う',
    declineHint: '「記録せずに使う」を選んでも、案内はすべてお使いいただけます。',
  },

  en: {
    title: 'Shirakawa-go AI Guide',
    provider: 'Provided by the Endo and Urata Laboratory, School of Informatics and '
      + 'Graduate School of Informatics, Nagoya University.',
    purpose: 'This guide is operated as a research project to improve tourist '
      + 'information. Your usage records are used only to improve the guide and for research.',
    recordTitle: 'What we record',
    record: [
      'The content of your question (as text)',
      'Whether it could be answered, the language you chose, and the date and time',
      'Which information centre it was used at',
    ],
    keepTitle: 'What we do not record',
    keep: [
      'Your voice itself',
      'Your name, contact details, or anything identifying you',
      'Your exact location (used only to choose the nearest information centre)',
    ],
    noteTitle: 'Please note',
    note: [
      'When you speak, your voice is sent to your browser’s speech recognition '
        + 'service (Google, if you are using Chrome) so that it can be transcribed.',
      'If your question is not in our list, the text is sent to an external AI service '
        + 'to compose an answer.',
    ],
    closing: 'Records are used only as statistics and are never published in a form '
      + 'that identifies anyone.',
    agree: 'Agree and continue',
    decline: 'Use without recording',
    declineHint: 'If you choose “Use without recording”, '
      + 'every part of the guide still works.',
  },

  zh: {
    title: '白川乡AI旅游向导',
    provider: '由名古屋大学 信息学部／研究生院信息学研究科　远藤・浦田研究室提供。',
    purpose: '本导览作为改进旅游信息服务的研究项目运行。使用记录仅用于改进导览与研究。',
    recordTitle: '记录的内容',
    record: [
      '您提问的内容（转换为文字）',
      '是否能够回答、所选语言、日期和时间',
      '在哪个导览处使用',
    ],
    keepTitle: '不记录的内容',
    keep: [
      '您的声音本身',
      '姓名、联系方式等可识别个人的信息',
      '您的具体位置（仅用于判断最近的导览处）',
    ],
    noteTitle: '请注意',
    note: [
      '使用语音提问时，为了转写文字，您的声音会发送至浏览器的语音识别服务'
        + '（使用Chrome时为Google）。',
      '如果问题不在问答集中，文字内容会发送至外部AI服务以生成回答。',
    ],
    closing: '记录仅作为统计使用，绝不会以可识别个人的形式公开。',
    agree: '同意并使用',
    decline: '不记录直接使用',
    declineHint: '即使选择「不记录直接使用」，导览的所有功能仍可正常使用。',
  },

  ko: {
    title: '시라카와고 AI 관광 가이드',
    provider: '나고야대학 정보학부／대학원 정보학연구과　엔도・우라타 연구실이 제공합니다.',
    purpose: '이 안내는 관광 안내를 개선하기 위한 연구로 운영되고 있습니다. '
      + '이용 기록은 안내 개선과 연구에만 사용합니다.',
    recordTitle: '기록하는 것',
    record: [
      '질문하신 내용（문자로 변환한 것）',
      '답변 가능 여부・선택하신 언어・날짜와 시각',
      '어느 안내소에서 사용되었는지',
    ],
    keepTitle: '기록하지 않는 것',
    keep: [
      '목소리 자체',
      '성함・연락처 등 개인을 알 수 있는 정보',
      '현재 위치의 좌표（가까운 안내소를 고르는 데에만 사용합니다）',
    ],
    noteTitle: '양해 부탁드립니다',
    note: [
      '음성으로 질문하실 때는 받아쓰기를 위해 브라우저의 음성 인식 서비스'
        + '（Chrome의 경우 Google）로 목소리가 전송됩니다.',
      '질문 목록에 없는 질문은 문자로 변환한 내용을 외부 AI 서비스로 보내 답변을 만듭니다.',
    ],
    closing: '기록은 통계로만 다루며, 개인을 알 수 있는 형태로 공표하지 않습니다.',
    agree: '동의하고 사용',
    decline: '기록하지 않고 사용',
    declineHint: '「기록하지 않고 사용」을 선택하셔도 안내는 모두 이용하실 수 있습니다.',
  },

  es: {
    title: 'Guía IA de Shirakawa-go',
    provider: 'Ofrecido por el Laboratorio Endo y Urata, Facultad de Informática y '
      + 'Escuela de Posgrado en Informática, Universidad de Nagoya.',
    purpose: 'Esta guía funciona como un proyecto de investigación para mejorar la '
      + 'información turística. Sus registros de uso se utilizan únicamente para mejorar '
      + 'la guía y para la investigación.',
    recordTitle: 'Lo que registramos',
    record: [
      'El contenido de su pregunta (convertido en texto)',
      'Si se pudo responder, el idioma elegido, la fecha y la hora',
      'En qué oficina de información se utilizó',
    ],
    keepTitle: 'Lo que no registramos',
    keep: [
      'Su voz en sí misma',
      'Su nombre, datos de contacto ni nada que permita identificarle',
      'Su ubicación exacta (solo se usa para elegir la oficina más cercana)',
    ],
    noteTitle: 'Tenga en cuenta',
    note: [
      'Al hablar, su voz se envía al servicio de reconocimiento de voz de su navegador '
        + '(Google, si usa Chrome) para transcribirla.',
      'Si su pregunta no está en nuestra lista, el texto se envía a un servicio de IA '
        + 'externo para redactar una respuesta.',
    ],
    closing: 'Los registros se tratan solo como estadísticas y nunca se publican de forma '
      + 'que permita identificar a nadie.',
    agree: 'Aceptar y continuar',
    decline: 'Usar sin registro',
    declineHint: 'Si elige «Usar sin registro», la guía sigue funcionando por completo.',
  },

  fr: {
    title: 'Guide IA de Shirakawa-go',
    provider: 'Proposé par le laboratoire Endo et Urata, Faculté d’informatique et '
      + 'École doctorale d’informatique, Université de Nagoya.',
    purpose: 'Ce guide est exploité dans le cadre d’un projet de recherche visant à '
      + 'améliorer l’information touristique. Vos données d’utilisation servent '
      + 'uniquement à améliorer le guide et à la recherche.',
    recordTitle: 'Ce que nous enregistrons',
    record: [
      'Le contenu de votre question (converti en texte)',
      'Si une réponse a pu être donnée, la langue choisie, la date et l’heure',
      'Le point d’information où le guide a été utilisé',
    ],
    keepTitle: 'Ce que nous n’enregistrons pas',
    keep: [
      'Votre voix elle-même',
      'Votre nom, vos coordonnées ou tout élément permettant de vous identifier',
      'Votre position exacte (utilisée uniquement pour choisir le point le plus proche)',
    ],
    noteTitle: 'À noter',
    note: [
      'Lorsque vous parlez, votre voix est envoyée au service de reconnaissance vocale '
        + 'de votre navigateur (Google si vous utilisez Chrome) pour être transcrite.',
      'Si votre question ne figure pas dans notre liste, le texte est envoyé à un service '
        + 'd’IA externe afin de composer une réponse.',
    ],
    closing: 'Les données sont traitées uniquement sous forme de statistiques et ne sont '
      + 'jamais publiées sous une forme permettant d’identifier quiconque.',
    agree: 'Accepter et continuer',
    decline: 'Utiliser sans enregistrement',
    declineHint: 'Si vous choisissez « Utiliser sans enregistrement », '
      + 'toutes les fonctions du guide restent disponibles.',
  },
};
