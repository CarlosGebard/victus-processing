from __future__ import annotations

import re
from typing import Any


_DOUBLE_BRACE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
_SINGLE_BRACE = re.compile(r"(?<!{){([a-zA-Z_][a-zA-Z0-9_]*)}(?!})")


def compile_template(template: str, variables: dict[str, Any]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            missing.add(name)
            return match.group(0)
        return str(variables[name])

    rendered = _DOUBLE_BRACE.sub(replace, template)
    rendered = _SINGLE_BRACE.sub(replace, rendered)
    if missing:
        raise ValueError(f"Missing prompt variables: {', '.join(sorted(missing))}")
    return rendered
