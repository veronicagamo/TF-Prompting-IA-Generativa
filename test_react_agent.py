import logging
from tools import calcular_macros_tool, generar_dieta_tool
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate

try:
    from langchain.agents import AgentExecutor, create_react_agent
except ImportError:
    from langchain_classic.agents import AgentExecutor, create_react_agent

logging.basicConfig(level=logging.INFO)

print("Initializing ChatOllama qwen2.5:3b...")
llm = ChatOllama(
    base_url="http://localhost:11434",
    model="qwen2.5:3b",
    temperature=0
)

# ReAct prompt template
template = """Eres un Agente Nutricional Inteligente de élite. Tienes acceso a las siguientes herramientas:

{tools}

Para usar una herramienta, usa estrictamente el siguiente formato:

Thought: ¿Qué debo hacer a continuación? Debo usar una herramienta para avanzar.
Action: la herramienta a usar, debe ser una de [{tool_names}]
Action Input: los parámetros de entrada para la herramienta en formato JSON o texto plano.
Observation: el resultado de la herramienta

Una vez que tengas la respuesta final, usa este formato:

Thought: Ya tengo toda la información necesaria.
Final Answer: el plan nutricional detallado y final devuelto por generar_dieta_tool.

Comienza.

Question: {input}
Thought: {agent_scratchpad}"""

prompt = PromptTemplate.from_template(template)

tools = [calcular_macros_tool, generar_dieta_tool]

print("\n--- TEST: ReAct Agent ---")
try:
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True
    )
    
    peticion = (
        "Hola, soy un hombre de 28 años, peso 75kg, altura 175cm, actividad moderada, objetivo pérdida de grasa. "
        "Mis alimentos preferidos son pollo y arroz. Excluye pescado."
    )
    
    print("Invoking agent...")
    res = agent_executor.invoke({"input": peticion})
    print("\n--- AGENT RESULT ---")
    print(res["output"])
except Exception as e:
    print("ReAct agent failed:", e)
    import traceback
    traceback.print_exc()
