import sys
import logging
from tools import calcular_macros_tool, generar_dieta_tool
from agent import get_agent_executor

logging.basicConfig(level=logging.INFO)

print("Starting debug script...")
url = "http://localhost:11434"
model = "qwen2.5:1.5b"  # Let's test with the light model first
tools = [calcular_macros_tool, generar_dieta_tool]

print(f"Creating agent executor for {model}...")
agent_executor = get_agent_executor(url, model, tools)

peticion_usuario = (
    "Hola, soy un usuario con el siguiente perfil:\n"
    "- Edad: 28 años\n"
    "- Sexo: Masculino\n"
    "- Peso: 75.0 kg\n"
    "- Altura: 175 cm\n"
    "- Nivel de Actividad: Moderado\n"
    "- Objetivo: Pérdida de grasa\n"
    "- Horizonte: 12 semanas\n"
    "- Alimentos Preferidos: Pollo, arroz\n"
    "- Alimentos Excluidos: Pescado"
)

print("Invoking agent stream...")
try:
    for chunk in agent_executor.stream({
        "input": peticion_usuario,
        "chat_history": []
    }):
        print("\n--- CHUNK RECEIVED ---")
        print(chunk)
except Exception as e:
    print(f"Exception raised: {e}")
    import traceback
    traceback.print_exc()

print("Debug script completed.")
