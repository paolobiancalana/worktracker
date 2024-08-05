import logging
import os

# Crea una directory per i log se non esiste
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configura il logger
logger = logging.getLogger('WorkTracker')
logger.setLevel(logging.DEBUG)

# Crea un file handler che registra i debug e superiori
fh = logging.FileHandler('logs/work_tracker.log')
fh.setLevel(logging.DEBUG)

# Crea un console handler che registra info e superiori
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Crea un formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# Aggiungi gli handler al logger
logger.addHandler(fh)
logger.addHandler(ch)