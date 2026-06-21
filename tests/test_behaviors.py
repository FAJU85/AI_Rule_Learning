"""Behavioral test suite for the AI Rule Learning System.

TDD Red-Green-Refactor for guardrails:
  Red   — define what behaviour a rule should trigger/prevent
  Green — verify the engine detects it correctly
  Refactor — confirm no false positives on clean inputs

Run with: pytest tests/test_behaviors.py -v
"""

from __future__ import annotations

import pytest

from src.core.alignment_sensor import AlignmentSensor
from src.core.gap_detector import GapDetector
from src.core.rule_engine import RuleEngine
from src.models.conversation import Conversation
from src.models.conversation import SensorReading
from src.models.conversation import Turn
from src.models.rules import Rule
from src.models.rules import RuleAction
from src.models.rules import RulePriority as Priority
from src.models.rules import RuleTrigger
from src.models.rules import RuleType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def detector():
    return GapDetector(gap_threshold=0.3)


@pytest.fixture
def make_turn():
    def _make(
        turn_number: int = 1,
        user_input: str = "Hello",
        agent_response: str = "Hi",
        sentiment_before: float | None = None,
        sentiment_after: float | None = None,
    ) -> Turn:
        return Turn(
            turn_number=turn_number,
            user_input=user_input,
            agent_response=agent_response,
            sentiment_before=sentiment_before,
            sentiment_after=sentiment_after,
        )

    return _make


@pytest.fixture
def correction_rule() -> Rule:
    return Rule(
        rule_id="test_correction_rule",
        name="Handle Explicit Corrections",
        description="Respond carefully when user corrects the AI",
        rule_type=RuleType.GUARDRAIL,
        priority=Priority.HIGH,
        trigger=RuleTrigger(keywords=["actually", "wrong", "incorrect", "that's not"]),
        action=RuleAction(
            type="modify_response",
            instruction="Acknowledge the correction, verify understanding, then provide accurate information",
        ),
    )


@pytest.fixture
def sentiment_rule() -> Rule:
    return Rule(
        rule_id="test_sentiment_rule",
        name="Empathy on Frustration",
        description="Show empathy when user sentiment is low",
        rule_type=RuleType.GUARDRAIL,
        priority=Priority.HIGH,
        trigger=RuleTrigger(sentiment_threshold=-0.3),
        action=RuleAction(
            type="modify_response",
            instruction="Begin with an empathy statement before providing the answer",
        ),
    )


# ---------------------------------------------------------------------------
# Gap detection behaviors
# ---------------------------------------------------------------------------


class TestExplicitCorrectionDetection:
    """RED → GREEN: explicit corrections must always be detected."""

    @pytest.mark.parametrize(
        "user_input",
        [
            "Actually that's wrong, you missed the error handling",
            "No, that is incorrect",
            "That's not what I asked for",
            "You're wrong, try again",
            "Incorrect — please fix this",
            "actually i need async/await not callbacks",
            "Not right, it should use a context manager",
        ],
    )
    def test_correction_phrases_trigger_gap(self, detector, make_turn, user_input):
        turns = [make_turn(user_input=user_input)]
        gaps = detector.detect(turns)
        assert any(g["type"] == "explicit_correction" for g in gaps), (
            f"Expected explicit_correction gap for: {user_input!r}"
        )

    @pytest.mark.parametrize(
        "user_input",
        [
            "Can you explain decorators?",
            "How do I deploy to Heroku?",
            "What is the difference between list and tuple?",
            "Please show me an example",
        ],
    )
    def test_clean_inputs_no_correction_gap(self, detector, make_turn, user_input):
        turns = [make_turn(user_input=user_input)]
        gaps = detector.detect(turns)
        assert not any(g["type"] == "explicit_correction" for g in gaps), (
            f"Unexpected explicit_correction gap for clean input: {user_input!r}"
        )

    def test_correction_gap_has_required_fields(self, detector, make_turn):
        turns = [make_turn(user_input="Actually that's wrong")]
        gaps = detector.detect(turns)
        gap = next(g for g in gaps if g["type"] == "explicit_correction")
        assert "severity" in gap
        assert "turn_number" in gap
        assert "description" in gap


class TestSentimentDropDetection:
    """Sentiment drops above threshold must be detected with correct severity."""

    def test_large_drop_triggers_gap(self, detector, make_turn):
        turns = [make_turn(sentiment_before=1.0, sentiment_after=0.2)]
        gaps = detector.detect(turns)
        assert any(g["type"] == "sentiment_drop" for g in gaps)

    def test_small_drop_below_threshold_no_gap(self, detector, make_turn):
        turns = [make_turn(sentiment_before=0.5, sentiment_after=0.4)]
        gaps = detector.detect(turns)
        assert not any(g["type"] == "sentiment_drop" for g in gaps)

    def test_no_sentiment_fields_no_gap(self, detector, make_turn):
        turns = [make_turn()]  # no sentiment fields
        gaps = detector.detect(turns)
        assert not any(g["type"] == "sentiment_drop" for g in gaps)

    def test_severity_scales_with_drop_size(self, detector, make_turn):
        small = make_turn(turn_number=1, sentiment_before=0.5, sentiment_after=0.1)
        large = make_turn(turn_number=2, sentiment_before=1.0, sentiment_after=-0.8)

        sev_small = next((g["severity"] for g in detector.detect([small]) if g["type"] == "sentiment_drop"), 0)
        sev_large = next((g["severity"] for g in detector.detect([large]) if g["type"] == "sentiment_drop"), 0)
        assert sev_large > sev_small


class TestRepeatedQuestionDetection:
    """Repeated questions must be flagged; unique questions must not."""

    def test_identical_question_triggers_gap(self, detector, make_turn):
        turns = [
            make_turn(1, "how do i deploy to heroku"),
            make_turn(2, "how do i deploy to heroku"),
        ]
        gaps = detector.detect(turns)
        assert any(g["type"] == "repeated_question" for g in gaps)

    def test_first_occurrence_not_flagged(self, detector, make_turn):
        turns = [make_turn(1, "how do i deploy to heroku")]
        gaps = detector.detect(turns)
        assert not any(g["type"] == "repeated_question" for g in gaps)

    def test_different_questions_no_repeat_gap(self, detector, make_turn):
        turns = [
            make_turn(1, "how do i deploy to heroku"),
            make_turn(2, "what is python"),
        ]
        gaps = detector.detect(turns)
        assert not any(g["type"] == "repeated_question" for g in gaps)

    def test_repeat_gap_references_original_turn(self, detector, make_turn):
        turns = [
            make_turn(1, "explain generators in python"),
            make_turn(3, "explain generators in python"),
        ]
        gaps = detector.detect(turns)
        gap = next((g for g in gaps if g["type"] == "repeated_question"), None)
        assert gap is not None
        assert gap["turn_number"] == 3


class TestCodeAntiPatternDetection:
    """Dangerous code patterns in AI responses must always be detected."""

    @pytest.mark.parametrize(
        "response,expected_subtype",
        [
            ("result = eval(user_input)", "eval_usage"),
            ("try:\n    pass\nexcept:\n    pass", "bare_except"),
            ('password = "mysecret123"', "hardcoded_secret"),
            ('api_key = "sk-abc123xyz"', "hardcoded_secret"),
        ],
    )
    def test_anti_pattern_triggers_gap(self, detector, make_turn, response, expected_subtype):
        turns = [make_turn(agent_response=response)]
        gaps = detector.detect(turns)
        matching = [g for g in gaps if f"code_anti_pattern:{expected_subtype}" == g["type"]]
        assert matching, f"Expected code_anti_pattern:{expected_subtype} in response: {response!r}"

    def test_safe_code_no_gap(self, detector, make_turn):
        safe_code = """
def fetch_data(url: str) -> dict:
    with requests.Session() as session:
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            logger.error("HTTP error", extra={"error": str(exc)})
            raise
"""
        turns = [make_turn(agent_response=safe_code)]
        gaps = detector.detect(turns)
        assert not any("code_anti_pattern" in g["type"] for g in gaps)

    def test_multiple_anti_patterns_all_detected(self, detector, make_turn):
        bad_code = 'password = "secret"\nresult = eval(code)\ntry:\n    pass\nexcept:\n    pass'
        turns = [make_turn(agent_response=bad_code)]
        gaps = detector.detect(turns)
        code_gaps = [g for g in gaps if "code_anti_pattern" in g["type"]]
        assert len(code_gaps) >= 2


# ---------------------------------------------------------------------------
# Rule matching behaviors
# ---------------------------------------------------------------------------


class TestRuleMatchingBehaviors:
    """TDD: rule engine must fire on expected inputs and stay silent on unrelated ones."""

    def test_keyword_rule_matches_on_keyword(self, correction_rule):
        engine = RuleEngine()
        engine._rules = [correction_rule]
        matched = engine.match_rules("That's wrong, please fix it")
        assert any(r.rule_id == correction_rule.rule_id for r in matched)

    def test_keyword_rule_no_match_on_unrelated_input(self, correction_rule):
        engine = RuleEngine()
        engine._rules = [correction_rule]
        matched = engine.match_rules("Can you explain what a REST API is?")
        assert not any(r.rule_id == correction_rule.rule_id for r in matched)

    def test_inactive_rule_never_matches(self, correction_rule):
        correction_rule.is_active = False
        engine = RuleEngine()
        engine._rules = [correction_rule]
        matched = engine.match_rules("actually that's wrong")
        assert not any(r.rule_id == correction_rule.rule_id for r in matched)

    def test_sentiment_rule_fires_below_threshold(self, sentiment_rule):
        engine = RuleEngine()
        engine._rules = [sentiment_rule]
        matched = engine.match_rules("this is useless", sentiment=-0.8)
        assert any(r.rule_id == sentiment_rule.rule_id for r in matched)

    def test_sentiment_rule_silent_above_threshold(self, sentiment_rule):
        engine = RuleEngine()
        engine._rules = [sentiment_rule]
        matched = engine.match_rules("thanks for the help", sentiment=0.9)
        assert not any(r.rule_id == sentiment_rule.rule_id for r in matched)

    def test_top_k_limits_results(self, correction_rule):
        rules = []
        for i in range(10):
            r = correction_rule.model_copy()
            r.rule_id = f"rule_{i}"
            rules.append(r)
        engine = RuleEngine()
        engine._rules = rules
        matched = engine.match_rules("actually wrong incorrect", top_k=3)
        assert len(matched) <= 3

    def test_rules_sorted_by_priority_descending(self):
        low = Rule(
            rule_id="low",
            name="Low",
            description="Low priority",
            rule_type=RuleType.GUARDRAIL,
            priority=Priority.LOW,
            trigger=RuleTrigger(keywords=["wrong"]),
            action=RuleAction(type="modify_response", instruction="Low action"),
        )
        critical = Rule(
            rule_id="critical",
            name="Critical",
            description="Critical priority",
            rule_type=RuleType.GUARDRAIL,
            priority=Priority.CRITICAL,
            trigger=RuleTrigger(keywords=["wrong"]),
            action=RuleAction(type="modify_response", instruction="Critical action"),
        )
        engine = RuleEngine()
        engine._rules = [low, critical]
        matched = engine.match_rules("that's wrong")
        assert matched[0].rule_id == "critical"

    def test_system_prompt_built_from_matched_rules(self, correction_rule):
        engine = RuleEngine()
        engine._rules = [correction_rule]
        matched = engine.match_rules("actually wrong")
        prompt = engine.build_system_prompt(matched, base_prompt="You are a helpful assistant.")
        assert "Active Rules" in prompt
        assert correction_rule.action.instruction in prompt


# ---------------------------------------------------------------------------
# End-to-end behavioral scenarios
# ---------------------------------------------------------------------------


class TestBehavioralScenarios:
    """Real-world scenarios — the 'user stories' TDD for guardrails."""

    def test_frustrated_user_triggers_both_sentiment_and_correction_gaps(self, detector, make_turn):
        """
        SCENARIO: User gets increasingly frustrated with wrong answers.
        EXPECTED: Both sentiment_drop AND explicit_correction detected.
        """
        turns = [
            make_turn(1, "Help me fix this bug", "Here is a solution...", 0.6, 0.6),
            make_turn(2, "That didn't work", "Try this instead...", 0.6, 0.2),
            make_turn(3, "You're wrong again, this is useless", "I apologize...", 0.2, -0.3),
        ]
        gaps = detector.detect(turns)
        gap_types = {g["type"] for g in gaps}
        assert "explicit_correction" in gap_types
        assert "sentiment_drop" in gap_types

    def test_ai_suggests_unsafe_code_triggers_code_gap(self, detector, make_turn):
        """
        SCENARIO: AI suggests eval() and hardcoded secret in same response.
        EXPECTED: Multiple code anti-pattern gaps detected.
        """
        turns = [
            make_turn(
                1,
                "Write a config loader",
                'password = "admin123"\nresult = eval(open("config.txt").read())',
            )
        ]
        gaps = detector.detect(turns)
        code_gaps = [g for g in gaps if "code_anti_pattern" in g["type"]]
        assert len(code_gaps) >= 2

    def test_unanswered_question_loop_detected(self, detector, make_turn):
        """
        SCENARIO: AI keeps failing to answer the same question.
        EXPECTED: repeated_question gap after second occurrence.
        """
        q = "what is the difference between list and tuple in python"
        turns = [make_turn(1, q, "Both are sequences..."), make_turn(2, q, "As I mentioned...")]
        gaps = detector.detect(turns)
        assert any(g["type"] == "repeated_question" for g in gaps)

    def test_clean_helpful_conversation_no_gaps(self, detector, make_turn):
        """
        SCENARIO: A perfect, helpful conversation.
        EXPECTED: Zero gaps detected.
        """
        turns = [
            make_turn(
                1, "Can you explain Python generators?", "Generators are lazy iterators defined with yield...", 0.5, 0.8
            ),
            make_turn(
                2,
                "Can you give an example?",
                "Sure! Here is a simple generator:\n\ndef count_up(n):\n    for i in range(n):\n        yield i",
                0.8,
                0.9,
            ),
        ]
        gaps = detector.detect(turns)
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# Alignment sensor behaviors
# ---------------------------------------------------------------------------


class TestAlignmentSensorBehaviors:
    """Behavioral tests for the GPS-style alignment sensor."""

    @pytest.fixture
    def same_vector_embed(self):
        return lambda _: [1.0, 0.0]

    @pytest.fixture
    def divergent_embed(self):
        call_count = {"n": 0}

        def _embed(text):
            call_count["n"] += 1
            return [1.0, 0.0] if call_count["n"] % 2 == 1 else [0.0, 1.0]

        return _embed

    def test_compliance_is_perfect_with_no_active_rules(self, same_vector_embed):
        sensor = AlignmentSensor(embed_fn=same_vector_embed)
        conv = Conversation(conversation_id="t-001")
        turn = Turn(turn_number=1, user_input="help", agent_response="here")
        reading = sensor.measure(turn, conv, active_rule_keywords=[])
        assert reading.rule_compliance_score == 1.0

    def test_compliance_drops_when_rule_keywords_absent_in_response(self, same_vector_embed):
        sensor = AlignmentSensor(embed_fn=same_vector_embed)
        conv = Conversation(conversation_id="t-002")
        turn = Turn(turn_number=1, user_input="help", agent_response="here is some info")
        reading = sensor.measure(turn, conv, active_rule_keywords=[["error", "exception", "handling"]])
        assert reading.rule_compliance_score < 1.0

    def test_heading_positive_after_score_improves(self, same_vector_embed):
        sensor = AlignmentSensor(embed_fn=same_vector_embed)
        conv = Conversation(conversation_id="t-003")
        first = Turn(
            turn_number=1,
            user_input="help",
            agent_response="here",
            sensor_reading=SensorReading(
                task_alignment_score=0.2,
                rule_compliance_score=0.2,
                drift_score=0.8,
                direction="off_course",
                heading=0.0,
            ),
        )
        conv.add_turn(first)
        second = Turn(turn_number=2, user_input="help", agent_response="sure here")
        reading = sensor.measure(second, conv, [])
        assert reading.heading > 0

    def test_direction_on_track_at_high_composite(self, same_vector_embed):
        sensor = AlignmentSensor(embed_fn=same_vector_embed)
        conv = Conversation(conversation_id="t-004")
        turn = Turn(turn_number=1, user_input="x", agent_response="x")
        reading = sensor.measure(turn, conv, [])
        assert reading.direction == "on_track"

    def test_sensor_reading_fields_always_present(self, same_vector_embed):
        sensor = AlignmentSensor(embed_fn=same_vector_embed)
        conv = Conversation(conversation_id="t-005")
        turn = Turn(turn_number=1, user_input="hello", agent_response="hi")
        reading = sensor.measure(turn, conv, [])
        assert 0.0 <= reading.task_alignment_score <= 1.0
        assert 0.0 <= reading.rule_compliance_score <= 1.0
        assert 0.0 <= reading.drift_score <= 1.0
        assert reading.direction in ("on_track", "drifting", "off_course")
        assert isinstance(reading.heading, float)
