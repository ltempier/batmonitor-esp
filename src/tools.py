from machine import RTC, Pin
from neopixel import NeoPixel
import _thread
import time

from env import env

led_pin = Pin(48, Pin.OUT)
np = NeoPixel(led_pin, 1)

def set_led_rgba(red, green, blue, brightness=1.0):
    red = max(0, min(255, int(red * brightness)))
    green = max(0, min(255, int(green * brightness)))
    blue = max(0, min(255, int(blue * brightness)))
    
    # Appliquer la couleur à la LED
    np[0] = (red, green, blue)
    np.write()
    
    return np

def blink_led(count=1, on_time=0.5, off_time=0.5, color=(255,255,255)):
    if len(color) == 3: 
        r, g, b = color
        a = 1 
    elif len(color) == 4:  
        r, g, b, a = color
    else:
        raise ValueError("Le paramètre 'color' doit être un tuple de longueur 3 (r, g, b) ou 4 (r, g, b, a).")
  
    def thread_function():
        for i in range(count):
            set_led_rgba(r,g,b,a)
            time.sleep(on_time)
            set_led_rgba(0, 0, 0, 0)
            if i < count - 1:
                time.sleep(off_time)

    _thread.start_new_thread(thread_function, ())
    
def get_rtc_datetime_str():
    rtc = RTC()
    year, month, day, _ , hour, minute, second, microseconds = rtc.datetime()
    return datetime_to_iso_str(year, month, day, hour, minute, second, microseconds)


def datetime_to_iso_str(year, month, day, hour, minute, second=0, microseconds=0 ):
    date_str = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
    
    if  microseconds != 0:
        date_str+= f".{int(microseconds / 1000):03d}"
    
    is_utc = env.get('IS_UTC', False)
    if is_utc:
        date_str += "Z"
    return date_str

def get_timestamp_from_rtc_datetime():
    rtc = RTC()
    year, month, day, weekday, hour, minute, second, microsecondes = rtc.datetime()
    
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Vérifier si l'année est bissextile
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days_in_month[1] = 29
    
    # Calculer les jours depuis 1970
    days = 0
    for y in range(1970, year):
        days += 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
    
    # Ajouter les jours des mois de l'année courante
    for m in range(1, month):
        days += days_in_month[m - 1]
    
    # Ajouter les jours du mois courant
    days += day - 1
    
    # Convertir en millisecondes
    millisecondes = days * 86400 * 1000  # Jours en millisecondes
    millisecondes += hour * 3600 * 1000  # Heures en millisecondes
    millisecondes += minute * 60 * 1000  # Minutes en millisecondes
    millisecondes += second * 1000       # Secondes en millisecondes
    millisecondes += microsecondes // 1000  # Microsecondes converties en millisecondes (division entière)
    #print(f"{(year, month, day, weekday, hour, minute, second, microsecondes)} => {timestamp}")
    
    return millisecondes

def get_mime_type(filepath):
    """Retourne le type MIME en fonction de l'extension du fichier."""
    ext = filepath.lower().split('.')[-1]
    mime_types = {
        'html': 'text/html',
        'js': 'application/javascript',
        'css': 'text/css',
        'png': 'image/png',
        'jpeg': 'image/jpeg',
        'jpg': 'image/jpeg',
        'gif': 'image/gif',
        'ico': 'image/x-icon',
        'json': 'application/json',
        'txt': 'text/plain',
        'csv': 'text/plain',
    }
    return mime_types.get(ext, 'application/octet-stream')


def parse_iso_date_str(date_str):
    """Parse une chaîne date-time 'YYYY-MM-DDTHH:MM:SS[.mmm][Z]' en tuple (year, month, day, hour, minute, second, microseconds).
    Raises ValueError pour formats ou valeurs invalides.
    """
    try:
        # Split into date and time parts
        date_part, time_part = date_str.split("T")
        year, month, day = date_part.split("-")

        microseconds = 0
        is_utc = False
        if time_part.endswith('Z'):
            is_utc = True
            time_part = time_part[:-1]  # Enlève le 'Z'
        
        hour, minute, second = time_part.split(":")
        
        if '.' in second:
            second, milliseconds = second.split(".")
            microseconds = int(milliseconds) * 1000

        # Convert to integers
        year = int(year)
        month = int(month)
        day = int(day)
        hour = int(hour)
        minute = int(minute)
        second = int(second)

        # Create date tuple
        date_tuple = (year, month, day, hour, minute, second, microseconds)

        # Validate the date
        is_valid_date(date_tuple)
        
        return date_tuple

    except ValueError as e:
        # Handle conversion errors or invalid date format
        if str(e).startswith("Invalid"):
            raise e  # Re-raise validation errors from is_valid_date
        raise ValueError("Invalid date string format. Expected 'YYYY-MM-DDTHH:MM:SS'")
    except Exception:
        raise ValueError("Invalid date string format. Expected 'YYYY-MM-DDTHH:MM:SS'")
    

def is_valid_date(date):
    """Validate a date tuple: (year, month, day, hour, minute, second, microseconds).
    Raises ValueError if the date is invalid, returns True if valid.
    """
    # Unpack the date tuple
    try:
        year, month, day, hour, minute, second, microseconds = date
    except ValueError:
        raise ValueError("Date must be a tuple of 7 elements: (year, month, day, hour, minute, second, microseconds)")

    # Validate year (>= 2025)
    if not isinstance(year, int) or year < 2025:
        raise ValueError("Invalid year: must be an integer >= 2025")

    # Validate month
    if not isinstance(month, int) or not (1 <= month <= 12):
        raise ValueError("Invalid month: must be an integer between 1 and 12")

    # Validate day (considering month and leap year)
    if not isinstance(day, int):
        raise ValueError("Invalid day: must be an integer")

    # Days in each month (non-leap year)
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Adjust February for leap years
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days_in_month[1] = 29

    if not (1 <= day <= days_in_month[month - 1]):
        raise ValueError(f"Invalid day: must be between 1 and {days_in_month[month - 1]} for month {month}")

    # Validate hour
    if not isinstance(hour, int) or not (0 <= hour <= 23):
        raise ValueError("Invalid hour: must be an integer between 0 and 23")

    # Validate minute
    if not isinstance(minute, int) or not (0 <= minute <= 59):
        raise ValueError("Invalid minute: must be an integer between 0 and 59")

    # Validate second
    if not isinstance(second, int) or not (0 <= second <= 59):
        raise ValueError("Invalid second: must be an integer between 0 and 59")

    # Validate microseconds
    if not isinstance(microseconds, int) or not (0 <= microseconds <= 999999):
        raise ValueError("Invalid microseconds: must be an integer between 0 and 999999")

    return True
    

def is_date_after(date_after, date_before):
    """Compare two dates to check if date_after is after date_before.
    Dates are tuples/lists: (year, month, day, hour, minute, second, microseconds).
    """
    # Ensure both inputs are valid and have the same length
    if not date_after or not date_before:
        raise ValueError("Date tuples/lists cannot be empty")
    if len(date_after) != len(date_before):
        raise ValueError("Date tuples/lists must have the same length")

    for i in range(len(date_before)):
        if date_after[i] > date_before[i]:
            return True
        elif date_after[i] < date_before[i]:
            return False
    return False  # If all components are equal, date_after is not after date_before
    
    
def format_memory(used, total):
    if total <= 0:
        return "0.0/0.0 (0%)"
    used_mo = round(used / (1024 * 1024), 1)
    total_mo = round(total / (1024 * 1024), 1)
    percent = round(100 * used / total, 1)
    return f"{used_mo} Mo / {total_mo} Mo ({percent}%)"
    
    
    
    