import unittest

from app.services.event_pipeline import NormalizedEvent, normalize_message, normalize_topics


class EventPipelineTests(unittest.TestCase):
    def test_transport_independent_canonical_hash(self):
        syslog = NormalizedEvent(7, "R1", "syslog", "WARNING, dhcp", " Rogue DHCP 192.0.2.1 ", ros_time="12:00:00")
        recovery = NormalizedEvent(7, "R1", "log_recovery", "dhcp,warning", "rogue dhcp 192.0.2.1", ros_time="12:00:00")
        self.assertEqual(syslog.normalized()[0], recovery.normalized()[0])

    def test_normalization_removes_transport_noise(self):
        self.assertEqual(normalize_topics(" Warning, DHCP, warning "), "dhcp,warning,warning")
        self.assertEqual(normalize_message("a\x00  b\n c"), "a b c")

    def test_dhcp_rogue_has_functional_deduplication_key(self):
        event = NormalizedEvent(2, "R2", "syslog", "dhcp,warning", "rogue DHCP server")
        _, key = event.normalized()
        self.assertEqual(key, "2:dhcp_rogue")

    def test_router_recovery_uses_a_distinct_deduplication_key(self):
        offline = NormalizedEvent(4, "Antares", "health_check", "health,critical", "Antares se desconectó",
                                  "critical", "router_offline", correlation_id="4:router_offline")
        online = NormalizedEvent(4, "Antares", "health_check", "health,recovery", "Antares se reconectó",
                                 "recovery", "router_online", correlation_id="4:router_online")
        self.assertNotEqual(offline.normalized()[1], online.normalized()[1])


if __name__ == "__main__":
    unittest.main()
