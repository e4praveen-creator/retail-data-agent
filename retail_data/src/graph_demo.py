"""Minimal LangGraph integration, not an LLM analyst. No API keys or network needed."""
import json
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from reports import run_report

class State(TypedDict, total=False):
    report: str
    start_date: str
    end_date: str
    result: dict

def query_dataset(state: State):
    return {'result':run_report(state['report'],state.get('start_date','2024-01-01'),state.get('end_date','2025-12-31'))}

def build_graph():
    graph=StateGraph(State)
    graph.add_node('query_dataset',query_dataset)
    graph.add_edge(START,'query_dataset')
    graph.add_edge('query_dataset',END)
    return graph.compile()

if __name__=='__main__':
    result=build_graph().invoke({'report':'division_sales'})
    print(json.dumps(result['result'],indent=2,default=str))
