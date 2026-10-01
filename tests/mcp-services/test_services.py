#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import kiosk_server
import order_accuracy_server
from plain_mcp_service import gated_handler
import service_runtime


class DomainContractTests(unittest.TestCase):
    def test_kiosk_context_has_decision_fields(self) -> None:
        context = kiosk_server.get_kiosk_context()

        self.assertEqual(context["schema_version"], "1.0")
        self.assertIn("queue_count", context["operations"])
        self.assertIn("estimated_wait_minutes", context["operations"])
        self.assertIn("is_raining", context["weather"])
        self.assertIn("items", context["menu"])
        self.assertIn("observed_at", context)

    def test_kiosk_weather_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"QSR_WEATHER_CONDITION": "clear"}):
            context = kiosk_server.get_kiosk_context()

        self.assertEqual(context["weather"]["condition"], "clear")
        self.assertFalse(context["weather"]["is_raining"])

    def test_kiosk_weather_simulator_toggles_every_thirty_seconds(self) -> None:
        with patch.dict(os.environ, {"QSR_WEATHER_TOGGLE_SECONDS": "30"}):
            first = kiosk_server._simulated_weather(now=0)
            same_period = kiosk_server._simulated_weather(now=29.999)
            next_period = kiosk_server._simulated_weather(now=30)

        self.assertTrue(first["is_raining"])
        self.assertEqual(first["condition"], same_period["condition"])
        self.assertFalse(next_period["is_raining"])
        self.assertNotEqual(first["condition"], next_period["condition"])

    def test_kiosk_queue_scenario_can_be_configured(self) -> None:
        with patch.dict(os.environ, {"QSR_QUEUE_COUNT": "0", "QSR_ESTIMATED_WAIT_MINUTES": "0"}):
            context = kiosk_server.get_kiosk_context()
        self.assertEqual(context["operations"]["queue_count"], 0)
        self.assertEqual(context["operations"]["estimated_wait_minutes"], 0)
        for variable in ("QSR_QUEUE_COUNT", "QSR_ESTIMATED_WAIT_MINUTES"):
            for value in ("-1", "not-a-number"):
                with self.subTest(variable=variable, value=value), patch.dict(os.environ, {variable: value}):
                    with self.assertRaises(ValueError):
                        kiosk_server.get_kiosk_context()

    def test_menu_change_is_visible_in_later_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "kiosk-state.json"
            with patch.dict(os.environ, {"QSR_KIOSK_STATE": str(state_path)}):
                result = kiosk_server.change_menu(
                    item_id="hot-chocolate",
                    available=True,
                    reason="Rain policy approved",
                )
                context = kiosk_server.get_kiosk_context()

        hot_chocolate = next(
            item for item in context["menu"]["items"] if item["id"] == "hot-chocolate"
        )
        self.assertEqual(result["status"], "accepted")
        self.assertTrue(hot_chocolate["available"])
        self.assertEqual(hot_chocolate["availability_reason"], "Rain policy approved")

    def test_menu_change_normalizes_common_item_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "kiosk-state.json"
            with patch.dict(os.environ, {"QSR_KIOSK_STATE": str(state_path)}):
                result = kiosk_server.change_menu(
                    item_id="hot_chocolate",
                    available=False,
                    reason="Operator request",
                )

        self.assertEqual(result["requested_change"]["item_id"], "hot-chocolate")

    def test_menu_bundle_persists_bounded_changes_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "kiosk-state.json"
            with patch.dict(os.environ, {"QSR_KIOSK_STATE": str(state_path)}):
                result = kiosk_server.change_menu_items(
                    changes=[
                        {
                            "item_id": "hot-chocolate",
                            "available": True,
                            "reason": "Warm drink for rain",
                        },
                        {
                            "item_id": "tea",
                            "available": True,
                            "reason": "Alternative warm drink",
                        },
                    ],
                    reason="Hermes weather recommendation",
                )
                context = kiosk_server.get_kiosk_context()

        items = {item["id"]: item for item in context["menu"]["items"]}
        self.assertEqual(len(result["changes"]), 2)
        self.assertTrue(items["hot-chocolate"]["available"])
        self.assertTrue(items["tea"]["available"])
        self.assertEqual(items["tea"]["availability_reason"], "Alternative warm drink")

    def test_order_accuracy_context_has_decision_fields(self) -> None:
        context = order_accuracy_server.get_order_accuracy_context()

        self.assertEqual(context["schema_version"], "1.0")
        self.assertIn("accuracy_rate", context["summary"])
        self.assertIn("stations", context)
        self.assertIn("recent_orders", context)
        self.assertIn("observed_at", context)

    def test_comp_is_denied_without_approver(self) -> None:
        result = gated_handler(order_accuracy_server.issue_comp, "needs_approval")(
            {"order_id": "ORD-1042", "amount": 5.0}
        )

        self.assertFalse(result["executed"])
        self.assertEqual(result["gate"], "needs_approval")


class TransportTests(unittest.TestCase):
    def test_simulation_registers_plain_mcp_tools(self) -> None:
        with patch.object(service_runtime, "serve") as serve:
            service_runtime.run_service(
                "kiosk-placeholder",
                kiosk_server.TOOL_SCHEMAS,
                kiosk_server.TOOL_HANDLERS,
                kiosk_server.TOOL_DESCRIPTIONS,
                action_gates={"change_menu": "automatic", "change_menu_items": "automatic"},
            )

        serve.assert_called_once()
        args = serve.call_args.args
        self.assertEqual(args[0], "kiosk-placeholder")
        self.assertEqual(set(args[1]), set(kiosk_server.TOOL_SCHEMAS))
        self.assertEqual(set(args[2]), set(kiosk_server.TOOL_HANDLERS))


if __name__ == "__main__":
    unittest.main()