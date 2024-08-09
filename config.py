import os, yaml
from dotenv import load_dotenv
import logging

load_dotenv()

class Config:
    CLIENT = os.getenv('CLIENT', 'discord')
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD_ID = os.getenv('GUILD_ID')
    
    WORK_START_TIME = "09:00"
    WORK_END_TIME = "18:00"
    WORK_BUFFER_BEFORE = 60
    WORK_BUFFER_AFTER = 60

    LUNCH_START_TIME = "13:00"
    LUNCH_END_TIME = "14:00"
    LUNCH_BUFFER_BEFORE = 30
    LUNCH_BUFFER_AFTER = 30

    CHECK_OFFLINE_LIMIT_TIME = "11:00"
    
    # Durata delle pause
    BREAK_DURATION = 15  # Durata massima di una pausa breve (in minuti)
    MAX_EXTENDED_BREAK_DURATION = 30
    MAX_LUNCH_DURATION = 60
    
    # Buffer per lo stato IDLE
    IDLE_BUFFER_TIME = 5  # Tempo aggiuntivo da attendere quando l'utente passa a IDLE (in minuti)
    
    # Altre configurazioni
    DISCORD_IDLE_TIME = 10  # Tempo dopo il quale Discord cambia lo stato in idle (in minuti)

    # Nuove configurazioni per straordinari e giorni festivi
    REGULAR_WORK_HOURS = 8  # Ore di lavoro regolari in un giorno
    MAX_WORK_HOURS = 12  # Massimo numero di ore di lavoro consentite in un giorno
    OVERTIME_THRESHOLD = 40  # Ore settimanali dopo le quali inizia lo straordinario
    HOLIDAY_WORK_MULTIPLIER = 1.5  # Moltiplicatore per il lavoro nei giorni festivi

    # Livello di log
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()

    #DEBUG
    INTERACTIVE_MODE = False
    TESTING = os.getenv('TESTING', 'False').lower() == 'true'
    TEST_USER_DISCORD_ID = os.getenv('TEST_USER_DISCORD_ID')
    SIMULATE_WORK_HOURS = os.getenv('SIMULATE_WORK_HOURS', 'False').lower() == 'true'
    SILENT_MODE = True

    @staticmethod
    def get_logging_level():
        return getattr(logging, Config.LOG_LEVEL, logging.DEBUG)

    @staticmethod
    def load_status_mapping():
        with open('status_mapping.yaml', 'r') as file:
            mappings = yaml.safe_load(file)
        return mappings.get(Config.CLIENT, {})

    @staticmethod
    def is_workday(date):
        return date.weekday() < 5

    @staticmethod
    def is_holiday(date):
        # Qui potresti implementare una logica più complessa per determinare i giorni festivi
        # Per ora, consideriamo solo i weekend come giorni festivi
        return date.weekday() >= 5