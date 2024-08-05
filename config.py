import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD_ID = os.getenv('GUILD_ID')
    
    # Orari di lavoro
    WORK_START_TIME = "07:00"  # Orario di inizio della giornata lavorativa
    WORK_END_TIME = "18:00"  # Orario di fine della giornata lavorativa
    
    # Orari della pausa pranzo
    LUNCH_START_TIME = "12:45"  # Orario di inizio della pausa pranzo
    LUNCH_END_TIME = "14:30"  # Orario di fine della pausa pranzo
    
    # Durata delle pause
    BREAK_DURATION = 15  # Durata massima di una pausa breve (in minuti)
    
    # Buffer per lo stato IDLE
    IDLE_BUFFER_TIME = 5  # Tempo aggiuntivo da attendere quando l'utente passa a IDLE (in minuti)
    
    # Altre configurazioni
    DISCORD_IDLE_TIME = 10  # Tempo dopo il quale Discord cambia lo stato in idle (in minuti)
    
    TESTING = os.getenv('TESTING', 'False').lower() == 'true'
    TEST_USER_DISCORD_ID = os.getenv('TEST_USER_DISCORD_ID')
    SIMULATE_WORK_HOURS = os.getenv('SIMULATE_WORK_HOURS', 'False').lower() == 'true'
    SILENT_MODE = True
