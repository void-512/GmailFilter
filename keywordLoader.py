import json
import re

def load_from_json(path):
    """
    Load keywords from JSON and compile regex lists for each block.
    Returns: blocks_compiled: dict[name -> list of compiled patterns], exclude_any (compiled or None)
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    include_all_list = cfg.get("include_all", {})
    include_all_compiled = {}
    for name, keywords in include_all_list.items():
        # compile each keyword as a regex; you can add r"\b...\b" for whole-word matching
        include_all_compiled[name] = [re.compile(re.escape(k), re.IGNORECASE) for k in keywords]

    exclude_any_list = cfg.get("exclude_any", [])
    exclude_any_compiled = re.compile("|".join(re.escape(k) for k in exclude_any_list), re.IGNORECASE) if exclude_any_list else None

    return include_all_compiled, exclude_any_compiled

def is_match(text, include_all_compiled, exclude_any_compiled=None):
    """
    Returns True iff:
      - text does NOT match any exclude_any pattern (if provided), AND
      - for every block in include_all_compiled, at least one pattern in that block matches text.
    """
    if exclude_any_compiled and exclude_any_compiled.search(text):
        return False

    # For each block: require at least one match
    for include_filter, patterns in include_all_compiled.items():
        if not any(p.search(text) for p in patterns):
            return False

    return True
