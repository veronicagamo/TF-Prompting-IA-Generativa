# -*- coding: utf-8 -*-
"""
Módulo de Herramientas (Tools) para el Agente Nutricional.
Define calcular_macros_tool y generar_dieta_tool con soporte para streaming y prompts optimizados.
"""

import json
import streamlit as st
from typing import Dict, Any
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

def calcular_macros_core(edad: int, sexo: str, peso: float, altura: float, nivel_actividad: str, objetivo: str) -> Dict[str, Any]:
    """
    Función pura en Python para realizar los cálculos metabólicos mediante Mifflin-St Jeor.
    """
    # 1. Calcular TMB (Tasa Metabólica Basal)
    if sexo.lower() in ["masculino", "hombre", "m", "masc"]:
        tmb = 10 * peso + 6.25 * altura - 5 * edad + 5
    else:
        tmb = 10 * peso + 6.25 * altura - 5 * edad - 161
        
    # 2. Factor de actividad
    actividad_factors = {
        "sedentario": 1.2,
        "ligero": 1.375,
        "moderado": 1.55,
        "intenso": 1.725,
        "muy intenso": 1.9
    }
    
    # Normalizar clave del nivel de actividad
    act_key = nivel_actividad.lower().strip()
    factor = 1.2  # Por defecto sedentario
    for k, v in actividad_factors.items():
        if k in act_key:
            factor = v
            break
            
    tdee = tmb * factor
    
    # 3. Ajuste según objetivo deportivo
    obj_key = objetivo.lower().strip()
    if "pérdida" in obj_key or "perdida" in obj_key or "grasa" in obj_key:
        calorias_objetivo = tdee - 500
        factor_proteina = 2.2  # Alto en proteínas para retención muscular en déficit
        ajuste_desc = "-500 kcal (Déficit calórico para Pérdida de grasa)"
    elif "hipertrofia" in obj_key or "ganar" in obj_key or "musculo" in obj_key:
        calorias_objetivo = tdee + 300
        factor_proteina = 2.2  # Óptimo para síntesis en superávit
        ajuste_desc = "+300 kcal (Superávit calórico para Hipertrofia)"
    else:  # Recomposición corporal o Mantenimiento
        calorias_objetivo = tdee
        factor_proteina = 2.0  # Estándar deportivo
        ajuste_desc = "Mantenimiento energético (Recomposición corporal)"
        
    # 4. Cálculo de Macronutrientes
    # Proteínas: factor_proteina g/kg
    proteinas_g = peso * factor_proteina
    proteinas_kcal = proteinas_g * 4
    
    # Grasas: 1g/kg
    grasas_g = peso * 1.0
    grasas_kcal = grasas_g * 9
    
    # Carbohidratos: El resto de las calorías
    rest_kcal = calorias_objetivo - (proteinas_kcal + grasas_kcal)
    carbohidratos_g = max(0.0, rest_kcal / 4)
    carbohidratos_kcal = carbohidratos_g * 4
    
    # Ajustar calorías reales basándose en el reparto exacto de macros
    calorias_reales = proteinas_kcal + grasas_kcal + carbohidratos_kcal
    
    # Calcular porcentajes calóricos
    pct_prot = (proteinas_kcal / calorias_reales) * 100 if calorias_reales > 0 else 0
    pct_gras = (grasas_kcal / calorias_reales) * 100 if calorias_reales > 0 else 0
    pct_carb = (carbohidratos_kcal / calorias_reales) * 100 if calorias_reales > 0 else 0
    
    return {
        "sexo": sexo,
        "edad": edad,
        "peso": peso,
        "altura": altura,
        "tmb": round(tmb, 1),
        "tdee": round(tdee, 1),
        "calorias_objetivo": round(calorias_objetivo, 1),
        "calorias_reales": round(calorias_reales, 1),
        "ajuste_descripcion": ajuste_desc,
        "macros": {
            "proteinas": round(proteinas_g, 1),
            "grasas": round(grasas_g, 1),
            "carbohidratos": round(carbohidratos_g, 1)
        },
        "macros_kcal": {
            "proteinas": round(proteinas_kcal, 1),
            "grasas": round(grasas_kcal, 1),
            "carbohidratos": round(carbohidratos_kcal, 1)
        },
        "macros_porcentaje": {
            "proteinas": round(pct_prot, 1),
            "grasas": round(pct_gras, 1),
            "carbohidratos": round(pct_carb, 1)
        }
    }


@tool
def calcular_macros_tool(edad: int, sexo: str, peso: float, altura: float, nivel_actividad: str, objetivo: str) -> str:
    """
    Calcula de manera determinista la Tasa Metabólica Basal (TMB), el Gasto Energético Diario Total (TDEE),
    las calorías objetivo y el reparto de macronutrientes (proteínas, grasas y carbohidratos)
    según la fórmula de Mifflin-St Jeor y directrices de nutrición deportiva.
    
    Parámetros:
    - edad (int): Edad del usuario en años.
    - sexo (str): Sexo biológico ('Masculino' o 'Femenino').
    - peso (float): Peso corporal en kg.
    - altura (float): Altura del usuario en cm.
    - nivel_actividad (str): Nivel de actividad física ('Sedentario', 'Ligero', 'Moderado', 'Intenso', 'Muy Intenso').
    - objetivo (str): Objetivo nutricional ('Pérdida de grasa', 'Hipertrofia', 'Recomposición corporal').
    """
    res = calcular_macros_core(edad, sexo, peso, altura, nivel_actividad, objetivo)
    return json.dumps(res, indent=2, ensure_ascii=False)


@tool
def generar_dieta_tool(calorias: float, macros: dict, alimentos_incluidos: str, alimentos_excluidos: str) -> str:
    """
    Usa el modelo de lenguaje (LLM) para generar una propuesta detallada de menú diario completo
    (Desayuno, Almuerzo, Merienda y Cena) adaptada a los requerimientos energéticos y respetando
    estrictamente los alimentos preferidos y excluidos.
    
    Parámetros:
    - calorias (float): Calorías diarias objetivo del plan.
    - macros (dict): Diccionario con los gramos de 'proteinas', 'grasas' y 'carbohidratos'.
    - alimentos_incluidos (str): Alimentos preferidos a incluir en las comidas.
    - alimentos_excluidos (str): Restricciones, alergias o alimentos a evitar obligatoriamente.
    """
    url = st.session_state.get("ollama_url", "http://localhost:11434")
    model = st.session_state.get("model_name", "qwen2.5:3b")
    
    # Instanciar ChatOllama con los parámetros actuales
    llm = ChatOllama(
        base_url=url,
        model=model,
        temperature=0.2,
    )
    
    prompt = f"""
    Eres un Nutricionista Deportivo de élite. Diseña un ejemplo de menú diario simplificado y estructurado que cumpla con:
    - Calorías: {calorias} kcal
    - Proteínas: {macros.get('proteinas', 0)}g
    - Grasas: {macros.get('grasas', 0)}g
    - Carbohidratos: {macros.get('carbohidratos', 0)}g
    
    Preferencias alimentarias:
    - Incluir: {alimentos_incluidos if alimentos_incluidos else 'Ninguno en particular'}
    - Excluir: {alimentos_excluidos if alimentos_excluidos else 'Ninguno'}
    
    REGLAS IMPORTANTES:
    1. Sé extremadamente conciso y directo para ahorrar tiempo de procesamiento en CPU.
    2. Divide en: Desayuno, Almuerzo, Merienda y Cena.
    3. Detalla únicamente el nombre del plato, ingredientes con sus pesos (g), preparación básica (1 frase) y estimación de macros.
    4. Al final, muestra una tabla simple comparando el Total consumido vs Objetivo.
    5. Escribe todo en español. No agregues introducciones largas ni textos complementarios.
    """
    
    try:
        res = llm.invoke(prompt)
        return res.content
    except Exception as e:
        return f"Error al generar la dieta: {str(e)}"
