import os
import re
import json
import logging
try:
    import PyPDF2
except ImportError:
    print("PyPDF2 no instalado. Instala con: pip install PyPDF2")
    PyPDF2 = None
try:
    import glob
except ImportError:
    print("Glob debería estar disponible por defecto")
    glob = None
from datetime import datetime
# Verificaciones de dependencias
if not PyPDF2:
    def _no_pypdf2(*args, **kwargs):
        raise ImportError("PyPDF2 no está instalado. Ejecuta: pip install PyPDF2")
    
    class MockPyPDF2:
        class PdfReader:
            def __init__(self, *args, **kwargs): raise ImportError("PyPDF2 no disponible")
    
    PyPDF2 = MockPyPDF2()

# Importar funciones de bocm_scraper con manejo de errores
try:
    from bocm_scraper import extraer_codigo_convenio, extraer_nombre_convenio
except ImportError:
    print("⚠️  No se pueden importar funciones de bocm_scraper")
    def extraer_codigo_convenio(texto): return None
    def extraer_nombre_convenio(texto): return "Sin identificar"

def setup_reference_folder():
    """Configura la carpeta de PDFs de referencia para códigos de convenio"""
    directorio_referencia = 'convenios_referencia'
    if not os.path.exists(directorio_referencia):
        os.makedirs(directorio_referencia)
        logging.info(f"Directorio de referencia creado: {directorio_referencia}")
    return directorio_referencia

def cargar_base_conocimiento():
    """Carga o crea la base de conocimiento de códigos de convenio"""
    archivo_conocimiento = 'codigos_convenios.json'
    
    if os.path.exists(archivo_conocimiento):
        try:
            with open(archivo_conocimiento, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error al cargar base de conocimiento: {e}")
            return {}
    else:
        # Crear archivo vacío
        with open(archivo_conocimiento, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        return {}

def guardar_base_conocimiento(base_conocimiento):
    """Guarda la base de conocimiento actualizada"""
    archivo_conocimiento = 'codigos_convenios.json'
    with open(archivo_conocimiento, 'w', encoding='utf-8') as f:
        json.dump(base_conocimiento, f, ensure_ascii=False, indent=2)

def extraer_empresa_de_descripcion(texto):
    """
    Extrae nombres de empresas basados en los ejemplos reales del BOCM
    """
    # Patrones basados en los BOCMs 2025
    patrones = [
        # Patrón para "Municipal de Transportes de Fuenlabrada"
        r'empresa (?:Municipal de Transportes de |)(.+?)(?: y | de | del |,|\.|$)',
        # Patrón para "Coordinadora Integral Óptica de Servicios Agrupados, S. L."
        r'empresa (.+?),? S\. ?L\.',
        # Patrón para "Boortmalt Spain, S. L."
        r'empresa (.+?),? S\. ?L\.',
        # Patrones generales
        r'convenio colectivo (?:de|para) (?:la empresa )?(.+?)(?: y | de | del | sobre |,|\.|$)'
    ]
    
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            empresa = match.group(1).strip()
            # Limpiar palabras comunes
            for palabra in ['la', 'el', 'los', 'las', 'empresa', 'compañía']:
                empresa = re.sub(r'\b' + palabra + r'\b', '', empresa, flags=re.IGNORECASE)
            return empresa.strip()
    
    # Si no se encuentra con patrones, extraer de la descripción
    palabras = texto.split()
    if len(palabras) > 3:
        # Buscar palabras clave como "empresa" o "convenio"
        for i, palabra in enumerate(palabras):
            if palabra.lower() in ['empresa', 'convenio'] and i+1 < len(palabras):
                return ' '.join(palabras[i+1:i+4])
    
    return None

def detectar_posibles_cambios(convenios_info, base_conocimiento):
    """
    Analiza la información del sumario para detectar posibles cambios en códigos
    de convenio, comparando con la base de conocimiento.
    """
    convenios_a_descargar = []
    convenios_sin_cambios = []
    
    # Palabras clave que indican modificaciones basadas en los BOCMs analizados
    indicadores_cambio = [
        'modificación', 'revisión', 'actualización', 'prórroga', 
        'extensión', 'ampliación', 'cambio', 'nuevo', 'corrección',
        'registro', 'depósito', 'publicación', 'acuerdo'
    ]
    
    for convenio in convenios_info:
        descripcion = convenio['descripcion'].lower()
        
        # 1. Indicadores explícitos de cambio en la descripción
        if any(indicador in descripcion for indicador in indicadores_cambio):
            print(f"Posible cambio detectado en: {convenio['descripcion']}")
            convenios_a_descargar.append(convenio)
            continue
            
        # 2. Extraer posible empresa o sector
        empresa = extraer_empresa_de_descripcion(descripcion)
        
        # 3. Verificar si ya existe en la base de conocimiento
        if empresa and empresa in base_conocimiento:
            ultimo_registro = base_conocimiento[empresa]
            
            # Verificar por fecha (más de 6 meses = posible actualización)
            ultima_fecha = ultimo_registro.get('fecha', '20000101')
            fecha_actual = datetime.now().strftime('%Y%m%d')
            
            if int(fecha_actual) - int(ultima_fecha) > 180:
                print(f"Posible actualización por tiempo: {convenio['descripcion']}")
                convenios_a_descargar.append(convenio)
                continue
            
            # Verificar términos de temporalidad
            if any(term in ultimo_registro.get('descripcion', '') for term in 
                  ['temporal', 'provisional', 'transitorio', 'vigencia', 'hasta']):
                print(f"Posible actualización por fin de vigencia: {convenio['descripcion']}")
                convenios_a_descargar.append(convenio)
                continue
            
            # Si no hay indicios de cambio, marcar como sin cambios
            print(f"Sin indicios de cambio: {convenio['descripcion']}")
            convenios_sin_cambios.append(convenio)
            continue
        
        # 4. Si no está en la base de conocimiento, descargar (posible nuevo convenio)
        print(f"Posible nuevo convenio: {convenio['descripcion']}")
        convenios_a_descargar.append(convenio)
    
    return convenios_a_descargar, convenios_sin_cambios

def procesar_pdfs_referencia(directorio_referencia):
    """
    Procesa los PDFs de referencia para extraer códigos de convenio
    y actualizar la base de conocimiento
    """
    print("\n--- Procesando PDFs de referencia ---")
    base_conocimiento = cargar_base_conocimiento()
    
    # Buscar PDFs en el directorio de referencia
    archivos_pdf = glob.glob(os.path.join(directorio_referencia, "*.PDF")) + glob.glob(os.path.join(directorio_referencia, "*.pdf"))
    
    if not archivos_pdf:
        print("No se encontraron PDFs de referencia. Por favor, añade algunos.")
        return base_conocimiento
    
    for archivo in archivos_pdf:
        try:
            # Extraer información del PDF
            with open(archivo, 'rb') as f:
                lector = PyPDF2.PdfReader(f)
                texto = ""
                # Primeras páginas suelen contener la info relevante
                for i in range(min(5, len(lector.pages))):
                    texto += lector.pages[i].extract_text()
            
            # Extraer código de convenio
            codigo = extraer_codigo_convenio(texto)
            if not codigo:
                print(f"No se pudo extraer código de: {os.path.basename(archivo)}")
                continue
                
            # Extraer nombre de empresa/sector
            empresa = extraer_empresa_de_descripcion(texto.lower())
            if not empresa:
                print(f"No se pudo identificar empresa en: {os.path.basename(archivo)}")
                continue
                
            # Extraer fecha del documento (del nombre de archivo BOCM-YYYYMMDD-XX.PDF)
            fecha = "20000101"  # Valor por defecto
            match_fecha = re.search(r'BOCM-(\d{8})-', os.path.basename(archivo))
            if match_fecha:
                fecha = match_fecha.group(1)
            
            # Guardar en base de conocimiento
            base_conocimiento[empresa] = {
                'codigo': codigo,
                'fecha': fecha,
                'archivo': os.path.basename(archivo),
                'descripcion': texto[:200].replace('\n', ' ')
            }
            
            print(f"Referencia procesada: {empresa} -> Código: {codigo}")
            
        except Exception as e:
            print(f"Error al procesar {os.path.basename(archivo)}: {e}")
    
    # Guardar base de conocimiento actualizada
    guardar_base_conocimiento(base_conocimiento)
    print(f"Base de conocimiento actualizada con {len(base_conocimiento)} registros")
    
    return base_conocimiento

def verificar_cambio_real(convenio_pdf, base_conocimiento):
    """
    Verifica si el PDF descargado contiene realmente un código diferente
    al registrado en la base de conocimiento
    """
    try:
        # Extraer información del PDF
        with open(convenio_pdf, 'rb') as f:
            lector = PyPDF2.PdfReader(f)
            texto = ""
            for i in range(min(5, len(lector.pages))):
                texto += lector.pages[i].extract_text()
        
        # Extraer código y empresa
        codigo_nuevo = extraer_codigo_convenio(texto)
        if not codigo_nuevo:
            print(f"No se pudo extraer código de convenio de {os.path.basename(convenio_pdf)}")
            return False, None, None
        
        empresa = extraer_empresa_de_descripcion(texto.lower())
        if not empresa:
            # Intentar extraer del nombre del archivo
            nombre_archivo = os.path.basename(convenio_pdf)
            print(f"No se pudo extraer empresa del PDF {nombre_archivo}, usando nombre de archivo")
            empresa = nombre_archivo
        
        # Verificar cambios mediante patrones específicos en el texto
        indicadores_cambio_texto = [
            'modificación del convenio', 
            'revisión salarial',
            'actualización', 
            'prórroga', 
            'cambio de código',
            'nueva publicación',
            'modificación parcial'
        ]
        
        cambio_detectado_en_texto = any(indicador in texto.lower() for indicador in indicadores_cambio_texto)
        
        # Verificar si la empresa está en la base de conocimiento
        if empresa in base_conocimiento:
            codigo_anterior = base_conocimiento[empresa]['codigo']
            
            # Comparar códigos (detección de cambio real)
            if codigo_anterior != codigo_nuevo:
                print(f"\n*** CAMBIO DETECTADO EN CÓDIGO DE CONVENIO ***")
                print(f"Empresa: {empresa}")
                print(f"Código anterior: {codigo_anterior}")
                print(f"Código nuevo: {codigo_nuevo}")
                print(f"Modificado el código {codigo_anterior} → {codigo_nuevo}")
                return True, codigo_anterior, codigo_nuevo
            elif cambio_detectado_en_texto:
                print(f"\nSe detectaron indicadores de cambio en el texto, pero el código sigue siendo {codigo_nuevo}")
                return False, codigo_anterior, codigo_nuevo
            else:
                print(f"\nCódigo sin cambios para {empresa}: {codigo_nuevo}")
                return False, codigo_anterior, codigo_nuevo
        else:
            # Convenio nuevo (no existe en la base de conocimiento)
            print(f"\n*** NUEVO CONVENIO DETECTADO ***")
            print(f"Empresa: {empresa}")
            print(f"Código: {codigo_nuevo}")
            return True, None, codigo_nuevo
        
    except Exception as e:
        print(f"Error al verificar cambio en {convenio_pdf}: {e}")
        return False, None, None