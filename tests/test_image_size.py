from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest

import torch
import torch.nn.functional as functional


class _ExecutionBlocker:
    def __init__(self, message):
        self.message = message


class _PreviewImage:
    def save_images(self, _images, filename_prefix=""):
        return {"ui": {"images": [{"filename": f"{filename_prefix}.png", "type": "temp"}]}}


def _load_module():
    comfy = types.ModuleType("comfy")
    comfy_utils = types.ModuleType("comfy.utils")
    comfy_utils.lanczos = lambda images, width, height: functional.interpolate(
        images, size=(height, width), mode="bicubic"
    )
    comfy.utils = comfy_utils
    nodes = types.ModuleType("nodes")
    nodes.MAX_RESOLUTION = 16384
    nodes.PreviewImage = _PreviewImage
    execution = types.ModuleType("comfy_execution")
    execution_graph = types.ModuleType("comfy_execution.graph")
    execution_graph.ExecutionBlocker = _ExecutionBlocker
    names = ("comfy", "comfy.utils", "nodes", "comfy_execution", "comfy_execution.graph")
    previous = {name: sys.modules.get(name) for name in names}
    sys.modules.update({
        "comfy": comfy,
        "comfy.utils": comfy_utils,
        "nodes": nodes,
        "comfy_execution": execution,
        "comfy_execution.graph": execution_graph,
    })
    try:
        path = pathlib.Path(__file__).resolve().parents[1] / "image_size.py"
        spec = importlib.util.spec_from_file_location("no8d_image_size_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


IMAGE_SIZE = _load_module()


def _image(width, height):
    return torch.rand((1, height, width, 3), dtype=torch.float32)


class ImageSizeTests(unittest.TestCase):
    def setUp(self):
        self.node = IMAGE_SIZE.NO8DImageSize()

    def run_node(self, image, **kwargs):
        response = self.node.resize(image, **kwargs)
        self.assertIn("source_images", response["ui"])
        return response["result"]

    def test_contract_defaults_to_shared_target_canvas_and_stretch(self):
        inputs = self.node.INPUT_TYPES()["required"]
        self.assertEqual(
            list(inputs)[1:9],
            ["auto_output", "aspect_ratio", "short_side", "long_side", "multiple_of", "interpolation", "method", "invert_ratio"],
        )
        self.assertTrue(inputs["auto_output"][1]["default"])
        self.assertEqual(inputs["aspect_ratio"][1]["default"], "1:1")
        self.assertEqual(inputs["short_side"][1]["default"], 512)
        self.assertEqual(inputs["long_side"][1]["default"], 512)
        self.assertEqual(inputs["multiple_of"][0], ["8", "16", "32", "64"])
        self.assertEqual(inputs["multiple_of"][1]["default"], "8")
        self.assertEqual(inputs["method"][0][:3], ["stretch", "crop", "pad"])
        self.assertEqual(inputs["method"][1]["default"], "stretch")
        self.assertEqual(inputs["fill_color"], ("STRING", {"default": "#000000"}))
        self.assertEqual(IMAGE_SIZE.NODE_DISPLAY_NAME_MAPPINGS["NO8DImageSize"], "NO8D-image-size")

    def test_stretch_outputs_shared_target_size(self):
        output, width, height = self.run_node(
            _image(100, 50),
            method="stretch",
            aspect_ratio="2:3",
            short_side=64,
            long_side=96,
            interpolation="bilinear",
        )
        self.assertEqual((width, height), (64, 96))
        self.assertEqual(output.shape, (1, 96, 64, 3))

    def test_invert_ratio_swaps_target_orientation(self):
        output, width, height = self.run_node(
            _image(100, 50),
            method="裁切",
            aspect_ratio="2:3",
            invert_ratio=True,
            short_side=64,
            long_side=96,
        )
        self.assertEqual((width, height), (96, 64))
        self.assertEqual(output.shape, (1, 64, 96, 3))

    def test_stretch_ignores_saved_invert_ratio(self):
        output, width, height = self.run_node(
            _image(100, 50),
            method="stretch",
            aspect_ratio="2:3",
            invert_ratio=True,
            short_side=64,
            long_side=96,
        )
        self.assertEqual((width, height), (64, 96))
        self.assertEqual(output.shape, (1, 96, 64, 3))

    def test_target_sides_align_to_selected_multiple(self):
        _, width, height = self.run_node(
            _image(100, 50),
            aspect_ratio="2:3",
            short_side=65,
            long_side=95,
            multiple_of=16,
        )
        self.assertEqual((width, height), (64, 96))

    def test_auto_output_off_blocks_all_downstream_outputs_but_keeps_preview(self):
        response = self.node.resize(_image(100, 50), auto_output=False)
        self.assertIn("source_images", response["ui"])
        self.assertTrue(all(isinstance(value, _ExecutionBlocker) for value in response["result"]))

    def test_32_and_64_are_supported_dimension_multiples(self):
        for multiple, expected in ((32, (64, 96)), (64, (64, 128))):
            with self.subTest(multiple=multiple):
                _, width, height = self.run_node(
                    _image(100, 50),
                    aspect_ratio="2:3",
                    short_side=65,
                    long_side=110,
                    multiple_of=multiple,
                )
                self.assertEqual((width, height), expected)

    def test_crop_canvas_position_controls_selected_region(self):
        image = torch.zeros((1, 64, 100, 3), dtype=torch.float32)
        image[:, :, :50, 0] = 1
        image[:, :, 50:, 2] = 1
        left, width, height = self.run_node(
            image,
            method="crop",
            aspect_ratio="1:1",
            short_side=32,
            long_side=32,
            interpolation="nearest",
            crop_canvas='{"crop":{"x":0,"y":0.5,"scale":0.5}}',
        )
        right, _, _ = self.run_node(
            image,
            method="crop",
            aspect_ratio="1:1",
            short_side=32,
            long_side=32,
            interpolation="nearest",
            crop_canvas='{"crop":{"x":1,"y":0.5,"scale":0.5}}',
        )
        self.assertEqual((width, height), (32, 32))
        self.assertGreater(left[..., 0].sum(), left[..., 2].sum())
        self.assertGreater(right[..., 2].sum(), right[..., 0].sum())

    def test_crop_output_matches_exact_source_region_when_size_matches(self):
        image = torch.arange(1 * 160 * 160 * 3, dtype=torch.float32).reshape(1, 160, 160, 3)
        image /= image.max()
        output, width, height = self.run_node(
            image,
            method="crop",
            aspect_ratio="1:1",
            short_side=80,
            long_side=80,
            interpolation="nearest",
            crop_canvas='{"crop":{"x":0.5,"y":0.5,"scale":0.5}}',
        )
        self.assertEqual((width, height), (80, 80))
        self.assertTrue(torch.equal(output, image[:, 40:120, 40:120, :]))

    def test_fill_defaults_to_contain_and_center(self):
        output, width, height = self.run_node(
            torch.ones((1, 50, 100, 3)),
            method="pad",
            aspect_ratio="1:1",
            short_side=80,
            long_side=80,
            interpolation="nearest",
        )
        self.assertEqual((width, height), (80, 80))
        self.assertTrue(torch.all(output[:, :20] == 0))
        self.assertTrue(torch.all(output[:, 20:60] == 1))

    def test_fill_canvas_controls_image_scale_position_and_color(self):
        image = torch.ones((1, 20, 20, 3))
        output, width, height = self.run_node(
            image,
            method="填充",
            aspect_ratio="1:1",
            short_side=80,
            long_side=80,
            interpolation="nearest",
            fill_color="#ff0000",
            crop_canvas='{"fill":{"x":0.25,"y":0.25,"scale":0.5}}',
        )
        self.assertEqual((width, height), (80, 80))
        self.assertTrue(torch.all(output[:, 0:40, 0:40] == 1))
        self.assertTrue(torch.equal(output[0, 79, 79], torch.tensor([1.0, 0.0, 0.0])))

    def test_frontend_has_mode_canvases_linked_dimensions_and_migration(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        canvas = (root / "web" / "image_size.js").read_text(encoding="utf-8")
        titles = (root / "web" / "node_titles_i18n.js").read_text(encoding="utf-8")
        translations = (root / "web" / "no8d_i18n.js").read_text(encoding="utf-8")
        self.assertIn("syncDimensions", canvas)
        self.assertIn("invalidateVueWidgets", canvas)
        self.assertIn("window.LiteGraph?.vueNodesMode", canvas)
        self.assertIn("setVueWidgetExcluded(fillColor, true)", canvas)
        self.assertIn('input.type = "color"', canvas)
        self.assertIn("openColorPicker", canvas)
        self.assertIn("sendProcessedImage", canvas)
        self.assertIn("imageSizeNode.inputs.auto_output = true", canvas)
        self.assertIn('imageSizeAutoOutput: "自动输出"', translations)
        self.assertIn('imageSizeSend: "发送"', translations)
        self.assertIn('["width", "height", "long_side", "condition", "force_size"]', canvas)
        self.assertIn("cropGeometry", canvas)
        self.assertIn("fillGeometry", canvas)
        self.assertIn("migrateWidgetValues", canvas)
        self.assertIn('short_side: "imageSizeShortSide"', titles)
        self.assertIn('long_side: "imageSizeLongSide"', titles)
        self.assertIn('imageSizeMethod: "对齐方式"', translations)


if __name__ == "__main__":
    unittest.main()
