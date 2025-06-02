import os
import sys
import tempfile
import requests
from datetime import datetime

# Añadir el directorio actual al path para importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bocm_scraper import BOCMScraper, download_sumario_temp
from detector_patrones_cambio import procesar_dia_con_detector_inteligente

def test_fecha_20230228():
    """Test completo para el 28/02/2023"""
    print("🧪 TEST COMPLETO PARA BOCM 28/02/2023")
    print("=" * 60)
    
    fecha = datetime(2023, 2, 28)
    fecha_str = "20230228"
    
    print(f"\n📅 Fecha: {fecha.strftime('%d/%m/%Y')}")
    print(f"📰 Boletín Nº 50")
    print(f"🔗 URL página: https://www.bocm.es/boletin/bocm-{fecha_str}-50")
    print(f"📄 URL sumario: https://www.bocm.es/boletin/CM_Boletin_BOCM/2023/02/28/05000.PDF")
    
    print("\n" + "-" * 60)
    print("PASO 1: Descargar sumario")
    print("-" * 60)
    
    try:
        # Descargar el sumario directamente para prueba
        url_sumario = "https://www.bocm.es/boletin/CM_Boletin_BOCM/2023/02/28/05000.PDF"
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
        
        print(f"📥 Descargando sumario desde: {url_sumario}")
        response = requests.get(url_sumario, timeout=30)
        
        if response.status_code == 200:
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Sumario descargado: {temp_path}")
            print(f"   Tamaño: {len(response.content) / 1024:.2f} KB")
        else:
            print(f"❌ Error al descargar: Status {response.status_code}")
            return
        
        print("\n" + "-" * 60)
        print("PASO 2: Analizar sumario con detector de patrones")
        print("-" * 60)
        
        # Procesar con el detector inteligente
        resultado = procesar_dia_con_detector_inteligente(fecha_str, temp_path)
        
        print(f"\n📊 RESULTADOS DEL ANÁLISIS:")
        print(f"   📄 Convenios analizados: {resultado.get('convenios_detectados', 0)}")
        print(f"   🔄 Convenios con cambios: {resultado.get('convenios_con_cambios', 0)}")
        
        if resultado.get('detalles'):
            print(f"\n📋 DETALLES DE CONVENIOS DETECTADOS:")
            for i, detalle in enumerate(resultado['detalles'], 1):
                print(f"\n   {i}. Documento: BOCM-{fecha_str}-{detalle['documento']}")
                print(f"      Código: {detalle['codigo']}")
                print(f"      Tipo: {detalle['tipo_cambio']}")
                print(f"      Descripción: {detalle['descripcion'][:80]}...")
                
                # Verificar si es el convenio de Mondelez
                if 'mondelez' in detalle['descripcion'].lower():
                    print(f"      ✅ ¡Convenio de Mondelez detectado!")
        else:
            print("\n❌ No se detectaron convenios con cambios")
            print("\n🔍 Verificando contenido del sumario...")
            
            # Leer el contenido para debug
            try:
                import PyPDF2
                with open(temp_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    # Buscar en la página 6 donde debería estar el convenio
                    if len(reader.pages) >= 6:
                        texto_pagina6 = reader.pages[5].extract_text()
                        if 'mondelez' in texto_pagina6.lower():
                            print("   ⚠️  El convenio de Mondelez está en la página 6")
                            print("   ⚠️  Pero el detector no lo está capturando")
                            
                            # Mostrar fragmento relevante
                            lineas = texto_pagina6.split('\n')
                            for i, linea in enumerate(lineas):
                                if 'mondelez' in linea.lower() or '28103512012023' in linea:
                                    print(f"\n   Línea {i}: {linea.strip()}")
                                    if i > 0:
                                        print(f"   Línea {i-1}: {lineas[i-1].strip()}")
                                    if i < len(lineas) - 1:
                                        print(f"   Línea {i+1}: {lineas[i+1].strip()}")
            except Exception as e:
                print(f"   Error al leer PDF: {e}")
        
        # Limpiar archivo temporal
        os.unlink(temp_path)
        print(f"\n🧹 Archivo temporal eliminado")
        
    except Exception as e:
        print(f"\n❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fecha_20230228()