try:
    import mysql.connector
except ImportError:
    print("mysql-connector-python no instalado. Instala con: pip install mysql-connector-python")
    mysql = None
# Verificación de MySQL
if not mysql:
    class MockMySQL:
        class connector:
            @staticmethod
            def connect(*args, **kwargs):
                raise ImportError("mysql-connector-python no disponible. Ejecuta: pip install mysql-connector-python")
            
            class Error(Exception):
                pass
    
    mysql = MockMySQL()

import json

#CRUD para la tabla convenios
def conectar_a_bbdd(silencioso=True):
    try:
        
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='root',
            database='convenios'
        )
        if not silencioso:
            print("Conexión a la base de datos establecida.")
        cursor = conn.cursor()
        return conn, cursor
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None, None
    
    
def insertar_convenio(nombre_convenio, id_procedencia, codigo_principal):
    if nombre_ya_esta(nombre_convenio):
        trigger_actualizar_convenio(nombre_convenio, id_procedencia, codigo_principal)
        print(f"El convenio '{nombre_convenio}' ya existe en la base de datos.")
        return None
    
    conn, cursor = conectar_a_bbdd(silencioso=True)
    query = """
    INSERT INTO convenios(nombre_convenio, id_procedencia, codigo_principal, codigos_historicos, id_version_actual)
    VALUES (%s, %s, %s, %s, %s)
    """
    codigos_historicos = json.dumps([])  # vacío al crear
    id_version_actual = None  # aún no hay versión
    params = (nombre_convenio, id_procedencia, codigo_principal, codigos_historicos, id_version_actual)
    cursor.execute(query, params)
    conn.commit()
    print("Convenio insertado correctamente.")
    return cursor.lastrowid  # devuelve el id_convenio insertado


def nombre_ya_esta(nombre_convenio):

    # Luego verificamos en la base de datos
    conn, cursor = conectar_a_bbdd(silencioso=True)
    query = """
        SELECT 1 FROM convenios 
        WHERE nombre_convenio = %s
        LIMIT 1
    """
    cursor.execute(query, (nombre_convenio,))
    existe = cursor.fetchone() is not None

    # Cerramos la conexión
    cursor.close()
    conn.close()

    return existe


def trigger_actualizar_convenio(nombre_convenio, id_procedencia, codigo_principal):
    conn, cursor = conectar_a_bbdd(silencioso=True)
    # Busca por nombre o por código principal
    query_select = """
        SELECT id_convenio FROM convenios
        WHERE nombre_convenio = %s OR codigo_principal = %s
        LIMIT 1
    """
    cursor.execute(query_select, (nombre_convenio, codigo_principal))
    row = cursor.fetchone()
    if row:
        id_convenio = row[0]
        # Actualiza los campos que quieras (aquí id_procedencia y codigo_principal)
        query_update = """
            UPDATE convenios
            SET id_procedencia = %s, codigo_principal = %s
            WHERE id_convenio = %s
        """
        cursor.execute(query_update, (id_procedencia, codigo_principal, id_convenio))
        conn.commit()
        print(f"Convenio actualizado correctamente (id: {id_convenio}).")
    else:
        print("No se encontró convenio para actualizar.")
    cursor.close()
    conn.close()
    
    
def insertar_codigo_historico(codigo_principal, nombre_convenio):
    conn, cursor = conectar_a_bbdd(silencioso=True)
    
    # Actualizar el campo codigos_historicos
    query = """
    UPDATE convenios
    SET codigos_historicos = JSON_ARRAY_APPEND(codigos_historicos, '$', %s)
    WHERE nombre_convenio = %s
    """
    
    params = (codigo_principal, nombre_convenio)
    
    cursor.execute(query, params)
    conn.commit()
    print("Código histórico insertado correctamente.")

    
def insertar_convenios_versiones(id_convenio, version_num, codigo_publicado, fecha_publicacion, fecha_inicio_vigencia, fecha_fin_vigencia, etapa_vigencia, resumen, fuente_pdf):
    conn, cursor = conectar_a_bbdd(silencioso=True)
    query = """
    INSERT INTO convenios_versiones (
        id_convenio, version_num, codigo_publicado, fecha_publicacion, fecha_inicio_vigencia, fecha_fin_vigencia, etapa_vigencia, resumen, fuente_pdf
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (id_convenio, version_num, codigo_publicado, fecha_publicacion, fecha_inicio_vigencia, fecha_fin_vigencia, etapa_vigencia, resumen, fuente_pdf)
    cursor.execute(query, params)
    conn.commit()
    print("Convenio_version insertado correctamente.")
    return cursor.lastrowid  # devuelve el id_version insertado

def actualizar_id_version_actual(id_convenio, id_version):
    conn, cursor = conectar_a_bbdd(silencioso=True)
    query = "UPDATE convenios SET id_version_actual = %s WHERE id_convenio = %s"
    cursor.execute(query, (id_version, id_convenio))
    conn.commit()
    print("id_version_actual actualizado correctamente.")
    

def leer_convenios_versiones():
    conn, cursor = conectar_a_bbdd(silencioso=True)
    cursor.execute("SELECT * FROM convenios_versiones;")
    for fila in cursor.fetchall():
        print(fila)
        
def leer_convenios():
    conn, cursor = conectar_a_bbdd(silencioso=True)
    cursor.execute("SELECT * FROM convenios;")
    for fila in cursor.fetchall():
        print(fila)        
        
    

    