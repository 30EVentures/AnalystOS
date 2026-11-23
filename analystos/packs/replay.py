"""A model client that replays recorded responses instead of paying for a call (Slice 112).

Same shape as ``anthropic.Anthropic().messages.create`` as far as AnalystOS
uses it: returns an object with ``content`` (a list of blocks with ``type``,
``name`` and ``input``) and ``stop_reason``. Every request is kept in
``requests`` so tests can check what would have been sent. Recorded responses
are written in the working session and stored under ``fixtures/``.

What replay proves: the pipeline, the verifier and the rendering, for free.
What it does not prove: that the production model writes content this good.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace


class ReplayExhausted(RuntimeError):
    pass


class _Messages:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        owner = self._owner
        owner.requests.append(copy.deepcopy(kwargs))
        if not owner.responses:
            raise ReplayExhausted("no recorded response left to replay")
        recorded = owner.responses.pop(0)
        if recorded is None:
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="")], stop_reason="end_turn")
        tool_name = kwargs.get("tool_choice", {}).get("name", "tool")
        block = SimpleNamespace(type="tool_use", name=tool_name, input=copy.deepcopy(recorded))
        return SimpleNamespace(content=[block], stop_reason="tool_use")


class ReplayClient:
    """Replays ``responses`` (tool inputs, or None for a reply with no tool call) in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = _Messages(self)

    @classmethod
    def from_files(cls, *paths):
        return cls([json.loads(Path(p).read_text(encoding="utf-8")) for p in paths])
