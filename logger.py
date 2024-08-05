import logging

class CompactFormatter(logging.Formatter):
    def format(self, record):
        # Aggiunge asctime al record se non è già presente
        if not hasattr(record, 'asctime'):
            record.asctime = self.formatTime(record, self.datefmt)
        
        formatted_record = f"{record.asctime} [{record.levelname}] {record.getMessage()}"
        return formatted_record

# Configura il logger per utilizzare il CompactFormatter
logger = logging.getLogger('WorkTracker')
logger.setLevel(logging.DEBUG)  # Imposta il livello di log

formatter = CompactFormatter('%(asctime)s [%(levelname)s] %(message)s')

file_handler = logging.FileHandler('worktracker.log')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

def log_user_action(user, action, level=logging.INFO):
    logger.log(level, f"{user}: {action}")

def log_exception(user, message):
    logger.exception(f"{user}: {message}")
