"""Unit tests for sprint 53: certification framework, stakeholder reporting,
continuous compliance monitoring, compliance calendar."""

import unittest
from datetime import datetime
from datetime import timedelta

# ---------------------------------------------------------------------------
# Inline pure-logic implementations
# ---------------------------------------------------------------------------


def add_certification(certs, cert_name, cert_type, issuing_body, issue_date, expiry_date, scope, rule_ids_csv):
    if not cert_name:
        return None, "certification name is required"
    rid_list = [r.strip() for r in rule_ids_csv.split(",") if r.strip()]
    cert = {
        "cert_id": "cert_001",
        "name": cert_name,
        "type": cert_type,
        "issuing_body": issuing_body,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "scope": scope,
        "linked_rule_ids": rid_list,
        "status": "active",
    }
    certs.append(cert)
    return cert, f"Certification '{cert_name}' added (id=cert_001, expires {expiry_date})."


def compute_cert_status(certs):
    now = datetime.utcnow()
    results = []
    for c in certs:
        expiry_str = c.get("expiry_date", "")
        days_until = None
        status = c.get("status", "active")
        if expiry_str and status != "revoked":
            try:
                expiry = datetime.fromisoformat(expiry_str)
                days_until = (expiry - now).days
                if days_until < 0:
                    status = "expired"
                elif days_until <= 30:
                    status = "pending_renewal"
                else:
                    status = "active"
            except ValueError:
                pass
        results.append({**c, "current_status": status, "days_until_expiry": days_until})
    return results


def compute_compliance_health(rules, incidents, slos, certs, goals):
    active = [r for r in rules if r.get("status") == "active"]
    healthy = 0
    for r in active:
        h = r.get("score_history", [])
        if h and sum(h) / len(h) >= 0.7:
            healthy += 1
    rule_health = round(healthy / len(active) * 100, 1) if active else 0.0

    open_critical = sum(
        1
        for i in incidents
        if i.get("status") not in ("resolved", "closed") and i.get("severity") in ("P0_critical", "P1_high")
    )
    incident_health = max(0.0, 100.0 - open_critical * 25)

    slo_ok = sum(1 for s in slos if s.get("status") == "ok")
    slo_health = round(slo_ok / len(slos) * 100, 1) if slos else 100.0

    active_certs = sum(1 for c in certs if c.get("current_status") == "active")
    cert_health = round(active_certs / len(certs) * 100, 1) if certs else 100.0

    aligned = sum(1 for g in goals if g.get("alignment_status") == "aligned")
    goal_health = round(aligned / len(goals) * 100, 1) if goals else 100.0

    overall = round(
        rule_health * 0.30 + incident_health * 0.25 + slo_health * 0.20 + cert_health * 0.15 + goal_health * 0.10, 1
    )
    return {
        "overall": overall,
        "rule_health": rule_health,
        "incident_health": incident_health,
        "slo_health": slo_health,
        "cert_health": cert_health,
        "goal_health": goal_health,
    }


def add_calendar_item(items, title, item_type, due_date, priority, description, owner, rule_ids_csv):
    if not title or not due_date:
        return None, "title and due date are required"
    rid_list = [r.strip() for r in rule_ids_csv.split(",") if r.strip()]
    item = {
        "item_id": f"cal_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "title": title,
        "type": item_type,
        "due_date": due_date,
        "priority": priority,
        "description": description,
        "owner": owner,
        "linked_rule_ids": rid_list,
        "status": "pending",
    }
    items.append(item)
    return item, f"Calendar item '{title}' added (due {due_date})."


def compute_calendar_status(items):
    now = datetime.utcnow()
    results = []
    for item in items:
        due_str = item.get("due_date", "")
        days_until = None
        urgency = "on_track"
        if due_str and item.get("status") == "pending":
            try:
                due = datetime.fromisoformat(due_str)
                days_until = (due - now).days
                if days_until < 0:
                    urgency = "overdue"
                elif days_until <= 7:
                    urgency = "urgent"
                elif days_until <= 30:
                    urgency = "upcoming"
            except ValueError:
                pass
        results.append({**item, "days_until": days_until, "urgency": urgency})
    return results


def complete_calendar_item(items, item_id, notes):
    if not item_id:
        return "item id is required"
    for item in items:
        if item.get("item_id", "").startswith(item_id):
            item["status"] = "completed"
            item["completion_notes"] = notes
            return f"Item '{item_id}' marked as completed."
    return f"Item '{item_id}' not found."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_RULES = [
    {"rule_id": "r1", "name": "Rule A", "status": "active", "score_history": [0.8, 0.85, 0.9]},
    {"rule_id": "r2", "name": "Rule B", "status": "active", "score_history": [0.5, 0.55, 0.6]},
    {"rule_id": "r3", "name": "Rule C", "status": "deprecated", "score_history": [0.9]},
]

FAKE_INCIDENTS = [
    {"incident_id": "i1", "severity": "P0_critical", "status": "open"},
    {"incident_id": "i2", "severity": "P2_medium", "status": "resolved"},
]

FAKE_SLOS = [
    {"slo_id": "s1", "status": "ok"},
    {"slo_id": "s2", "status": "ok"},
    {"slo_id": "s3", "status": "breached"},
]

FAKE_CERTS = [
    {
        "cert_id": "c1",
        "name": "ISO 27001",
        "type": "iso_27001",
        "status": "active",
        "expiry_date": (datetime.utcnow() + timedelta(days=180)).strftime("%Y-%m-%d"),
        "current_status": "active",
    },
    {
        "cert_id": "c2",
        "name": "SOC2",
        "type": "soc2",
        "status": "active",
        "expiry_date": (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d"),
        "current_status": "expired",
    },
]

FAKE_GOALS = [
    {
        "goal_id": "g1",
        "objective": "Reduce Harm",
        "alignment_status": "aligned",
        "actual_score": 85,
        "target_score": 80,
    },
    {
        "goal_id": "g2",
        "objective": "High Accuracy",
        "alignment_status": "misaligned",
        "actual_score": 60,
        "target_score": 90,
    },
]


# ---------------------------------------------------------------------------
# Tests: Certification Framework
# ---------------------------------------------------------------------------


class TestCertificationFramework(unittest.TestCase):
    def test_add_certification_success(self):
        certs = []
        cert, msg = add_certification(
            certs, "ISO 27001", "iso_27001", "BSI Group", "2024-01-01", "2027-01-01", "All AI systems", "r1,r2"
        )
        self.assertIsNotNone(cert)
        self.assertIn("ISO 27001", msg)
        self.assertIn("2027-01-01", msg)
        self.assertEqual(len(certs), 1)
        self.assertEqual(cert["linked_rule_ids"], ["r1", "r2"])

    def test_add_certification_requires_name(self):
        certs = []
        cert, msg = add_certification(certs, "", "iso_27001", "BSI", "2024-01-01", "2027-01-01", "", "")
        self.assertIsNone(cert)
        self.assertIn("required", msg.lower())

    def test_active_cert_not_expiring(self):
        certs = [{"cert_id": "c1", "name": "Test", "expiry_date": "2099-01-01", "status": "active"}]
        result = compute_cert_status(certs)
        self.assertEqual(result[0]["current_status"], "active")
        self.assertGreater(result[0]["days_until_expiry"], 30)

    def test_expired_cert_detected(self):
        certs = [{"cert_id": "c1", "name": "Old Cert", "expiry_date": "2020-01-01", "status": "active"}]
        result = compute_cert_status(certs)
        self.assertEqual(result[0]["current_status"], "expired")
        self.assertLess(result[0]["days_until_expiry"], 0)

    def test_pending_renewal_within_30_days(self):
        soon = (datetime.utcnow() + timedelta(days=15)).strftime("%Y-%m-%d")
        certs = [{"cert_id": "c1", "name": "Expiring Soon", "expiry_date": soon, "status": "active"}]
        result = compute_cert_status(certs)
        self.assertEqual(result[0]["current_status"], "pending_renewal")

    def test_revoked_cert_not_recomputed(self):
        certs = [{"cert_id": "c1", "name": "Revoked", "expiry_date": "2099-01-01", "status": "revoked"}]
        result = compute_cert_status(certs)
        self.assertEqual(result[0]["current_status"], "revoked")

    def test_empty_certs_returns_empty(self):
        result = compute_cert_status([])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Tests: Continuous Compliance Monitoring
# ---------------------------------------------------------------------------


class TestContinuousComplianceMonitoring(unittest.TestCase):
    def test_overall_score_is_weighted_average(self):
        h = compute_compliance_health(FAKE_RULES, FAKE_INCIDENTS, FAKE_SLOS, FAKE_CERTS, FAKE_GOALS)
        # rule_health: r1(85%→healthy), r2(58%→not), r3(deprecated→not active) → 1/2=50%
        self.assertAlmostEqual(h["rule_health"], 50.0, places=0)
        # incident_health: 1 open P0 → 100-25=75
        self.assertEqual(h["incident_health"], 75.0)
        # slo_health: 2/3 ok → 66.7%
        self.assertAlmostEqual(h["slo_health"], 66.7, places=0)
        # overall is in range
        self.assertGreater(h["overall"], 0)
        self.assertLessEqual(h["overall"], 100)

    def test_no_open_critical_incidents_gives_100_incident_health(self):
        clean_incidents = [{"severity": "P2_medium", "status": "resolved"}]
        h = compute_compliance_health(FAKE_RULES, clean_incidents, [], [], [])
        self.assertEqual(h["incident_health"], 100.0)

    def test_two_open_p0_incidents_reduces_health(self):
        bad_incidents = [
            {"severity": "P0_critical", "status": "open"},
            {"severity": "P0_critical", "status": "investigating"},
        ]
        h = compute_compliance_health(FAKE_RULES, bad_incidents, [], [], [])
        self.assertEqual(h["incident_health"], 50.0)

    def test_all_slos_ok_gives_100_slo_health(self):
        all_ok_slos = [{"status": "ok"}, {"status": "ok"}]
        h = compute_compliance_health([], [], all_ok_slos, [], [])
        self.assertEqual(h["slo_health"], 100.0)

    def test_all_certs_active_gives_100_cert_health(self):
        active_certs = [{"current_status": "active"}, {"current_status": "active"}]
        h = compute_compliance_health([], [], [], active_certs, [])
        self.assertEqual(h["cert_health"], 100.0)

    def test_no_active_rules_gives_zero_rule_health(self):
        no_active = [{"rule_id": "r1", "status": "deprecated", "score_history": [0.9]}]
        h = compute_compliance_health(no_active, [], [], [], [])
        self.assertEqual(h["rule_health"], 0.0)

    def test_overall_clamped_to_0_100(self):
        h = compute_compliance_health([], [], [], [], [])
        self.assertGreaterEqual(h["overall"], 0)
        self.assertLessEqual(h["overall"], 100)


# ---------------------------------------------------------------------------
# Tests: Compliance Calendar
# ---------------------------------------------------------------------------


class TestComplianceCalendar(unittest.TestCase):
    def _future(self, days):
        return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")

    def _past(self, days):
        return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    def test_add_calendar_item_success(self):
        items = []
        item, msg = add_calendar_item(
            items, "Annual Audit", "audit", self._future(90), "high", "Yearly governance audit", "Alice", "r1,r2"
        )
        self.assertIsNotNone(item)
        self.assertIn("Annual Audit", msg)
        self.assertEqual(len(items), 1)
        self.assertEqual(item["linked_rule_ids"], ["r1", "r2"])

    def test_add_calendar_item_requires_title(self):
        items = []
        item, msg = add_calendar_item(items, "", "audit", self._future(10), "high", "", "", "")
        self.assertIsNone(item)
        self.assertIn("required", msg.lower())

    def test_add_calendar_item_requires_due_date(self):
        items = []
        item, msg = add_calendar_item(items, "Review", "review", "", "medium", "", "", "")
        self.assertIsNone(item)
        self.assertIn("required", msg.lower())

    def test_overdue_item_detected(self):
        items = [
            {
                "item_id": "cal_001",
                "title": "Late Audit",
                "type": "audit",
                "due_date": self._past(5),
                "status": "pending",
            }
        ]
        result = compute_calendar_status(items)
        self.assertEqual(result[0]["urgency"], "overdue")
        self.assertLess(result[0]["days_until"], 0)

    def test_urgent_within_7_days(self):
        items = [
            {
                "item_id": "cal_002",
                "title": "Urgent Review",
                "type": "review",
                "due_date": self._future(3),
                "status": "pending",
            }
        ]
        result = compute_calendar_status(items)
        self.assertEqual(result[0]["urgency"], "urgent")

    def test_upcoming_within_30_days(self):
        items = [
            {
                "item_id": "cal_003",
                "title": "Upcoming Training",
                "type": "training",
                "due_date": self._future(20),
                "status": "pending",
            }
        ]
        result = compute_calendar_status(items)
        self.assertEqual(result[0]["urgency"], "upcoming")

    def test_on_track_for_distant_due_date(self):
        items = [
            {
                "item_id": "cal_004",
                "title": "Annual Review",
                "type": "review",
                "due_date": self._future(90),
                "status": "pending",
            }
        ]
        result = compute_calendar_status(items)
        self.assertEqual(result[0]["urgency"], "on_track")

    def test_complete_item(self):
        items = [
            {"item_id": "cal_001", "title": "Test", "type": "audit", "due_date": self._future(10), "status": "pending"}
        ]
        msg = complete_calendar_item(items, "cal_001", "All done")
        self.assertIn("completed", msg)
        self.assertEqual(items[0]["status"], "completed")
        self.assertEqual(items[0]["completion_notes"], "All done")

    def test_complete_item_not_found(self):
        items = []
        msg = complete_calendar_item(items, "cal_999", "")
        self.assertIn("not found", msg)

    def test_completed_item_has_on_track_urgency(self):
        items = [
            {"item_id": "cal_001", "title": "Done", "type": "audit", "due_date": self._past(5), "status": "completed"}
        ]
        result = compute_calendar_status(items)
        self.assertEqual(result[0]["urgency"], "on_track")


if __name__ == "__main__":
    unittest.main()
