from collections.abc import Sequence
from typing import Any

from langchain.tools import BaseTool
from langchain_core.runnables import Runnable

from deepagents import DeepAgentState
from deal_pilot.utils.trace_wrapper import trace_wrapper
from deal_pilot.utils.get_prompt import get_prompt
from deal_pilot.agents.main_agent_state import MainAgentState
from deal_pilot.middlewares.turn_summary import turn_summary
from deal_pilot.agents.agent_factory import AgentFactory
from langchain.agents.middleware import AgentMiddleware, AgentState


class MainAgentFactory(AgentFactory):
    @property
    def name(self) -> str:
        return "main_agent"

    def get_state_schema(self) -> type[DeepAgentState] | None:
        return MainAgentState

    def get_middlewares(self) -> Sequence[AgentMiddleware[AgentState[Any], None, Any]]:
        return [turn_summary]


main_agent_factory = MainAgentFactory()
factory = main_agent_factory.factory

agent_factory_with_trace = trace_wrapper(factory)
