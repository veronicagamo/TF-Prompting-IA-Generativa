import json
import logging
from tools import calcular_macros_tool, generar_dieta_tool
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

logging.basicConfig(level=logging.INFO)

print("Initializing ChatOllama qwen2.5:3b...")
llm = ChatOllama(
    base_url="http://localhost:11434",
    model="qwen2.5:3b",
    temperature=0
)

# Test 1: create_tool_calling_agent with a very simple system prompt
print("\n--- TEST 1: Tool Calling Agent ---")
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "Eres un asistente de nutrición. Debes usar calcular_macros_tool para calcular las necesidades y generar_dieta_tool para armar el menú. Sé breve."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

try:
    agent = create_tool_calling_agent(llm, [calcular_macros_tool, generar_dieta_tool], prompt_template)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=[calcular_macros_tool, generar_dieta_tool],
        verbose=True,
        return_intermediate_steps=True
    )
    peticion = "Hombre, 28 años, 75kg, 175cm, actividad moderada, pérdida de grasa."
    print("Invoking agent...")
    res = agent_executor.invoke({"input": peticion})
    print("Test 1 Result:", res.keys())
    if "intermediate_steps" in res:
        print("Steps:", res["intermediate_steps"])
except Exception as e:
    print("Test 1 failed:", e)
