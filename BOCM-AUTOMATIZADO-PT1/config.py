# Configuraciones

import os
import logging

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONVENIOS_DIR = os.path.join(BASE_DIR, "convenios_bocm")
REFERENCIAS_DIR = os.path.join(BASE_DIR, "convenios_referencia")
KNOWLEDGE_FILE = os.path.join(BASE_DIR, "codigos_convenios.json")

# ID de procedencia fijo
ID_PROCEDENCIA = 3

# Configuración de logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='bocm_scraper.log',
        filemode='a'
    )