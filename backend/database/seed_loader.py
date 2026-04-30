"""
Test seed data for learner profiles.

Populates VocabularyItem + SRReview and GrammarConcept rows so tests
that need a non-empty learner model don't have to build fixtures by hand.
"""

from datetime import datetime
from sqlalchemy.orm import Session  # type: ignore

from database.models import VocabularyItem, SRReview, GrammarConcept


_VOCABULARY: dict[str, list[dict]] = {
    "spanish": [
        {"word": "hola",       "translation": "hello",       "example_sentence": "Hola, ¿cómo estás?"},
        {"word": "gracias",    "translation": "thank you",   "example_sentence": "Muchas gracias por tu ayuda."},
        {"word": "agua",       "translation": "water",       "example_sentence": "Quiero un vaso de agua."},
        {"word": "casa",       "translation": "house",       "example_sentence": "Mi casa es grande."},
        {"word": "hablar",     "translation": "to speak",    "example_sentence": "Quiero hablar español."},
    ],
    "french": [
        {"word": "bonjour",    "translation": "hello",       "example_sentence": "Bonjour, comment ça va?"},
        {"word": "merci",      "translation": "thank you",   "example_sentence": "Merci beaucoup."},
        {"word": "eau",        "translation": "water",       "example_sentence": "Je veux de l'eau."},
        {"word": "maison",     "translation": "house",       "example_sentence": "Ma maison est grande."},
        {"word": "parler",     "translation": "to speak",    "example_sentence": "Je veux parler français."},
    ],
    "german": [
        {"word": "hallo",      "translation": "hello",       "example_sentence": "Hallo, wie geht es dir?"},
        {"word": "danke",      "translation": "thank you",   "example_sentence": "Danke sehr."},
        {"word": "wasser",     "translation": "water",       "example_sentence": "Ich möchte Wasser."},
        {"word": "haus",       "translation": "house",       "example_sentence": "Mein Haus ist groß."},
        {"word": "sprechen",   "translation": "to speak",    "example_sentence": "Ich möchte Deutsch sprechen."},
    ],
    "italian": [
        {"word": "ciao",       "translation": "hello",       "example_sentence": "Ciao, come stai?"},
        {"word": "grazie",     "translation": "thank you",   "example_sentence": "Grazie mille."},
        {"word": "acqua",      "translation": "water",       "example_sentence": "Voglio un bicchiere d'acqua."},
        {"word": "casa",       "translation": "house",       "example_sentence": "La mia casa è grande."},
        {"word": "parlare",    "translation": "to speak",    "example_sentence": "Voglio parlare italiano."},
    ],
}

_GRAMMAR: dict[str, list[dict]] = {
    "spanish": [
        {"concept_key": "present_tense_regular",  "concept_name": "Present tense — regular verbs"},
        {"concept_key": "articles_gender",         "concept_name": "Definite and indefinite articles (gender)"},
        {"concept_key": "noun_adjective_agreement","concept_name": "Noun–adjective gender and number agreement"},
    ],
    "french": [
        {"concept_key": "present_tense_regular",  "concept_name": "Présent de l'indicatif — verbes réguliers"},
        {"concept_key": "articles_gender",         "concept_name": "Articles définis et indéfinis (genre)"},
        {"concept_key": "noun_adjective_agreement","concept_name": "Accord nom–adjectif"},
    ],
    "german": [
        {"concept_key": "present_tense_regular",  "concept_name": "Präsens — regelmäßige Verben"},
        {"concept_key": "noun_gender_cases",       "concept_name": "Nomen: Genus und Kasus"},
        {"concept_key": "verb_position",           "concept_name": "Verb position in main and subordinate clauses"},
    ],
    "italian": [
        {"concept_key": "present_tense_regular",  "concept_name": "Presente indicativo — verbi regolari"},
        {"concept_key": "articles_gender",         "concept_name": "Articoli determinativi e indeterminativi"},
        {"concept_key": "noun_adjective_agreement","concept_name": "Accordo nome–aggettivo"},
    ],
}


def seed_learner_profile(
    db: Session,
    profile_id: int,
    language: str,
    cefr_level: str = "A1",
) -> dict:
    """
    Insert starter vocabulary and grammar rows for a learner profile.
    Safe to call multiple times — skips rows that already exist.
    Returns counts of rows actually inserted.
    """
    language = language.lower()
    vocab_rows = _VOCABULARY.get(language, [])
    grammar_rows = _GRAMMAR.get(language, [])
    vocabulary_added = 0
    grammar_added = 0

    now = datetime.utcnow()

    for entry in vocab_rows:
        exists = (
            db.query(VocabularyItem)
            .filter(
                VocabularyItem.learner_profile_id == profile_id,
                VocabularyItem.word == entry["word"],
            )
            .first()
        )
        if exists:
            continue

        item = VocabularyItem(
            learner_profile_id=profile_id,
            word=entry["word"],
            translation=entry["translation"],
            example_sentence=entry.get("example_sentence"),
            cefr_level=cefr_level,
            introduced_at=now,
        )
        db.add(item)
        db.flush()

        db.add(SRReview(
            vocabulary_item_id=item.id,
            easiness_factor=2.5,
            interval_days=1,
            repetitions=0,
            next_review_date=now,
        ))
        vocabulary_added += 1

    for entry in grammar_rows:
        exists = (
            db.query(GrammarConcept)
            .filter(
                GrammarConcept.learner_profile_id == profile_id,
                GrammarConcept.concept_key == entry["concept_key"],
            )
            .first()
        )
        if exists:
            continue

        db.add(GrammarConcept(
            learner_profile_id=profile_id,
            concept_key=entry["concept_key"],
            concept_name=entry["concept_name"],
            cefr_level=cefr_level,
            introduced=True,
            introduced_at=now,
        ))
        grammar_added += 1

    db.commit()
    return {"vocabulary_added": vocabulary_added, "grammar_added": grammar_added}
