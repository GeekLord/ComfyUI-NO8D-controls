from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = "no8d_dynamic_prompt_test"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package
_load(f"{PACKAGE}.prompt_config", ROOT / "prompt_config.py")
_load(f"{PACKAGE}.prompt_provider", ROOT / "prompt_provider.py")
_load(f"{PACKAGE}.prompt_plus", ROOT / "prompt_plus.py")
dynamic = _load(f"{PACKAGE}.dynamic_prompt", ROOT / "dynamic_prompt.py")


def facts():
    return {
        "visual_style": "live-action street photography",
        "primary_subject": "a woman seated at a green table",
        "appearance_and_clothing": "dark sunglasses and an oversized charcoal blazer",
        "pose_expression_and_gaze": "leaning forward while sipping through a red straw",
        "props_and_interactions": "holding a red soda can and a hot dog",
        "environment_and_spatial_relationships": "outside an orange-fronted hot-dog shop",
        "composition_camera_and_lens": "a close wide-angle frontal view",
        "lighting_palette_and_atmosphere": "warm orange and green daylight palette",
        "visible_text": 'the storefront reads "DOG"',
        "uncertainties": "",
    }


def plan(opening=""):
    return {
        "opening_description": opening,
        "shots": [
            {
                "start_seconds": 0,
                "visual_progression": "she lowers the soda can and raises the hot dog toward her mouth",
                "camera_motion": "the camera holds a static shot",
                "synchronized_sound": "the straw releases with a soft click",
            }
        ],
        "ending_description": "she pauses with the hot dog near her mouth",
        "overall_soundscape": "soft street traffic and restaurant ambience",
        "non_diegetic_music": "N/A",
    }


class DynamicPromptTests(unittest.TestCase):
    def setUp(self):
        dynamic.NO8DDynamicPrompt._cache.clear()

    def test_static_prompt_no_longer_exposes_h3(self):
        from no8d_dynamic_prompt_test import prompt_plus

        options = prompt_plus.NO8DBatchPromptPlus.INPUT_TYPES()["required"]["prompt_rules"][0]
        self.assertEqual(options, ("Krea2", "Ideogram4"))
        self.assertEqual(
            prompt_plus.NODE_DISPLAY_NAME_MAPPINGS["NO8DBatchPromptPlus"],
            "NO8D-Static-Prompt",
        )

    def test_dynamic_node_has_official_duration_range(self):
        inputs = dynamic.NO8DDynamicPrompt.INPUT_TYPES()["required"]
        self.assertEqual(inputs["duration"][1]["min"], 4)
        self.assertEqual(inputs["duration"][1]["max"], 15)
        self.assertNotIn("output_language", inputs)
        self.assertIn("NO8DDynamicPrompt", dynamic.NODE_CLASS_MAPPINGS)

    def test_i2va_compiler_preserves_visual_facts_verbatim(self):
        result = dynamic._compile_h3_prompt(plan(), facts(), 8, "I2VA")
        self.assertTrue(result.startswith("For the target video, at 0.00 seconds"))
        for field, value in facts().items():
            if field != "uncertainties":
                self.assertIn(value, result)
        self.assertIn("integrated_multimodal_description: [Shot 1]", result)
        self.assertIn("overall_soundscape:", result)
        self.assertIn("non_diegetic_music:", result)
        self.assertEqual(dynamic._prompt_errors(result, 8, "I2VA", 1), [])

    def test_t2va_has_no_picture_reference(self):
        result = dynamic._compile_h3_prompt(
            plan("A woman sits outside an orange-fronted hot-dog shop"), {}, 8, "T2VA"
        )
        self.assertNotIn("<Picture 1>", result)
        self.assertTrue(result.startswith("integrated_multimodal_description:"))
        self.assertEqual(dynamic._prompt_errors(result, 8, "T2VA", 1), [])

    def test_validator_rejects_bad_timestamps(self):
        value = plan("opening")
        value["shots"].append(
            {
                "start_seconds": 8,
                "visual_progression": "cut",
                "camera_motion": "",
                "synchronized_sound": "",
            }
        )
        errors = dynamic._plan_errors(value, 8, 0, "T2VA")
        self.assertTrue(any("before the target duration" in error for error in errors))

    def test_official_soundscape_rules_reject_unrequested_na(self):
        value = plan("opening")
        value["overall_soundscape"] = "N/A"
        result = dynamic._compile_h3_prompt(value, {}, 8, "T2VA")
        self.assertTrue(any("complete silence" in error for error in dynamic._prompt_errors(result, 8, "T2VA", 1)))
        self.assertEqual(dynamic._prompt_errors(result, 8, "T2VA", 1, "complete silence throughout"), [])

    def test_music_rejects_abstract_mood_language(self):
        value = plan("opening")
        value["non_diegetic_music"] = "A melancholic piano melody matching the mood."
        errors = dynamic._plan_errors(value, 8, 1, "T2VA")
        self.assertTrue(any("instrumentation" in error for error in errors))

    def test_compiler_does_not_duplicate_final_time_phrase(self):
        value = plan("opening")
        value["shots"][0]["visual_progression"] += ". By the 8-second mark, she reaches the curb"
        value["ending_description"] = "At the 8-second mark, she stops at the curb"
        result = dynamic._compile_h3_prompt(value, {}, 8, "T2VA")
        self.assertIn("By the 8-second mark, she stops at the curb", result)
        self.assertEqual(result.count("By the 8-second mark"), 1)

    def test_planner_requires_official_dialogue_and_english_rewrite_rules(self):
        messages = dynamic._planner_messages("她说：你好", {}, 8, 1, "自行判断", "T2VA")
        system = messages[0]["content"]
        self.assertIn("<d>[Language] ...</d>", system)
        self.assertIn("rewrite sections in fluent modern English", system)
        self.assertIn("Preserve user-supplied dialogue", system)

    def test_json_transport_repairs_incomplete_response_once(self):
        calls = ["{\"opening_description\":", '{"opening_description":"ok"}']
        with mock.patch.object(dynamic._shared, "_chat_completion", side_effect=calls) as completion:
            value, raw, _ = dynamic._call_json(
                base_url="https://example.com/v1",
                api_key="key",
                model="model",
                service_type="openai_compatible",
                messages=[{"role": "user", "content": "return json"}],
                temperature=0.7,
                max_tokens=100,
                seed=0,
                name="test",
                schema={"type": "object"},
                label="test response",
            )
        self.assertEqual(value, {"opening_description": "ok"})
        self.assertEqual(raw, calls[1])
        self.assertEqual(completion.call_count, 2)

    def test_image_mode_uses_vision_facts_then_text_planner(self):
        service = {
            "id": "test",
            "base_url": "https://example.com/v1",
            "api_key": "secret",
            "type": "openai_compatible",
            "vision_model": "vision-model",
        }
        model_cfg = {"name": "text-model", "temperature": 0.7}
        calls = []

        def fake_call_json(**kwargs):
            calls.append(kwargs)
            if kwargs["name"] == "no8d_h3_visual_facts":
                return facts(), "facts", None
            return plan(), "plan", None

        with mock.patch.object(dynamic, "_call_json", side_effect=fake_call_json):
            result = dynamic.NO8DDynamicPrompt()._generate_item(
                image_data_url="data:image/jpeg;base64,AA==",
                image_hash="image-hash",
                user_intent="she takes a bite",
                duration=8,
                shot_count=0,
                style_preset="自行判断",
                seed=9,
                service=service,
                model_cfg=model_cfg,
            )

        self.assertEqual([call["model"] for call in calls], ["vision-model", "text-model"])
        self.assertIn("dark sunglasses and an oversized charcoal blazer", result)


if __name__ == "__main__":
    unittest.main()
