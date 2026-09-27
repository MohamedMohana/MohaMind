"""Language catalog for MohaMind's proactive messages and prompts.

Free-form chat already mirrors whatever language the user writes in — the
system prompt handles that. This module localizes everything MohaMind says
on its own initiative (briefings, reminder pushes, expiry alerts, reports)
plus the instruction prepended to Telegram commands.

AGENT_LANGUAGE selects the language: "ar" (default) or "en".
Adding a language means adding its entries to CATALOG and extending the
phrase functions where grammar needs code (day counts).
"""

from __future__ import annotations

from moha_mind.config import settings

SUPPORTED_LANGUAGES = ("ar", "en")


def agent_language() -> str:
    """The configured language for proactive messages ('ar' or 'en')."""
    value = (getattr(settings, "agent_language", "ar") or "ar").strip().lower()
    return value if value in SUPPORTED_LANGUAGES else "ar"


CATALOG: dict[str, dict[str, str]] = {
    "voice.disabled": {
        "ar": "الرسائل الصوتية غير مفعّلة. يمكن تفعيلها عبر VOICE_ENABLED=true بعد تثبيت uv sync --extra voice.",
        "en": "Voice is disabled. Install uv sync --extra voice and set VOICE_ENABLED=true to enable it.",
    },
    "voice.unavailable": {
        "ar": "مكتبة الصوت غير مثبتة. شغّل uv sync --extra voice ثم أعد تشغيل المساعد.",
        "en": "Voice dependencies are missing. Run uv sync --extra voice and restart the agent.",
    },
    "voice.processing": {
        "ar": "جارٍ تحويل الصوت إلى نص محليًا. قد يستغرق الاستخدام الأول وقتًا لتنزيل النموذج.",
        "en": "Transcribing locally. First use may take longer while the model downloads.",
    },
    "voice.too_large": {
        "ar": "حجم الملف يتجاوز الحد المسموح أو غير معروف. أرسل تسجيلًا أصغر.",
        "en": "The file exceeds the size limit or its size is unknown. Please send a smaller recording.",
    },
    "voice.too_long": {
        "ar": "التسجيل يتجاوز المدة المسموحة. أرسل تسجيلًا أقصر.",
        "en": "The recording exceeds the duration limit. Please send a shorter recording.",
    },
    "voice.no_speech": {
        "ar": "لم أتمكن من التقاط كلام واضح. حاول التسجيل مرة أخرى أو اكتب رسالتك.",
        "en": "No speech was detected. Try recording again or type your message.",
    },
    "voice.failed": {
        "ar": "تعذّرت معالجة الرسالة الصوتية. اكتب رسالتك أو تحقق من إعدادات نموذج الصوت.",
        "en": "Could not process this voice request. Type your message or check the voice model settings.",
    },
    "voice.preview": {"ar": "النص المستخرج من التسجيل:", "en": "Transcript:"},
    "voice.review": {
        "ar": "راجع النص قبل إرساله للمساعد. للإصلاح، ألغِ الطلب واكتب النص الصحيح. ينتهي الطلب بعد 5 دقائق.",
        "en": "Review before sending to the agent. To correct it, cancel and type your message. Expires in 5 minutes.",
    },
    "voice.confirm": {"ar": "إرسال للمساعد", "en": "Send to agent"},
    "voice.cancel": {"ar": "إلغاء", "en": "Cancel"},
    "voice.cancelled": {"ar": "أُلغي الطلب الصوتي.", "en": "Voice request cancelled."},
    "voice.sent": {"ar": "أُرسل النص للمساعد.", "en": "Transcript sent to the agent."},
    "voice.expired": {
        "ar": "انتهى هذا الطلب أو لا يخص هذه المحادثة. أرسل تسجيلًا جديدًا.",
        "en": "This request expired or belongs to another chat. Send a new recording.",
    },
    # ----- Telegram command instruction -----
    "agent.instruction": {
        "ar": (
            "أجب المستخدم باللغة العربية الواضحة والمهنية، بنبرة ودودة ومباشرة. "
            "استخدم عناوين قصيرة ونقاطًا عند الحاجة، ولا تستخدم الإنجليزية إلا لأسماء الأوامر أو المصطلحات التقنية. "
            "عند ذكر وقت بصيغة 12 ساعة، اكتب ص أو م بوضوح مثل 1:30 م أو 5:00 ص."
        ),
        "en": (
            "Answer the user in clear, professional English with a warm, direct tone. "
            "Use short headings and bullet points when helpful. "
            "When mentioning 12-hour times, write AM or PM clearly, e.g. 1:30 PM or 5:00 AM."
        ),
    },
    # ----- chat -----
    "chat.done_fallback": {
        "ar": "تم تنفيذ طلبك ✅",
        "en": "Done — your request has been carried out ✅",
    },
    # ----- morning briefing -----
    "briefing.mode": {
        "ar": "MODE: Morning Briefing - Generate a comprehensive daily briefing in Arabic",
        "en": "MODE: Morning Briefing - Generate a comprehensive daily briefing in English",
    },
    "briefing.prompt": {
        "ar": (
            "اكتب ملخص الصباح لهذا اليوم باللغة العربية الواضحة والمهنية. "
            "ضمّن مواعيد التقويم، المهام ذات الأولوية، العناصر القريبة من الانتهاء، "
            "اقتراحات مناسبة لليوم، وأي روابط مهمة بين المعلومات. "
            "اجعل النبرة دافئة ومباشرة، واستخدم عناوين قصيرة ونقاطًا مرتبة."
        ),
        "en": (
            "Write this morning's briefing in clear, professional English. "
            "Include calendar appointments, priority tasks, items close to expiry, "
            "suitable suggestions for the day, and any important connections between the information. "
            "Keep the tone warm and direct, and use short headings and tidy bullet points."
        ),
    },
    "briefing.generation_error": {
        "ar": "صباح الخير. واجهت مشكلة أثناء إعداد ملخصك الكامل اليوم. الخطأ: {error}",
        "en": "Good morning. I hit a problem while preparing your full briefing today. Error: {error}",
    },
    "briefing.header": {
        "ar": "🌅 صباح الخير. {date}",
        "en": "🌅 Good morning. {date}",
    },
    "briefing.push_error": {
        "ar": "صباح الخير. واجهت مشكلة أثناء إعداد الملخص الكامل اليوم. اكتب لي وسأعطيك ملخصًا سريعًا.",
        "en": (
            "Good morning. I had trouble preparing the full briefing today. "
            "Message me and I'll give you a quick summary."
        ),
    },
    # ----- weekly review -----
    "review.mode": {
        "ar": "MODE: Weekly Life Review - Arabic",
        "en": "MODE: Weekly Life Review - English",
    },
    "review.prompt": {
        "ar": (
            "اكتب المراجعة الأسبوعية باللغة العربية الواضحة والمهنية. "
            "ضمّن المهام النشطة، الأنماط التي لاحظتها، ملخصًا ماليًا، "
            "العادات الصحية، العلاقات الاجتماعية، واقتراحات عملية للأسبوع القادم. "
            "لا تعرض المهام المكتملة أو المؤرشفة كعمل مطلوب، ولا تعتبر تجاوز الموعد دليلًا على الإنجاز. "
            "سيضاف سؤال متابعة للمهام المتأخرة تلقائيًا؛ لا تكرره ولا تغيّر أي بيانات. "
            "كن بنّاءً ومباشرًا دون إطالة."
        ),
        "en": (
            "Write the weekly review in clear, professional English. "
            "Include active tasks, patterns you noticed, a financial summary, "
            "health habits, social relationships, and practical suggestions for the coming week. "
            "Never present completed or archived tasks as pending, or assume a past due date means completion. "
            "An overdue-task follow-up will be appended automatically; do not repeat it or modify any data. "
            "Be constructive and direct without padding."
        ),
    },
    "review.cleanup": {
        "ar": "هذه المهام تجاوزت موعدها. هل أنجزتها، أم تريد أرشفتها وإزالتها من الملخص، أم إبقاءها؟ "
        "اذكر اسم المهمة والخيار المطلوب؛ لن أؤرشفها دون موافقتك:",
        "en": "These tasks are past due. Are they done, should I archive them and remove them from summaries, "
        "or should they stay active? Reply with the task name and action; I won't archive without your approval:",
    },
    "review.error": {
        "ar": "تعذر إعداد المراجعة الأسبوعية الآن. سأحاول مرة أخرى في الموعد القادم.",
        "en": "Could not prepare the weekly review right now. I'll try again at the next scheduled time.",
    },
    "review.header": {
        "ar": "📊 المراجعة الأسبوعية",
        "en": "📊 Weekly Review",
    },
    # ----- reminder engine -----
    "remind.title": {"ar": "⏰ التذكيرات:", "en": "⏰ Reminders:"},
    "remind.task_3d": {"ar": "📋 مهمة مستحقة بعد 3 أيام: {task}", "en": "📋 Task due in 3 days: {task}"},
    "remind.task_1d": {"ar": "📋 مهمة مستحقة غدًا: {task}", "en": "📋 Task due tomorrow: {task}"},
    "remind.task_0d": {"ar": "📋 مهمة مستحقة اليوم: {task}", "en": "📋 Task due today: {task}"},
    "remind.task_overdue": {
        "ar": "⚠️ مهمة متأخرة: {task} (كان موعدها {due})",
        "en": "⚠️ Overdue task: {task} (was due {due})",
    },
    "remind.expiry_tomorrow": {"ar": "🔔 ينتهي غدًا: {detail}", "en": "🔔 Expires tomorrow: {detail}"},
    "remind.occasion_countdown": {"ar": "💍 {phrase}: {title}", "en": "💍 {phrase}: {title}"},
    "remind.occasion_week": {"ar": "🎉 بعد أسبوع: {title}", "en": "🎉 One week away: {title}"},
    "remind.occasion_tomorrow": {"ar": "🎁 غدًا: {title}", "en": "🎁 Tomorrow: {title}"},
    "remind.occasion_today": {"ar": "🎊 اليوم: {title}", "en": "🎊 Today: {title}"},
    "remind.timed": {"ar": "⏰ تذكير: {text}", "en": "⏰ Reminder: {text}"},
    "remind.event_time": {"ar": "وقت الحدث: {when}", "en": "Event time: {when}"},
    "remind.notes": {"ar": "ملاحظات: {notes}", "en": "Notes: {notes}"},
    "remind.family_tomorrow": {"ar": "👨‍👩‍👧‍👦 غدًا: {line}", "en": "👨‍👩‍👧‍👦 Tomorrow: {line}"},
    "remind.family_today": {"ar": "👨‍👩‍👧‍👦 اليوم: {line}", "en": "👨‍👩‍👧‍👦 Today: {line}"},
    # ----- expiry guardian -----
    "expiry.title": {"ar": "🔔 تنبيه الانتهاء", "en": "🔔 Expiry Alert"},
    "expiry.urgent_header": {"ar": "🔴 عاجل - ينتهي هذا الأسبوع:", "en": "🔴 Urgent — expires this week:"},
    "expiry.today": {"ar": "ينتهي اليوم", "en": "expires today"},
    "expiry.month_header": {"ar": "🟡 ينتهي هذا الشهر:", "en": "🟡 Expires this month:"},
    "expiry.quarter_header": {"ar": "🟢 خلال 90 يومًا:", "en": "🟢 Within 90 days:"},
    # ----- social pulse -----
    "social.header": {
        "ar": "📱 نبض العلاقات - حان وقت التواصل",
        "en": "📱 Relationship Pulse — time to reconnect",
    },
    "social.last_contact": {
        "ar": "  - {person}: آخر تواصل {phrase}",
        "en": "  - {person}: last contact {phrase}",
    },
    "social.long_time": {
        "ar": "    💡 مر وقت طويل. قد يكون مناسبًا إرسال رسالة أو ترتيب مكالمة.",
        "en": "    💡 It has been a long while. A message or a quick call might be nice.",
    },
    "social.footer": {
        "ar": "استخدم ‎/social لرؤية التفاصيل أو أخبرني بتسجيل تواصل جديد.",
        "en": "Use ‎/social for details, or tell me to log a new contact.",
    },
    # ----- reliability guardian -----
    "guardian.title": {"ar": "🛡️ تقرير سلامة MohaMind — {status}", "en": "🛡️ MohaMind Integrity Report — {status}"},
    "guardian.ok": {"ar": "✅ سليم", "en": "✅ Healthy"},
    "guardian.attention": {"ar": "⚠️ يحتاج انتباه", "en": "⚠️ Needs attention"},
    "guardian.critical": {"ar": "أمور خطيرة:", "en": "Critical issues:"},
    "guardian.warnings": {"ar": "تنبيهات:", "en": "Warnings:"},
    "guardian.info": {"ar": "معلومات:", "en": "Info:"},
    "guardian.footer": {
        "ar": "الذاكرة محفوظة، والنسخة الاحتياطية اتحدثت.",
        "en": "Memory is safe and the backup is up to date.",
    },
    # ----- nightly memory consolidator -----
    "consolidator.header": {"ar": "🧠 تجميع الذاكرة · {when}", "en": "🧠 Memory consolidation · {when}"},
    "consolidator.applied": {"ar": "ما تم حفظه:", "en": "Applied:"},
    "consolidator.queued": {"ar": "بانتظار قرارك:", "en": "Awaiting your call:"},
    # ----- scheduler jobs -----
    "jobs.subscription_prompt": {
        "ar": (
            "اكتب الرد باللغة العربية الواضحة. راجع كل الاشتراكات والفواتير، "
            "اعرض إجمالي التكلفة الشهرية، ونبّهني لأي شيء غير معتاد."
        ),
        "en": (
            "Write the reply in clear English. Review all subscriptions and bills, "
            "show the total monthly cost, and flag anything unusual."
        ),
    },
    "jobs.subscription_header": {
        "ar": "💰 مراجعة الاشتراكات والفواتير الشهرية",
        "en": "💰 Monthly Subscriptions & Bills Review",
    },
    "jobs.pregnancy_header": {"ar": "🤰 تحديث الحمل:", "en": "🤰 Pregnancy update:"},
    # ----- Telegram command requests (sent to the LLM) -----
    "req.today": {
        "ar": "اعرض جدول اليوم كاملًا: المهام، التقويم، المواعيد، وأي شيء مهم يحتاج انتباهي.",
        "en": (
            "Show today's full schedule: tasks, calendar, appointments, and anything important that needs my attention."
        ),
    },
    "req.tomorrow": {
        "ar": "اعرض جدول الغد: المهام، التقويم، المواعيد، وأي شيء مهم يحتاج انتباهي.",
        "en": (
            "Show tomorrow's schedule: tasks, calendar, appointments, and anything important that needs my attention."
        ),
    },
    "req.week": {
        "ar": "اعرض نظرة عامة على هذا الأسبوع: كل الأحداث، المهام ذات المواعيد، والتواريخ المهمة.",
        "en": "Show an overview of this week: all events, tasks with due dates, and important dates.",
    },
    "req.calendar": {
        "ar": "اعرض مواعيد اليوم من تقويم Google وتقويم Microsoft، مع ترتيب واضح حسب الوقت.",
        "en": "Show today's appointments from Google Calendar and Microsoft Calendar, clearly ordered by time.",
    },
    "req.radar": {
        "ar": "اعرض رادار الانتباه لما يحتاج متابعة خلال 30 يومًا، ورتّبه حسب الأولوية.",
        "en": "Show the attention radar for everything that needs follow-up within 30 days, ordered by priority.",
    },
    "req.car": {
        "ar": "اعرض حالة السيارة: الصيانة القادمة، الاستمارة، التأمين، وأي تنبيه مهم.",
        "en": "Show the vehicle status: upcoming service, registration, insurance, and any important alert.",
    },
    "req.pay": {
        "ar": "اعرض الفواتير والمدفوعات القادمة، بما في ذلك الاشتراكات التي ستتجدد قريبًا.",
        "en": "Show upcoming bills and payments, including subscriptions that renew soon.",
    },
    "req.health": {
        "ar": "اعرض تذكيرات الصحة: الأدوية، مواعيد الأطباء القادمة، وحالة النادي أو التمارين.",
        "en": "Show health reminders: medications, upcoming doctor appointments, and gym or exercise status.",
    },
    "req.family": {
        "ar": "اعرض تحديثات العائلة: الحمل، أحداث الأطفال، والمواعيد القادمة.",
        "en": "Show family updates: pregnancy, kids' events, and upcoming appointments.",
    },
    "req.social": {
        "ar": "من يحتاج أن أتواصل معه؟ راجع العلاقات وجهّز ملخصًا مختصرًا للأشخاص المهمين.",
        "en": (
            "Who do I need to reach out to? Review my relationships "
            "and prepare a short summary of the important people."
        ),
    },
    "req.add_task": {
        "ar": "أضف هذه المهمة:\n{text}",
        "en": "Add this task:\n{text}",
    },
    "req.remember": {
        "ar": "احفظ هذه المعلومة في التصنيف المناسب من الذاكرة:\n{text}",
        "en": "Save this information in the appropriate memory category:\n{text}",
    },
    "req.remind": {
        "ar": (
            "أنشئ تذكيرًا موقّتًا لهذا الطلب. افهم العربية العامية واللهجة السعودية/الخليجية طبيعيًا. "
            "حوّل أي تاريخ أو وقت نسبي إلى وقت محدد بتوقيت {tz}، واستخدم أدوات التذكير المناسبة:\n"
            "للتكرار المرن استخدم حقول times وweekdays وskip_weekends وinterval_days وlead_days عند الحاجة.\n"
            "{text}"
        ),
        "en": (
            "Create a timed reminder for this request. "
            "Convert any relative date or time into a concrete time in the {tz} timezone, "
            "and use the appropriate reminder tools:\n"
            "for flexible recurrence use the times, weekdays, skip_weekends, interval_days "
            "and lead_days fields when needed.\n"
            "{text}"
        ),
    },
}


def t(key: str, *, lang: str | None = None, **kwargs: object) -> str:
    """Look up a catalog string in the given (or configured) language.

    Unknown keys return the key itself so a missing entry never crashes a
    scheduled job; unknown languages fall back to Arabic.
    """
    entry = CATALOG.get(key)
    if not entry:
        return key
    text = entry.get(lang or agent_language()) or entry["ar"]
    return text.format(**kwargs) if kwargs else text


def occasion_day_phrase(days: int, lang: str | None = None) -> str:
    """'in N days' phrase used for occasion countdowns."""
    language = lang or agent_language()
    if language == "en":
        if days == 0:
            return "today"
        if days == 1:
            return "tomorrow"
        return f"in {days} days"
    if days == 0:
        return "اليوم"
    if days == 1:
        return "غدًا"
    if days == 2:
        return "بعد يومين"
    if 3 <= days <= 10:
        return f"بعد {days} أيام"
    return f"بعد {days} يومًا"


def days_left_phrase(days: int, lang: str | None = None) -> str:
    """'N days left' phrase used for expiry alerts."""
    language = lang or agent_language()
    if language == "en":
        if days == 0:
            return "expires today"
        if days == 1:
            return "1 day left"
        return f"{days} days left"
    if days == 0:
        return "ينتهي اليوم"
    if days == 1:
        return "باقي يوم واحد"
    if days == 2:
        return "باقي يومان"
    if 3 <= days <= 10:
        return f"باقي {days} أيام"
    return f"باقي {days} يومًا"


def days_ago_phrase(days: int, lang: str | None = None) -> str:
    """'N days ago' phrase used for social nudges."""
    language = lang or agent_language()
    if language == "en":
        if days == 1:
            return "1 day ago"
        return f"{days} days ago"
    if days == 1:
        return "منذ يوم واحد"
    if days == 2:
        return "منذ يومين"
    if 3 <= days <= 10:
        return f"منذ {days} أيام"
    return f"منذ {days} يومًا"
