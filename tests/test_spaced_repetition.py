"""
Tests for the SM-2 spaced repetition algorithm.
"""


from datetime import datetime, timedelta
from backend.memory.spaced_repetition import (
    calculate_next_review,
    add_vocabulary_item,
    get_due_reviews,
    record_review,
    get_vocabulary_stats,
)
from backend.config import SM2_DEFAULT_EASINESS, SM2_MIN_EASINESS


# Unit tests for calculate_next_review

class TestCalculateNextReview:

    def test_perfect_recall_first_review(self):
        """Quality 5 on first review → interval = 1 day."""
        ef, interval, reps = calculate_next_review(
            easiness_factor=SM2_DEFAULT_EASINESS,
            interval_days=1,
            repetitions=0,
            quality=5,
        )
        assert interval == 1
        assert reps == 1
        assert ef > SM2_DEFAULT_EASINESS  # EF goes up on perfect recall

    def test_perfect_recall_second_review(self):
        """Quality 5 on second review → interval = 6 days."""
        ef, interval, reps = calculate_next_review(
            easiness_factor=SM2_DEFAULT_EASINESS,
            interval_days=1,
            repetitions=1,
            quality=5,
        )
        assert interval == 6
        assert reps == 2

    def test_failed_recall_resets(self):
        """Quality < 3 → interval resets to 1, repetitions reset to 0."""
        ef, interval, reps = calculate_next_review(
            easiness_factor=SM2_DEFAULT_EASINESS,
            interval_days=20,
            repetitions=5,
            quality=1,
        )
        assert interval == 1
        assert reps == 0
        # EF should stay the same on failure
        assert ef == SM2_DEFAULT_EASINESS

    def test_easiness_factor_decreases_on_hard_recall(self):
        """Quality 3 (hard but correct) → EF decreases."""
        ef, interval, reps = calculate_next_review(
            easiness_factor=SM2_DEFAULT_EASINESS,
            interval_days=6,
            repetitions=2,
            quality=3,
        )
        assert ef < SM2_DEFAULT_EASINESS

    def test_easiness_factor_never_below_minimum(self):
        """EF should never drop below SM2_MIN_EASINESS."""
        ef = SM2_DEFAULT_EASINESS
        interval = 1
        reps = 0
        # Simulate many hard recalls
        for _ in range(20):
            ef, interval, reps = calculate_next_review(ef, interval, reps, quality=3)
        assert ef >= SM2_MIN_EASINESS

    def test_interval_grows_with_good_recall(self):
        """Consistent quality 5 → interval keeps growing."""
        ef = SM2_DEFAULT_EASINESS
        interval = 1
        reps = 0
        intervals = []
        for _ in range(5):
            ef, interval, reps = calculate_next_review(ef, interval, reps, quality=5)
            intervals.append(interval)
        # Each interval should be larger than the previous
        assert all(intervals[i] <= intervals[i+1] for i in range(len(intervals)-1))

    def test_quality_boundary_pass_fail(self):
        """Quality 3 = pass (repetitions increase), quality 2 = fail (reset)."""
        _, _, reps_pass = calculate_next_review(2.5, 1, 0, quality=3)
        _, _, reps_fail = calculate_next_review(2.5, 1, 0, quality=2)
        assert reps_pass == 1   # passed
        assert reps_fail == 0   # failed, reset


# Integration tests with DB

class TestSpacedRepetitionDB:

    def test_add_vocabulary_item(self, db, test_profile):
        item = add_vocabulary_item(
            db, test_profile.id, "hola", "hello", "A1", "¡Hola!"
        )
        assert item.id is not None
        assert item.word == "hola"
        assert item.translation == "hello"
        assert item.mastered is False
        assert item.sr_review is not None
        assert item.sr_review.easiness_factor == SM2_DEFAULT_EASINESS

    def test_new_item_is_due_immediately(self, db, test_profile):
        add_vocabulary_item(db, test_profile.id, "gracias", "thank you", "A1")
        due = get_due_reviews(db, test_profile.id)
        assert len(due) == 1
        assert due[0].word == "gracias"

    def test_record_good_review_reschedules(self, db, test_profile):
        item = add_vocabulary_item(db, test_profile.id, "casa", "house", "A1")
        review = record_review(db, item.id, quality=5)
        # After first good review, next review is in 1 day — no longer due now
        assert review.interval_days >= 1
        assert review.next_review_date > datetime.utcnow()

    def test_record_failed_review_stays_due_soon(self, db, test_profile):
        item = add_vocabulary_item(db, test_profile.id, "difícil", "difficult", "B1")
        # Simulate having reviewed it before (interval was 10 days)
        item.sr_review.interval_days = 10
        item.sr_review.repetitions = 3
        db.commit()
        review = record_review(db, item.id, quality=1)  # failed
        assert review.interval_days == 1  # reset
        assert review.repetitions == 0    # reset

    def test_mastery_after_long_interval(self, db, test_profile):
        item = add_vocabulary_item(db, test_profile.id, "agua", "water", "A1")
        # Fast-track to mastery conditions
        item.sr_review.interval_days = 25
        item.sr_review.easiness_factor = 2.6
        item.sr_review.repetitions = 8
        db.commit()
        record_review(db, item.id, quality=5)
        db.refresh(item)
        assert item.mastered is True

    def test_multiple_items_only_due_returned(self, db, test_profile):
        add_vocabulary_item(db, test_profile.id, "uno", "one", "A1")
        item2 = add_vocabulary_item(db, test_profile.id, "dos", "two", "A1")
        # Push item2 review far into the future
        item2.sr_review.next_review_date = datetime.utcnow() + timedelta(days=30)
        db.commit()
        due = get_due_reviews(db, test_profile.id)
        assert len(due) == 1
        assert due[0].word == "uno"

    def test_vocabulary_stats(self, db, seeded_profile):
        stats = get_vocabulary_stats(db, seeded_profile.id)
        assert stats["total_words"] > 0
        assert stats["mastered"] == 0
        assert stats["mastery_rate"] == 0.0
        assert "due_today" in stats
