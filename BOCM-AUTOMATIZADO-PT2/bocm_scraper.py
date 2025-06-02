import logging
import requests
import os
import time
import re
import json
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import threading
from detector_patrones_cambio import procesar_dia_con_detector_inteligente

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Verificar dependencias
try:
    import requests
    REQUESTS_DISPONIBLE = True
except ImportError:
    REQUESTS_DISPONIBLE = False

try:
    import PyPDF2
    PYPDF2_DISPONIBLE = True
except ImportError:
    PYPDF2_DISPONIBLE = False

try:
    import glob
    GLOB_DISPONIBLE = True
except ImportError:
    GLOB_DISPONIBLE = False

try:
    from bs4 import BeautifulSoup
    BS4_DISPONIBLE = True
except ImportError:
    BS4_DISPONIBLE = False


class ScraperError(Exception):
    """Excepción personalizada para errores del scraper"""
    pass


def verificar_dependencias():
    """Verifica que las dependencias necesarias estén disponibles"""
    dependencias_faltantes = []
    
    if not REQUESTS_DISPONIBLE:
        dependencias_faltantes.append("requests")
    if not PYPDF2_DISPONIBLE:
        dependencias_faltantes.append("PyPDF2")
    
    if dependencias_faltantes:
        print(f"❌ DEPENDENCIAS FALTANTES: {', '.join(dependencias_faltantes)}")
        print("   Ejecuta: python instalar_dependencias.py")
        print("   O manualmente: pip install " + " ".join(dependencias_faltantes))
        return False
    
    return True


class BOCMScraper:
    """Scraper ARREGLADO para el BOCM"""
    
    MAIN_PAGE_URL = "https://www.bocm.es"

    def __init__(self):
        if not verificar_dependencias():
            raise ScraperError("Dependencias no disponibles")
        
        # Sesión con pool ampliado
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Pool grande para múltiples conexiones
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=0
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def get_sumario_url(self, date_obj: datetime) -> str:
        """Obtiene la URL del sumario - VERSIÓN ARREGLADA"""
        if not REQUESTS_DISPONIBLE:
            raise ScraperError("requests no está disponible")
        
        year = date_obj.strftime('%Y')
        month = date_obj.strftime('%m')
        day = date_obj.strftime('%d')
        fecha_str = date_obj.strftime('%Y%m%d')
        
        # Verificar si es fin de semana
        dia_semana = date_obj.weekday()
        es_fin_semana = dia_semana >= 5
        
        if es_fin_semana:
            print(f"   ℹ️  {date_obj.strftime('%d/%m/%Y')} es fin de semana - verificando si hay BOCM especial...")
        
        print(f"   🔍 Buscando sumario...")
        
        # GENERAR URLs CORRECTAMENTE
        todas_urls = []
        
        # Para fines de semana, el formato BOCM-YYYYMMDD0XX es prioritario
        if es_fin_semana:
            # Números más probables para fines de semana
            numeros_prioritarios = [75, 50, 100, 125, 150, 25, 175, 200]
            
            # Generar URLs para números prioritarios
            for num in numeros_prioritarios:
                # Para 75 -> BOCM-20250329075.PDF (sin cero extra)
                if num < 10:
                    url = f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/BOCM-{fecha_str}00{num}.PDF"
                elif num < 100:
                    url = f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/BOCM-{fecha_str}0{num}.PDF"
                else:
                    url = f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/BOCM-{fecha_str}{num}.PDF"
                todas_urls.append(url)
            
            # Luego probar el resto de números
            for i in range(1, 201):
                if i not in numeros_prioritarios:
                    if i < 10:
                        url = f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/BOCM-{fecha_str}00{i}.PDF"
                    elif i < 100:
                        url = f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/BOCM-{fecha_str}0{i}.PDF"
                    else:
                        url = f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/BOCM-{fecha_str}{i}.PDF"
                    todas_urls.append(url)
        
        # Para días normales, formatos estándar
        for i in range(1, 201):
            # Formato 05000.PDF, 12300.PDF, etc.
            if i < 10:
                todas_urls.append(f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/00{i}00.PDF")
                todas_urls.append(f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/0{i}00.PDF")
                todas_urls.append(f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/0{i}000.PDF")
            elif i < 100:
                todas_urls.append(f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/0{i}00.PDF")
                todas_urls.append(f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/{i}00.PDF")
                todas_urls.append(f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/{i}000.PDF")
            else:
                todas_urls.append(f"https://www.bocm.es/boletin/CM_Boletin_BOCM/{year}/{month}/{day}/{i}00.PDF")
        
        # Mostrar las primeras URLs a verificar para debug
        print(f"   📍 Primeras URLs a verificar:")
        for idx, url in enumerate(todas_urls[:5]):
            print(f"      {idx+1}. {url.split('/')[-1]}")
        
        # BÚSQUEDA PARALELA
        tiempo_inicio = time.time()
        url_encontrada = None
        
        # Configuración optimizada
        max_workers = 50  # Muchos threads
        batch_size = 100  # Lotes grandes
        timeout_conexion = 2.0  # Timeout más realista
        
        # Variable para detener cuando se encuentra
        encontrado = threading.Event()
        
        def verificar_url(url):
            """Verifica una URL"""
            if encontrado.is_set():
                return None
                
            try:
                response = self.session.head(url, timeout=timeout_conexion, allow_redirects=True)
                if response.status_code == 200:
                    encontrado.set()
                    return url
            except:
                pass
            return None
        
        # Procesar TODAS las URLs sin límite artificial
        intentos = 0
        for i in range(0, len(todas_urls), batch_size):
            if encontrado.is_set():
                break
                
            batch = todas_urls[i:i+batch_size]
            
            # Mostrar progreso
            if i > 0:
                tiempo_transcurrido = time.time() - tiempo_inicio
                print(f"   Progreso: {i} URLs verificadas en {int(tiempo_transcurrido)}s...")
            
            # Verificar lote en paralelo
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(verificar_url, url): url for url in batch}
                
                for future in as_completed(futures, timeout=20):
                    try:
                        resultado = future.result()
                        if resultado:
                            url_encontrada = resultado
                            # Cancelar el resto
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            break
                    except:
                        pass
                
                if url_encontrada:
                    break
            
            intentos = i + len(batch)
            
            # NO limitar por tiempo, dejar que busque
        
        if url_encontrada:
            formato = url_encontrada.split('/')[-1]
            tiempo_total = time.time() - tiempo_inicio
            print(f"   ✅ Encontrado: {formato} ({tiempo_total:.1f}s, {intentos} URLs verificadas)")
            logging.info(f"Sumario encontrado: {url_encontrada}")
            return url_encontrada
        
        # No encontrado
        tiempo_total = time.time() - tiempo_inicio
        print(f"   ℹ️  No se encontró BOCM para {date_obj.strftime('%d/%m/%Y')}")
        print(f"      (Verificadas {intentos} URLs en {tiempo_total:.1f}s)")
        raise ScraperError(f"No hay BOCM publicado para {date_obj.strftime('%d/%m/%Y')}")


def download_sumario_temp(date_obj: datetime, scraper: BOCMScraper):
    """Descarga el sumario del BOCM en un archivo temporal"""
    if not REQUESTS_DISPONIBLE:
        print("❌ No se puede descargar: requests no disponible")
        return None
    
    try:
        sumario_url = scraper.get_sumario_url(date_obj)
        
        # Crear archivo temporal
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_path = temp_file.name
        temp_file.close()
        
        logging.info(f"Descargando sumario temporalmente: {sumario_url}")
        response = requests.get(sumario_url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            f.write(response.content)
            
        logging.info(f"Sumario descargado correctamente (temporal): {temp_path}")
        return temp_path
    except ScraperError as e:
        logging.error(f"[{date_obj.strftime('%Y-%m-%d')}] {e}")
        return None
    except Exception as e:
        logging.error(f"Error al descargar sumario para {date_obj.strftime('%Y-%m-%d')}: {e}")
        return None


# Mantener el resto de funciones igual
def extraer_documentos_del_sumario(ruta_sumario):
    """Extrae las URLs de todos los documentos referenciados en el sumario del BOCM"""
    if not PYPDF2_DISPONIBLE:
        print("❌ No se puede procesar PDF: PyPDF2 no disponible")
        return []
    
    if not REQUESTS_DISPONIBLE:
        print("❌ No se puede verificar URLs: requests no disponible")
        return []
    
    try:
        # Abrir el PDF del sumario
        with open(ruta_sumario, 'rb') as archivo:
            lector = PyPDF2.PdfReader(archivo)
            texto_sumario = ""
            
            # Extraer todo el texto del sumario
            for pagina in lector.pages:
                texto_sumario += pagina.extract_text()
        
        # Extraer la fecha del nombre del sumario si está en la ruta, o del contenido
        match_fecha = re.search(r'/CM_Boletin_BOCM/(\d{4})/(\d{2})/(\d{2})/', ruta_sumario)
        
        if not match_fecha:
            # Intentar extraer de cabecera del sumario
            fecha_regex = r'(\d{1,2})\s+DE\s+([A-ZÑ]+)\s+DE\s+(\d{4})'
            match_fecha_texto = re.search(fecha_regex, texto_sumario, re.IGNORECASE)
            
            if match_fecha_texto:
                dia = match_fecha_texto.group(1).zfill(2)
                mes_texto = match_fecha_texto.group(2).upper()
                anio = match_fecha_texto.group(3)
                
                # Convertir mes en texto a número
                meses = {
                    'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
                    'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
                    'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
                }
                mes = meses.get(mes_texto, '01')
            else:
                fecha_actual = datetime.now()
                anio = fecha_actual.strftime('%Y')
                mes = fecha_actual.strftime('%m')
                dia = fecha_actual.strftime('%d')
        else:
            anio = match_fecha.group(1)
            mes = match_fecha.group(2)
            dia = match_fecha.group(3)
        
        fecha_formateada = f"{anio}{mes}{dia}"
        
        # Lista para almacenar los documentos encontrados
        documentos = []
        
        # Buscamos secciones para identificar a qué consejería pertenece cada documento
        seccion_actual = ""
        lineas = texto_sumario.split('\n')
        
        for linea in lineas:
            linea = linea.strip()
            
            # Identificar secciones importantes (consejerías)
            if linea.isupper() and len(linea) > 10 and ('CONSEJERÍA' in linea or 'PRESIDENCIA' in linea):
                seccion_actual = linea
                logging.info(f"Sección identificada: {seccion_actual}")
                continue
                
            # Buscar documentos que comienzan con número
            match_doc = re.match(r'^\s*(\d+)\s+(.+)', linea.strip())
            if match_doc:
                num_doc = match_doc.group(1)
                descripcion = match_doc.group(2).strip()
                
                if seccion_actual:
                    descripcion_completa = f"{descripcion} - {seccion_actual}"
                else:
                    descripcion_completa = descripcion
                
                # Construir la URL del documento
                url_doc = f"https://www.bocm.es/boletin/CM_Orden_BOCM/{anio}/{mes}/{dia}/BOCM-{fecha_formateada}-{num_doc}.PDF"
                
                # Verificar si la URL existe
                try:
                    response = requests.head(url_doc, timeout=5)
                    if response.status_code == 200:
                        documentos.append({
                            'id': num_doc,
                            'descripcion': descripcion_completa,
                            'seccion': seccion_actual,
                            'url': url_doc
                        })
                        logging.info(f"Documento encontrado: {descripcion_completa}")
                except Exception as e:
                    logging.debug(f"Error al verificar documento {url_doc}: {e}")
        
        logging.info(f"Total de documentos extraídos del sumario: {len(documentos)}")
        return documentos
    
    except Exception as e:
        logging.error(f"Error al analizar el sumario: {e}")
        return []


def extraer_convenios_del_sumario(ruta_sumario):
    """Extrae TODOS los posibles convenios colectivos"""
    try:
        todos_documentos = extraer_documentos_del_sumario(ruta_sumario)
        
        if not todos_documentos:
            logging.warning("No se encontraron documentos en el sumario")
            return []
        
        palabras_clave_convenios = [
            'convenio colectivo',
            'acuerdo laboral',
            'convenio de empresa',
            'acuerdo de empresa',
            'pacto de empresa',
            'revisión salarial',
            'prórroga convenio',
            'acuerdo marco',
            'código número',
            'registro, depósito y publicación'
        ]
        
        convenios_seleccionados = []
        
        for doc in todos_documentos:
            descripcion_lower = doc['descripcion'].lower()
            
            if any(palabra in descripcion_lower for palabra in palabras_clave_convenios):
                convenios_seleccionados.append(doc)
                logging.info(f"Documento seleccionado: {doc['descripcion']}")
                
        logging.info(f"Total de documentos seleccionados: {len(convenios_seleccionados)}")
        return convenios_seleccionados
    
    except Exception as e:
        logging.error(f"Error al extraer convenios del sumario: {e}")
        return []


def extraer_codigo_convenio(texto):
    """Extrae códigos de convenio"""
    patrones = [
        r'Código número (\d{14})',
        r'código (?:de convenio )?n[úu]mero (?:\w+\.)?\s*(\d{5,14})',
        r'\((?:C|c)ódigo (?:n[úu]mero )?(\d{5,14})\)',
        r'BOCM-\d{8}-\d+.*?código\s+(\d{5,14})'
    ]
    
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            codigo = match.group(1).strip()
            return codigo
    
    return None


def extraer_nombre_convenio(texto):
    """Extrae un nombre simplificado para el convenio"""
    consejeria_pattern = r'(Consejería de [^,\.]+)'
    match_consejeria = re.search(consejeria_pattern, texto, re.IGNORECASE)
    
    if match_consejeria:
        orden_pattern = r'ORDEN\s+(\d+/\d+|\d+\s+de\s+[a-zñáéíóú]+)'
        match_orden = re.search(orden_pattern, texto, re.IGNORECASE)
        
        if match_orden:
            return f"{match_orden.group(0)}, {match_consejeria.group(0)}"
        else:
            inicio_pattern = r'(ORDEN|RESOLUCIÓN)([^\.]+)'
            match_inicio = re.search(inicio_pattern, texto, re.IGNORECASE)
            if match_inicio:
                return f"{match_inicio.group(1)}{match_inicio.group(2)[:50]}... - {match_consejeria.group(0)}"
    
    bocm_pattern = r'BOCM-(\d+-\d+)'
    match_bocm = re.search(bocm_pattern, texto)
    if match_bocm:
        return f"BOCM {match_bocm.group(1)}"
        
    return texto.replace("\n", " ")[:150]


def extraer_info_convenio(ruta_pdf):
    """Extrae el título y número de convenio de un PDF"""
    if not PYPDF2_DISPONIBLE:
        print("❌ No se puede procesar PDF: PyPDF2 no disponible")
        return {
            'archivo': os.path.basename(ruta_pdf),
            'titulo': None,
            'codigo': None
        }
    
    try:
        with open(ruta_pdf, 'rb') as archivo:
            lector = PyPDF2.PdfReader(archivo)
            
            paginas_a_analizar = min(5, len(lector.pages))
            texto = ""
            for i in range(paginas_a_analizar):
                texto += lector.pages[i].extract_text()
        
        titulo = extraer_nombre_convenio(texto)
        
        if not titulo:
            nombre_archivo = os.path.basename(ruta_pdf)
            match_nombre = re.search(r'BOCM-(\d+)-(\d+)', nombre_archivo)
            if match_nombre:
                fecha = match_nombre.group(1)
                numero = match_nombre.group(2)
                titulo = f"Documento BOCM {fecha}-{numero}"
            else:
                titulo = f"Documento {nombre_archivo}"
        
        codigo = extraer_codigo_convenio(texto)
        
        if not codigo:
            nombre_archivo = os.path.basename(ruta_pdf)
            match_nombre = re.search(r'BOCM-(\d+)-(\d+)', nombre_archivo)
            if match_nombre:
                codigo = f"BOCM-{match_nombre.group(1)}-{match_nombre.group(2)}"
        
        return {
            'archivo': os.path.basename(ruta_pdf),
            'titulo': titulo,
            'codigo': codigo
        }
        
    except Exception as e:
        logging.error(f"Error al extraer información del convenio {ruta_pdf}: {e}")
        return {
            'archivo': os.path.basename(ruta_pdf),
            'titulo': None,
            'codigo': None
        }


def procesar_pdfs(directorio_o_lista):
    """Procesa todos los PDFs en el directorio y extrae información"""
    if not PYPDF2_DISPONIBLE:
        print("❌ No se pueden procesar PDFs: PyPDF2 no disponible")
        return []
    
    resultados = []
    
    if isinstance(directorio_o_lista, list):
        archivos_pdf = directorio_o_lista
    else:
        if GLOB_DISPONIBLE:
            archivos_pdf = glob.glob(os.path.join(directorio_o_lista, "*.PDF")) + glob.glob(os.path.join(directorio_o_lista, "*.pdf"))
        else:
            archivos_pdf = []
            if os.path.exists(directorio_o_lista):
                for archivo in os.listdir(directorio_o_lista):
                    if archivo.lower().endswith('.pdf'):
                        archivos_pdf.append(os.path.join(directorio_o_lista, archivo))
    
    if not archivos_pdf:
        logging.info("No se encontraron archivos PDF para procesar.")
        return resultados
    
    logging.info(f"Procesando {len(archivos_pdf)} archivos PDF...")
    
    for archivo in archivos_pdf:
        info = extraer_info_convenio(archivo)
        resultados.append((
            info['archivo'],
            info['titulo'] if info['titulo'] else "No identificado",
            info['codigo'] if info['codigo'] else "No identificado"
        ))
    
    return resultados


def descargar_convenios(convenios_info, directorio_destino):
    """Descarga los convenios a partir de la información proporcionada"""
    if not REQUESTS_DISPONIBLE:
        print("❌ No se pueden descargar convenios: requests no disponible")
        return []
    
    if not convenios_info:
        logging.warning("No hay convenios para descargar")
        return []
    
    if not os.path.exists(directorio_destino):
        os.makedirs(directorio_destino)
    
    logging.info(f"Descargando {len(convenios_info)} posibles convenios")
    
    rutas_descargadas = []
    
    for convenio in convenios_info:
        url = convenio['url']
        filename = url.split('/')[-1]
        ruta_local = os.path.join(directorio_destino, filename)
        
        try:
            if os.path.exists(ruta_local):
                logging.info(f"El archivo ya existe: {filename}")
                rutas_descargadas.append(ruta_local)
                continue
            
            logging.info(f"Descargando convenio: {url}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                with open(ruta_local, 'wb') as archivo:
                    archivo.write(response.content)
                logging.info(f"Convenio descargado: {filename}")
                rutas_descargadas.append(ruta_local)
            else:
                logging.warning(f"No se pudo descargar {url}: Error {response.status_code}")
                
        except Exception as e:
            logging.error(f"Error al descargar {url}: {e}")
    
    return rutas_descargadas


def estado_dependencias():
    """Devuelve el estado de las dependencias"""
    return {
        'requests': REQUESTS_DISPONIBLE,
        'beautifulsoup4': BS4_DISPONIBLE,
        'PyPDF2': PYPDF2_DISPONIBLE,
        'glob': GLOB_DISPONIBLE
    }


def mensaje_dependencias_faltantes():
    """Genera mensaje con dependencias faltantes"""
    estado = estado_dependencias()
    faltantes = [nombre for nombre, disponible in estado.items() if not disponible]
    
    if faltantes:
        return f"⚠️  Dependencias faltantes: {', '.join(faltantes)}\n   Ejecuta: python instalar_dependencias.py"
    else:
        return "✅ Todas las dependencias están disponibles"