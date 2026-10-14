from __future__ import annotations

import hashlib
import json
import os
import re
import threading

from . import prompt_plus as _shared
from .prompt_config import prompt_config_manager


_PIPELINE_VERSION = "minimax-h3-compiler-v1"
_H3_CHAR_LIMIT = 7000
_DURATION_MIN = 4
_DURATION_MAX = 15
_STYLE_INPUTS = _shared._STYLE_PRESET_INPUTS

_FACT_FIELDS = (
    "visual_style",
    "primary_subject",
    "appearance_and_clothing",
    "pose_expression_and_gaze",
    "props_and_interactions",
    "environment_and_spatial_relationships",
    "composition_camera_and_lens",
    "lighting_palette_and_atmosphere",
    "visible_text",
    "uncertainties",
)
_PLAN_FIELDS = (
    "opening_description",
    "shots",
    "ending_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_SHOT_FIELDS = ("start_seconds", "visual_progression", "camera_motion", "synchronized_sound")


def _normalize_duration(value):
    duration = _shared._safe_int(value, 8)
    if not _DURATION_MIN <= duration <= _DURATION_MAX:
        raise ValueError(f"NO8D-Dynamic-Prompt: duration must be an integer from {_DURATION_MIN} to {_DURATION_MAX} seconds.")
    return duration


def _parse_object(text, label):
    cleaned = _shared._strip_code_fence(_shared._strip_thinking(str(text or ""))).strip()
    try:
        value = _shared._parse_analysis_envelope(cleaned)
    except ValueError as exc:
        raise ValueError(f"{label} is not a complete JSON object: {exc}") from exc
    return value


def _facts_schema():
    return {
        "type": "object",
        "properties": {field: {"type": "string"} for field in _FACT_FIELDS},
        "required": list(_FACT_FIELDS),
        "additionalProperties": False,
    }


def _plan_schema():
    shot = {
        "type": "object",
        "properties": {
            "start_seconds": {"type": "number"},
            "visual_progression": {"type": "string"},
            "camera_motion": {"type": "string"},
            "synchronized_sound": {"type": "string"},
        },
        "required": list(_SHOT_FIELDS),
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "opening_description": {"type": "string"},
            "shots": {"type": "array", "items": shot},
            "ending_description": {"type": "string"},
            "overall_soundscape": {"type": "string"},
            "non_diegetic_music": {"type": "string"},
        },
        "required": list(_PLAN_FIELDS),
        "additionalProperties": False,
    }


def _response_format(base_url, service_type, name, schema):
    if not (
        _shared._supports_native_json_schema(base_url)
        or _shared._uses_ollama_native(base_url, service_type)
    ):
        return None
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}


def _language_rule():
    return (
        "Write rewrite sections in fluent modern English. Preserve user-supplied dialogue, lyrics, and visible scene "
        "text verbatim in their original language; do not translate or rewrite them."
    )


def _style_rule(style_preset):
    preset = _shared._normalize_style_preset(style_preset)
    if preset == "自行判断":
        return "Derive the target visual style from the reference image when present, otherwise from the user's intent."
    return _shared._STYLE_PRESET_RULES.get(preset, "")


def _facts_messages(user_intent, image_data_url, style_preset):
    system = f"""You are the factual visual-analysis stage for a MiniMax-H3 image-to-video prompt.
Analyze only the supplied opening-frame image. Do not write the final H3 prompt and do not invent hidden details.
Record exact visible identity traits, clothing, pose, expression, gaze, props, environment, composition, camera relation,
lens evidence, lighting, palette, atmosphere, spatial relationships, and visible text. Mark uncertain evidence in
uncertainties instead of guessing. The user's intent is context only and must not override visible evidence.
{_style_rule(style_preset)}
{_language_rule()}
Return exactly one JSON object matching the requested schema, without markdown."""
    content = [{"type": "text", "text": f"USER INTENT\n{user_intent or '(none supplied)'}"}]
    content.append({"type": "image_url", "image_url": {"url": image_data_url}})
    return [{"role": "system", "content": system}, {"role": "user", "content": content}]


def _facts_errors(value):
    if not isinstance(value, dict):
        return ["The visual facts response is not an object."]
    errors = [f"Missing visual fact `{field}`." for field in _FACT_FIELDS if field not in value]
    required_content = _FACT_FIELDS[:-2]
    errors.extend(
        f"Visual fact `{field}` must contain grounded image evidence."
        for field in required_content
        if not str(value.get(field) or "").strip()
    )
    return errors


def _planner_messages(user_intent, facts, duration, shot_count, style_preset, mode):
    count_rule = (
        f"Return exactly {shot_count} shots."
        if shot_count > 0
        else "Choose the minimum useful number of shots; prefer one continuous shot unless a cut adds essential information."
    )
    anchor_rule = (
        "The supplied VISUAL FACTS are the exact first frame at 0.00 seconds. Do not restate or redesign them in "
        "opening_description; leave opening_description empty. Plan only the visible development after that frame."
        if mode == "I2VA"
        else "This is text-to-video. opening_description must establish a complete opening visual from the user's intent."
    )
    system = f"""You are the temporal-planning stage for an official MiniMax-H3 audiovisual prompt.
Return a compact JSON plan, not the final prompt. The target duration is exactly {duration} seconds.
{anchor_rule}
{count_rule}
Shot 1 must start at 0. Later shot start_seconds values must be strictly increasing, greater than 0, and less than
{duration}. Every action must be physically continuous from the preceding state. Preserve visible identity, clothing,
pose anchors, props, environment, composition, lighting, palette, and spatial relationships unless the user explicitly
requests a visible change. Never replace the subject, outfit, pose, or setting with a conventional alternative.
Camera motion must use natural prose and distinguish pan/tilt/zoom from physical truck/pedestal/push/pull movement.
Write camera motion as natural English action using the official motion names Zoom In/Out, Push In/Pull Out, Pan
Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly/Strongly,
POV, or Roll Clockwise/Counterclockwise. Add "with small/large amplitude" and "at slow/fast speed" only when meaningful;
do not substitute vague synonyms such as moves forward and do not stack labels.
For every user-supplied spoken or sung line, assign a stable speaker ID such as (S1), preserve the wording and punctuation
verbatim, and wrap only the language tag and content in <d>[Language] ...</d>. Never invent dialogue or lyrics.
Preserve visible scene text verbatim in English double quotation marks. Put synchronized speech, impacts, diegetic music,
or shot-specific sound in synchronized_sound. Put 1-4 English sentences of ambience, physical action sounds, and
non-verbal human sounds in overall_soundscape; use N/A only when the user explicitly requests complete silence. Put 1-3
English sentences of audience-only score in non_diegetic_music, or N/A when there is no non-diegetic music. End the
action at exactly the {duration}-second mark.
{_style_rule(style_preset)}
{_language_rule()}
Return exactly one JSON object matching the requested schema, without markdown."""
    payload = {
        "mode": mode,
        "duration_seconds": duration,
        "user_intent": user_intent,
        "locked_visual_facts": facts or {},
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def _plan_errors(value, duration, shot_count, mode):
    if not isinstance(value, dict):
        return ["The temporal plan is not an object."]
    errors = [f"Missing plan field `{field}`." for field in _PLAN_FIELDS if field not in value]
    shots = value.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("The temporal plan must contain at least one shot.")
        return errors
    if shot_count > 0 and len(shots) != shot_count:
        errors.append(f"Expected exactly {shot_count} shots, found {len(shots)}.")
    if len(shots) > 6:
        errors.append("The temporal plan must not contain more than 6 shots.")
    starts = []
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            errors.append(f"Shot {index} is not an object.")
            continue
        errors.extend(f"Shot {index} is missing `{field}`." for field in _SHOT_FIELDS if field not in shot)
        if not str(shot.get("visual_progression") or "").strip():
            errors.append(f"Shot {index} must describe visible temporal progression.")
        try:
            starts.append(float(shot.get("start_seconds")))
        except (TypeError, ValueError):
            errors.append(f"Shot {index} has an invalid start_seconds value.")
    if len(starts) == len(shots):
        if abs(starts[0]) > 0.0005:
            errors.append("Shot 1 must start at 0 seconds.")
        if any(value <= 0 or value >= duration for value in starts[1:]):
            errors.append("Every later shot must start after 0 and before the target duration.")
        if starts != sorted(starts) or len(starts) != len(set(starts)):
            errors.append("Shot start times must be strictly increasing.")
    if mode == "I2VA" and str(value.get("opening_description") or "").strip():
        errors.append("I2VA opening_description must be empty because the image facts are the exact first frame.")
    if mode == "T2VA" and not str(value.get("opening_description") or "").strip():
        errors.append("T2VA opening_description must establish the complete opening visual.")
    music = str(value.get("non_diegetic_music") or "").strip()
    abstract_music = re.search(
        r"\b(?:melancholic|reflective|emotional|dramatic|tense|uplifting|ominous|hopeful|sad|happy|joyful|"
        r"romantic|mysterious|eerie|suspenseful)\b|\b(?:matching|enhancing|creating|supporting)\s+(?:the\s+)?"
        r"(?:mood|emotion|atmosphere|feeling)",
        music,
        re.IGNORECASE,
    )
    if music != "N/A" and abstract_music:
        errors.append(
            "non_diegetic_music must describe only instrumentation, tempo, rhythm, and dynamic change; remove abstract "
            "mood words and emotional-purpose explanations."
        )
    return errors


def _opening_from_facts(facts):
    ordered = (
        "visual_style",
        "composition_camera_and_lens",
        "primary_subject",
        "appearance_and_clothing",
        "pose_expression_and_gaze",
        "props_and_interactions",
        "environment_and_spatial_relationships",
        "lighting_palette_and_atmosphere",
        "visible_text",
    )
    values = [str(facts.get(field) or "").strip() for field in ordered]
    return "; ".join(dict.fromkeys(value for value in values if value))


def _format_timestamp(seconds):
    value = max(0.0, float(seconds))
    minutes = int(value // 60)
    remainder = value - minutes * 60
    return f"{minutes:02d}:{remainder:06.3f}"


def _without_competing_final_state(text, duration):
    value = str(text or "").strip()
    if not value:
        return ""
    duration_token = re.escape(str(duration))
    pattern = (
        rf"(?:^|(?<=[.!?])\s+)(?:By|At)\s+(?:the\s+)?{duration_token}(?:\.0+)?"
        rf"(?:-second mark|\s+seconds?)\s*,?\s*[^.!?]*(?:[.!?]|$)"
    )
    return re.sub(pattern, "", value, flags=re.IGNORECASE).strip()


def _lowercase_leading_article(text):
    value = str(text or "").strip()
    match = re.match(r"^(The|A|An|She|He|They|It)\b", value)
    return match.group(1).lower() + value[match.end(1):] if match else value


def _compile_h3_prompt(plan, facts, duration, mode):
    pieces = []
    if mode == "I2VA":
        pieces.append(
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
    shots = plan["shots"]
    body = []
    opening = _opening_from_facts(facts) if mode == "I2VA" else str(plan.get("opening_description") or "").strip()
    for index, shot in enumerate(shots, start=1):
        if index == 1:
            prefix = "[Shot 1]"
        else:
            prefix = f"[Shot {index}] At {_format_timestamp(shot['start_seconds'])},"
            prefix += " the camera cuts to"
        content = []
        if index == 1 and opening:
            content.append(opening)
        progression = str(shot.get("visual_progression") or "").strip()
        ending = str(plan.get("ending_description") or "").strip() if index == len(shots) else ""
        if ending:
            progression = _without_competing_final_state(progression, duration)
        content.extend(
            value
            for value in (
                progression,
                str(shot.get("camera_motion") or "").strip(),
                str(shot.get("synchronized_sound") or "").strip(),
            )
            if value
        )
        if ending:
            ending = re.sub(
                r"^(?:by|at)\s+(?:the\s+)?(?:\d+(?:\.\d+)?-second mark|\d+(?:\.\d+)?\s+seconds?)\s*,?\s*",
                "",
                ending,
                flags=re.IGNORECASE,
            )
            lead = f"By the {duration}-second mark"
            content.append(f"{lead}, {_lowercase_leading_article(ending)}")
        joined = ". ".join(value.strip(" .") for value in content if value)
        body.append(f"{prefix} {joined}".strip())
    pieces.append("integrated_multimodal_description: " + " ".join(body).strip())
    soundscape = str(plan.get("overall_soundscape") or "").strip() or "N/A"
    music = str(plan.get("non_diegetic_music") or "").strip() or "N/A"
    pieces.append("overall_soundscape: " + soundscape)
    pieces.append("non_diegetic_music: " + music)
    return "\n\n".join(pieces).strip()


def _prompt_errors(text, duration, mode, expected_shots, user_intent=""):
    errors = []
    fields = ("integrated_multimodal_description:", "overall_soundscape:", "non_diegetic_music:")
    positions = [text.find(field) for field in fields]
    errors.extend(f"Missing required H3 field `{field}`." for field, position in zip(fields, positions) if position < 0)
    if all(position >= 0 for position in positions) and positions != sorted(positions):
        errors.append("H3 fields are not in the official order.")
    if any(text.count(field) != 1 for field in fields):
        errors.append("Every H3 field must appear exactly once.")
    if mode == "I2VA" and not text.startswith(
        "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
    ):
        errors.append("I2VA is missing the exact official first-frame alignment instruction.")
    if mode == "T2VA" and "<Picture 1>" in text:
        errors.append("T2VA must not contain a Picture reference.")
    headers = re.findall(r"\[Shot\s+(\d+)\]", text)
    unique = []
    for value in headers:
        number = int(value)
        if number not in unique:
            unique.append(number)
    if unique != list(range(1, expected_shots + 1)):
        errors.append("Shot numbers must be sequential starting at Shot 1.")
    cuts = [float(minutes) * 60 + float(seconds) for minutes, seconds in re.findall(r"At\s+(\d{2}):(\d{2}\.\d{3})", text)]
    if len(cuts) != max(0, expected_shots - 1):
        errors.append("Every shot after Shot 1 must have one timestamp.")
    if cuts != sorted(cuts) or len(cuts) != len(set(cuts)) or any(value <= 0 or value >= duration for value in cuts):
        errors.append("Cut timestamps must be unique, increasing, and inside the target duration.")
    if len(text) > _H3_CHAR_LIMIT:
        errors.append(f"The H3 prompt exceeds {_H3_CHAR_LIMIT} characters.")
    soundscape_match = re.search(
        r"overall_soundscape:\s*(.*?)\n\nnon_diegetic_music:", text, flags=re.DOTALL
    )
    silence_requested = bool(re.search(r"\b(?:complete|total|absolute)\s+silence\b|完全静音|全程静音", user_intent, re.IGNORECASE))
    if soundscape_match and soundscape_match.group(1).strip() == "N/A" and not silence_requested:
        errors.append("overall_soundscape may be N/A only when the user explicitly requests complete silence.")
    if "```" in text:
        errors.append("The H3 prompt must not contain a markdown fence.")
    return errors


def _call_json(
    *, base_url, api_key, model, service_type, messages, temperature, max_tokens, seed, name, schema, label,
):
    response_format = _response_format(base_url, service_type, name, schema)
    raw = _shared._chat_completion(
        base_url, api_key, model, messages, temperature, max_tokens, seed, service_type, response_format
    )
    try:
        return _parse_object(raw, label), raw, response_format
    except ValueError:
        repair_messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "The response was not a complete JSON object. Return the same requested data again as exactly one "
                    "complete JSON object matching the schema, with no markdown or commentary."
                ),
            },
        ]
        repaired = _shared._chat_completion(
            base_url, api_key, model, repair_messages, 0.0, max_tokens, seed, service_type, response_format
        )
        return _parse_object(repaired, f"repaired {label}"), repaired, response_format


class NO8DDynamicPrompt:
    _cache = {}
    _cache_lock = threading.Lock()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "duration": ("INT", {"default": 8, "min": 4, "max": 15, "step": 1}),
                "shot_count": ("INT", {"default": 0, "min": 0, "max": 6, "step": 1}),
                "style_preset": (_STYLE_INPUTS, {"default": "自行判断"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "control_after_generate": True}),
                "extra_rules": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {"images": ("IMAGE",)},
            "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "run"
    CATEGORY = "NO8D-control"

    @classmethod
    def IS_CHANGED(cls, duration=8, shot_count=0, style_preset="自行判断", seed=0, extra_rules="", images=None, prompt=None, unique_id=None):
        service, model_cfg = prompt_config_manager.current_service()
        payload = {
            "pipeline": _PIPELINE_VERSION,
            "duration": _normalize_duration(duration),
            "shot_count": _shared._safe_int(shot_count, 0),
            "style": _shared._normalize_style_preset(style_preset),
            "seed": _shared._safe_int(seed, 0),
            "intent": str(extra_rules or "").strip(),
            "images": _shared._images_to_hashes(images),
            "service": service.get("id"),
            "base_url": service.get("base_url", ""),
            "text_model": model_cfg.get("name", ""),
            "vision_model": service.get("vision_model", ""),
            "api_key": _shared._api_key_fingerprint(service.get("api_key", "")),
            "links": _shared._linked_inputs_signature(prompt, unique_id, ("images",)),
        }
        return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @classmethod
    def _cache_get(cls, key):
        with cls._cache_lock:
            return cls._cache.get(key)

    @classmethod
    def _cache_put(cls, key, value):
        with cls._cache_lock:
            cls._cache[key] = value
            while len(cls._cache) > 128:
                cls._cache.pop(next(iter(cls._cache)))

    def _generate_item(self, *, image_data_url, image_hash, user_intent, duration, shot_count, style_preset, seed, service, model_cfg):
        base_url = service.get("base_url", "")
        api_key = service.get("api_key", "") or os.getenv("NO8D_PROMPT_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        service_type = service.get("type", "openai_compatible")
        text_model = str(model_cfg.get("name", "") or "").strip()
        vision_model = str(service.get("vision_model", "") or text_model).strip()
        temperature = _shared._safe_float(model_cfg.get("temperature"), 0.7)
        mode = "I2VA" if image_data_url else "T2VA"
        cache_payload = {
            "pipeline": _PIPELINE_VERSION,
            "mode": mode,
            "image": image_hash,
            "intent": user_intent,
            "duration": duration,
            "shot_count": shot_count,
            "style": style_preset,
            "seed": seed,
            "service": service.get("id"),
            "base_url": base_url,
            "text_model": text_model,
            "vision_model": vision_model,
            "api_key": _shared._api_key_fingerprint(api_key),
        }
        cache_key = hashlib.sha1(json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        facts = {}
        if image_data_url:
            facts_messages = _facts_messages(user_intent, image_data_url, style_preset)
            facts, raw, _ = _call_json(
                base_url=base_url,
                api_key=api_key,
                model=vision_model,
                service_type=service_type,
                messages=facts_messages,
                temperature=min(temperature, 0.1),
                max_tokens=2048,
                seed=seed,
                name="no8d_h3_visual_facts",
                schema=_facts_schema(),
                label="visual facts",
            )
            errors = _facts_errors(facts)
            if errors:
                repair = facts_messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": "Return the complete visual-facts JSON only. Correct these issues:\n- " + "\n- ".join(errors)},
                ]
                facts, _, _ = _call_json(
                    base_url=base_url,
                    api_key=api_key,
                    model=vision_model,
                    service_type=service_type,
                    messages=repair,
                    temperature=0.0,
                    max_tokens=2048,
                    seed=seed,
                    name="no8d_h3_visual_facts_repair",
                    schema=_facts_schema(),
                    label="repaired visual facts",
                )
                errors = _facts_errors(facts)
                if errors:
                    raise RuntimeError("NO8D-Dynamic-Prompt: visual facts remained invalid after one correction:\n- " + "\n- ".join(errors))

        plan_messages = _planner_messages(user_intent, facts, duration, shot_count, style_preset, mode)
        plan, raw_plan, _ = _call_json(
            base_url=base_url,
            api_key=api_key,
            model=text_model,
            service_type=service_type,
            messages=plan_messages,
            temperature=temperature if mode == "T2VA" else min(temperature, 0.2),
            max_tokens=4096,
            seed=seed,
            name="no8d_h3_temporal_plan",
            schema=_plan_schema(),
            label="temporal plan",
        )
        errors = _plan_errors(plan, duration, shot_count, mode)
        candidate = _compile_h3_prompt(plan, facts, duration, mode) if not errors else ""
        if not errors:
            errors = _prompt_errors(candidate, duration, mode, len(plan["shots"]), user_intent)
        if errors:
            repair_messages = plan_messages + [
                {"role": "assistant", "content": raw_plan},
                {
                    "role": "user",
                    "content": (
                        "Repair only the temporal-plan JSON. Preserve the locked facts and user intent. Return complete "
                        "JSON without markdown. Correct these issues:\n- " + "\n- ".join(errors)
                    ),
                },
            ]
            plan, _, _ = _call_json(
                base_url=base_url,
                api_key=api_key,
                model=text_model,
                service_type=service_type,
                messages=repair_messages,
                temperature=0.0,
                max_tokens=4096,
                seed=seed,
                name="no8d_h3_temporal_plan_repair",
                schema=_plan_schema(),
                label="repaired temporal plan",
            )
            errors = _plan_errors(plan, duration, shot_count, mode)
            candidate = _compile_h3_prompt(plan, facts, duration, mode) if not errors else ""
            if not errors:
                errors = _prompt_errors(candidate, duration, mode, len(plan["shots"]), user_intent)
            if errors:
                raise RuntimeError("NO8D-Dynamic-Prompt: H3 plan remained invalid after one correction:\n- " + "\n- ".join(errors))

        self._cache_put(cache_key, candidate)
        return candidate

    def run(self, duration=8, shot_count=0, style_preset="自行判断", seed=0, extra_rules="", images=None, prompt=None, unique_id=None):
        duration = _normalize_duration(duration)
        shot_count = max(0, min(6, _shared._safe_int(shot_count, 0)))
        style_preset = _shared._normalize_style_preset(style_preset)
        user_intent = str(extra_rules or "").strip()
        encoded = _shared._images_to_data_urls(images)
        if not encoded and not user_intent:
            return ([],)
        service, model_cfg = prompt_config_manager.current_service()
        items = encoded or [("", "")]
        base_seed = _shared._safe_int(seed, 0)
        results = []
        for index, (image_data_url, image_hash) in enumerate(items):
            effective_seed = base_seed + index if base_seed else 0
            results.append(
                self._generate_item(
                    image_data_url=image_data_url,
                    image_hash=image_hash,
                    user_intent=user_intent,
                    duration=duration,
                    shot_count=shot_count,
                    style_preset=style_preset,
                    seed=effective_seed,
                    service=service,
                    model_cfg=model_cfg,
                )
            )
        return (results,)


NODE_CLASS_MAPPINGS = {"NO8DDynamicPrompt": NO8DDynamicPrompt}
NODE_DISPLAY_NAME_MAPPINGS = {"NO8DDynamicPrompt": "NO8D-Dynamic-Prompt"}
