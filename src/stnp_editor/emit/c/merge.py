from __future__ import annotations

import re

_USER_BLOCK = re.compile(
    r"/\*\s*USER (CODE|DESC) BEGIN (\S+)\s*\*/(.*?)/\*\s*USER \1 END \2\s*\*/",
    re.DOTALL,
)


def extract_user_regions(text: str) -> dict[tuple[str, str], str]:
    found: dict[tuple[str, str], str] = {}
    for match in _USER_BLOCK.finditer(text):
        key = (match.group(1), match.group(2))
        found[key] = match.group(0)
    return found


def merge_user_regions(new_text: str, old_text: str) -> str:
    """Keep USER CODE / USER DESC bodies from old_text when ids still exist."""
    old = extract_user_regions(old_text)
    used: set[tuple[str, str]] = set()

    def _repl(match: re.Match[str]) -> str:
        key = (match.group(1), match.group(2))
        if key in old:
            used.add(key)
            return old[key]
        return match.group(0)

    out = _USER_BLOCK.sub(_repl, new_text)
    orphans = [old[key] for key in old if key not in used]
    if orphans:
        out = out.rstrip() + "\n\n/* USER ORPHAN BEGIN */\n"
        out += "\n".join(orphans)
        out += "\n/* USER ORPHAN END */\n"
    return out
