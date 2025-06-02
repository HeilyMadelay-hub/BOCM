import os
import sys
from datetime import datetime
import logging
import json
import io
import re
import requests


# Importar módulos del proyecto
from config import setup_logging, CONVENIOS_DIR
from bocm_scraper import BOCMScraper, download_sumario_temp
from detector_patrones_cambio import procesar_dia_con_detector_inteligente
from utils import limpiar_archivos_temporales
from insertar_convenios import insertar_convenio
import PyPDF2  

def main():
    """
    Versión mejorada del procesador que SOLO procesa convenios 
    con cambios de código detectados en el patrón del sumario
    """
    print("=== BOCM AUTOMATIZADO ===")
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
        
        # 5. Confirmar procesamiento 
        if resultado['convenios_con_cambios'] > 0:
            respuesta = input("¿Deseas procesar estos convenios? (s/n): ").lower().strip()
            
            if respuesta == 's' or respuesta == 'si':
                print("\n⬇️ Procesando convenios...")
                
                # Lista para el JSON de salida
                convenios_para_json = []
                
                # Procesar cada convenio detectado
                for detalle in resultado.get('detalles', []):
                    try:
                        # 1. Construir URL del PDF individual
                        year = fecha_hoy.year
                        month = fecha_hoy.month
                        day = fecha_hoy.day
                        
                        url_pdf = f"https://www.bocm.es/boletin/CM_Orden_BOCM/{year}/{month:02d}/{day:02d}/BOCM-{fecha_str}-{detalle['documento']}.PDF"
                        
                        print(f"\n📥 Descargando convenio {detalle['codigo']}...")
                        
                        # 2. Descargar PDF
                        response = requests.get(url_pdf, timeout=30)
                        if response.status_code != 200:
                            print(f"   ❌ Error descargando PDF")
                            continue
                            
                        # 3. Extraer nombre del convenio
                        pdf_file = io.BytesIO(response.content)
                        reader = PyPDF2.PdfReader(pdf_file)
                        
                        # Buscar nombre en las primeras páginas
                        texto = ""
                        for i in range(min(3, len(reader.pages))):
                            texto += reader.pages[i].extract_text()
                        
                        # Buscar patrón de nombre
                        match = re.search(r"convenio colectivo de(?:\s+la)?\s+empresa\s+([^(,\n]+)", texto, re.IGNORECASE)
                        
                        if match:
                            nombre_convenio = match.group(1).strip().replace('\n', ' ')[:200]
                        else:
                            nombre_convenio = f"Convenio {detalle['codigo']}"
                        
                        # 4. Preparar datos
                        codigo_principal = detalle['codigo']
                        id_procedencia = 3  # BOCM
                        
                        # 5. Agregar a lista para JSON
                        convenios_para_json.append({
                            "fichero": f"BOCM-{fecha_str}-{detalle['documento']}.PDF",
                            "nombre_convenio": nombre_convenio,
                            "codigo_principal": codigo_principal,
                            "id_procedencia": id_procedencia
                        })
                        
                        # 6. Insertar en base de datos
                        print(f"   📝 Insertando: {nombre_convenio}")
                        insertar_convenio(nombre_convenio, id_procedencia, codigo_principal)
                        
                    except Exception as e:
                        print(f"   ❌ Error procesando convenio: {e}")
                        continue
                
                # 7. Imprimir JSON
                print('\n=== JSON ===')
                print(json.dumps(convenios_para_json, ensure_ascii=False))
                
                print(f"\n✅ Procesados {len(convenios_para_json)} convenios")
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
                
                # En la parte donde dice "¿Deseas procesar estos convenios? (s/n):"
                if respuesta == 's' or respuesta == 'si':
                    print("\n⬇️ Procesando convenios...")
                    
                    # Lista para el JSON de salida
                    convenios_para_json = []
                    
                    # Procesar cada convenio detectado
                    for detalle in resultado.get('detalles', []):
                        try:
                            # 1. Construir URL del PDF individual
                            fecha_obj = datetime.strptime(fecha_input, '%Y%m%d')
                            year = fecha_obj.year
                            month = fecha_obj.month
                            day = fecha_obj.day
                            
                            url_pdf = f"https://www.bocm.es/boletin/CM_Orden_BOCM/{year}/{month:02d}/{day:02d}/BOCM-{fecha_input}-{detalle['documento']}.PDF"
                            
                            print(f"\n📥 Descargando convenio {detalle['codigo']}...")
                            
                            # 2. Descargar PDF
                            response = requests.get(url_pdf, timeout=30)
                            if response.status_code != 200:
                                print(f"   ❌ Error descargando PDF")
                                continue

                            nombre_archivo_pdf = f"BOCM-{fecha_input}-{detalle['documento']}.PDF"
                            ruta_pdf = os.path.join(CONVENIOS_DIR, nombre_archivo_pdf)

                            if not os.path.exists(CONVENIOS_DIR):
                                os.makedirs(CONVENIOS_DIR)

                            # Guardar el PDF
                            with open(ruta_pdf, 'wb') as f:
                                f.write(response.content)
                            print(f"   💾 PDF guardado en: {ruta_pdf}")

                            # 3. Extraer nombre del convenio
                            pdf_file = io.BytesIO(response.content)
                            reader = PyPDF2.PdfReader(pdf_file)
                            
                            # Buscar nombre en las primeras páginas
                            texto = ""
                            for i in range(min(3, len(reader.pages))):
                                texto += reader.pages[i].extract_text()
                            
                            # Buscar patrón de nombre
                            import re
                            match = re.search(r"convenio colectivo de(?:\s+la)?\s+empresa\s+([^(,\n]+)", texto, re.IGNORECASE)
                            
                            if match:
                                nombre_convenio = match.group(1).strip().replace('\n', ' ')[:200]
                            else:
                                nombre_convenio = f"Convenio {detalle['codigo']}"
                            
                            # 4. Preparar datos
                            codigo_principal = detalle['codigo']
                            id_procedencia = 3  # BOCM
                            
                            # 5. Agregar a lista para JSON
                            convenios_para_json.append({
                                "fichero": f"BOCM-{fecha_input}-{detalle['documento']}.PDF",
                                "nombre_convenio": nombre_convenio,
                                "codigo_principal": codigo_principal,
                                "id_procedencia": id_procedencia
                            })
                            
                            # 6. Insertar en base de datos
                            print(f"   📝 Insertando: {nombre_convenio}")
                            insertar_convenio(nombre_convenio, id_procedencia, codigo_principal)
                            
                        except Exception as e:
                            print(f"   ❌ Error procesando convenio: {e}")
                            continue
                    
                    # 7. Imprimir JSON (como hace tu compañero)
                    print('\n=== JSON ===')
                    print(json.dumps(convenios_para_json, ensure_ascii=False))
                    
                    print(f"\n✅ Procesados {len(convenios_para_json)} convenios")
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
            main()
            break
        elif opcion == '2':
            modo_fecha_especifica()
            break
        elif opcion == '3':
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción inválida. Usa 1, 2 o 3")