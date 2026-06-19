"""Unit tests for the Maturity Model (Levels 1–6) assessment logic."""
import unittest


# ---------------------------------------------------------------------------
# Inline pure-logic implementations (mirrors space/app.py without gradio/HF)
# ---------------------------------------------------------------------------

def assess_maturity(capability_results: dict[str, bool]) -> dict:
    """
    capability_results: {label: bool} for every capability across all 6 levels.
    Returns current_level, per-level assessment, and gaps to next level.
    """
    LEVELS = [
        {
            "level": 1,
            "name": "Initial",
            "caps": [
                "Rules defined",
                "Rule categories used",
                "At least one active rule",
                "Rule descriptions present",
            ],
        },
        {
            "level": 2,
            "name": "Defined",
            "caps": [
                "Rule lifecycle tracked",
                "Rule ownership assigned",
                "Sessions imported",
                "Exceptions managed",
                "Dependencies mapped",
            ],
        },
        {
            "level": 3,
            "name": "Managed",
            "caps": [
                "Incidents tracked",
                "Rule enforcement logged",
                "AI audits conducted",
                "Human overrides logged",
                "Conflict detection run",
                "RCA log entries present",
            ],
        },
        {
            "level": 4,
            "name": "Measured",
            "caps": [
                "Trust score computed",
                "SLOs defined",
                "Benchmark cases defined",
                "Rule coverage measured",
                "Compliance forecasts run",
                "Decision provenance recorded",
            ],
        },
        {
            "level": 5,
            "name": "Optimized",
            "caps": [
                "Regression detection run",
                "Rule learning detected",
                "Improvement cycles active",
                "Reputation snapshots taken",
                "Adversarial robustness tested",
                "Goal alignment monitored",
                "Predictive compliance horizon set",
            ],
        },
        {
            "level": 6,
            "name": "Autonomous",
            "caps": [
                "Certifications registered",
                "Audit trail integrity chain active",
                "Fairness/bias analyses run",
                "Control mapping complete",
                "Meta-governance roles assigned",
                "Compliance calendar active",
                "Stakeholder reports generated",
                "Gaming detection active",
            ],
        },
    ]

    level_results = []
    current_level = 0
    all_previous_passed = True

    for level_def in LEVELS:
        caps = []
        for label in level_def["caps"]:
            passed = capability_results.get(label, False)
            caps.append({"label": label, "passed": passed})

        total = len(caps)
        passed_count = sum(1 for c in caps if c["passed"])
        pct = round(passed_count / total * 100, 1) if total else 0.0
        achieved = (passed_count == total) and all_previous_passed

        if achieved:
            current_level = level_def["level"]
        elif all_previous_passed and passed_count < total:
            all_previous_passed = False

        level_results.append({
            "level": level_def["level"],
            "name": level_def["name"],
            "caps": caps,
            "passed": passed_count,
            "total": total,
            "pct": pct,
            "achieved": achieved,
        })

    next_level_idx = current_level
    gaps = []
    if next_level_idx < len(level_results):
        next_lvl = level_results[next_level_idx]
        gaps = [c["label"] for c in next_lvl["caps"] if not c["passed"]]

    return {
        "current_level": current_level,
        "current_name": LEVELS[current_level - 1]["name"] if current_level > 0 else "Not Started",
        "level_results": level_results,
        "gaps_to_next": gaps,
        "next_level": current_level + 1 if current_level < 6 else None,
        "next_level_name": LEVELS[current_level]["name"] if current_level < 6 else "Achieved",
    }


def _all_caps_for_levels(up_to_level: int) -> dict[str, bool]:
    """Build a capability_results dict where all caps up to given level are True."""
    LEVEL_CAPS = {
        1: ["Rules defined", "Rule categories used", "At least one active rule", "Rule descriptions present"],
        2: ["Rule lifecycle tracked", "Rule ownership assigned", "Sessions imported", "Exceptions managed", "Dependencies mapped"],
        3: ["Incidents tracked", "Rule enforcement logged", "AI audits conducted", "Human overrides logged", "Conflict detection run", "RCA log entries present"],
        4: ["Trust score computed", "SLOs defined", "Benchmark cases defined", "Rule coverage measured", "Compliance forecasts run", "Decision provenance recorded"],
        5: ["Regression detection run", "Rule learning detected", "Improvement cycles active", "Reputation snapshots taken", "Adversarial robustness tested", "Goal alignment monitored", "Predictive compliance horizon set"],
        6: ["Certifications registered", "Audit trail integrity chain active", "Fairness/bias analyses run", "Control mapping complete", "Meta-governance roles assigned", "Compliance calendar active", "Stakeholder reports generated", "Gaming detection active"],
    }
    result = {}
    for lvl in range(1, up_to_level + 1):
        for cap in LEVEL_CAPS[lvl]:
            result[cap] = True
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMaturityLevelProgression(unittest.TestCase):

    def test_no_capabilities_gives_level_0(self):
        result = assess_maturity({})
        self.assertEqual(result["current_level"], 0)
        self.assertEqual(result["current_name"], "Not Started")

    def test_level_1_achieved_when_all_l1_caps_met(self):
        caps = _all_caps_for_levels(1)
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 1)
        self.assertEqual(result["current_name"], "Initial")

    def test_level_2_achieved_when_l1_and_l2_caps_met(self):
        caps = _all_caps_for_levels(2)
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 2)
        self.assertEqual(result["current_name"], "Defined")

    def test_level_3_achieved(self):
        caps = _all_caps_for_levels(3)
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 3)

    def test_level_4_achieved(self):
        caps = _all_caps_for_levels(4)
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 4)

    def test_level_5_achieved(self):
        caps = _all_caps_for_levels(5)
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 5)

    def test_level_6_achieved(self):
        caps = _all_caps_for_levels(6)
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 6)
        self.assertIsNone(result["next_level"])
        self.assertEqual(result["next_level_name"], "Achieved")

    def test_partial_level_1_gives_level_0(self):
        # Only 2 of 4 L1 caps
        caps = {"Rules defined": True, "Rule categories used": True}
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 0)

    def test_skipping_level_2_blocks_higher_levels(self):
        # All L1 done, skip L2, all L3+ done → still only level 1
        caps = _all_caps_for_levels(1)
        caps.update({c: True for c in [
            "Incidents tracked", "Rule enforcement logged", "AI audits conducted",
            "Human overrides logged", "Conflict detection run", "RCA log entries present",
        ]})
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 1)  # L2 not achieved → L3 can't count

    def test_level_not_achieved_if_one_cap_missing(self):
        caps = _all_caps_for_levels(1)
        caps["Rule descriptions present"] = False
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 0)

    def test_gaps_report_missing_capabilities_for_next_level(self):
        # L1 complete, L2 partially done — gaps should list the missing L2 caps
        caps = _all_caps_for_levels(1)
        caps["Rule lifecycle tracked"] = True
        caps["Rule ownership assigned"] = True
        # Sessions imported, Exceptions managed, Dependencies mapped → missing
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 1)
        self.assertIn("Sessions imported", result["gaps_to_next"])
        self.assertIn("Exceptions managed", result["gaps_to_next"])
        self.assertIn("Dependencies mapped", result["gaps_to_next"])

    def test_gaps_empty_when_at_max_level(self):
        caps = _all_caps_for_levels(6)
        result = assess_maturity(caps)
        self.assertEqual(result["gaps_to_next"], [])

    def test_next_level_is_current_plus_one(self):
        for lvl in range(1, 6):
            caps = _all_caps_for_levels(lvl)
            result = assess_maturity(caps)
            self.assertEqual(result["next_level"], lvl + 1)

    def test_all_level_results_present(self):
        result = assess_maturity({})
        self.assertEqual(len(result["level_results"]), 6)
        self.assertEqual([l["level"] for l in result["level_results"]], [1, 2, 3, 4, 5, 6])

    def test_pct_correct_for_partial_level(self):
        caps = _all_caps_for_levels(1)  # all L1 = 4 caps
        caps["Rule lifecycle tracked"] = True  # 1 of 5 L2 caps
        result = assess_maturity(caps)
        l2 = result["level_results"][1]  # index 1 = level 2
        self.assertEqual(l2["passed"], 1)
        self.assertEqual(l2["total"], 5)
        self.assertEqual(l2["pct"], 20.0)

    def test_achieved_flag_correct(self):
        caps = _all_caps_for_levels(3)
        result = assess_maturity(caps)
        for lvl_result in result["level_results"]:
            if lvl_result["level"] <= 3:
                self.assertTrue(lvl_result["achieved"], f"Level {lvl_result['level']} should be achieved")
            else:
                self.assertFalse(lvl_result["achieved"], f"Level {lvl_result['level']} should not be achieved")


class TestMaturityLevelNames(unittest.TestCase):
    def test_level_names_are_correct(self):
        expected = {1: "Initial", 2: "Defined", 3: "Managed", 4: "Measured", 5: "Optimized", 6: "Autonomous"}
        for lvl, name in expected.items():
            caps = _all_caps_for_levels(lvl)
            result = assess_maturity(caps)
            self.assertEqual(result["current_name"], name)


class TestMaturityEdgeCases(unittest.TestCase):
    def test_extra_unknown_capabilities_ignored(self):
        caps = _all_caps_for_levels(1)
        caps["Unknown capability XYZ"] = True
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 1)

    def test_false_caps_at_higher_level_dont_count(self):
        caps = _all_caps_for_levels(2)
        caps["Incidents tracked"] = False  # L3 cap missing
        result = assess_maturity(caps)
        self.assertEqual(result["current_level"], 2)

    def test_level_result_structure(self):
        result = assess_maturity(_all_caps_for_levels(2))
        for lvl_result in result["level_results"]:
            self.assertIn("level", lvl_result)
            self.assertIn("name", lvl_result)
            self.assertIn("caps", lvl_result)
            self.assertIn("passed", lvl_result)
            self.assertIn("total", lvl_result)
            self.assertIn("pct", lvl_result)
            self.assertIn("achieved", lvl_result)


if __name__ == "__main__":
    unittest.main()
