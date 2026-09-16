"""The tool registry: the approval gate's source of truth.

Risk classification lives here, never in tool bodies. A tool registered without an
explicit risk level is UNCLASSIFIED, which is gated. No tool can be executed by the
graph without passing through `ToolRegistry.get()`.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, create_model

from enola.core.enums import GATED_RISKS, Risk
from enola.core.errors import RegistryError

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: Risk
    fn: Callable[..., Any]
    args_model: type[BaseModel]
    # A human-readable label for the Approvals screen ("email · outbound").
    kind_label: str

    @property
    def gated(self) -> bool:
        return self.risk in GATED_RISKS

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.args_model.model_validate(args).model_dump()

    def as_langchain_tool(self) -> BaseTool:
        """Schema only. The graph never lets LangChain execute the function directly."""
        return StructuredTool.from_function(
            func=self.fn, name=self.name, description=self.description, args_schema=self.args_model
        )


def _args_model_from_signature(fn: Callable[..., Any], name: str) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for param in inspect.signature(fn).parameters.values():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else str
        default = param.default if param.default is not inspect.Parameter.empty else ...
        fields[param.name] = (annotation, default)
    return create_model(f"{name}_args", **fields)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise RegistryError(f"Tool '{spec.name}' is already registered")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError:
            raise RegistryError(f"Unknown tool '{name}'") from None

    def is_gated(self, name: str) -> bool:
        """Unknown tools are gated too: nothing runs on the strength of a name alone."""
        spec = self._tools.get(name)
        return spec is None or spec.gated

    def all(self) -> list[ToolSpec]:
        return sorted(self._tools.values(), key=lambda s: s.name)

    def langchain_tools(self) -> list[BaseTool]:
        return [spec.as_langchain_tool() for spec in self.all()]

    def tool(
        self,
        risk: Risk | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        kind_label: str = "",
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Register a plain function as a tool.

            @registry.tool(risk=Risk.EXTERNAL)
            def send_email(to: str, subject: str, body: str) -> str: ...

        Leaving `risk` out is allowed and means UNCLASSIFIED, which is gated.
        """

        def decorate(fn: Callable[P, R]) -> Callable[P, R]:
            tool_name = name or fn.__name__
            doc = description or (inspect.getdoc(fn) or "").strip()
            if not doc:
                raise RegistryError(f"Tool '{tool_name}' needs a description (docstring)")
            self.register(
                ToolSpec(
                    name=tool_name,
                    description=doc,
                    risk=risk if risk is not None else Risk.UNCLASSIFIED,
                    fn=fn,
                    args_model=_args_model_from_signature(fn, tool_name),
                    kind_label=kind_label or tool_name.replace("_", " "),
                )
            )
            return fn

        return decorate


# The application registry. Tool modules import this and decorate their functions.
registry = ToolRegistry()
tool = registry.tool
