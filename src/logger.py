from tools import get_rtc_datetime_str

class Logger:
    _instance = None  # ← Logger singleton !

    def __new__(cls, *args, **kwargs):
        """Logger : Une seule instance TOUJOURS"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.entries = []
            self.max_logs = 500

    def add(self, message=None, tag=None):
        if message is None:
            return
        
        print(message)

        self.entries.append((get_rtc_datetime_str(),str(message),tag))

        if len(self.entries) > self.max_logs:
            self.entries.pop(0)  # FIFO


# === Instance unique ===
logger = Logger() 


# === Récupérer les logs : plus récent → plus ancien ===
def get_logs():
    """Retourne les logs du plus récent au plus ancien"""
    return logger.entries[::-1]

# === Fonctions de log ===
def log(*args, tag="INFO"):
    message = ' '.join(map(str, args)) if args else None
    logger.add(message, tag)

def log_err(*args):
    message = ' '.join(map(str, args)) if args else None
    logger.add(message, 'ERR')

def log_warn(*args):
    message = ' '.join(map(str, args)) if args else None
    logger.add(message, 'WARN')