from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class CaseState(TypedDict):
    # Input
    raw_text: str
    jurisdiction: str
    lost_wages: float
    future_care: float

    # Filled by medical_agent (Node 1)
    injuries: list
    parsed_lost_wages: float    # extracted from text, used if user didn't provide
    parsed_future_care: float   # extracted from text, used if user didn't provide

    # Filled by damages_agent (Node 3)
    valuation: dict
    case_opinions: list

    # Filled by legal_agent (Node 4)
    demand_letter: str

    # Control flow
    messages: Annotated[list, add_messages]
    retry_count: int
    errors: list
