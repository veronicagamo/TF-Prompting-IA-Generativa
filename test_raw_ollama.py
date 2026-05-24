from langchain_ollama import ChatOllama
from tools import calcular_macros_tool, generar_dieta_tool

print("Initializing ChatOllama...")
llm = ChatOllama(
    base_url="http://localhost:11434",
    model="qwen2.5:1.5b",
    temperature=0
)

print("Binding tools...")
llm_with_tools = llm.bind_tools([calcular_macros_tool, generar_dieta_tool])

peticion_usuario = (
    "Hola, soy un usuario de 28 años, masculino, peso 75kg, altura 175cm, actividad moderada, objetivo pérdida de grasa."
)

print("Invoking ChatOllama with tools...")
res = llm_with_tools.invoke(peticion_usuario)
print("\n--- RESPONSE ---")
print(res)
print("Tool calls:", res.tool_calls)
