# Utilidades generales

import os
import re
import logging
from datetime import datetime
from bocm_scraper import extraer_codigo_convenio

def limpiar_archivos_temporales(ruta_archivo):
    """Elimina archivos temporales creados durante el proceso"""
    try:
        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo)
            logging.info(f"Archivo temporal eliminado: {ruta_archivo}")
    except Exception as e:
        logging.error(f"Error al eliminar archivo temporal {ruta_archivo}: {e}")

def extraer_fecha_de_pdf(nombre_archivo):
    """Extrae la fecha de un nombre de archivo BOCM"""
    match = re.search(r'BOCM-(\d{8})-', nombre_archivo)
    if match:
        fecha_str = match.group(1)
        try:
            return datetime.strptime(fecha_str, '%Y%m%d')
        except:
            pass
    return None
