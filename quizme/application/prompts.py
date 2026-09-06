"""Prompt template loader.

Templates live in ``quizme/prompts/<version>.md`` with three sections:

    ## System
    ...
    ## User
    ... {placeholders} ...
    ## Response schema
    ```json
    { ... }
    ```

``load(version)`` returns a :class:`Prompt`; ``prompt.render(**vars)`` fills the
``{placeholder}`` fields in the user section. The filename *is* the
``prompt_version`` recorded on every ``llm_call`` and ``KUOperation`` (AD-8).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

_SECTION = re.compile(r"^##\s+(System|User|Response schema)\s*$", re.MULTILINE)
_JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Prompt:
    version: str
    system: str
    user_template: str
    schema: dict[str, Any]

    def render(self, **fields: object) -> str:
        out = self.user_template
        for key, value in fields.items():
            out = out.replace("{" + key + "}", str(value))
        leftover = re.findall(r"\{([a-z_][a-z0-9_]*)\}", out)
        if leftover:
            raise KeyError(f"{self.version}: unfilled placeholders {leftover}")
        return out


@lru_cache(maxsize=64)
def load(version: str) -> Prompt:
    text = resources.files("quizme.prompts").joinpath(f"{version}.md").read_text(encoding="utf-8")
    parts = _SECTION.split(text)
    # parts = [preamble, 'System', sys, 'User', user, 'Response schema', schema]
    sections = {parts[i].lower().replace(" ", "_"): parts[i + 1] for i in range(1, len(parts), 2)}

    schema_txt = sections.get("response_schema", "")
    m = _JSON_BLOCK.search(schema_txt)
    if not m:
        raise ValueError(f"{version}: no ```json``` schema block")
    schema = json.loads(m.group(1))

    return Prompt(
        version=version,
        system=sections["system"].strip(),
        user_template=sections["user"].strip(),
        schema=schema,
    )
