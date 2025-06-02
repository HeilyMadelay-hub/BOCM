import os
import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
try:
    import PyPDF2
except ImportError:
    print("PyPDF2 no instalado. Instala con: pip install PyPDF2")
    PyPDF2 = None

class DetectorPatronesCambio:
    """
    Detector inteligente de patrones que indican cambios en códigos de convenio
    específicamente en sumarios del BOCM
    """
    
    def __init__(self):
        # Patrones específicos que indican CAMBIO de código en el sumario
        self.patrones_cambio_sumario = [
            # Patrones para "registro, depósito y publicación"
            r'registro,\s*depósito\s*y\s*publicación.*código\s*número\s*(\d{14})',
            r'sobre\s*registro,\s*depósito\s*y\s*publicación.*\(código\s*número\s*(\d{14})\)',
            
            # Patrones para convenio colectivo con código
            r'convenio\s*colectivo.*\(código\s*número\s*(\d{14})\)',
            r'convenio\s*colectivo.*código\s*número\s*(\d{14})',
            
            # Patrón específico para casos como Mondelez
            r'empresa\s+[^,]+,\s*[^,]+\s*\(código\s*número\s*(\d{14})\)',
            
            # Patrones más generales
            r'código\s*número\s*(\d{14})',
            r'\(código\s*número\s*(\d{14})\)'
        ]
        
        # Palabras clave que CONFIRMAN que es un convenio real
        self.palabras_clave_convenio = [
            'convenio colectivo',
            'acuerdo laboral', 
            'código número',
            'registro, depósito y publicación',
            'convenio de empresa',
            'acuerdo de empresa',
            'fuerza de ventas',
            'resolución'
        ]
        
        # Palabras que EXCLUYEN (no son convenios laborales)
        self.palabras_exclusion = [
            'convocatoria',
            'provisión de puestos',
            'libre designación',
            'concurso de méritos',
            'pruebas selectivas',
            'funcionarios',
            'oposiciones',
            'subvenciones',
            'formalización del contrato',
            'anuncio periódico',
            'convenio de colaboración',
            'convenio de ejecución',
            'convenio ayuda infraestructuras',
            'convenio específico',
            'plan estratégico'
        ]
    
    def analizar_sumario_dia(self, ruta_sumario: str, fecha_objetivo: str) -> List[Dict]:
        """
        Analiza el sumario del día y detecta SOLO convenios con cambios de código
        
        Args:
            ruta_sumario: Ruta al PDF del sumario
            fecha_objetivo: Fecha en formato YYYYMMDD
            
        Returns:
            Lista de convenios con cambios detectados
        """
        try:
            logging.info(f"Analizando sumario para detectar cambios de código: {ruta_sumario}")
            
            # Extraer texto del sumario
            texto_sumario = self._extraer_texto_pdf(ruta_sumario)
            if not texto_sumario:
                return []
            
            # Detectar documentos con patrones de cambio
            convenios_con_cambios = self._detectar_cambios_en_texto(texto_sumario, fecha_objetivo)
            
            logging.info(f"Detectados {len(convenios_con_cambios)} convenios con cambios de código")
            return convenios_con_cambios
            
        except Exception as e:
            logging.error(f"Error analizando sumario: {e}")
            return []
    
    def _extraer_texto_pdf(self, ruta_pdf: str) -> str:
        """Extrae texto del PDF del sumario con mejor manejo"""
        try:
            with open(ruta_pdf, 'rb') as archivo:
                lector = PyPDF2.PdfReader(archivo)
                texto = ""
                for pagina in lector.pages:
                    texto += pagina.extract_text() + "\n"
            return texto
        except Exception as e:
            logging.error(f"Error extrayendo texto del PDF: {e}")
            return ""

    def _detectar_cambios_en_texto(self, texto: str, fecha: str) -> List[Dict]:
        """
        Detecta convenios con cambios de código analizando el texto del sumario
        VERSIÓN CORREGIDA para el formato real del BOCM
        """
        convenios_detectados = []
        
        # Normalizar el texto - quitar saltos de línea excesivos
        texto_normalizado = re.sub(r'\n+', ' ', texto)
        texto_normalizado = re.sub(r'\s+', ' ', texto_normalizado)
        
        # Buscar TODOS los códigos de convenio en el texto completo
        # Patrón mejorado que captura el contexto completo
        patron_completo = r'(convenio colectivo[^(]+\(Código número (\d{14})\)[^B]*BOCM-\d{8}-(\d+))'
        
        matches = re.finditer(patron_completo, texto_normalizado, re.IGNORECASE)
        
        for match in matches:
            descripcion_completa = match.group(1)
            codigo_detectado = match.group(2)
            num_doc = match.group(3)
            
            # Verificar que no sea excluido
            desc_lower = descripcion_completa.lower()
            es_excluido = any(palabra in desc_lower for palabra in self.palabras_exclusion)
            
            if not es_excluido:
                # Extraer empresa si es posible
                empresa_match = re.search(r'empresa\s+([^(]+)\s*\(', descripcion_completa)
                empresa = empresa_match.group(1).strip() if empresa_match else "No identificada"
                
                convenio = {
                    'id': num_doc,
                    'descripcion': descripcion_completa.strip(),
                    'seccion': 'CONSEJERÍA DE ECONOMÍA, HACIENDA Y EMPLEO',
                    'url': f"https://www.bocm.es/boletin/CM_Orden_BOCM/{fecha[:4]}/{fecha[4:6]}/{fecha[6:8]}/BOCM-{fecha}-{num_doc}.PDF",
                    'codigo_detectado': codigo_detectado,
                    'empresa': empresa,
                    'patron_cambio': True,
                    'razon_cambio': "Nuevo registro/depósito"  # Ajustar según el texto
                }
                
                convenios_detectados.append(convenio)
                logging.info(f"CAMBIO DETECTADO: Doc {num_doc} - Código {codigo_detectado} - Empresa: {empresa}")
        
        # Si no encuentra con el patrón anterior, intentar patrón más flexible
        if not convenios_detectados:
            # Buscar códigos y luego su contexto
            for patron in self.patrones_cambio_sumario:
                for match in re.finditer(patron, texto_normalizado, re.IGNORECASE):
                    codigo = match.group(1)
                    
                    # Buscar el contexto alrededor del código
                    pos = match.start()
                    inicio = max(0, pos - 200)
                    fin = min(len(texto_normalizado), pos + 100)
                    contexto = texto_normalizado[inicio:fin]
                    
                    # Verificar si es un convenio laboral
                    if any(palabra in contexto.lower() for palabra in self.palabras_clave_convenio):
                        # Buscar número BOCM
                        bocm_match = re.search(r'BOCM-\d{8}-(\d+)', contexto)
                        num_doc = bocm_match.group(1) if bocm_match else str(len(convenios_detectados) + 1)
                        
                        convenio = {
                            'id': num_doc,
                            'descripcion': contexto.strip(),
                            'seccion': 'CONSEJERÍA DE ECONOMÍA, HACIENDA Y EMPLEO',
                            'url': f"https://www.bocm.es/boletin/CM_Orden_BOCM/{fecha[:4]}/{fecha[4:6]}/{fecha[6:8]}/BOCM-{fecha}-{num_doc}.PDF",
                            'codigo_detectado': codigo,
                            'patron_cambio': True,
                            'razon_cambio': self._identificar_tipo_cambio(contexto)
                        }
                        
                        # Evitar duplicados
                        if not any(c['codigo_detectado'] == codigo for c in convenios_detectados):
                            convenios_detectados.append(convenio)
                            logging.info(f"CAMBIO DETECTADO: Doc {num_doc} - Código {codigo}")
        
        logging.info(f"Total de convenios detectados: {len(convenios_detectados)}")
        return convenios_detectados   
    
    def _es_seccion(self, linea: str) -> bool:
        """Identifica si una línea es una sección (consejería)"""
        return (linea.isupper() and len(linea) > 10 and 
                ('CONSEJERÍA' in linea or 'PRESIDENCIA' in linea))
    
    def _identificar_tipo_cambio(self, descripcion: str) -> str:
        """Identifica el tipo de cambio detectado"""
        desc_lower = descripcion.lower()
        
        if 'modificación' in desc_lower or 'cambio' in desc_lower:
            return "Modificación de código"
        elif 'registro' in desc_lower and 'depósito' in desc_lower:
            return "Nuevo registro/depósito"
        elif 'prórroga' in desc_lower or 'extensión' in desc_lower:
            return "Prórroga/Extensión"
        elif 'actualización' in desc_lower:
            return "Actualización"
        elif 'corrección' in desc_lower:
            return "Corrección"
        elif 'resolución' in desc_lower:
            return "Nueva resolución"
        else:
            return "Cambio detectado"

class ProcesadorInteligenteBOCM:
    """
    Procesador principal que integra la detección inteligente de cambios
    """
    
    def __init__(self):
        self.detector = DetectorPatronesCambio()
        self.base_conocimiento_file = 'codigos_convenios.json'
    
    def procesar_dia(self, fecha: str, ruta_sumario: str) -> Dict:
        """
        Procesa el sumario de un día específico buscando SOLO cambios reales
        
        Args:
            fecha: Fecha en formato YYYYMMDD
            ruta_sumario: Ruta al PDF del sumario
            
        Returns:
            Resultado del procesamiento
        """
        resultado = {
            'fecha': fecha,
            'convenios_detectados': 0,
            'convenios_con_cambios': 0,
            'convenios_descargados': 0,
            'convenios_insertados': 0,
            'detalles': []
        }
        
        try:
            # 1. Detectar convenios con cambios en el sumario
            logging.info(f"=== PROCESANDO DÍA {fecha} ===")
            convenios_con_cambios = self.detector.analizar_sumario_dia(ruta_sumario, fecha)
            
            resultado['convenios_detectados'] = len(convenios_con_cambios)
            resultado['convenios_con_cambios'] = len(convenios_con_cambios)
            
            if not convenios_con_cambios:
                logging.info("No se detectaron convenios con cambios de código para este día")
                return resultado
            
            # 2. Informar resultados
            for convenio in convenios_con_cambios:
                detalle = {
                    'documento': convenio['id'],
                    'codigo': convenio['codigo_detectado'],
                    'tipo_cambio': convenio['razon_cambio'],
                    'descripcion': convenio['descripcion'][:100] + "..."
                }
                resultado['detalles'].append(detalle)
                
                logging.info(f"CONVENIO A PROCESAR:")
                logging.info(f"  - Documento: {convenio['id']}")
                logging.info(f"  - Código: {convenio['codigo_detectado']}")
                logging.info(f"  - Tipo: {convenio['razon_cambio']}")
                logging.info(f"  - URL: {convenio['url']}")
            
            return resultado
            
        except Exception as e:
            logging.error(f"Error procesando día {fecha}: {e}")
            return resultado

# Función principal para integrar con el sistema existente
def procesar_dia_con_detector_inteligente(fecha_str: str, ruta_sumario: str) -> Dict:
    """
    Función principal que puede ser llamada desde main.py
    
    Args:
        fecha_str: Fecha en formato YYYYMMDD
        ruta_sumario: Ruta al sumario PDF
        
    Returns:
        Diccionario con resultados del procesamiento
    """
    procesador = ProcesadorInteligenteBOCM()
    return procesador.procesar_dia(fecha_str, ruta_sumario)

