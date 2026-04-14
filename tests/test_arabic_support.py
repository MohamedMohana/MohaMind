from moha_mind.utils.arabic_support import build_arabic_understanding_context, normalize_colloquial_arabic


class TestArabicSupport:
    def test_normalizes_arabic_digits(self):
        normalized, notes = normalize_colloquial_arabic("ذكرني الساعه ٧ يوم ١٤")
        assert "7" in normalized
        assert "14" in normalized
        assert any("Arabic digits" in note for note in notes)

    def test_normalizes_colloquial_dates(self):
        normalized, notes = normalize_colloquial_arabic("ذكرني بعد بكره عندي موعد")
        assert "بعد غد" in normalized
        assert any("day after tomorrow" in note for note in notes)

    def test_normalizes_alternating_days_phrase(self):
        normalized, notes = normalize_colloquial_arabic("ودي أروح النادي يوم نعم ويوم لا")
        assert "كل يومين" in normalized
        assert any("every two days" in note for note in notes)

    def test_builds_arabic_context(self):
        context = build_arabic_understanding_context("ذكرني بكره الساعه ٧")
        assert "COLLOQUIAL ARABIC INTERPRETATION" in context
        assert "normalized reading" in context

    def test_normalizes_afternoon_time(self):
        normalized, notes = normalize_colloquial_arabic("موعدي الساعه ٤ العصر")
        assert "16:00" in normalized
        assert any("16:00" in note for note in notes)

    def test_normalizes_morning_time_without_saah(self):
        normalized, notes = normalize_colloquial_arabic("بكره 5 الصبح عندي رحلة")
        assert "غدا الساعة 05:00" in normalized
        assert any("05:00" in note for note in notes)
