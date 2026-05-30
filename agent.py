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
import re
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError
from langchain_core.agents import AgentAction

logger = logging.getLogger("NutriAgent.AgentExecutor")


class MealItem(BaseModel):
    food: str = Field(min_length=1)
    grams: int = Field(gt=0)
    preparation: str = Field(min_length=1)


class DayMeals(BaseModel):
    Desayuno: list[MealItem] = Field(min_length=1)
    Almuerzo: list[MealItem] = Field(min_length=1)
    Merienda: list[MealItem] = Field(min_length=1)
    Cena: list[MealItem] = Field(min_length=1)


class DayPlan(BaseModel):
    day: str = Field(min_length=1)
    title: str = Field(min_length=1)
    meals: DayMeals


class LLMMenuPayload(BaseModel):
    plan_type: str = Field(min_length=1)
    days: list[DayPlan] = Field(min_length=1)
    justification: str = Field(min_length=1)

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
        self.active_replacements = {}
        
        # Cargar base de datos de alimentos de la UCM si existe
        self.food_db = {}
        db_path = str(Path(__file__).resolve().parent / "ucm_food_database.json")
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
        
        # Resolver reemplazos de exclusiones de alimentos recursivamente
        visited = set()
        while name_lower in self.active_replacements:
            if name_lower in visited:
                break
            visited.add(name_lower)
            name_lower = self.active_replacements[name_lower].lower().strip()
            
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

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    def _get_tool_by_name(self, tool_name: str):
        for tool in self.tools:
            name = getattr(tool, "name", "")
            if name == tool_name:
                return tool
        raise ValueError(f"Tool no encontrada: {tool_name}")

    def _extract_json_block(self, text: str) -> dict:
        if isinstance(text, dict):
            return text
        if isinstance(text, list):
            return {"days": text}

        raw = (text or "").strip()
        if not raw:
            raise ValueError("Respuesta vacia del LLM")

        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                raise ValueError("No se encontro JSON en la salida del LLM")
            return json.loads(match.group(0))

    def _validate_payload_with_reason(self, llm_payload: dict, tipo_plan: str) -> tuple[bool, str]:
        if not isinstance(llm_payload, dict):
            return False, "Payload no es objeto JSON."

        try:
            parsed = LLMMenuPayload.model_validate(llm_payload)
        except ValidationError as exc:
            return False, f"Schema Pydantic inválido: {exc}"

        expected_days = 7 if tipo_plan == "Plan Semanal (7 días)" else 1
        if len(parsed.days) != expected_days:
            return False, f"Cantidad de days inválida: esperado {expected_days}, recibido {len(parsed.days)}."

        if expected_days == 7:
            expected_order = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            got_order = [d.day for d in parsed.days]
            if got_order != expected_order:
                return False, f"Orden semanal inválido: recibido {got_order}."

        return True, "OK"

    def _repair_empty_meals(self, llm_payload: dict, catalog: list[dict]) -> dict:
        """
        Evita reintentos lentos cuando el LLM devuelve una comida vacía.
        La IA sigue definiendo el plan, y solo completamos huecos con un alimento UCM permitido.
        """
        if not isinstance(llm_payload, dict):
            return llm_payload

        fallback_food = catalog[0]["name"] if catalog else "Avena"
        required_meals = ["Desayuno", "Almuerzo", "Merienda", "Cena"]

        for day in llm_payload.get("days", []):
            if not isinstance(day, dict):
                continue
            meals = day.setdefault("meals", {})
            if not isinstance(meals, dict):
                day["meals"] = {}
                meals = day["meals"]
            for meal_name in required_meals:
                if not isinstance(meals.get(meal_name), list) or len(meals.get(meal_name, [])) == 0:
                    meals[meal_name] = [{
                        "food": fallback_food,
                        "grams": 100,
                        "preparation": "preparación simple"
                    }]

        return llm_payload

    def _lookup_food_item(self, food_name: str) -> dict:
        if not self.food_db:
            return {"kcal": 0.0, "proteins": 0.0, "carbs": 0.0, "fats": 0.0, "fiber": 0.0, "name": food_name}

        normalized = self._normalize_text(food_name)
        if normalized in self.food_db:
            return self.food_db[normalized]

        for db_key, db_item in self.food_db.items():
            if normalized and (normalized in db_key or db_key in normalized):
                return db_item

        return {"kcal": 0.0, "proteins": 0.0, "carbs": 0.0, "fats": 0.0, "fiber": 0.0, "name": food_name}

    def _parse_user_foods(self, raw: str) -> list:
        return [x.strip() for x in re.split(r"[,;]", raw or "") if x.strip()]

    def _match_food_names(self, foods: list) -> list:
        matched = []
        for item in foods:
            normalized = self._normalize_text(item)
            if normalized in self.food_db:
                name = self.food_db[normalized]["name"]
                if name not in matched:
                    matched.append(name)
                continue

            for db_key, db_item in self.food_db.items():
                if normalized and (normalized in db_key or db_key in normalized):
                    if db_item["name"] not in matched:
                        matched.append(db_item["name"])
                    break
        return matched

    def _food_category(self, food_name: str) -> str:
        text = self._normalize_text(food_name)
        if any(x in text for x in ["pollo", "ternera", "pavo", "atun", "atún", "salmon", "salmón", "merluza", "huevo", "clara", "whey", "queso", "yogur", "yogurt"]):
            return "proteina"
        if any(x in text for x in ["aceite", "nuez", "almendra", "avellana", "pistacho", "aguacate", "mantequilla", "cacahuete", "anacardo"]):
            return "grasa"
        if any(x in text for x in ["platano", "plátano", "manzana", "pera", "naranja", "kiwi", "fresa", "fruta", "melon", "melón", "sandia", "sandía"]):
            return "fruta"
        return "carbohidrato"

    def _compact_food(self, food: dict) -> dict:
        return {
            "name": food.get("name", ""),
            "kcal": food.get("kcal", 0.0),
            "proteins": food.get("proteins", 0.0),
            "carbs": food.get("carbs", 0.0),
            "fats": food.get("fats", 0.0),
        }

    def _matches_any_keyword(self, food_name: str, keywords: list[str]) -> bool:
        normalized = self._normalize_text(food_name)
        return any(keyword in normalized for keyword in keywords)

    def _select_food_candidates(
        self,
        keywords: list[str],
        excluded_set: set[str],
        preferred_set: set[str],
        limit: int = 3,
        sort_by: str = "kcal",
        descending: bool = True
    ) -> list[dict]:
        candidates = []
        for food in self.food_db.values():
            name = food.get("name", "")
            normalized = self._normalize_text(name)
            if normalized in excluded_set:
                continue
            if not self._matches_any_keyword(name, keywords):
                continue
            candidates.append(food)

        candidates.sort(
            key=lambda item: (
                self._normalize_text(item.get("name", "")) not in preferred_set,
                -float(item.get(sort_by, 0.0)) if descending else float(item.get(sort_by, 0.0)),
                item.get("name", "")
            )
        )

        selected = []
        seen = set()
        for food in candidates:
            normalized = self._normalize_text(food.get("name", ""))
            if normalized and normalized not in seen:
                seen.add(normalized)
                selected.append(self._compact_food(food))
            if len(selected) >= limit:
                break
        return selected

    def _build_catalog_for_llm(self, alimentos_preferidos: str, alimentos_excluidos: str) -> tuple:
        preferred_raw = self._parse_user_foods(alimentos_preferidos)
        excluded_raw = self._parse_user_foods(alimentos_excluidos)

        preferred = self._match_food_names(preferred_raw)
        excluded = self._match_food_names(excluded_raw)
        excluded_set = {self._normalize_text(x) for x in excluded}
        preferred_set = {self._normalize_text(x) for x in preferred}

        preferred_foods = []
        for food_name in preferred:
            food = self._lookup_food_item(food_name)
            normalized = self._normalize_text(food.get("name", ""))
            if normalized and normalized not in excluded_set:
                preferred_foods.append(self._compact_food(food))

        selected = []
        selected.extend(preferred_foods[:5])
        selected.extend(self._select_food_candidates(["pechuga de pollo", "pollo", "huevo", "clara"], excluded_set, preferred_set, limit=2, sort_by="proteins"))
        selected.extend(self._select_food_candidates(["arroz integral", "avena", "patata", "pan integral"], excluded_set, preferred_set, limit=2, sort_by="carbs"))
        selected.extend(self._select_food_candidates(["aceite de oliva", "aguacate"], excluded_set, preferred_set, limit=1, sort_by="fats"))

        unique_catalog = []
        seen = set()
        for food in selected:
            normalized = self._normalize_text(food.get("name", ""))
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_catalog.append(food)
            if len(unique_catalog) >= 10:
                break

        logger.info(f"Catálogo compacto para LLM: {len(unique_catalog)} alimentos.")
        return unique_catalog, preferred, excluded

    def _to_menu_data(self, llm_payload: dict) -> tuple:
        try:
            parsed_payload = LLMMenuPayload.model_validate(llm_payload)
        except ValidationError as exc:
            raise ValueError(f"Payload LLM no cumple schema Pydantic: {exc}") from exc

        days = [d.model_dump() for d in parsed_payload.days]

        menu_data = {}
        for day_obj in days:
            day_name = day_obj.get("day", "Día")
            title = day_obj.get("title", "Plan nutricional")
            meals = day_obj.get("meals", {})
            if not isinstance(meals, dict):
                continue

            meal_lines = {}
            grams_per_food = {}
            for meal_name in ["Desayuno", "Almuerzo", "Merienda", "Cena"]:
                entries = meals.get(meal_name, [])
                if not isinstance(entries, list):
                    entries = []
                lines = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    food_name = str(entry.get("food", "")).strip()
                    if not food_name:
                        continue
                    try:
                        grams = max(1, int(float(entry.get("grams", 0))))
                    except Exception:
                        grams = 1
                    prep = str(entry.get("preparation", "")).strip()
                    line = f"{grams}g de {food_name}"
                    if prep:
                        line += f" ({prep})"
                    lines.append(line)
                    grams_per_food[food_name] = grams_per_food.get(food_name, 0) + grams
                meal_lines[meal_name] = "\n".join(lines) if lines else "Sin propuesta."

            macros = self.calc_menu_nutrition(grams_per_food)
            menu_data[day_name] = {
                "title": title,
                "meals": meal_lines,
                "macros": macros,
            }

        if not menu_data:
            raise ValueError("No se pudo construir menu_data a partir del JSON del LLM")

        return menu_data, parsed_payload.justification

    def _build_stream_text(self, menu_data: dict, justification: str) -> str:
        lines = []
        if len(menu_data) > 1:
            lines.append("### 📋 Plan Semanal Detallado (Lunes a Domingo)\n")
        else:
            only_day = list(menu_data.keys())[0]
            lines.append(f"### 📋 Menú Diario Detallado ({only_day.upper()})\n")

        for day, info in menu_data.items():
            lines.append(f"#### {day}: {info.get('title', 'Plan nutricional')}")
            meals = info.get("meals", {})
            for meal_name in ["Desayuno", "Almuerzo", "Merienda", "Cena"]:
                lines.append(f"- **{meal_name}:**")
                meal_content = meals.get(meal_name, "Sin propuesta.")
                for row in [x.strip() for x in meal_content.split("\n") if x.strip()]:
                    lines.append(f"  - {row}")
            m = info.get("macros", {})
            lines.append(
                f"- Totales estimados: {m.get('kcal', 0)} kcal | "
                f"{m.get('proteins', 0)}g P | {m.get('carbs', 0)}g C | "
                f"{m.get('fats', 0)}g G | {m.get('fiber', 0)}g fibra\n"
            )

        lines.append("### 📚 Justificación")
        lines.append(justification or "El menú se ajusta a objetivos calóricos, macros y preferencias.")
        lines.append("")
        return "\n".join(lines)

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

        # 1. Ejecutar calcular_macros_tool (llamada real a tool)
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
        calc_tool = self._get_tool_by_name("calcular_macros_tool")
        calc_raw = calc_tool.invoke(action_calc.tool_input)
        if isinstance(calc_raw, str):
            macros_res = json.loads(calc_raw)
        else:
            macros_res = dict(calc_raw)
        observation_calc = json.dumps(macros_res, indent=2, ensure_ascii=False)
        yield {"steps": [AgentStep(action_calc, observation_calc)]}

        # 2. Ejecutar generar_dieta_tool (LLM + contexto UCM JSON)
        calorias = macros_res["calorias_objetivo"]
        macros_dict = macros_res["macros"]
        catalog, preferred_matched, excluded_matched = self._build_catalog_for_llm(
            alimentos_preferidos=alimentos_preferidos,
            alimentos_excluidos=alimentos_excluidos,
        )

        action_diet = AgentAction(
            tool="generar_dieta_tool",
            tool_input={
                "calorias": calorias,
                "macros": macros_dict,
                "alimentos_incluidos": alimentos_preferidos,
                "alimentos_excluidos": alimentos_excluidos,
                "tipo_plan": tipo_plan,
                "contexto_alimentos_json": json.dumps(catalog, ensure_ascii=False),
                "repair_instruction": ""
            },
            log=f"Generando propuesta de {tipo_plan} adaptada a requerimientos y preferencias alimentarias..."
        )
        yield {"actions": [action_diet]}

        diet_tool = self._get_tool_by_name("generar_dieta_tool")
        llm_payload = {}
        llm_raw = ""
        llm_attempts_debug = []
        max_attempts = 1
        for attempt in range(1, max_attempts + 1):
            llm_raw = diet_tool.invoke(action_diet.tool_input)
            raw_text = llm_raw if isinstance(llm_raw, str) else json.dumps(llm_raw, ensure_ascii=False)
            llm_payload = {}
            valid = False
            reason = "Sin validar."

            try:
                llm_payload = self._extract_json_block(llm_raw)
                llm_payload = self._repair_empty_meals(llm_payload, catalog)
                if isinstance(llm_payload, dict) and llm_payload.get("error"):
                    reason = str(llm_payload["error"])
                    valid = False
                    llm_attempts_debug.append({
                        "attempt": attempt,
                        "valid": valid,
                        "reason": reason,
                        "raw_response": raw_text
                    })
                    logger.error(f"Error invocando LLM: {reason}")
                    break
                valid, reason = self._validate_payload_with_reason(llm_payload, tipo_plan)
            except Exception as parse_exc:
                reason = f"No se pudo parsear JSON: {parse_exc}"
                valid = False

            llm_attempts_debug.append({
                "attempt": attempt,
                "valid": valid,
                "reason": reason,
                "raw_response": raw_text
            })

            if valid:
                if attempt > 1:
                    logger.info(f"LLM devolvio JSON valido en reintento {attempt}/{max_attempts}.")
                break

            logger.warning(
                f"JSON LLM invalido en intento {attempt}/{max_attempts}: "
                f"{reason}"
            )
            if attempt < max_attempts:
                expected_days = 7 if tipo_plan == "Plan Semanal (7 días)" else 1
                action_diet.tool_input["repair_instruction"] = (
                    "Tu respuesta anterior no cumplio schema Pydantic. "
                    f"Devuelve JSON con days de longitud exacta {expected_days}, "
                    "cada day con meals completas (Desayuno/Almuerzo/Merienda/Cena), "
                    "y todos los items con food:string, grams:int>0, preparation:string."
                )

        observation_diet = json.dumps(llm_payload, indent=2, ensure_ascii=False)
        yield {"steps": [AgentStep(action_diet, observation_diet)]}

        try:
            menu_data, llm_justification = self._to_menu_data(llm_payload)
        except Exception as parse_error:
            logger.error(f"No se pudo construir menu_data desde LLM JSON: {parse_error}")
            fallback_day = "Lunes"
            menu_data = {
                fallback_day: {
                    "title": "Plan de contingencia",
                    "meals": {
                        "Desayuno": "Sin propuesta válida del LLM.",
                        "Almuerzo": "Sin propuesta válida del LLM.",
                        "Merienda": "Sin propuesta válida del LLM.",
                        "Cena": "Sin propuesta válida del LLM.",
                    },
                    "macros": {"kcal": 0.0, "proteins": 0.0, "carbs": 0.0, "fats": 0.0, "fiber": 0.0},
                }
            }
            llm_justification = (
                "El modelo no devolvió un JSON con el formato esperado. "
                "Revisa la disponibilidad del modelo y vuelve a intentar."
            )
        try:
            import streamlit as st
            st.session_state["menu_data"] = menu_data
            st.session_state["tipo_plan"] = tipo_plan
            st.session_state["llm_menu_json"] = llm_payload
            st.session_state["llm_raw_attempts"] = llm_attempts_debug
        except Exception:
            pass

        pref_text = ", ".join(preferred_matched) if preferred_matched else "No se detectaron preferencias exactas en UCM."
        excl_text = ", ".join(excluded_matched) if excluded_matched else "No se detectaron exclusiones exactas en UCM."
        agent_text = self._build_stream_text(
            menu_data=menu_data,
            justification=(
                f"{llm_justification}\n\n"
                f"- Preferencias UCM detectadas: {pref_text}\n"
                f"- Exclusiones UCM detectadas: {excl_text}"
            ).strip(),
        )

        chunk_size = 35
        for i in range(0, len(agent_text), chunk_size):
            yield {"diet_chunk": agent_text[i:i + chunk_size]}
            time.sleep(0.005)

        yield {"output": agent_text}
        return

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
        import random
        if tipo_plan == "Menú Diario (1 día)":
            # Para no hacer siempre el mismo menú, seleccionamos un día aleatorio de la semana
            dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            dia_elegido = random.choice(dias)
            dias_a_procesar = [dia_elegido]
            output_header = f"### 📋 Menú Diario Detallado ({dia_elegido.upper()})\n\n"
        else:
            dias_a_procesar = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            output_header = "### 📋 Plan Semanal Detallado (Lunes a Domingo)\n\n"

        # Mapeo de nombres comunes en español para comprobación robusta
        common_names = {
            "avena": "avena",
            "clara": "clara de huevo",
            "huevo": "huevo de gallina entero",
            "pechuga_pollo": "pechuga de pollo",
            "arroz_integral": "arroz integral",
            "aceite": "aceite de oliva",
            "pan_integral": "pan integral",
            "platano": "plátano",
            "ternera_magra": "ternera magra",
            "pasta_integral": "pasta integral",
            "nuez": "nueces sin cáscara",
            "patata_nueva": "patata nueva",
            "whey": "proteína whey"
        }

        # 1. Parsear inclusiones y exclusiones del usuario
        preferred_items = [x.strip() for x in re.split(r'[,;]', alimentos_preferidos) if x.strip()]
        excluded_items = [x.strip() for x in re.split(r'[,;]', alimentos_excluidos) if x.strip()]

        # Encontrar los nombres exactos en la base de datos para los alimentos preferidos y excluidos
        preferred_matched = []
        for item in preferred_items:
            item_lower = item.lower().strip()
            matched_name = None
            if item_lower in self.food_db:
                matched_name = self.food_db[item_lower]["name"]
            else:
                for db_key, db_item in self.food_db.items():
                    if item_lower in db_key:
                        matched_name = db_item["name"]
                        break
            if matched_name and matched_name not in preferred_matched:
                preferred_matched.append(matched_name)

        excluded_matched = []
        for item in excluded_items:
            item_lower = item.lower().strip()
            matched_name = None
            if item_lower in self.food_db:
                matched_name = self.food_db[item_lower]["name"]
            else:
                for db_key, db_item in self.food_db.items():
                    if item_lower in db_key:
                        matched_name = db_item["name"]
                        break
            if matched_name and matched_name not in excluded_matched:
                excluded_matched.append(matched_name)

        # Helper para verificar si un alimento está excluido
        def is_excluded(db_name: str) -> bool:
            db_name_lower = db_name.lower().strip()
            for excl in excluded_matched:
                if excl.lower().strip() in db_name_lower:
                    return True
            # Comprobar también con el identificador del ingrediente si aplica
            common = common_names.get(db_name, db_name_lower)
            for excl in excluded_matched:
                if excl.lower().strip() in common:
                    return True
            return False

        # Helper para clasificar alimentos en las 4 categorías principales (usado en la tabla)
        def classify_food(food_name: str) -> str:
            food_name_lower = food_name.lower().strip()
            food_item = self.food_db.get(food_name_lower)
            if not food_item:
                return "carbohidratos"
            name_lower = food_item["name"].lower()
            if any(x in name_lower for x in ["aceite", "mantequilla", "margarina", "nuez", "nueces", "almendra", "pistacho", "avellana", "cacahuete", "anacardo", "semilla", "aguacate"]):
                return "grasas"
            if any(x in name_lower for x in ["plátano", "platano", "manzana", "pera", "naranja", "fresa", "fruta", "uva", "piña", "kiwi", "limón", "limon", "mandarina", "melocotón", "melocoton", "cereza", "ciruela", "higo", "dátil", "datil", "mango"]):
                return "frutas"
            if any(x in name_lower for x in ["pollo", "pavo", "ternera", "cerdo", "vaca", "buey", "atún", "atun", "salmón", "salmon", "merluza", "bacalao", "pescado", "marisco", "pulpo", "calamar", "clara", "huevo", "queso", "yogur", "leche", "suero", "whey"]):
                return "proteinas"
            p = food_item.get("proteins", 0)
            c = food_item.get("carbs", 0)
            g = food_item.get("fats", 0)
            if g > p and g > c:
                return "grasas"
            if p > c and p > g:
                return "proteinas"
            return "carbohidratos"

        # Helper para clasificar alimentos en categorías culinarias detalladas (para evitar alcachofas de desayuno)
        def classify_food_detailed(food_name: str) -> str:
            food_name_lower = food_name.lower().strip()
            food_item = self.food_db.get(food_name_lower)
            if not food_item:
                return "desconocido"
            
            name_lower = food_item["name"].lower()
            
            # 1. Frutas
            if any(x in name_lower for x in ["plátano", "platano", "manzana", "pera", "naranja", "fresa", "fruta", "uva", "piña", "kiwi", "limón", "limon", "mandarina", "melocotón", "melocoton", "cereza", "ciruela", "higo", "dátil", "datil", "mango", "arándano", "arandano", "melón", "melon", "sandía", "sandia", "albaricoque", "pomelo"]):
                return "frutas"
                
            # 2. Cereales de desayuno / Avena
            if any(x in name_lower for x in ["avena", "gofio", "muesli", "cereal de desayuno", "salvado de avena"]):
                return "cereales_desayuno"
                
            # 3. Panes
            if any(x in name_lower for x in ["pan integral", "pan de avena", "pan de centeno", "pan de trigo", "tostas", "biscote"]):
                return "panes"
                
            # 4. Grasas saludables (frutos secos, semillas, aguacate)
            if any(x in name_lower for x in ["nuez", "nueces", "almendra", "pistacho", "avellana", "cacahuete", "anacardo", "semilla", "aguacate", "pipas"]):
                return "frutos_secos"
                
            # 5. Grasas aderezo (aceites)
            if any(x in name_lower for x in ["aceite", "mantequilla", "margarina"]):
                return "grasas_aderezo"
                
            # 6. Proteínas suplemento / desayuno
            if any(x in name_lower for x in ["suero", "whey", "proteína de suero", "clara de huevo", "clara", "requesón", "requeson", "queso fresco batido", "yogur griego"]):
                return "proteinas_desayuno"
                
            # 7. Proteínas comida principal
            if any(x in name_lower for x in ["pollo", "pavo", "ternera", "cerdo", "vaca", "buey", "atún", "atun", "salmón", "salmon", "merluza", "bacalao", "pescado", "marisco", "pulpo", "calamar", "huevo", "queso", "jamón", "jamon", "lomo", "emperador", "trucha"]):
                return "proteinas_comida"
                
            # 8. Carbohidratos salados / legumbres / verduras
            if any(x in name_lower for x in ["arroz", "pasta", "patata", "boniato", "batata", "lenteja", "garbanzo", "alubia", "judía", "judia", "alcachofa", "esparrago", "verdura", "brócoli", "brocoli", "coliflor", "espinaca", "acelga", "calabacín", "calabacin", "zanahoria", "guisante", "maíz", "maiz", "quinoa", "cuscús", "cuscus"]):
                return "carbos_salados"
                
            p = food_item.get("proteins", 0)
            c = food_item.get("carbs", 0)
            g = food_item.get("fats", 0)
            
            if g > p and g > c:
                return "frutos_secos"
            if p > c and p > g:
                return "proteinas_comida"
            return "carbos_salados"

        # Clasificar los alimentos preferidos no excluidos por categoría detallada
        pref_by_detailed_cat = {
            "cereales_desayuno": [],
            "frutas": [],
            "panes": [],
            "frutos_secos": [],
            "grasas_aderezo": [],
            "proteinas_desayuno": [],
            "proteinas_comida": [],
            "carbos_salados": []
        }
        for item in preferred_matched:
            if not is_excluded(item):
                cat = classify_food_detailed(item)
                if cat in pref_by_detailed_cat:
                    pref_by_detailed_cat[cat].append(item)

        # Nombre oficial de base de datos por defecto para cada identificador base
        default_db_names = {
            "avena": "Avena",
            "clara": "Clara de huevo",
            "huevo": "Huevo de gallina",
            "pechuga_pollo": "Pechuga de pollo",
            "arroz_integral": "Arroz integral",
            "aceite": "Aceite de oliva",
            "pan_integral": "Pan integral",
            "platano": "Plátano",
            "ternera_magra": "Ternera magra",
            "pasta_integral": "Pasta integral",
            "nuez": "Nuez sin cascara",
            "patata_nueva": "Patata nueva",
            "whey": "whey"
        }

        # Mapear cada base_id a su categoría detallada
        slot_categories = {
            "avena": "cereales_desayuno",
            "platano": "frutas",
            "pan_integral": "panes",
            "nuez": "frutos_secos",
            "aceite": "grasas_aderezo",
            "clara": "proteinas_desayuno",
            "whey": "proteinas_desayuno",
            "pechuga_pollo": "proteinas_comida",
            "ternera_magra": "proteinas_comida",
            "arroz_integral": "carbos_salados",
            "pasta_integral": "carbos_salados",
            "patata_nueva": "carbos_salados"
        }

        # Agrupaciones por defecto de los identificadores para fallbacks cuando no hay preferidos
        default_alternatives = {
            "cereales_desayuno": ["avena"],
            "frutas": ["platano"],
            "panes": ["pan_integral"],
            "frutos_secos": ["nuez"],
            "grasas_aderezo": ["aceite"],
            "proteinas_desayuno": ["clara", "whey"],
            "proteinas_comida": ["pechuga_pollo", "ternera_magra"],
            "carbos_salados": ["arroz_integral", "pasta_integral", "patata_nueva"]
        }

        self.active_replacements = {}
        category_indices = {cat: 0 for cat in pref_by_detailed_cat.keys()}

        # 2. Asignar reemplazos para cada categoría detallada de manera inteligente
        for base_id, cat in slot_categories.items():
            prefs = pref_by_detailed_cat[cat]
            if prefs:
                idx = category_indices[cat]
                repl = prefs[idx % len(prefs)]
                category_indices[cat] += 1
                # Solo lo agregamos si difiere del valor por defecto, o si el por defecto está excluido
                if repl.lower().strip() != default_db_names[base_id].lower().strip() or is_excluded(default_db_names[base_id]):
                    self.active_replacements[base_id] = repl
            else:
                # Si no hay preferidos en esta categoría detailed, gestionamos únicamente las exclusiones
                if is_excluded(default_db_names[base_id]):
                    # Buscar un ingrediente alternativo de la misma categoría que no esté excluido
                    repl = base_id
                    for alt in default_alternatives[cat]:
                        if not is_excluded(default_db_names[alt]):
                            repl = default_db_names[alt]
                            break
                    if repl != base_id:
                        self.active_replacements[base_id] = repl

        # Manejo especial para Huevo Mixto si está excluido
        if is_excluded("Huevo de gallina"):
            if not is_excluded("Clara de huevo"):
                self.active_replacements["huevo"] = "Clara de huevo"
            else:
                if pref_by_detailed_cat["proteinas_comida"]:
                    self.active_replacements["huevo"] = pref_by_detailed_cat["proteinas_comida"][0]
                else:
                    for alt in default_alternatives["proteinas_comida"]:
                        if not is_excluded(default_db_names[alt]):
                            self.active_replacements["huevo"] = default_db_names[alt]
                            break

        friendly_names = {
            "avena": "Avena cocida",
            "clara": "Clara de Huevo",
            "huevo": "Huevo entero",
            "pechuga_pollo": "Pechuga de Pollo a la plancha",
            "arroz_integral": "Arroz Integral cocido",
            "aceite": "Aceite de Oliva en crudo",
            "pan_integral": "Pan Integral",
            "platano": "Plátano",
            "ternera_magra": "Ternera Magra a la plancha",
            "pasta_integral": "Pasta Integral cocida",
            "nuez": "Nueces sin Cáscara",
            "patata_nueva": "Patata Nueva cocida",
            "whey": "Proteína de Suero (Whey)"
        }

        text_replacements = {
            "avena": {
                "patterns": ["Avena batida", "Avena cocida", "Avena"]
            },
            "clara": {
                "patterns": ["Clara de Huevo cocidas a fuego lento", "Clara de Huevo en tortilla", "Clara de Huevo a la sartén", "Clara de Huevo revueltas", "Clara de Huevo cocidas con canela", "Clara de Huevo cocidas en agua", "Clara de Huevo"]
            },
            "huevo": {
                "patterns": [
                    "Huevo de Gallina entero (2 huevos medianos)",
                    "Huevo de Gallina entero (2 huevos cocidos)",
                    "Huevo de Gallina entero (2 huevos)",
                    "Huevo de Gallina entero (2 huevos poché)",
                    "Huevo de Gallina entero (2 huevos fritos con poco aceite)",
                    "Huevo de Gallina entero (2 huevos duros)",
                    "Huevo de Gallina entero (2 huevos pasados por agua)",
                    "Huevo de Gallina entero"
                ]
            },
            "pechuga_pollo": {
                "patterns": ["Pechuga de Pollo a la plancha con finas hierbas", "Pechuga de Pollo deshebrada", "Pechuga de Pollo troceada y salteada", "Pechuga de Pollo a la plancha con verduras al vapor", "Pechuga de Pollo a la plancha", "Pechuga de Pollo"]
            },
            "arroz_integral": {
                "patterns": ["Arroz Integral cocido (pesado en seco)", "Arroz Integral cocido", "Arroz Integral"]
            },
            "aceite": {
                "patterns": ["Aceite de Oliva en crudo para aderezar", "Aceite de Oliva para cocinar", "Aceite de Oliva para la sartén", "Aceite de Oliva en crudo", "Aceite de Oliva"]
            },
            "pan_integral": {
                "patterns": ["Pan Integral", "Pan integral"]
            },
            "platano": {
                "patterns": ["Plátano en rodajas por encima", "Plátano maduro", "Plátano"]
            },
            "ternera_magra": {
                "patterns": ["Ternera Magra picada y hecha a la plancha", "Ternera Magra con ensalada verde libre de aderezo", "Ternera Magra al horno con especificaciones", "Ternera Magra a la plancha", "Ternera Magra a la parrilla", "Ternera Magra salteada con calabacín libre", "Ternera Magra"]
            },
            "pasta_integral": {
                "patterns": ["Pasta Integral (en seco) salteada", "Pasta Integral en seco", "Pasta Integral"]
            },
            "nuez": {
                "patterns": ["Nueces sin Cáscara", "Nueces"]
            },
            "patata_nueva": {
                "patterns": ["Patata Nueva cocida o al vapor con su piel", "Patata Nueva asada al horno", "Patata Nueva"]
            },
            "whey": {
                "patterns": ["Proteína de Suero (Whey) disuelta en agua", "Proteína de Suero (Whey)", "Proteína Whey"]
            }
        }

        # Generar menús activos con sustituciones de texto aplicadas
        import copy
        active_menus = copy.deepcopy(base_menus)
        for day, menu in active_menus.items():
            for ing, repl in self.active_replacements.items():
                friendly_repl = friendly_names.get(repl, repl.replace("_", " "))
                for meal_name, template in list(menu["meals"].items()):
                    # Conservar marcadores de posición usando tokens temporales
                    placeholders = re.findall(r"\{[a-zA-Z0-9_]+\}", template)
                    temp_template = template
                    for idx, ph in enumerate(placeholders):
                        temp_template = temp_template.replace(ph, f"__PH_{idx}__")
                    
                    new_template = temp_template
                    patterns = text_replacements.get(ing, {}).get("patterns", [ing])
                    for pattern in patterns:
                        new_template = new_template.replace(pattern, friendly_repl)
                        new_template = new_template.replace(pattern.lower(), friendly_repl.lower())
                        new_template = new_template.replace(pattern.capitalize(), friendly_repl.capitalize())
                    if ing == "huevo":
                        new_template = new_template.replace("Tortilla: ", "Plato: ").replace("Revuelto: ", "Plato: ")
                    if ing == "pan_integral":
                        new_template = new_template.replace("Sándwich: ", "Tostas: ")
                    
                    # Restaurar marcadores de posición originales
                    for idx, ph in enumerate(placeholders):
                        new_template = new_template.replace(f"__PH_{idx}__", ph)
                    menu["meals"][meal_name] = new_template

                title = menu["title"]
                placeholders_title = re.findall(r"\{[a-zA-Z0-9_]+\}", title)
                temp_title = title
                for idx, ph in enumerate(placeholders_title):
                    temp_title = temp_title.replace(ph, f"__PH_{idx}__")
                
                patterns = text_replacements.get(ing, {}).get("patterns", [ing])
                for pattern in patterns:
                    temp_title = temp_title.replace(pattern, friendly_repl)
                    temp_title = temp_title.replace(pattern.lower(), friendly_repl.lower())
                    temp_title = temp_title.replace(pattern.capitalize(), friendly_repl.capitalize())
                
                for idx, ph in enumerate(placeholders_title):
                    temp_title = temp_title.replace(f"__PH_{idx}__", ph)
                menu["title"] = temp_title

        # Construir estructura de menú para renderizado de alta fidelidad
        menu_structure = {}
        for day in dias_a_procesar:
            menu_data = active_menus[day]
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
            menu_data = active_menus[day]
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

        # Añadir la sección de Justificación obligatoria en formato tabla (UCM)
        def get_food_justification(food_item: dict) -> tuple:
            name = food_item["name"]
            cat = classify_food(name)
            
            # Valores por defecto para mantener consistencia académica
            original_justifications = {
                "avena": ("*Densidad de Fibra*", "Mantiene la saciedad y energía estable."),
                "pechuga de pollo": ("*Proteína Magra*", "Ideal para requerimiento proteico sin exceder calorías."),
                "clara de huevo": ("*Albúmina Pura*", "Eleva la proteína libre de grasas."),
                "huevo de gallina": ("*Valor Biológico*", "Esencial para el perfil lipídico e inmunológico."),
                "aceite de oliva": ("*Ácidos Grasos Saludables*", "Crucial para regular el entorno hormonal durante la pérdida de grasa."),
                "pan integral": ("*Carbohidrato Complejo*", "Carbohidrato de absorción lenta que mejora la sensibilidad a la insulina."),
                "ternera magra": ("*Proteína de Reemplazo*", "Excelente alternativa rica en hierro y zinc (en lugar de pollo)."),
                "nuez sin cascara": ("*Grasas de Reemplazo*", "Excelente fuente de Omega-3 vegetal (en lugar de aceite)."),
                "patata nueva": ("*Carbohidrato de Fácil Digestión*", "Excelente fuente de energía post-entrenamiento."),
                "pasta integral": ("*Carbohidrato de Rendimiento*", "Energía sostenida y recarga de glucógeno muscular."),
                "plátano": ("*Fructosa y Potasio*", "Aporte rápido de glucógeno y prevención de calambres.")
            }
            
            name_lower = name.lower()
            for key, val in original_justifications.items():
                if key in name_lower or name_lower in key:
                    return val
            
            p = food_item.get("proteins", 0)
            c = food_item.get("carbs", 0)
            g = food_item.get("fats", 0)
            f = food_item.get("fiber", 0)
            
            if cat == "proteinas":
                return (f"*Fuente de Proteína ({p}g)*", f"Aporte de aminoácidos esenciales para la síntesis de tejido muscular ({name}).")
            elif cat == "grasas":
                return (f"*Aporte de Lípidos ({g}g)*", f"Ácidos grasos esenciales para la síntesis hormonal y absorción de vitaminas ({name}).")
            elif cat == "frutas":
                return (f"*Vitaminas y Fibra*", f"Aporte de micronutrientes, hidratación y carbohidratos de asimilación natural ({name}).")
            else:
                if f > 3:
                    return (f"*Carbohidrato Alto en Fibra ({f}g)*", f"Energía sostenida, control glucémico y mejora del tránsito digestivo ({name}).")
                return (f"*Fuente de Energía Líquida/Compleja*", f"Aporte energético principal para el mantenimiento del glucógeno ({name}).")

        justificacion = (
            f"### 📚 Justificación de la Elección de Alimentos (UCM)\n\n"
            f"Las elecciones de alimentos del plan se basan rigurosamente en la densidad y calidad de los macronutrientes oficiales de la guía de la Universidad Complutense de Madrid:\n\n"
            f"| Alimento | Código UCM | Parámetro Destacado | Aporte por 100g | Función en el Plan |\n"
            f"| :--- | :--- | :--- | :--- | :--- |\n"
        )
        
        # Recopilar alimentos activos de forma ordenada y sin duplicados
        active_foods = {}
        for day in dias_a_procesar:
            menu_data = active_menus[day]
            portions = menu_data["portions"]
            for ing, base_g in portions.items():
                if base_g > 0:
                    db_item = self.get_food(ing)
                    if db_item and "name" in db_item:
                        active_foods[db_item["name"].lower().strip()] = db_item
                        
        for db_name, item in sorted(active_foods.items()):
            param, funcion = get_food_justification(item)
            code = item.get("code", "N/A")
            kcal = item.get("kcal", 0)
            p = item.get("proteins", 0)
            c = item.get("carbs", 0)
            g = item.get("fats", 0)
            f = item.get("fiber", 0)
            
            cat = classify_food(item["name"])
            if cat == "proteinas":
                aportes = f"{kcal} kcal, {p}g P"
            elif cat == "carbohidratos":
                aportes = f"{kcal} kcal, {c}g C, {f}g F"
            elif cat == "grasas":
                aportes = f"{kcal} kcal, {g}g G"
            else:
                aportes = f"{kcal} kcal, {c}g C"
                
            justificacion += f"| **{item['name']}** | `{code}` | {param} | {aportes} | {funcion} |\n"
            
        justificacion += "\n"
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
