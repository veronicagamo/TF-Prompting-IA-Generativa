# -*- coding: utf-8 -*-
"""
Aplicación Streamlit: Agente Nutricional Inteligente
Carga modularizada. Importa lógica de 'tools.py' y 'agent.py'.
Soporte para streaming de pasos del agente en tiempo real.
"""

import os
import warnings

# Silenciar logs ruidosos de bibliotecas de terceros y advertencias
os.environ["NUMEXPR_MAX_THREADS"] = "16"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # Silencia avisos de TensorFlow
warnings.filterwarnings("ignore", category=UserWarning)  # Silencia avisos de PyTorch/CUDA

import streamlit as st
import requests
import json
import traceback
import logging

# Configurar logging principal a nivel WARNING para evitar spam de librerías
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("nutriagent.log", encoding="utf-8")
    ]
)
# Configurar nuestro logger específico a nivel INFO para la aplicación
logger = logging.getLogger("NutriAgent")
logger.setLevel(logging.INFO)

# Importar lógica local
from tools import calcular_macros_core, calcular_macros_tool, generar_dieta_tool
from agent import get_agent_executor

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA Y ESTILOS CSS
# ==========================================

st.set_page_config(
    page_title="NutriAgent AI - Agente Nutricional Inteligente",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para una interfaz premium y moderna
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    /* Configuración de fuente global */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Degradados en títulos */
    .title-gradient {
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 50%, #FF4D4D 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.2rem;
        margin-bottom: 0.2rem;
        text-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    .subtitle-gradient {
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        background: linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid rgba(124, 58, 237, 0.1);
        padding-bottom: 5px;
    }
    
    /* Tarjetas y Contenedores */
    .card {
        background: rgba(30, 41, 59, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        margin-bottom: 20px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        transition: all 0.3s ease !important;
    }
    
    .card:hover {
        border-color: rgba(239, 68, 68, 0.2) !important;
        box-shadow: 0 12px 40px 0 rgba(239, 68, 68, 0.08) !important;
        transform: translateY(-2px) !important;
    }
    
    /* Colores personalizados para tarjetas de métricas */
    .metric-card-kcal {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, rgba(239, 68, 68, 0.15) 100%) !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
    }
    .metric-card-proteins {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(16, 185, 129, 0.15) 100%) !important;
        border: 1px solid rgba(16, 185, 129, 0.2) !important;
    }
    .metric-card-fats {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.05) 0%, rgba(245, 158, 11, 0.15) 100%) !important;
        border: 1px solid rgba(245, 158, 11, 0.2) !important;
    }
    .metric-card-carbs {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(59, 130, 246, 0.15) 100%) !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
    }
    
    .metric-label {
        font-size: 0.95rem !important;
        color: #9CA3AF !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    
    .metric-value {
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        font-family: 'Outfit', sans-serif !important;
        margin-bottom: 4px !important;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    section[data-testid="stSidebar"] h3 {
        font-family: 'Outfit', sans-serif !important;
        color: #F8FAFC !important;
        font-weight: 700 !important;
    }
    
    /* Input and form styling */
    div[data-testid="stForm"] {
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 16px !important;
        background-color: rgba(15, 23, 42, 0.4) !important;
        padding: 20px !important;
    }
    
    /* Estilo del botón principal */
    .stButton>button {
        background: linear-gradient(135deg, #E02424 0%, #FF8E53 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        padding: 12px 30px !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(224, 36, 36, 0.3) !important;
        width: 100% !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 22px rgba(224, 36, 36, 0.4) !important;
        background: linear-gradient(135deg, #FF8E53 0%, #E02424 100%) !important;
    }
    
    /* Barra de progreso de Macros */
    .macro-progress-container {
        margin-bottom: 15px;
    }
    .macro-label-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.9rem;
        margin-bottom: 5px;
        font-weight: 600;
    }
    .macro-bar-outer {
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        height: 12px;
        width: 100%;
        overflow: hidden;
    }
    .macro-bar-inner {
        height: 100%;
        border-radius: 10px;
    }
    
    /* Badges de estado de conexión */
    .badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-online {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-offline {
        background-color: rgba(239, 68, 68, 0.2);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    /* Estilos de tarjetas de comidas */
    .meal-card {
        background: rgba(30, 41, 59, 0.45) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 18px !important;
        margin-bottom: 15px !important;
        min-height: 200px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15) !important;
        transition: all 0.2s ease !important;
    }
    .meal-card:hover {
        border-color: rgba(239, 68, 68, 0.25) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 24px rgba(239, 68, 68, 0.12) !important;
    }
    .meal-title {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        margin-bottom: 12px !important;
        color: #F8FAFC !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
        padding-bottom: 6px !important;
    }
    .meal-ingredients {
        font-size: 0.88rem !important;
        color: #D1D5DB !important;
        line-height: 1.6 !important;
    }
    .day-banner {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(255, 142, 83, 0.15) 100%) !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
        border-radius: 12px !important;
        padding: 12px 20px !important;
        margin-bottom: 20px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.3rem !important;
        color: #F8FAFC !important;
    }
    .daily-totals-card {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 16px 24px !important;
        margin-top: 15px !important;
        margin-bottom: 10px !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        flex-wrap: wrap !important;
    }
    .total-metric {
        text-align: center !important;
        flex: 1 !important;
        min-width: 90px !important;
    }
    .total-val {
        font-weight: 800 !important;
        font-size: 1.25rem !important;
        color: #F8FAFC !important;
        font-family: 'Outfit', sans-serif !important;
    }
    .total-lbl {
        font-size: 0.78rem !important;
        color: #9CA3AF !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
</style>
""", unsafe_allow_html=True)


# Inicializar variables de estado de sesión para persistencia de la dieta y los macros
if "menu_data" not in st.session_state:
    st.session_state["menu_data"] = None
if "diet_streamed" not in st.session_state:
    st.session_state["diet_streamed"] = ""
if "macros_preview" not in st.session_state:
    st.session_state["macros_preview"] = None


# ==========================================
# COMPROBACIÓN DE SERVIDOR OLLAMA
# ==========================================

def test_ollama_connection(url: str) -> bool:
    """
    Intenta realizar un ping al servidor de Ollama para verificar su disponibilidad.
    """
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return True
    except Exception:
        pass
    return False

# ==========================================
# INTERFAZ DE STREAMLIT (SIDEBAR)
# ==========================================

# Cargar base de datos de alimentos de la UCM si existe
food_db = []
db_path = "/home/veronica/Descargas/Propmting/Trabajo Final/ucm_food_database.json"
if os.path.exists(db_path):
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            food_db = json.load(f)
    except Exception as e:
        logger.error(f"Error al cargar base de datos en app: {e}")

st.sidebar.markdown("### ⚙️ Configuración del Servidor")

ollama_url = st.sidebar.text_input(
    "URL del Servidor Ollama", 
    value="http://localhost:11434",
    help="La URL local o remota donde se está ejecutando el servicio de Ollama."
)
st.session_state["ollama_url"] = ollama_url

model_name = st.sidebar.selectbox(
    "Modelo LLM",
    options=["qwen2.5:3b", "qwen2.5:1.5b"],
    index=0,
    help="Selecciona el modelo de lenguaje instalado en tu servidor Ollama."
)
st.session_state["model_name"] = model_name

# Comprobar estado de conexión
is_ollama_connected = test_ollama_connection(ollama_url)

if is_ollama_connected:
    st.sidebar.markdown(
        '**Estado del Servidor:** <span class="badge badge-online">ONLINE</span>', 
        unsafe_allow_html=True
    )
else:
    st.sidebar.markdown(
        '**Estado del Servidor:** <span class="badge badge-offline">OFFLINE</span>', 
        unsafe_allow_html=True
    )
    st.sidebar.warning(
        "⚠️ No se pudo conectar al servidor de Ollama. Asegúrate de iniciar Ollama (`ollama serve`) en tu terminal."
    )

if food_db:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 Buscador de Alimentos UCM")
    search_query = st.sidebar.text_input("Buscar alimento en la guía UCM...", "")
    if search_query:
        matches = [f for f in food_db if search_query.lower() in f["name"].lower()]
        if matches:
            st.sidebar.markdown(f"Se encontraron **{len(matches)}** resultados:")
            for f in matches[:5]:
                st.sidebar.markdown(
                    f"**{f['name']}** (100g):\n"
                    f"- Calorías: {int(f['kcal'])} kcal\n"
                    f"- P: {f['proteins']}g | G: {f['fats']}g | C: {f['carbs']}g | F: {f['fiber']}g"
                )
            if len(matches) > 5:
                st.sidebar.info(f"Y {len(matches) - 5} alimentos más...")
        else:
            st.sidebar.warning("No se encontraron alimentos con ese nombre.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📚 Información sobre Herramientas")
st.sidebar.info(
    "Este agente utiliza:\n"
    "1. **`calcular_macros_tool`**: Una función matemática para calcular de manera precisa tu consumo de calorías y macros.\n"
    "2. **`generar_dieta_tool`**: Una consulta al modelo para generar un plan de alimentación diaria a tu medida."
)

# ==========================================
# INTERFAZ DE STREAMLIT (CUERPO PRINCIPAL)
# ==========================================

st.markdown('<h1 class="title-gradient">🍎 NutriAgent AI</h1>', unsafe_allow_html=True)
st.markdown("##### **Tu Agente Inteligente de Nutrición Deportiva Personalizada**")
st.markdown("Diseña planes nutricionales estructurados científicamente, ajustados a tus macros ideales y preferencias alimentarias.")

# Contenedor de formulario principal
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📝 Perfil del Usuario")

with st.form("nutrition_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sexo = st.selectbox("Sexo biológico", ["Masculino", "Femenino"], help="Utilizado para la ecuación metabólica.")
        edad = st.number_input("Edad (años)", min_value=12, max_value=100, value=28, step=1)
        altura = st.number_input("Altura (cm)", min_value=100, max_value=250, value=175, step=1, help="Necesaria para la fórmula de Mifflin-St Jeor.")
        
    with col2:
        peso = st.number_input("Peso actual (kg)", min_value=35.0, max_value=200.0, value=75.0, step=0.5)
        nivel_actividad = st.selectbox(
            "Nivel de actividad física",
            [
                "Sedentario (Poco o ningún ejercicio)",
                "Ligero (Ejercicio ligero 1-3 días/semana)",
                "Moderado (Ejercicio moderado 3-5 días/semana)",
                "Intenso (Ejercicio intenso 6-7 días/semana)",
                "Muy Intenso (Entrenamiento pesado o trabajo físico)"
            ],
            index=2
        )
        objetivo = st.selectbox(
            "Objetivo Nutricional",
            ["Pérdida de grasa", "Hipertrofia (Ganar masa muscular)", "Recomposición corporal"],
            index=0
        )
        
    with col3:
        horizonte_semanas = st.slider("Horizonte temporal (semanas)", min_value=4, max_value=24, value=12, step=1)
        # Cargar base de datos de la UCM para obtener todos los nombres de alimentos
        ucm_foods = []
        db_path = "/home/veronica/Descargas/Propmting/Trabajo Final/ucm_food_database.json"
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ucm_foods = sorted(list(set(item["name"].strip() for item in data)))
            except Exception as e:
                logger.error(f"Error al cargar alimentos UCM en app.py: {e}")

        # Establecer alimentos predeterminados en caso de que existan en la base de datos
        default_preferidos = [
            f for f in ["Pechuga de pollo", "Arroz integral", "Avena", "Huevo de gallina", "Aguacate"] 
            if f in ucm_foods
        ]
        default_excluidos = [
            f for f in ["Cacahuete sin cascara"] 
            if f in ucm_foods
        ]

        alimentos_preferidos_list = st.multiselect(
            "Alimentos preferidos / a incluir (UCM)",
            options=ucm_foods,
            default=default_preferidos,
            help="Selecciona los alimentos que deseas priorizar en tu plan alimentario."
        )
        alimentos_excluidos_list = st.multiselect(
            "Alimentos a evitar / excluir (UCM)",
            options=ucm_foods,
            default=default_excluidos,
            help="Selecciona los alimentos que deseas excluir del menú generado."
        )
        alimentos_preferidos = ", ".join(alimentos_preferidos_list)
        alimentos_excluidos = ", ".join(alimentos_excluidos_list)
        tipo_plan = st.selectbox(
            "Duración del Plan",
            ["Menú Diario (1 día)", "Plan Semanal (7 días)"],
            index=0,
            help="Selecciona si deseas un plan para un único día o un calendario semanal completo."
        )
        
    submit_button = st.form_submit_button("🚀 Generar Plan Nutricional")
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# FLUJO DEL AGENTE DE IA (STREAMING)
# ==========================================

if submit_button:
    # Reiniciar estados anteriores para evitar solapamientos durante la nueva carga
    st.session_state["menu_data"] = None
    st.session_state["diet_streamed"] = ""
    st.session_state["macros_preview"] = None
    
    if not is_ollama_connected:
        st.error(
            "🔴 **Error de Conexión:** No es posible iniciar el Agente Nutricional porque el servidor Ollama está apagado. "
            "Por favor, abre una terminal y ejecuta el comando `ollama run qwen2.5:3b` para levantar el modelo antes de continuar."
        )
    else:
        st.markdown('<h3 class="subtitle-gradient">🧠 Actividades del Agente</h3>', unsafe_allow_html=True)
        
        # 1. Ejecutar el Agente
        try:
            logger.info("Iniciando flujo de generación del Agente Nutricional...")
            tools = [calcular_macros_tool, generar_dieta_tool]
            agent_executor = get_agent_executor(ollama_url, model_name, tools)
            
            peticion_usuario = (
                f"Hola, soy un usuario con el siguiente perfil:\n"
                f"- Edad: {edad} años\n"
                f"- Sexo: {sexo}\n"
                f"- Peso: {peso} kg\n"
                f"- Altura: {altura} cm\n"
                f"- Nivel de Actividad: {nivel_actividad}\n"
                f"- Objetivo: {objetivo}\n"
                f"- Horizonte: {horizonte_semanas} semanas\n"
                f"- Alimentos Preferidos: {alimentos_preferidos}\n"
                f"- Alimentos Excluidos: {alimentos_excluidos}"
            )
            logger.info(f"Datos recibidos del usuario:\n{peticion_usuario}")
            
            # Contenedor temporal de escritura durante la llamada del agente
            placeholder_dieta = st.empty()
            diet_streamed = ""
            
            # Usar st.status para agrupar y mostrar los pensamientos e invocaciones del agente en tiempo real
            status_box = st.status("🕵️ Agente Nutricional pensando...", expanded=True)
            
            with status_box:
                for chunk in agent_executor.stream({
                    "input": peticion_usuario,
                    "chat_history": [],
                    "edad": edad,
                    "sexo": sexo,
                    "peso": peso,
                    "altura": altura,
                    "nivel_actividad": nivel_actividad,
                    "objetivo": objetivo,
                    "alimentos_preferidos": alimentos_preferidos,
                    "alimentos_excluidos": alimentos_excluidos,
                    "tipo_plan": tipo_plan
                }):
                    # 1. Si el agente decide realizar una acción (invocar herramienta)
                    if "actions" in chunk:
                        for action in chunk["actions"]:
                            logger.info(f"[PENSAMIENTO AGENTE] {action.log.strip()}")
                            st.markdown(f"🤖 **Pensamiento:** {action.log}")
                            st.markdown(f"👉 Invocando herramienta `{action.tool}` con parámetros:")
                            st.code(json.dumps(action.tool_input, indent=2, ensure_ascii=False), language="json")
                    
                    # 2. Si se completa la ejecución de una herramienta (obtenemos el paso intermedio)
                    elif "steps" in chunk:
                        for step in chunk["steps"]:
                            tool_name = step.action.tool
                            logger.info(f"[HERRAMIENTA COMPLETADA] `{tool_name}` ejecutada con éxito.")
                            
                            if tool_name == "calcular_macros_tool":
                                st.success("✅ **Cálculo de macros completado.**")
                                try:
                                    macros_preview = json.loads(step.observation)
                                    st.session_state["macros_preview"] = macros_preview
                                except Exception as e:
                                    logger.error(f"Error parseando macros: {e}")
                                    
                            elif tool_name == "generar_dieta_tool":
                                st.success("✅ **Menú diario generado.**")
                                
                    # 3. Recibir fragmentos de texto en tiempo real
                    elif "diet_chunk" in chunk:
                        if not diet_streamed:
                            status_box.update(label="✅ Cálculo de Macros Completado", state="complete", expanded=False)
                        
                        diet_streamed += chunk["diet_chunk"]
                        st.session_state["diet_streamed"] = diet_streamed
                        placeholder_dieta.markdown(diet_streamed + "▌")
                        
                    # 4. Al finalizar, obtenemos el output final de la cadena
                    elif "output" in chunk:
                        logger.info("Planificación y generación del informe final completada con éxito.")
                
                status_box.update(label="✅ Planificación Completa", state="complete", expanded=False)
            
            # Limpiar el cursor del streaming temporal
            placeholder_dieta.empty()
            
            # Forzar recarga para renderizar la interfaz definitiva de alta fidelidad de forma limpia
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()
                
        except Exception as e:
            logger.error(f"Error durante el procesamiento del agente: {str(e)}")
            logger.error(traceback.format_exc())
            st.error("🚨 Ocurrió un error al procesar el agente:")
            st.exception(e)

# ==========================================
# RENDERIZADO DE LA INTERFAZ PERMANENTE (FUERA DEL SUBMIT BUTTON)
# ==========================================

if st.session_state.get("macros_preview") or st.session_state.get("menu_data") or st.session_state.get("diet_streamed"):
    
    # 1. RENDERIZADO DE MACROS E INDICADORES
    if st.session_state.get("macros_preview"):
        macros_preview = st.session_state["macros_preview"]
        
        st.markdown('<h3 class="subtitle-gradient">📊 Plan Nutricional Generado</h3>', unsafe_allow_html=True)
        col_c, col_p, col_g, col_h = st.columns(4)
        
        with col_c:
            st.markdown(f"""
            <div class="card metric-card-kcal" style="text-align: center;">
                <div class="metric-label">Calorías Diarias</div>
                <div class="metric-value" style="color: #FF5A5A;">{macros_preview['calorias_objetivo']} <span style="font-size: 1rem;">kcal</span></div>
                <div style="font-size: 0.8rem; color: #9CA3AF;">{macros_preview['ajuste_descripcion']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_p:
            g_prot = macros_preview['macros']['proteinas']
            kcal_prot = macros_preview['macros_kcal']['proteinas']
            st.markdown(f"""
            <div class="card metric-card-proteins" style="text-align: center;">
                <div class="metric-label">Proteínas (2.2g/kg)</div>
                <div class="metric-value" style="color: #4ADE80;">{g_prot} <span style="font-size: 1rem;">g</span></div>
                <div style="font-size: 0.8rem; color: #9CA3AF;">{kcal_prot} kcal</div>
            </div>
            """, unsafe_allow_html=True)
        with col_g:
            g_gras = macros_preview['macros']['grasas']
            kcal_gras = macros_preview['macros_kcal']['grasas']
            st.markdown(f"""
            <div class="card metric-card-fats" style="text-align: center;">
                <div class="metric-label">Grasas (1.0g/kg)</div>
                <div class="metric-value" style="color: #FBBF24;">{g_gras} <span style="font-size: 1rem;">g</span></div>
                <div style="font-size: 0.8rem; color: #9CA3AF;">{kcal_gras} kcal</div>
            </div>
            """, unsafe_allow_html=True)
        with col_h:
            g_carb = macros_preview['macros']['carbohidratos']
            kcal_carb = macros_preview['macros_kcal']['carbohidratos']
            st.markdown(f"""
            <div class="card metric-card-carbs" style="text-align: center;">
                <div class="metric-label">Carbohidratos</div>
                <div class="metric-value" style="color: #60A5FA;">{g_carb} <span style="font-size: 1rem;">g</span></div>
                <div style="font-size: 0.8rem; color: #9CA3AF;">{kcal_carb} kcal</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("#### **Distribución Porcentual del Aporte Calórico**")
        pct_prot = macros_preview['macros_porcentaje']['proteinas']
        pct_gras = macros_preview['macros_porcentaje']['grasas']
        pct_carb = macros_preview['macros_porcentaje']['carbohidratos']
        
        st.markdown(f"""
        <div class="card">
            <div class="macro-progress-container">
                <div class="macro-label-row">
                    <span>Proteínas</span>
                    <span>{pct_prot}% ({macros_preview['macros']['proteinas']}g)</span>
                </div>
                <div class="macro-bar-outer">
                    <div class="macro-bar-inner" style="width: {pct_prot}%; background-color: #4ADE80;"></div>
                </div>
            </div>
            <div class="macro-progress-container">
                <div class="macro-label-row">
                    <span>Grasas</span>
                    <span>{pct_gras}% ({macros_preview['macros']['grasas']}g)</span>
                </div>
                <div class="macro-bar-outer">
                    <div class="macro-bar-inner" style="width: {pct_gras}%; background-color: #FBBF24;"></div>
                </div>
            </div>
            <div class="macro-progress-container">
                <div class="macro-label-row">
                    <span>Carbohidratos</span>
                    <span>{pct_carb}% ({macros_preview['macros']['carbohidratos']}g)</span>
                </div>
                <div class="macro-bar-outer">
                    <div class="macro-bar-inner" style="width: {pct_carb}%; background-color: #60A5FA;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 2. RENDERIZADO DE LAS DIETAS
    if st.session_state.get("menu_data"):
        menu_data = st.session_state["menu_data"]
        
        st.markdown("### 📋 Plan Semanal Detallado (Lunes a Domingo)" if len(menu_data) > 1 else "### 📋 Menú Diario Detallado")
        
        if len(menu_data) > 1:
            dias = list(menu_data.keys())
            tabs = st.tabs([f"📅 {day}" for day in dias])
            for idx, tab in enumerate(tabs):
                day = dias[idx]
                day_info = menu_data[day]
                with tab:
                    st.markdown(f'<div class="day-banner">🟢 {day.upper()}: {day_info["title"]}</div>', unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    meal_icons = {"Desayuno": "🍳", "Almuerzo": "🍗", "Merienda": "🍌", "Cena": "🥗"}
                    
                    for col, (meal_name, meal_content) in zip([col1, col2, col3, col4], day_info["meals"].items()):
                        icon = meal_icons.get(meal_name, "🍽️")
                        lines = [line.strip() for line in meal_content.split('\n') if line.strip()]
                        formatted_content = "".join([f'<div style="margin-bottom: 6px;">• {line}</div>' for line in lines])
                        col.markdown(f"""
                        <div class="meal-card">
                            <div class="meal-title">{icon} {meal_name}</div>
                            <div class="meal-ingredients">{formatted_content}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    m = day_info["macros"]
                    st.markdown(f"""
                    <div class="daily-totals-card">
                        <div class="total-metric">
                            <div class="total-val" style="color: #FF5A5A;">{m['kcal']:,}</div>
                            <div class="total-lbl">Calorías (kcal)</div>
                        </div>
                        <div class="total-metric">
                            <div class="total-val" style="color: #4ADE80;">{m['proteins']}g</div>
                            <div class="total-lbl">Proteína</div>
                        </div>
                        <div class="total-metric">
                            <div class="total-val" style="color: #60A5FA;">{m['carbs']}g</div>
                            <div class="total-lbl">Carbohidratos</div>
                        </div>
                        <div class="total-metric">
                            <div class="total-val" style="color: #FBBF24;">{m['fats']}g</div>
                            <div class="total-lbl">Grasas</div>
                        </div>
                        <div class="total-metric">
                            <div class="total-val" style="color: #A78BFA;">{m['fiber']}g</div>
                            <div class="total-lbl">Fibra</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            day = list(menu_data.keys())[0]
            day_info = menu_data[day]
            st.markdown(f'<div class="day-banner">🟢 {day_info["title"]}</div>', unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            meal_icons = {"Desayuno": "🍳", "Almuerzo": "🍗", "Merienda": "🍌", "Cena": "🥗"}
            for col, (meal_name, meal_content) in zip([col1, col2, col3, col4], day_info["meals"].items()):
                icon = meal_icons.get(meal_name, "🍽️")
                lines = [line.strip() for line in meal_content.split('\n') if line.strip()]
                formatted_content = "".join([f'<div style="margin-bottom: 6px;">• {line}</div>' for line in lines])
                col.markdown(f"""
                <div class="meal-card">
                    <div class="meal-title">{icon} {meal_name}</div>
                    <div class="meal-ingredients">{formatted_content}</div>
                </div>
                """, unsafe_allow_html=True)
                
            m = day_info["macros"]
            st.markdown(f"""
            <div class="daily-totals-card">
                <div class="total-metric">
                    <div class="total-val" style="color: #FF5A5A;">{m['kcal']:,}</div>
                    <div class="total-lbl">Calorías (kcal)</div>
                </div>
                <div class="total-metric">
                    <div class="total-val" style="color: #4ADE80;">{m['proteins']}g</div>
                    <div class="total-lbl">Proteína</div>
                </div>
                <div class="total-metric">
                    <div class="total-val" style="color: #60A5FA;">{m['carbs']}g</div>
                    <div class="total-lbl">Carbohidratos</div>
                </div>
                <div class="total-metric">
                    <div class="total-val" style="color: #FBBF24;">{m['fats']}g</div>
                    <div class="total-lbl">Grasas</div>
                </div>
                <div class="total-metric">
                    <div class="total-val" style="color: #A78BFA;">{m['fiber']}g</div>
                    <div class="total-lbl">Fibra</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Mostrar justificación
        diet_streamed = st.session_state.get("diet_streamed", "")
        just_idx = diet_streamed.find("### 📚 Justificación")
        if just_idx != -1:
            st.markdown(diet_streamed[just_idx:])
            
    elif st.session_state.get("diet_streamed"):
        # Mostrar el texto intermedio mientras se genera
        st.markdown("#### **Informe y Recomendaciones del Agente Nutricional**")
        st.markdown(st.session_state["diet_streamed"] + "▌")
