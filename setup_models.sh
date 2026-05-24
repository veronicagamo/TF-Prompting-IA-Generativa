#!/bin/bash
# Script de configuración y descarga de modelos de Ollama

echo "=== Configuración de Modelos Ollama ==="

# 1. Comprobar si ollama está instalado
if ! command -v ollama &> /dev/null
then
    echo "❌ Error: Ollama no está instalado en el sistema."
    echo "Por favor, visita https://ollama.com para instalarlo."
    exit 1
fi

echo "✅ Ollama detectado."

# 2. Verificar si el servicio de Ollama está activo
echo "Verificando servicio de Ollama..."
if ! curl -s http://localhost:11434 &> /dev/null
then
    echo "⚠️ El servidor de Ollama no parece estar ejecutándose."
    echo "Intentando iniciar 'ollama serve' en segundo plano..."
    ollama serve &
    sleep 3
    
    if ! curl -s http://localhost:11434 &> /dev/null
    then
        echo "❌ No se pudo iniciar el servicio de Ollama automáticamente."
        echo "Por favor, abre otra terminal y ejecuta: ollama serve"
        exit 1
    fi
fi
echo "✅ Servidor de Ollama en ejecución."

# 3. Descargar los modelos necesarios
echo "Descargando modelo principal qwen2.5:3b (este proceso puede tardar unos minutos)..."
ollama pull qwen2.5:3b

echo "Descargando modelo ligero qwen2.5:1.5b (para mayor velocidad en CPU)..."
ollama pull qwen2.5:1.5b

echo "=== Modelos disponibles actualmente ==="
ollama list

echo "✅ Configuración completa. Ya puedes ejecutar la aplicación con:"
echo "   streamlit run app.py"
