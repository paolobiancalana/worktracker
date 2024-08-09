import logging
from config import Config

# Configurazione del logger
logger = logging.getLogger('WorkTracker')
logger.setLevel(Config.LOG_LEVEL)

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(module)s: %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler('logs/work_tracker.log')
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

def log_user_action(user, message):
    logger.info(f"{user}: {message}")

def log_exception(exception, message="Exception occurred"):
    logger.error(f"{message}: {exception}")
