"""Align image dimensions to model-safe multiples with optional visual cropping."""

import json
import torch
import torch.nn.functional as functional

import comfy.utils
import nodes
from comfy_execution.graph import ExecutionBlocker


INTERPOLATIONS = [
    "nearest", "bilinear", "bicubic", "area", "nearest-exact", "lanczos",
    "最近邻", "双线性", "双三次", "区域", "精确最近邻", "兰索斯",
    "Nearest", "Bilinear", "Bicubic", "Area", "Nearest exact", "Lanczos",
]
METHODS = [
    "stretch", "crop", "pad", "拉伸", "裁切", "填充",
    # Legacy values retained for saved-workflow validation.
    "fill / crop", "keep proportion", "补边", "保持比例",
    "Crop", "Pad", "Stretch", "Fill / crop", "Keep proportion",
]
CONDITIONS = [
    # Legacy compatibility input. The alignment node now always evaluates size.
    "always", "downscale if bigger", "upscale if smaller", "if bigger area", "if smaller area",
    "总是", "仅在原图较大时缩小", "仅在原图较小时放大", "仅在原图面积较大时", "仅在原图面积较小时",
    "Always", "Downscale if bigger", "Upscale if smaller", "If bigger area", "If smaller area",
]
ASPECT_RATIOS = {
    "original": None,
    "原图比例": None,
    "Original": None,
    "1:1": (1, 1),
    "1:2": (1, 2),
    "2:3": (2, 3),
    "3:4": (3, 4),
    "4:5": (4, 5),
    "9:16": (9, 16),
    "9:21": (9, 21),
}

INTERPOLATION_ALIASES = {
    "最近邻": "nearest", "Nearest": "nearest",
    "双线性": "bilinear", "Bilinear": "bilinear",
    "双三次": "bicubic", "Bicubic": "bicubic",
    "区域": "area", "Area": "area",
    "精确最近邻": "nearest-exact", "Nearest exact": "nearest-exact",
    "兰索斯": "lanczos", "Lanczos": "lanczos",
}
METHOD_ALIASES = {
    "裁切": "crop", "Crop": "crop",
    "填充": "pad", "补边": "pad", "Pad": "pad",
    "拉伸": "stretch", "Stretch": "stretch",
    "fill / crop": "crop", "Fill / crop": "crop",
    "keep proportion": "crop", "Keep proportion": "crop", "保持比例": "crop",
}


def _normalize_multiple(value):
    value = int(value)
    return min((8, 16, 32, 64), key=lambda candidate: abs(candidate - value))


def _nearest_multiple(value, multiple):
    return max(multiple, int(round(int(value) / multiple)) * multiple)


def _resize(image, width, height, interpolation):
    channels_first = image.movedim(-1, 1)
    if interpolation == "lanczos":
        resized = comfy.utils.lanczos(channels_first, width, height)
    else:
        resized = functional.interpolate(channels_first, size=(height, width), mode=interpolation)
    return resized.movedim(1, -1)


def _crop_state(crop_canvas):
    try:
        data = json.loads(crop_canvas) if isinstance(crop_canvas, str) else (crop_canvas or {})
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    if isinstance(data.get("crop"), dict):
        data = data["crop"]
    x = min(1.0, max(0.0, float(data.get("x", 0.5))))
    y = min(1.0, max(0.0, float(data.get("y", 0.5))))
    scale = min(1.0, max(0.05, float(data.get("scale", 1.0))))
    return x, y, scale


def _ratio(aspect_ratio, invert_ratio, source_width, source_height):
    ratio = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["original"])
    if ratio is None:
        ratio = (source_width, source_height)
    if invert_ratio:
        ratio = (ratio[1], ratio[0])
    return ratio


def _target_size(source_width, source_height, aspect_ratio, invert_ratio, short_side, long_side, multiple):
    ratio_width, ratio_height = _ratio(
        aspect_ratio, invert_ratio, source_width, source_height
    )
    short_side = _nearest_multiple(short_side or 512, multiple)
    long_side = _nearest_multiple(long_side or short_side, multiple)
    if ratio_width == ratio_height:
        width = height = short_side
    elif ratio_width < ratio_height:
        width, height = short_side, long_side
    else:
        width, height = long_side, short_side
    return width, height


def _crop_geometry(source_width, source_height, target_width, target_height, state):
    center_x, center_y, scale = state
    target_ratio = target_width / target_height
    source_ratio = source_width / source_height
    if source_ratio > target_ratio:
        maximum_height = source_height
        maximum_width = maximum_height * target_ratio
    else:
        maximum_width = source_width
        maximum_height = maximum_width / target_ratio
    width = max(1, round(maximum_width * scale))
    height = max(1, round(maximum_height * scale))

    left = round(center_x * source_width - width / 2)
    top = round(center_y * source_height - height / 2)
    left = min(max(0, left), source_width - width)
    top = min(max(0, top), source_height - height)
    return left, top, width, height


def _fill_state(canvas_value):
    try:
        data = json.loads(canvas_value) if isinstance(canvas_value, str) else (canvas_value or {})
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    if isinstance(data.get("fill"), dict):
        data = data["fill"]
    x = min(1.0, max(0.0, float(data.get("x", 0.5))))
    y = min(1.0, max(0.0, float(data.get("y", 0.5))))
    scale = min(4.0, max(0.05, float(data.get("scale", 1.0))))
    return x, y, scale


def _color(value, channels, device, dtype):
    text = str(value or "#000000").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    try:
        rgb = [int(text[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    except (TypeError, ValueError):
        rgb = [0.0, 0.0, 0.0]
    values = (rgb + [1.0] * max(0, channels - 3))[:channels]
    return torch.tensor(values, device=device, dtype=dtype)


def _composite_to_canvas(image, width, height, fill_color, canvas_value, interpolation):
    source_height, source_width = image.shape[1:3]
    position_x, position_y, scale = _fill_state(canvas_value)
    contain = min(width / source_width, height / source_height)
    resized_width = max(1, round(source_width * contain * scale))
    resized_height = max(1, round(source_height * contain * scale))
    resized = _resize(image, resized_width, resized_height, interpolation)

    channels = image.shape[3]
    output = torch.empty(
        (image.shape[0], height, width, channels), device=image.device, dtype=image.dtype
    )
    output[:] = _color(fill_color, channels, image.device, image.dtype)
    center_x = round(position_x * width)
    center_y = round(position_y * height)
    left = center_x - resized_width // 2
    top = center_y - resized_height // 2
    source_left = max(0, -left)
    source_top = max(0, -top)
    destination_left = max(0, left)
    destination_top = max(0, top)
    copy_width = min(resized_width - source_left, width - destination_left)
    copy_height = min(resized_height - source_top, height - destination_top)
    if copy_width > 0 and copy_height > 0:
        output[
            :, destination_top:destination_top + copy_height,
            destination_left:destination_left + copy_width, :
        ] = resized[
            :, source_top:source_top + copy_height,
            source_left:source_left + copy_width, :
        ]
    return output


class NO8DImageSize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "auto_output": (
                    "BOOLEAN",
                    {"default": True, "label_on": "on", "label_off": "off"},
                ),
                "aspect_ratio": (list(ASPECT_RATIOS.keys()), {"default": "1:1"}),
                "short_side": ("INT", {"default": 512, "min": 8, "max": nodes.MAX_RESOLUTION, "step": 8}),
                "long_side": ("INT", {"default": 512, "min": 8, "max": nodes.MAX_RESOLUTION, "step": 8}),
                "multiple_of": (["8", "16", "32", "64"], {"default": "8"}),
                "interpolation": (INTERPOLATIONS, {"default": "lanczos"}),
                "method": (METHODS, {"default": "stretch"}),
                "invert_ratio": ("BOOLEAN", {"default": False}),
                "crop_canvas": ("NO8D_IMAGE_SIZE_CANVAS", {"default": '{"crop":{"x":0.5,"y":0.5,"scale":1},"fill":{"x":0.5,"y":0.5,"scale":1}}'}),
                "fill_color": ("STRING", {"default": "#000000"}),
                # Legacy compatibility widgets are hidden by the frontend.
                "width": ("INT", {"default": 0, "min": 0, "max": nodes.MAX_RESOLUTION, "step": 8}),
                "height": ("INT", {"default": 0, "min": 0, "max": nodes.MAX_RESOLUTION, "step": 8}),
                "condition": (CONDITIONS, {"default": "always"}),
                "force_size": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "resize"
    OUTPUT_NODE = True
    CATEGORY = "NO8D-control"
    DESCRIPTION = "Resize to a ratio-based target using stretch, an interactive crop, or an interactive fill canvas."

    def resize(
        self,
        image,
        auto_output=True,
        aspect_ratio="1:1",
        invert_ratio=False,
        short_side=512,
        long_side=512,
        multiple_of=8,
        interpolation="lanczos",
        method="stretch",
        crop_canvas='{"crop":{"x":0.5,"y":0.5,"scale":1},"fill":{"x":0.5,"y":0.5,"scale":1}}',
        fill_color="#000000",
        width=0,
        height=0,
        condition="always",
        force_size=False,
    ):
        del condition, force_size, width, height
        source_height, source_width = image.shape[1:3]
        multiple = _normalize_multiple(multiple_of)
        interpolation = INTERPOLATION_ALIASES.get(interpolation, interpolation.lower())
        method = METHOD_ALIASES.get(method, method.lower())
        target_width, target_height = _target_size(
            source_width, source_height, aspect_ratio,
            invert_ratio if method != "stretch" else False,
            short_side, long_side, multiple,
        )

        if method == "crop":
            crop_state = _crop_state(crop_canvas)
            left, top, crop_width, crop_height = _crop_geometry(
                source_width, source_height, target_width, target_height, crop_state
            )
            cropped = image[:, top:top + crop_height, left:left + crop_width, :]
            output = _resize(cropped, target_width, target_height, interpolation)
        elif method == "pad":
            output = _composite_to_canvas(
                image, target_width, target_height, fill_color, crop_canvas, interpolation
            )
        else:
            output = _resize(image, target_width, target_height, interpolation)

        output = torch.clamp(output, 0, 1)
        preview = nodes.PreviewImage().save_images(image, filename_prefix="NO8DImageSizeSource")
        if auto_output:
            result = (output, output.shape[2], output.shape[1])
        else:
            result = tuple(ExecutionBlocker(None) for _ in range(3))
        return {
            "ui": {"source_images": preview["ui"]["images"]},
            "result": result,
        }


NODE_CLASS_MAPPINGS = {"NO8DImageSize": NO8DImageSize}
NODE_DISPLAY_NAME_MAPPINGS = {"NO8DImageSize": "NO8D-image-size"}
