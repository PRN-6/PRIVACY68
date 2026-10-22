"""
Tests for the declarative command registry.

The point of the registry is that a command is described in ONE place:
its identity, its lane, the ways it can be recognised, how its arguments
are extracted and what runs it. These tests pin that promise down:

  * every catalogue command is reachable and executable
  * the catalogue is the single source of truth for the taxonomy
  * adding one spec is enough to make a new command work end to end
  * the slots a command needs are extracted correctly
"""

import unittest

from actions.catalog import SITES
from actions.dispatch import resolve
from actions.executor import execute_system_command_detailed
from actions.fast_lane import fast_lane_router
from actions.intent_classifier import INTENT_TO_LANE, TRAINING_DATA, intent_classifier
from actions.param_extractor import param_extractor
from actions.registry import LANE_API, LANE_FAST, LANE_LLM, registry


class TestRegistryIntegrity(unittest.TestCase):
    """The registry itself must be coherent."""

    def test_every_command_is_registered(self):
        self.assertGreater(len(registry.all()), 10)

    def test_every_command_has_an_intent_and_a_lane(self):
        for spec in registry.all():
            self.assertTrue(spec.intent, f"'{spec.id}' has no intent")
            self.assertIn(spec.lane, (LANE_FAST, LANE_API, LANE_LLM),
                          f"'{spec.id}' has an unknown lane")

    def test_every_intent_maps_to_exactly_one_command(self):
        intents = [spec.intent for spec in registry.all()]
        duplicates = {i for i in intents if intents.count(i) > 1}
        self.assertEqual(duplicates, set(),
                         f"these intents are claimed by more than one command: {duplicates}")

    def test_only_llm_lane_commands_may_have_no_handler(self):
        for spec in registry.all():
            if spec.handler is None:
                self.assertIn(spec.lane, (LANE_LLM, LANE_FAST),
                              f"'{spec.id}' has no handler but is not an LLM-lane command")

    def test_the_taxonomy_comes_from_the_catalogue(self):
        """The classifier's intent -> lane map is the registry's, not a copy."""
        self.assertEqual(
            INTENT_TO_LANE,
            registry.intent_lane(),
            "the classifier is using a stale copy of the intent taxonomy",
        )

    def test_every_intent_is_reachable_from_the_classifier(self):
        """Each catalogue intent has at least one training example."""
        trained = {intent for _, intent in TRAINING_DATA}
        for spec in registry.all():
            self.assertIn(spec.intent, trained,
                          f"intent '{spec.intent}' has no training example")


class TestCatalogueCommands(unittest.TestCase):
    """The commands the catalogue ships with must actually work."""

    def test_system_actions(self):
        for phrase, expected in [
            ("volume up", "volume_up"),
            ("volume down", "volume_down"),
            ("mute", "volume_mute"),
            ("unmute", "volume_unmute"),
            ("lock screen", "lock"),
            ("take a screenshot", "screenshot"),
            ("close window", "close_window"),
            ("maximize window", "maximize"),
            ("minimize window", "minimize"),
            ("press enter", "enter"),
        ]:
            with self.subTest(phrase=phrase):
                match = registry.match(phrase, lane=LANE_FAST)
                self.assertIsNotNone(match, f"'{phrase}' was not recognised")
                self.assertEqual(match.slots.get("action"), expected)

    def test_unmute_is_not_mute(self):
        """'unmute' must not be handled as 'mute' — they are different actions."""
        mute = registry.match("mute", lane=LANE_FAST)
        unmute = registry.match("unmute", lane=LANE_FAST)
        self.assertEqual(mute.slots.get("action"), "volume_mute")
        self.assertEqual(unmute.slots.get("action"), "volume_unmute")

    def test_settings_pages(self):
        for phrase, page in [
            ("open settings", ""),
            ("open bluetooth settings", "bluetooth"),
            ("go to bluetooth", "bluetooth"),
            ("switch to display", "display"),
            ("go to sound tab", "sound"),
        ]:
            with self.subTest(phrase=phrase):
                match = registry.match(phrase, lane=LANE_FAST)
                self.assertIsNotNone(match, f"'{phrase}' was not recognised")
                self.assertEqual(match.slots.get("page", ""), page)

    def test_websites_and_apps_do_not_collide(self):
        for site in SITES:
            with self.subTest(site=site):
                match = registry.match(f"open {site}", lane=LANE_FAST)
                self.assertIsNotNone(match, f"'{site}' was not recognised")
        for app in ("chrome", "notepad", "calculator", "vs code", "firefox"):
            with self.subTest(app=app):
                match = registry.match(f"open {app}", lane=LANE_FAST)
                self.assertIsNotNone(match, f"'{app}' was not recognised")
                self.assertEqual(match.spec.id, "system.application")

    def test_api_commands_live_in_the_api_lane(self):
        for phrase in ("what is the weather in Tokyo",
                       "what is my ip",
                       "search machine learning algorithms on google"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(registry.match(phrase, lane=LANE_FAST))
                self.assertIsNotNone(registry.match(phrase, lane=LANE_API))


class TestSlotExtraction(unittest.TestCase):
    """The arguments of a command must be pulled out of the utterance."""

    def test_create_folder(self):
        slots = param_extractor.extract_slots(
            "create a folder named Privacy on Desktop", "create_folder")
        self.assertEqual(slots.get("name"), "Privacy")
        self.assertEqual(slots.get("path"), "Desktop")

    def test_create_folder_with_the_verb_after_the_name(self):
        slots = param_extractor.extract_slots(
            "Create MCA folder in downloads", "create_folder")
        self.assertEqual(slots.get("name"), "MCA")
        self.assertEqual(slots.get("path"), "downloads")

    def test_create_file_with_content(self):
        slots = param_extractor.extract_slots(
            "create file todo.txt with content buy groceries", "create_file")
        self.assertEqual(slots.get("name"), "todo.txt")
        self.assertEqual(slots.get("content"), "buy groceries")

    def test_rename_keeps_both_names_and_the_folder(self):
        slots = param_extractor.extract_slots(
            "rename file old_doc.txt to final_doc.txt in downloads", "rename_item")
        self.assertEqual(slots.get("source"), "old_doc.txt")
        self.assertEqual(slots.get("name"), "final_doc.txt")
        self.assertEqual(slots.get("path"), "downloads")

    def test_delete_keeps_the_target(self):
        slots = param_extractor.extract_slots(
            "delete the file notes.txt from desktop", "delete_item")
        self.assertEqual(slots.get("name"), "notes.txt")
        self.assertEqual(slots.get("path"), "desktop")

    def test_web_search_splits_query_and_site(self):
        slots = param_extractor.extract_slots(
            "search machine learning algorithms on google", "web_search")
        self.assertEqual(slots.get("query"), "machine learning algorithms")
        self.assertEqual(slots.get("site"), "google")

    def test_absolute_paths_are_preserved(self):
        slots = param_extractor.extract_slots(
            r"create MCA folder in C:\Users\prins\Desktop", "create_folder")
        self.assertEqual(slots.get("path"), r"C:\Users\prins\Desktop")
        self.assertEqual(slots.get("name"), "MCA")


class TestAddingACommand(unittest.TestCase):
    """
    The whole point of the registry: a new command is one spec.

    This test registers a command exactly the way a developer would, and
    checks that it is recognised, understood and executed without any
    other file being touched.
    """

    def tearDown(self):
        registry.unregister("test.ping")

    def test_a_new_spec_is_immediately_usable(self):
        from actions.registry import CommandSpec, Matcher

        registry.register(CommandSpec(
            id="test.ping",
            lane=LANE_FAST,
            intent="test_ping",
            handler=lambda ctx: {
                "tool": "test_ping",
                "success": True,
                "message": f"pong {ctx.slot('target')}",
            },
            matchers=(Matcher(pattern=r"^\s*ping\s+(?P<target>.+?)\s*$"),),
            examples=("ping the server",),
            priority=99,
        ))

        # 1. The registry recognises it.
        match = registry.match("ping the server", lane=LANE_FAST)
        self.assertIsNotNone(match)
        self.assertEqual(match.spec.id, "test.ping")
        self.assertEqual(match.slots.get("target"), "the server")

        # 2. The classifier knows the intent.
        lane, intent, confidence = intent_classifier.classify("ping the server")
        self.assertEqual(lane, LANE_FAST)
        self.assertEqual(intent, "test_ping")

        # 3. The fast lane resolves it.
        result = fast_lane_router.try_execute_fast("ping the server")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("tool"), "test_ping")
        self.assertTrue(result.get("success"))

        # 4. The executor runs it end to end.
        outcome = execute_system_command_detailed("ping the server")
        self.assertTrue(outcome.get("success"))
        self.assertEqual(outcome.get("tool"), "test_ping")


class TestClassificationIsCatalogueDriven(unittest.TestCase):
    """The classifier must agree with the catalogue."""

    def test_known_commands_classify_to_their_own_intent(self):
        for phrase, intent in [
            ("mute volume", "system_action"),
            ("open settings", "open_settings"),
            ("open youtube", "open_website"),
            ("open chrome", "open_application"),
            ("open downloads", "open_folder"),
            ("what is the weather", "api_weather"),
            ("what is my ip", "api_ip_info"),
        ]:
            with self.subTest(phrase=phrase):
                _, classified, _ = intent_classifier.classify(phrase)
                self.assertEqual(classified, intent)

    def test_unknown_phrasings_do_not_become_commands(self):
        for phrase in ("asdkjh askdjh", "flurble wozzle"):
            with self.subTest(phrase=phrase):
                _, intent, confidence = intent_classifier.classify(phrase)
                self.assertEqual(intent, "unknown")

    def test_resolve_refuses_a_lane_that_does_not_own_the_command(self):
        self.assertIsNone(resolve("what is the weather in Tokyo", LANE_FAST))
        self.assertIsNotNone(resolve("what is the weather in Tokyo", LANE_API))


if __name__ == "__main__":
    unittest.main()
