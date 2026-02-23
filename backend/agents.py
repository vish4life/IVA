import operator
from typing import Annotated, List, Union, TypedDict, Dict
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM
llm = ChatOllama(
    model=os.getenv("MODEL_NAME", "llama3.2"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    temperature=0
)

# State definition
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    customer_info: Dict
    auth_status: bool

# Initialize tools globally or on demand
_tools = []

async def get_tools_cached():
    global _tools
    if not _tools:
        client = MultiServerMCPClient({
            "banking": {
                "command": "python",
                "args": ["/Users/lakshmishashankch/Development/IVA/backend/mcp_server.py"],
                "transport": "stdio"
            }
        })
        _tools = await client.get_tools()
    return _tools

# Define Specialized Agents
async def get_onboarding_agent():
    tools = await get_tools_cached()
    return create_react_agent(
        model=llm,
        tools=[t for t in tools if t.name in ["get_customer_profile", "apply_for_product"]],
        prompt="""You are an Onboarding Specialist. Help NEW customers with:
        1. Account Opening
        2. Loan Applications
        3. Credit Card Applications
        Always check if the customer already exists using 'get_customer_profile' if they provide an email.
        Then use 'apply_for_product' to submit their application.
        IMPORTANT: Provide tool arguments as plain strings or numbers, never as dictionaries with type info."""
    )

async def get_banking_agent():
    tools = await get_tools_cached()
    return create_react_agent(
        model=llm,
        tools=[t for t in tools if t.name in ["get_account_balance", "transfer_funds", "update_customer_address", "validate_transaction_fraud"]],
        prompt="""You are a Banking Assistant for AUTHENTICATED users. 
        You can check balances, transfer funds, and update addresses.
        Use the user's email from the context to pull all associated accounts if needed.
        CRITICAL: For transfers > $5000, ALWAYS call 'validate_transaction_fraud' before confirming.
        IMPORTANT: Provide tool arguments as plain strings or numbers, never as dictionaries with type info."""
    )

async def get_advisory_agent():
    tools = await get_tools_cached()
    return create_react_agent(
        model=llm,
        tools=[t for t in tools if t.name in ["query_policy_rag"]],
        prompt="""You are a Financial Advisor and Policy Expert.
        Use 'query_policy_rag' to answer questions about bank policies like ACH or cheque clearing.
        IMPORTANT: Provide 'search_query' as a plain text string ONLY. Do not use dictionaries or type definitions.
        Provide personalized investment or credit card suggestions based on user interests."""
    )

# Routing Logic
def router(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1].content.lower()
    
    if not state["auth_status"]:
        return "onboarding"
    
    if any(word in last_message for word in ["policy", "clearing", "ach", "cheque", "suggest", "investment"]):
        return "advisory"
    
    return "banking"

# Individual node wrappers to handle the async agent calls
async def onboarding_node(state: AgentState):
    agent = await get_onboarding_agent()
    result = await agent.ainvoke(state)
    return {"messages": result["messages"]}

async def banking_node(state: AgentState):
    agent = await get_banking_agent()
    result = await agent.ainvoke(state)
    return {"messages": result["messages"]}

async def advisory_node(state: AgentState):
    agent = await get_advisory_agent()
    result = await agent.ainvoke(state)
    return {"messages": result["messages"]}

# Build Workflow
workflow = StateGraph(AgentState)

workflow.add_node("onboarding", onboarding_node)
workflow.add_node("banking", banking_node)
workflow.add_node("advisory", advisory_node)

# Entry point logic using a "routing" node or set_entry_point with conditional
def entry_router(state: AgentState):
    return router(state)

workflow.set_conditional_entry_point(
    entry_router,
    {
        "onboarding": "onboarding",
        "banking": "banking",
        "advisory": "advisory"
    }
)

workflow.add_edge("onboarding", END)
workflow.add_edge("banking", END)
workflow.add_edge("advisory", END)

graph = workflow.compile()

async def process_query(query: str, customer_info: Dict, auth_status: bool):
    # Ensure tools are initialized before running graph
    await get_tools_cached()
    
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "customer_info": customer_info,
        "auth_status": auth_status
    }
    
    result = await graph.ainvoke(initial_state)
    return result["messages"][-1].content
