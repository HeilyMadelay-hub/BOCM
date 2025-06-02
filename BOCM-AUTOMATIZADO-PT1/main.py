import os
import sys
from datetime import datetime
import logging

# Importar módulos del proyecto
from config import setup_logging, CONVENIOS_DIR
from bocm_scraper import BOCMScraper, download_sumario_temp
from detector_patrones_cambio import procesar_dia_con_detector_inteligente
from utils import limpiar_archivos_temporales
import PyPDF2  

def main_inteligente():
    """
    Versión mejorada del procesador que SOLO procesa convenios 
    con cambios de código detectados en el patrón del sumario
    """
    print("=== BOCM AUTOMATIZADO - MODO INTELIGENTE ===")
    print("Solo procesará convenios con cambios de código detectados")
    
    # Configuración inicial
    setup_logging()
    
    # Crear directorios necesarios
    if not os.path.exists(CONVENIOS_DIR):
        os.makedirs(CONVENIOS_DIR)
    
    # Obtener fecha de hoy
    fecha_hoy = datetime.now()
    fecha_str = fecha_hoy.strftime('%Y%m%d')
    
    print(f"\n📅 Procesando fecha: {fecha_hoy.strftime('%d/%m/%Y')}")
    
    try:
        # 1. Descargar sumario del día
        print("\n🔍 Descargando sumario del BOCM...")
        scraper = BOCMScraper()
        ruta_sumario_temp = download_sumario_temp(fecha_hoy, scraper)
        
        if not ruta_sumario_temp:
            print("❌ No se encontró el sumario del BOCM para hoy.")
            return
        
        print(f"✅ Sumario descargado: {ruta_sumario_temp}")
        print("\n🔍 DEBUG: Extrayendo texto del sumario para verificar...")
        with open(ruta_sumario_temp, 'rb') as f:
            lector = PyPDF2.PdfReader(f)
            texto_sample = lector.pages[0].extract_text()[:1000]
            print("Primeros 1000 caracteres del sumario:")
            print(texto_sample)
            print("\n¿Se ven códigos de convenio? Buscar '(Código número XXXXXXXXXXXXXX)'")
        # 2. ANÁLISIS INTELIGENTE - Detectar patrones de cambio
        print("\n🧠 Analizando sumario con detector inteligente...")
        resultado = procesar_dia_con_detector_inteligente(fecha_str, ruta_sumario_temp)
        
        # 3. Mostrar resultados del análisis
        print(f"\n📊 RESULTADOS DEL ANÁLISIS:")
        print(f"   📄 Documentos analizados en sumario: {resultado.get('convenios_detectados', 0)}")
        print(f"   🔄 Convenios con cambios detectados: {resultado.get('convenios_con_cambios', 0)}")
        
        if resultado['convenios_con_cambios'] == 0:
            print("\n✅ No se detectaron cambios en códigos de convenio para hoy.")
            print("   El sistema funcionó correctamente - no hay nada que procesar.")
            limpiar_archivos_temporales(ruta_sumario_temp)
            return
        
        # 4. Mostrar detalles de los cambios detectados
        print(f"\n🎯 CONVENIOS CON CAMBIOS DETECTADOS:")
        for i, detalle in enumerate(resultado.get('detalles', []), 1):
            print(f"   {i}. Documento: {detalle['documento']}")
            print(f"      Código: {detalle['codigo']}")
            print(f"      Tipo: {detalle['tipo_cambio']}")
            print(f"      Descripción: {detalle['descripcion']}")
            print()
        
        # 5. Confirmar procesamiento (opcional)
        if resultado['convenios_con_cambios'] > 0:
            respuesta = input("¿Deseas procesar estos convenios? (s/n): ").lower().strip()
            
            if respuesta == 's' or respuesta == 'si':
                print("\n⬇️ Descargando convenios con cambios...")
                # TODO: Integrar con el sistema de descarga y BD
                # descargar_convenios(resultado['detalles'], CONVENIOS_DIR)
                # insertar_en_bd(resultado['detalles'])
                print(f"✅ Se procesarían {resultado['convenios_con_cambios']} convenios")
                print("   (Integración con descarga y BD pendiente)")
            else:
                print("❌ Procesamiento cancelado por el usuario.")
        
        # 6. Limpiar archivos temporales
        limpiar_archivos_temporales(ruta_sumario_temp)
        
        print("\n🎉 Proceso completado exitosamente!")
        
    except Exception as e:
        logging.error(f"Error en el proceso principal: {e}")
        print(f"❌ Error durante el procesamiento: {e}")
        
        # Limpiar en caso de error
        if 'ruta_sumario_temp' in locals() and ruta_sumario_temp:
            limpiar_archivos_temporales(ruta_sumario_temp)

def modo_fecha_especifica():
    """
    Permite procesar una fecha específica en lugar de hoy
    """
    print("\n📅 MODO FECHA ESPECÍFICA")
    
    while True:
        fecha_input = input("Ingresa la fecha (YYYYMMDD) o 'salir': ").strip()
        
        if fecha_input.lower() == 'salir':
            break
            
        if len(fecha_input) != 8 or not fecha_input.isdigit():
            print("❌ Formato incorrecto. Usa YYYYMMDD (ej: 20250525)")
            continue
        
        try:
            # Validar fecha
            fecha_obj = datetime.strptime(fecha_input, '%Y%m%d')
            print(f"\n🔍 Procesando fecha: {fecha_obj.strftime('%d/%m/%Y')}")
            
            # Descargar sumario de la fecha específica
            scraper = BOCMScraper()
            ruta_sumario_temp = download_sumario_temp(fecha_obj, scraper)
            
            if not ruta_sumario_temp:
                print(f"❌ No se encontró sumario para {fecha_obj.strftime('%d/%m/%Y')}")
                continue
            
            # === AÑADIR ESTE DEBUG ===
            print("\n🔍 DEBUG: Verificando contenido del sumario...")
            try:
                import PyPDF2
                with open(ruta_sumario_temp, 'rb') as f:
                    lector = PyPDF2.PdfReader(f)
                    print(f"   Páginas en el PDF: {len(lector.pages)}")
                    
                    # Extraer texto de las primeras páginas
                    texto_completo = ""
                    for i in range(min(3, len(lector.pages))):
                        texto_pagina = lector.pages[i].extract_text()
                        texto_completo += texto_pagina
                    
                    # Buscar convenios colectivos
                    print(f"\n   Buscando 'convenio colectivo' en el texto...")
                    convenios_encontrados = texto_completo.lower().count('convenio colectivo')
                    print(f"   Encontradas {convenios_encontrados} menciones de 'convenio colectivo'")
                    
                    # Buscar códigos
                    print(f"\n   Buscando códigos de convenio...")
                    import re
                    codigos = re.findall(r'(?:código|Código)\s*(?:número|numero)?\s*(\d{14})', texto_completo, re.IGNORECASE)
                    print(f"   Códigos encontrados: {len(codigos)}")
                    if codigos:
                        for i, codigo in enumerate(codigos[:5], 1):
                            print(f"      {i}. {codigo}")
                    
                    # Mostrar muestra del texto
                    print(f"\n   MUESTRA DEL TEXTO EXTRAÍDO:")
                    print("   " + "="*50)
                    # Buscar sección de Economía
                    if 'ECONOMÍA' in texto_completo:
                        indice = texto_completo.find('ECONOMÍA')
                        muestra = texto_completo[indice:indice+1000].replace('\n', ' ')
                        print(f"   {muestra}")
                    else:
                        print(f"   {texto_completo[:1000].replace(chr(10), ' ')}")
                    print("   " + "="*50)
                    
            except Exception as e:
                print(f"   Error en debug: {e}")
            # === FIN DEL DEBUG ===
            
            # Procesar con detector inteligente
            resultado = procesar_dia_con_detector_inteligente(fecha_input, ruta_sumario_temp)
            
            # Mostrar resultados
            print(f"\n📊 RESULTADOS PARA {fecha_obj.strftime('%d/%m/%Y')}:")
            print(f"   🔄 Convenios con cambios: {resultado.get('convenios_con_cambios', 0)}")
            
            if resultado.get('detalles'):
                print(f"\n📋 DETALLES:")
                for detalle in resultado['detalles']:
                    print(f"   - Doc {detalle['documento']}: {detalle['tipo_cambio']} (Código: {detalle['codigo']})")
            
            # Preguntar si desea procesar los convenios detectados
            if resultado['convenios_con_cambios'] > 0:
                print(f"\n🎯 Se detectaron {resultado['convenios_con_cambios']} convenios con cambios")
                respuesta = input("¿Deseas procesar estos convenios? (s/n): ").lower().strip()
                
                if respuesta == 's' or respuesta == 'si':
                    print("\n⬇️ Procesando convenios...")
                    print("✅ Convenios procesados (integración con BD pendiente)")
                else:
                    print("❌ Procesamiento cancelado")
            
            # Limpiar
            limpiar_archivos_temporales(ruta_sumario_temp)
            
        except ValueError:
            print("❌ Fecha inválida")
        except Exception as e:
            print(f"❌ Error procesando fecha: {e}")
            logging.error(f"Error en modo_fecha_especifica: {e}")



if __name__ == "__main__":
    print("🤖 BOCM AUTOMATIZADO - DETECTOR INTELIGENTE")
    print("=" * 50)
    print("1. Procesar HOY")
    print("2. Procesar fecha específica")
    print("3. Salir")
    
    while True:
        opcion = input("\nSelecciona una opción (1-3): ").strip()
        
        if opcion == '1':
            main_inteligente()
            break
        elif opcion == '2':
            modo_fecha_especifica()
            break
        elif opcion == '3':
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción inválida. Usa 1, 2 o 3")