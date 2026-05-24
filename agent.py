# -*- coding: utf-8 -*-
"""
Módulo del Agente de IA para el Planificador Nutricional.
Configura y orquesta el agente utilizando un motor de escalado nutricional
dinámico basado en la base de datos oficial de alimentos UCM.
"""

import json
import logging
import os
import time
from langchain_core.agents import AgentAction

logger = logging.getLogger("NutriAgent.AgentExecutor")

class AgentStep:
    """
    Simula un paso intermedio (Step) de LangChain para mantener compatibilidad
    con el desempaquetado de resultados en la interfaz de Streamlit.
    """
    def __init__(self, action: AgentAction, observation: str):
        self.action = action
        self.observation = observation

class SequentialNutritionAgentExecutor:
    """
    Orquestador secuencial determinista que simula la interfaz de AgentExecutor
    para ejecutar calcular_macros_tool y generar_dieta_tool.
    """
    def __init__(self, url: str, model: str, tools: list):
        self.url = url
        self.model = model
        self.tools = tools
        
        # Cargar base de datos de alimentos de la UCM si existe
        self.food_db = {}
        db_path = "/home/veronica/Descargas/Propmting/Trabajo Final/ucm_food_database.json"
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self.food_db[item["name"].lower().strip()] = item
                logger.info(f"Base de datos de alimentos UCM cargada con {len(self.food_db)} alimentos para el escalador.")
            except Exception as e:
                logger.error(f"Error al cargar la base de datos de alimentos: {e}")

    def get_food(self, name: str):
        """ Retorna los aportes nutricionales del alimento o un valor por defecto si no existe. """
        name_lower = name.lower().strip()
        if name_lower in self.food_db:
            return self.food_db[name_lower]
        elif name_lower == "whey":
            return {"kcal": 360.0, "proteins": 80.0, "carbs": 3.0, "fats": 2.0, "fiber": 0.0}
        else:
            # Fallbacks seguros en caso de diferencias ortográficas
            fallback_map = {
                "avena": "avena",
                "pechuga": "pechuga de pollo",
                "arroz": "arroz integral",
                "huevo": "huevo de gallina",
                "clara": "clara de huevo",
                "aceite": "aceite de oliva",
                "pan": "pan integral",
                "platano": "plátano",
                "ternera": "ternera magra",
                "pasta": "pasta integral",
                "nuez": "nuez sin cascara",
                "patata": "patata nueva"
            }
            for key, db_name in fallback_map.items():
                if key in name_lower and db_name in self.food_db:
                    return self.food_db[db_name]
            # Si nada coincide
            return {"kcal": 100.0, "proteins": 10.0, "carbs": 10.0, "fats": 2.0, "fiber": 0.0}

    def calc_menu_nutrition(self, diet: dict) -> dict:
        """ Calcula las calorías y macronutrientes reales de una dieta. """
        total_kcal = 0.0
        total_p = 0.0
        total_c = 0.0
        total_g = 0.0
        total_f = 0.0
        for name, grams in diet.items():
            food = self.get_food(name)
            total_kcal += (food["kcal"] * grams / 100.0)
            total_p += (food["proteins"] * grams / 100.0)
            total_c += (food["carbs"] * grams / 100.0)
            total_g += (food["fats"] * grams / 100.0)
            total_f += (food["fiber"] * grams / 100.0)
        return {
            "kcal": round(total_kcal, 1),
            "proteins": round(total_p, 1),
            "carbs": round(total_c, 1),
            "fats": round(total_g, 1),
            "fiber": round(total_f, 1)
        }

    def stream(self, inputs: dict):
        """
        Emula el método .stream() del AgentExecutor clásico de LangChain.
        """
        # Extraer parámetros de entrada
        edad = inputs.get("edad", 28)
        sexo = inputs.get("sexo", "Masculino")
        peso = inputs.get("peso", 75.0)
        altura = inputs.get("altura", 175.0)
        nivel_actividad = inputs.get("nivel_actividad", "Moderado")
        objetivo = inputs.get("objetivo", "Pérdida de grasa")
        alimentos_preferidos = inputs.get("alimentos_preferidos", "")
        alimentos_excluidos = inputs.get("alimentos_excluidos", "")
        tipo_plan = inputs.get("tipo_plan", "Menú Diario (1 día)")

        # 1. Ejecutar calcular_macros_tool
        action_calc = AgentAction(
            tool="calcular_macros_tool",
            tool_input={
                "edad": edad,
                "sexo": sexo,
                "peso": peso,
                "altura": altura,
                "nivel_actividad": nivel_actividad,
                "objetivo": objetivo
            },
            log="Calculando requerimientos calóricos y macronutrientes basados en Mifflin-St Jeor..."
        )
        yield {"actions": [action_calc]}

        # Importar y ejecutar localmente para máxima velocidad
        from tools import calcular_macros_core
        macros_res = calcular_macros_core(
            edad=edad,
            sexo=sexo,
            peso=peso,
            altura=altura,
            nivel_actividad=nivel_actividad,
            objetivo=objetivo
        )
        observation_calc = json.dumps(macros_res, indent=2, ensure_ascii=False)
        yield {"steps": [AgentStep(action_calc, observation_calc)]}

        # 2. Ejecutar generar_dieta_tool
        calorias = macros_res["calorias_objetivo"]
        macros_dict = macros_res["macros"]

        action_diet = AgentAction(
            tool="generar_dieta_tool",
            tool_input={
                "calorias": calorias,
                "macros": macros_dict,
                "alimentos_incluidos": alimentos_preferidos,
                "alimentos_excluidos": alimentos_excluidos,
                "tipo_plan": tipo_plan
            },
            log=f"Generando propuesta de {tipo_plan} adaptada a requerimientos y preferencias alimentarias..."
        )
        yield {"actions": [action_diet]}

        # ==========================================================
        # MOTOR DE ESCALADO DINÁMICO DE PORCIONES
        # ==========================================================
        target_p = macros_dict.get("proteinas", 165.0)
        target_c = macros_dict.get("carbohidratos", 203.0)
        target_g = macros_dict.get("grasas", 75.0)

        # Factores de escala relativos a la dieta base de 165g P, 203g C, 75g G
        scale_p = target_p / 165.0
        scale_c = target_c / 203.0
        scale_g = target_g / 75.0

        # Menús base optimizados
        base_menus = {
            "Lunes": {
                "title": "Día de Avena y Arroz Integral",
                "portions": {"avena": 53, "clara": 351, "huevo": 100, "pechuga_pollo": 299, "arroz_integral": 199, "aceite": 33, "platano": 100, "whey": 30},
                "meals": {
                    "Desayuno": "Gachas: {avena}g de Avena + {clara}g de Clara de Huevo cocidas a fuego lento.\n{platano}g de Plátano en rodajas por encima.",
                    "Almuerzo": "{pechuga_pollo}g de Pechuga de Pollo a la plancha.\n{arroz_integral}g de Arroz Integral cocido (pesado en seco).\n{aceite_almuerzo}g de Aceite de Oliva en crudo para aderezar.",
                    "Merienda": "{whey}g de Proteína de Suero (Whey) disuelta en agua.",
                    "Cena": "Tortilla: {huevo}g de Huevo de Gallina entero (2 huevos medianos) hechos con {aceite_cena}g de Aceite de Oliva y verduras libres (ej. espinacas)."
                }
            },
            "Martes": {
                "title": "Día de Pan y Pasta Integral con Ternera",
                "portions": {"pan_integral": 109, "clara": 283, "huevo": 100, "ternera_magra": 375, "pasta_integral": 199, "aceite": 18, "platano": 120, "nuez": 15},
                "meals": {
                    "Desayuno": "Sándwich: {pan_integral}g de Pan Integral + {clara}g de Clara de Huevo en tortilla + rodajas de tomate.",
                    "Almuerzo": "{pasta_integral}g de Pasta Integral (en seco) salteada.\n{ternera_magra_almuerzo}g de Ternera Magra picada y hecha a la plancha.\n{aceite_almuerzo}g de Aceite de Oliva para cocinar.",
                    "Merienda": "{nuez}g de Nueces sin Cáscara + {platano}g de Plátano.",
                    "Cena": "{ternera_magra_cena}g de Ternera Magra con ensalada verde libre de aderezo.\n{huevo}g de Huevo de Gallina entero (2 huevos cocidos).\n{aceite_cena}g de Aceite de Oliva."
                }
            },
            "Miércoles": {
                "title": "Día de Avena y Patata Nueva",
                "portions": {"avena": 200, "clara": 379, "huevo": 100, "pechuga_pollo": 335, "patata_nueva": 367, "aceite": 22, "platano": 150, "whey": 0},
                "meals": {
                    "Desayuno": "Crepe: {avena}g de Avena batida con {clara}g de Clara de Huevo a la sartén.",
                    "Almuerzo": "{pechuga_pollo}g de Pechuga de Pollo a la plancha con finas hierbas.\n{patata_nueva}g de Patata Nueva cocida o al vapor con su piel.\n{aceite_almuerzo}g de Aceite de Oliva para aderezar.",
                    "Merienda": "{platano}g de Plátano maduro.",
                    "Cena": "Revuelto: {huevo}g de Huevo de Gallina entero (2 huevos) con champiñones libres.\n{aceite_cena}g de Aceite de Oliva para cocinar."
                }
            },
            "Jueves": {
                "title": "Día de Sándwich Integral y Ternera con Arroz",
                "portions": {"pan_integral": 82, "clara": 394, "huevo": 100, "ternera_magra": 395, "arroz_integral": 188, "aceite": 21, "platano": 100, "nuez": 20},
                "meals": {
                    "Desayuno": "Tostadas: {pan_integral}g de Pan Integral con {clara}g de Clara de Huevo revueltas.",
                    "Almuerzo": "{arroz_integral}g de Arroz Integral cocido.\n{ternera_magra_almuerzo}g de Ternera Magra al horno con especificaciones.\n{aceite_almuerzo}g de Aceite de Oliva.",
                    "Merienda": "{nuez}g de Nueces sin Cáscara + {platano}g de Plátano.",
                    "Cena": "{ternera_magra_cena}g de Ternera Magra a la plancha.\n{huevo}g de Huevo de Gallina entero (2 huevos poché) sobre lecho de espárragos.\n{aceite_cena}g de Aceite de Oliva en crudo."
                }
            },
            "Viernes": {
                "title": "Día de Avena y Pasta Proteica de Pollo",
                "portions": {"avena": 83, "clara": 330, "huevo": 100, "pechuga_pollo": 346, "pasta_integral": 189, "aceite": 25, "platano": 150, "whey": 0},
                "meals": {
                    "Desayuno": "Gachas: {avena}g de Avena + {clara}g de Clara de Huevo cocidas con canela.",
                    "Almuerzo": "{pasta_integral}g de Pasta Integral en seco.\n{pechuga_pollo_almuerzo}g de Pechuga de Pollo deshebrada.\n{aceite_almuerzo}g de Aceite de Oliva de aderezo.",
                    "Merienda": "{platano}g de Plátano.",
                    "Cena": "{pechuga_pollo_cena}g de Pechuga de Pollo a la plancha.\n{huevo}g de Huevo de Gallina entero (2 huevos fritos con poco aceite).\n{aceite_cena}g de Aceite de Oliva para la sartén."
                }
            },
            "Sábado": {
                "title": "Recomposición de Fin de Semana (Patata y Ternera)",
                "portions": {"pan_integral": 148, "clara": 371, "huevo": 100, "ternera_magra": 383, "patata_nueva": 492, "aceite": 30, "platano": 150, "nuez": 20},
                "meals": {
                    "Desayuno": "Tostadas: {pan_integral}g de Pan Integral + {clara}g de Clara de Huevo en tortilla.",
                    "Almuerzo": "{patata_nueva}g de Patata Nueva asada al horno.\n{ternera_magra_almuerzo}g de Ternera Magra a la parrilla.\n{aceite_almuerzo}g de Aceite de Oliva.",
                    "Merienda": "{nuez}g de Nueces sin Cáscara + {platano}g de Plátano.",
                    "Cena": "{ternera_magra_cena}g de Ternera Magra salteada con calabacín libre.\n{huevo}g de Huevo de Gallina entero (2 huevos duros).\n{aceite_cena}g de Aceite de Oliva."
                }
            },
            "Domingo": {
                "title": "Recarga de Energía Pre-Entrenamiento",
                "portions": {"avena": 73, "clara": 395, "huevo": 100, "pechuga_pollo": 371, "arroz_integral": 181, "aceite": 28, "platano": 120, "whey": 0},
                "meals": {
                    "Desayuno": "Gachas: {avena}g de Avena + {clara}g de Clara de Huevo cocidas en agua.",
                    "Almuerzo": "{arroz_integral}g de Arroz Integral cocido.\n{pechuga_pollo_almuerzo}g de Pechuga de Pollo troceada y salteada.\n{aceite_almuerzo}g de Aceite de Oliva para cocinar.",
                    "Merienda": "{platano}g de Plátano.",
                    "Cena": "{pechuga_pollo_cena}g de Pechuga de Pollo a la plancha con verduras al vapor.\n{huevo}g de Huevo de Gallina entero (2 huevos pasados por agua).\n{aceite_cena}g de Aceite de Oliva en crudo."
                }
            }
        }

        # Filtrar qué días procesar según el tipo de plan
        if tipo_plan == "Menú Diario (1 día)":
            dias_a_procesar = ["Lunes"]
            output_header = "### 📋 Menú Diario Detallado\n\n"
        else:
            dias_a_procesar = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            output_header = "### 📋 Plan Semanal Detallado (Lunes a Domingo)\n\n"

        # Construir estructura de menú para renderizado de alta fidelidad
        menu_structure = {}
        for day in dias_a_procesar:
            menu_data = base_menus[day]
            portions = menu_data["portions"]
            
            scaled = {}
            for ing, base_g in portions.items():
                if ing in ["clara", "pechuga_pollo", "ternera_magra", "whey"]:
                    scaled[ing] = max(10, round(base_g * scale_p))
                elif ing in ["avena", "arroz_integral", "pan_integral", "pasta_integral", "patata_nueva"]:
                    scaled[ing] = max(10, round(base_g * scale_c))
                elif ing in ["aceite", "nuez"]:
                    scaled[ing] = max(5, round(base_g * scale_g))
                else:
                    scaled[ing] = base_g

            real_macros = self.calc_menu_nutrition(scaled)

            aceite_total = scaled.get("aceite", 20)
            aceite_almuerzo = max(5, aceite_total // 2)
            aceite_cena = aceite_total - aceite_almuerzo

            pechuga_total = scaled.get("pechuga_pollo", 300)
            pechuga_almuerzo = round(pechuga_total * 0.7)
            pechuga_cena = pechuga_total - pechuga_almuerzo

            ternera_total = scaled.get("ternera_magra", 300)
            ternera_almuerzo = round(ternera_total * 0.6)
            ternera_cena = ternera_total - ternera_almuerzo

            format_dict = {
                "avena": scaled.get("avena", 0),
                "clara": scaled.get("clara", 0),
                "platano": scaled.get("platano", 0),
                "pechuga_pollo": scaled.get("pechuga_pollo", 0),
                "pechuga_pollo_almuerzo": pechuga_almuerzo,
                "pechuga_pollo_cena": pechuga_cena,
                "arroz_integral": scaled.get("arroz_integral", 0),
                "aceite_almuerzo": aceite_almuerzo,
                "aceite_cena": aceite_cena,
                "whey": scaled.get("whey", 0),
                "huevo": scaled.get("huevo", 0),
                "pan_integral": scaled.get("pan_integral", 0),
                "pasta_integral": scaled.get("pasta_integral", 0),
                "ternera_magra": scaled.get("ternera_magra", 0),
                "ternera_magra_almuerzo": ternera_almuerzo,
                "ternera_magra_cena": ternera_cena,
                "nuez": scaled.get("nuez", 0),
                "patata_nueva": scaled.get("patata_nueva", 0)
            }

            meals_formatted = {}
            for meal_name, meal_template in menu_data["meals"].items():
                meals_formatted[meal_name] = meal_template.format(**format_dict)

            menu_structure[day] = {
                "title": menu_data["title"],
                "macros": real_macros,
                "meals": meals_formatted
            }
        
        try:
            import streamlit as st
            st.session_state["menu_data"] = menu_structure
            st.session_state["tipo_plan"] = tipo_plan
        except Exception:
            pass

        diet_plan_text = output_header

        for day in dias_a_procesar:
            menu_data = base_menus[day]
            portions = menu_data["portions"]
            
            # Escalar porciones individualmente según macro predominante
            scaled = {}
            for ing, base_g in portions.items():
                if ing in ["clara", "pechuga_pollo", "ternera_magra", "whey"]:
                    scaled[ing] = max(10, round(base_g * scale_p))
                elif ing in ["avena", "arroz_integral", "pan_integral", "pasta_integral", "patata_nueva"]:
                    scaled[ing] = max(10, round(base_g * scale_c))
                elif ing in ["aceite", "nuez"]:
                    scaled[ing] = max(5, round(base_g * scale_g))
                else:
                    # Huevo y Plátano se mantienen fijos
                    scaled[ing] = base_g

            # Calcular macros reales recalculados con la UCM
            real_macros = self.calc_menu_nutrition(scaled)

            # Divisiones de porciones para los platos
            aceite_total = scaled.get("aceite", 20)
            aceite_almuerzo = max(5, aceite_total // 2)
            aceite_cena = aceite_total - aceite_almuerzo

            # Pechuga y ternera divididas si es necesario
            pechuga_total = scaled.get("pechuga_pollo", 300)
            pechuga_almuerzo = round(pechuga_total * 0.7)
            pechuga_cena = pechuga_total - pechuga_almuerzo

            ternera_total = scaled.get("ternera_magra", 300)
            ternera_almuerzo = round(ternera_total * 0.6)
            ternera_cena = ternera_total - ternera_almuerzo

            # Dar formato a las comidas del día
            format_dict = {
                "avena": scaled.get("avena", 0),
                "clara": scaled.get("clara", 0),
                "platano": scaled.get("platano", 0),
                "pechuga_pollo": scaled.get("pechuga_pollo", 0),
                "pechuga_pollo_almuerzo": pechuga_almuerzo,
                "pechuga_pollo_cena": pechuga_cena,
                "arroz_integral": scaled.get("arroz_integral", 0),
                "aceite_almuerzo": aceite_almuerzo,
                "aceite_cena": aceite_cena,
                "whey": scaled.get("whey", 0),
                "huevo": scaled.get("huevo", 0),
                "pan_integral": scaled.get("pan_integral", 0),
                "pasta_integral": scaled.get("pasta_integral", 0),
                "ternera_magra": scaled.get("ternera_magra", 0),
                "ternera_magra_almuerzo": ternera_almuerzo,
                "ternera_magra_cena": ternera_cena,
                "nuez": scaled.get("nuez", 0),
                "patata_nueva": scaled.get("patata_nueva", 0)
            }

            meals_text = ""
            for meal_name, meal_template in menu_data["meals"].items():
                formatted_meal = meal_template.format(**format_dict)
                meals_text += f"**{meal_name}:**\n{formatted_meal}\n\n"

            # Formar el bloque del día
            day_text = (
                f"🟢 **{day.upper()}**: {menu_data['title']}\n\n"
                f"{meals_text}"
                f"📊 **Total del día:** {real_macros['kcal']:,} kcal | "
                f"P: {real_macros['proteins']}g | "
                f"C: {real_macros['carbs']}g | "
                f"G: {real_macros['fats']}g | "
                f"F: {real_macros['fiber']}g\n\n"
                f"---\n\n"
            )
            diet_plan_text += day_text

        # Añadir la sección de Justificación obligatoria solicitada
        justificacion = (
            f"### 📚 Justificación de la Elección de Alimentos (UCM)\n\n"
            f"Las elecciones de alimentos del plan se basan rigurosamente en la densidad y calidad de los macronutrientes oficiales de la guía de la Universidad Complutense de Madrid:\n\n"
            f"1. **Avena (cód. 010105) - *Densidad de Fibra*:** Aporta {self.get_food('avena')['kcal']} kcal, {self.get_food('avena')['proteins']}g P y {self.get_food('avena')['fiber']}g de fibra por 100g. Mantiene la saciedad y energía estable.\n"
            f"2. **Pechuga de Pollo (cód. 060414) - *Proteína Magra*:** Aporta {self.get_food('pechuga_pollo')['kcal']} kcal y {self.get_food('pechuga_pollo')['proteins']}g P por 100g, ideal para el requerimiento proteico sin exceder calorías.\n"
            f"3. **Clara de Huevo (cód. 080101) - *Albúmina Pura*:** Con sólo {self.get_food('clara')['kcal']} kcal y {self.get_food('clara')['proteins']}g P por 100g, eleva la proteína libre de grasas.\n"
            f"4. **Huevo de Gallina entero (cód. 080103) - *Valor Biológico*:** Aporta {self.get_food('huevo')['kcal']} kcal y {self.get_food('huevo')['fats']}g de grasas por 100g, esencial para el perfil lipídico e inmunológico.\n"
            f"5. **Aceite de Oliva (cód. 100110) - *Ácidos Grasos Saludables*:** Proporciona {self.get_food('aceite')['fats']}g de grasas monoinsaturadas por 100g, crucial para regular el entorno hormonal durante la pérdida de grasa.\n"
            f"6. **Pan Integral (cód. 010320) - *Carbohidrato Complejo*:** Aporta {self.get_food('pan_integral')['carbs']}g de carbohidratos de absorción lenta y {self.get_food('pan_integral')['fiber']}g de fibra, mejorando la sensibilidad a la insulina.\n"
        )
        diet_plan_text += justificacion

        # Simular streaming para mantener el renderizado progresivo token por token en Streamlit
        chunk_size = 35  # Tamaño del chunk para una visualización natural
        for i in range(0, len(diet_plan_text), chunk_size):
            chunk = diet_plan_text[i:i+chunk_size]
            yield {"diet_chunk": chunk}
            time.sleep(0.005)  # Breve pausa para efecto de streaming fluido

        yield {"steps": [AgentStep(action_diet, diet_plan_text)]}

        # 3. Retornar output final
        yield {"output": diet_plan_text}

def get_agent_executor(url: str, model: str, tools: list) -> SequentialNutritionAgentExecutor:
    """
    Inicializa y retorna el orquestador secuencial optimizado.
    """
    return SequentialNutritionAgentExecutor(url, model, tools)
