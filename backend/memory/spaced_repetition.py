"""
Spaced Repetition — SM-2 Algorithm Implementation.

SM-2 is the algorithm behind Anki and SuperMemo.
It calculates how long to wait before reviewing a word again
based on how well the learner recalled it.

Quality scale (0–5):
    5 — perfect recall, no hesitation
    4 — correct with slight hesitation
    3 — correct with significant difficulty
    2 — incorrect but the correct answer felt familiar
    1 — incorrect, barely recognised
    0 — complete blackout

Reference: https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session # type: ignore

from database.models import VocabularyItem, SRReview
from config import (
    SM2_DEFAULT_EASINESS,
    SM2_MIN_EASINESS,
    SM2_INITIAL_INTERVAL_1,
    SM2_INITIAL_INTERVAL_2,
)


# ── SM-2 Core ─────────────────────────────────────────────────────────────────

def calculate_next_review(
    easiness_factor: float,
    interval_days: int,
    repetitions: int,
    quality: int,
) -> tuple[float, int, int]:
    """
    Core SM-2 calculation.

    Args:
        easiness_factor: current EF (starts at 2.5)
        interval_days:   current interval in days
        repetitions:     number of correct reviews in a row
        quality:         0–5 recall quality for this review

    Returns:
        (new_easiness_factor, new_interval_days, new_repetitions)
    """
    if quality < 3:
        # Failed — reset repetitions and interval, don't change EF
        return easiness_factor, 1, 0

    # Update easiness factor
    new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(SM2_MIN_EASINESS, new_ef)

    # Calculate new interval
    new_repetitions = repetitions + 1
    if new_repetitions == 1:
        new_interval = SM2_INITIAL_INTERVAL_1
    elif new_repetitions == 2:
        new_interval = SM2_INITIAL_INTERVAL_2
    else:
        new_interval = round(interval_days * new_ef)

    return new_ef, new_interval, new_repetitions


# DB Operations

def add_vocabulary_item(
    db: Session,
    profile_id: int,
    word: str,
    translation: str,
    cefr_level: str = "A1",
    example_sentence: str = "",
) -> VocabularyItem:
    """Add a new word to the learner's vocabulary list with a fresh SR schedule."""
    item = VocabularyItem(
        learner_profile_id=profile_id,
        word=word,
        translation=translation,
        cefr_level=cefr_level,
        example_sentence=example_sentence,
    )
    db.add(item)
    db.flush()

    # Create SR schedule — due immediately (first review)
    review = SRReview(
        vocabulary_item_id=item.id,
        easiness_factor=SM2_DEFAULT_EASINESS,
        interval_days=SM2_INITIAL_INTERVAL_1,
        repetitions=0,
        next_review_date=datetime.utcnow(),
    )
    db.add(review)
    db.commit()
    db.refresh(item)
    return item


def get_due_reviews(db: Session, profile_id: int, limit: int = 20) -> list[VocabularyItem]:
    """
    Returns vocabulary items due for review today.
    Called at the start of every session — these always get reviewed first.
    """
    now = datetime.utcnow()
    return (
        db.query(VocabularyItem)
        .join(SRReview, VocabularyItem.id == SRReview.vocabulary_item_id)
        .filter(
            VocabularyItem.learner_profile_id == profile_id,
            VocabularyItem.mastered == False,
            SRReview.next_review_date <= now,
        )
        .order_by(SRReview.next_review_date.asc())
        .limit(limit)
        .all()
    )


def record_review(db: Session, vocabulary_item_id: int, quality: int) -> SRReview:
    """
    Record the result of a vocabulary review and schedule the next one.

    Args:
        vocabulary_item_id: ID of the word reviewed
        quality: 0–5 recall quality
    """
    review = (
        db.query(SRReview)
        .filter(SRReview.vocabulary_item_id == vocabulary_item_id)
        .first()
    )
    if not review:
        raise ValueError(f"No SR review found for vocabulary item {vocabulary_item_id}")

    item = db.query(VocabularyItem).filter(VocabularyItem.id == vocabulary_item_id).first()

    # Run SM-2
    new_ef, new_interval, new_repetitions = calculate_next_review(
        easiness_factor=review.easiness_factor,
        interval_days=review.interval_days,
        repetitions=review.repetitions,
        quality=quality,
    )

    # Update SR record
    review.easiness_factor = new_ef
    review.interval_days = new_interval
    review.repetitions = new_repetitions
    review.last_reviewed_at = datetime.utcnow()
    review.last_quality = quality
    review.next_review_date = datetime.utcnow() + timedelta(days=new_interval)

    # Update vocabulary item stats
    item.times_seen += 1
    if quality >= 3:
        item.times_correct += 1

    # Mark as mastered if EF is high and interval is long (> 21 days)
    if new_interval > 21 and new_ef >= 2.5:
        item.mastered = True

    db.commit()
    db.refresh(review)
    return review


def get_due_items_summary(db: Session, profile_id: int) -> dict:
    """
    Returns a summary of due items formatted for the agent and the UI.
    """
    due_items = get_due_reviews(db, profile_id)
    return {
        "count": len(due_items),
        "items": [
            {
                "id": item.id,
                "word": item.word,
                "translation": item.translation,
                "level": item.cefr_level,
                "times_seen": item.times_seen,
            }
            for item in due_items
        ],
    }


def get_vocabulary_stats(db: Session, profile_id: int) -> dict:
    """Overview of vocabulary progress for the learner dashboard."""
    total = db.query(VocabularyItem).filter(VocabularyItem.learner_profile_id == profile_id).count()
    mastered = db.query(VocabularyItem).filter(
        VocabularyItem.learner_profile_id == profile_id,
        VocabularyItem.mastered == True,
    ).count()
    due_today = len(get_due_reviews(db, profile_id))

    return {
        "total_words": total,
        "mastered": mastered,
        "in_progress": total - mastered,
        "due_today": due_today,
        "mastery_rate": round((mastered / total * 100), 1) if total > 0 else 0.0,
    }