"""Model definitions and mapping from Gemini frontend JS source."""

# MODE_CATEGORY enum from 028-6eb337387583.js:
#   1=FAST, 2=THINKING, 3=PRO, 4=AUTO, 5=FAST_DYNAMIC_THINKING, 6=FLASH_LITE

MODELS = {
    'gemini-4-argon': {
        'mode': None, 'think': 1,
        'desc': 'Pro Argon, requires a verified account route and quota',
    },
    "gemini-3.7-flash": {
        "mode": 1, "think": 4,
        "desc": "Latest all-around model (Gemini 3.7 Flash)",
    },
    "gemini-3.6-flash": {
        "mode": 1, "think": 1,
        "desc": "All-around model (Gemini 3.6 Flash)",
    },
    "gemini-3.5-flash": {
        "mode": 1, "think": 4,
        "desc": "Alias for gemini-3.6-flash (backend upgraded)",
    },
    "gemini-3.5-flash-thinking": {
        "mode": 2, "think": 0,
        "desc": "Deep thinking mode, longest output (~20k chars)",
    },
    "gemini-3.1-pro": {
        "mode": 3, "think": 4,
        "desc": "Pro model (requires cookie for real routing)",
    },
    "gemini-3.1-pro-enhanced": {
        "mode": 3, "think": 4, "extra": {31: 2, 80: 3},
        "desc": "Pro with enhanced output (experimental)",
    },
    "gemini-auto": {
        "mode": 4, "think": 4,
        "desc": "Auto model selection",
    },
    "gemini-3.5-flash-thinking-lite": {
        "mode": 5, "think": 0,
        "desc": "Dynamic thinking with adaptive depth",
    },
    "gemini-flash-lite": {
        "mode": 6, "think": 4,
        "desc": "Lightweight fast model",
    },
}


def thinking_depth(effort, default):
    # Verified against Gemini Web's XJb/kBd enum on 2026-10-28:
    # STANDARD=1 (Low), MEDIUM=4, EXTENDED=2 (High).
    # These are web protocol values, not token budgets.
    if effort is None:
        return default
    if not isinstance(effort, str) or effort not in ('low', 'medium', 'high'):
        raise ValueError('Invalid reasoning_effort; use low, medium, or high')
    return {'low': 1, 'medium': 4, 'high': 2}[effort]


def resolve_model(model_name: str, default: str = "gemini-3.6-flash", effort=None):
    """Resolve model name to (name, mode_id, think_mode, error, extra_fields).

    Unknown model names fail without routing to a different model.
    """
    think_override = None
    if "@think=" in model_name:
        model_name, think_str = model_name.rsplit("@think=", 1)
        try:
            think_override = int(think_str)
        except ValueError:
            return None, None, None, f"Invalid think level: {think_str}", None
    from .config import CONFIG
    cfg = (CONFIG.get('extra_models') or {}).get(model_name) or MODELS.get(model_name)
    if not cfg:
        return None, None, None, 'Model chưa được xác minh hoặc không được hỗ trợ', None
    if cfg.get('mode') is None:
        return None, None, None, 'Model cần tài khoản và quota đã xác minh', None
    mode_id = cfg["mode"]
    think_mode = think_override if think_override is not None else cfg["think"]
    try:
        think_mode = thinking_depth(effort, think_mode)
    except ValueError as error:
        return None, None, None, str(error), None
    extra = cfg.get("extra")
    return model_name, mode_id, think_mode, None, extra
