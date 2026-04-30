"""
Test seed data for learner profiles.

Populates VocabularyItem + SRReview and GrammarConcept rows so tests
that need a non-empty learner model don't have to build fixtures by hand.

Vocabulary entries carry a "level" field (CEFR).  seed_learner_profile()
includes all entries whose level is AT OR BELOW the requested level, so a
B1 learner always gets more words seeded than an A1 learner.
"""

from datetime import datetime
from sqlalchemy.orm import Session  # type: ignore

from database.models import VocabularyItem, SRReview, GrammarConcept

_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


_VOCABULARY: dict[str, list[dict]] = {
    "spanish": [
        # A1 — core basics
        {"level": "A1", "word": "hola",       "translation": "hello",        "example_sentence": "Hola, ¿cómo estás?"},
        {"level": "A1", "word": "gracias",    "translation": "thank you",    "example_sentence": "Muchas gracias por tu ayuda."},
        {"level": "A1", "word": "agua",       "translation": "water",        "example_sentence": "Quiero un vaso de agua."},
        {"level": "A1", "word": "casa",       "translation": "house",        "example_sentence": "Mi casa es grande."},
        {"level": "A1", "word": "hablar",     "translation": "to speak",     "example_sentence": "Quiero hablar español."},
        # A2 — everyday vocabulary
        {"level": "A2", "word": "trabajo",    "translation": "work/job",     "example_sentence": "Mi trabajo es interesante."},
        {"level": "A2", "word": "familia",    "translation": "family",       "example_sentence": "Mi familia es grande."},
        {"level": "A2", "word": "ciudad",     "translation": "city",         "example_sentence": "Vivo en una ciudad grande."},
        {"level": "A2", "word": "tiempo",     "translation": "time/weather", "example_sentence": "No tengo tiempo."},
        {"level": "A2", "word": "dinero",     "translation": "money",        "example_sentence": "Necesito dinero."},
        # B1 — intermediate
        {"level": "B1", "word": "aunque",     "translation": "although",     "example_sentence": "Aunque llueve, salgo."},
        {"level": "B1", "word": "además",     "translation": "furthermore",  "example_sentence": "Además, es barato."},
        {"level": "B1", "word": "sin embargo","translation": "however",      "example_sentence": "Sin embargo, no estoy seguro."},
        {"level": "B1", "word": "lograr",     "translation": "to achieve",   "example_sentence": "Logré aprender español."},
        {"level": "B1", "word": "acuerdo",    "translation": "agreement",    "example_sentence": "Llegamos a un acuerdo."},
    ],
    "french": [
        {"level": "A1", "word": "bonjour",    "translation": "hello",        "example_sentence": "Bonjour, comment ça va?"},
        {"level": "A1", "word": "merci",      "translation": "thank you",    "example_sentence": "Merci beaucoup."},
        {"level": "A1", "word": "eau",        "translation": "water",        "example_sentence": "Je veux de l'eau."},
        {"level": "A1", "word": "maison",     "translation": "house",        "example_sentence": "Ma maison est grande."},
        {"level": "A1", "word": "parler",     "translation": "to speak",     "example_sentence": "Je veux parler français."},
        {"level": "A2", "word": "travail",    "translation": "work",         "example_sentence": "Mon travail est intéressant."},
        {"level": "A2", "word": "famille",    "translation": "family",       "example_sentence": "Ma famille est grande."},
        {"level": "B1", "word": "cependant",  "translation": "however",      "example_sentence": "Cependant, je ne suis pas sûr."},
        {"level": "B1", "word": "réussir",    "translation": "to succeed",   "example_sentence": "J'ai réussi à apprendre."},
        {"level": "B1", "word": "accord",     "translation": "agreement",    "example_sentence": "Nous avons trouvé un accord."},
    ],
    "german": [
        {"level": "A1", "word": "hallo",      "translation": "hello",        "example_sentence": "Hallo, wie geht es dir?"},
        {"level": "A1", "word": "danke",      "translation": "thank you",    "example_sentence": "Danke sehr."},
        {"level": "A1", "word": "wasser",     "translation": "water",        "example_sentence": "Ich möchte Wasser."},
        {"level": "A1", "word": "haus",       "translation": "house",        "example_sentence": "Mein Haus ist groß."},
        {"level": "A1", "word": "sprechen",   "translation": "to speak",     "example_sentence": "Ich möchte Deutsch sprechen."},
        {"level": "A2", "word": "arbeit",     "translation": "work",         "example_sentence": "Meine Arbeit ist interessant."},
        {"level": "A2", "word": "familie",    "translation": "family",       "example_sentence": "Meine Familie ist groß."},
        {"level": "B1", "word": "obwohl",     "translation": "although",     "example_sentence": "Obwohl es regnet, gehe ich raus."},
        {"level": "B1", "word": "außerdem",   "translation": "furthermore",  "example_sentence": "Außerdem ist es günstig."},
        {"level": "B1", "word": "erreichen",  "translation": "to achieve",   "example_sentence": "Ich habe mein Ziel erreicht."},
    ],
    "italian": [
        {"level": "A1", "word": "ciao",       "translation": "hello",        "example_sentence": "Ciao, come stai?"},
        {"level": "A1", "word": "grazie",     "translation": "thank you",    "example_sentence": "Grazie mille."},
        {"level": "A1", "word": "acqua",      "translation": "water",        "example_sentence": "Voglio un bicchiere d'acqua."},
        {"level": "A1", "word": "casa",       "translation": "house",        "example_sentence": "La mia casa è grande."},
        {"level": "A1", "word": "parlare",    "translation": "to speak",     "example_sentence": "Voglio parlare italiano."},
        {"level": "A2", "word": "lavoro",     "translation": "work",         "example_sentence": "Il mio lavoro è interessante."},
        {"level": "A2", "word": "famiglia",   "translation": "family",       "example_sentence": "La mia famiglia è grande."},
        {"level": "B1", "word": "tuttavia",   "translation": "however",      "example_sentence": "Tuttavia, non sono sicuro."},
        {"level": "B1", "word": "riuscire",   "translation": "to succeed",   "example_sentence": "Sono riuscito ad imparare."},
        {"level": "B1", "word": "accordo",    "translation": "agreement",    "example_sentence": "Abbiamo raggiunto un accordo."},
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
    # Include all words at or below the requested CEFR level
    max_idx = _CEFR_ORDER.index(cefr_level) if cefr_level in _CEFR_ORDER else 0
    allowed_levels = set(_CEFR_ORDER[: max_idx + 1])
    vocab_rows = [
        e for e in _VOCABULARY.get(language, [])
        if e.get("level", "A1") in allowed_levels
    ]
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
            cefr_level=entry.get("level", cefr_level),   # use the word's own level
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
