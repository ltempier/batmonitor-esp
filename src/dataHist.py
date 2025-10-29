import time
from machine import RTC
import os
import _thread

from tools import is_date_after, is_valid_date, datetime_to_iso_str, parse_iso_date_str
from env import env
from logger import log, log_warn, log_err

class DataHist:
    def __init__(self, max_size=1000, load_backup=True):
        """Initialiser l'historique des données."""
        self.max_size = max_size
        self.data = []  # Liste pour stocker les mesures
        self.rtc = RTC()
        self.old_datetime = None
        self.dir_path = './data'
        self.backup_file_path = f"{self.dir_path}/backup_every_10_minutes.txt"
        self.lock = _thread.allocate_lock()  # Verrou pour protéger l'accès à self.data
        
        try:
            os.listdir(self.dir_path)
        except OSError:
            os.mkdir(self.dir_path)
        if load_backup:
            self.load_backup()

    def add(self, v1, a1, v2, a2, v3, a3):
        year, month, day, _, hour, minute, second, microseconds = self.rtc.datetime()
        # Ajouter les données avec verrouillage
        with self.lock:
            self.data.insert(0, [year, month, day, hour, minute, second, microseconds, v1, a1, v2, a2, v3, a3])
            if len(self.data) > self.max_size:
                self.data.pop()  # Supprime la plus ancienne entrée

        if self.old_datetime is not None and minute != self.old_datetime[4]:
            # Copier les données nécessaires pour éviter les conflits
            with self.lock:
                data_copy = self.data[:]  # Copie de self.data pour le thread
            # Lancer process_daily dans un thread
            _thread.start_new_thread(self._thread_process_daily, (data_copy, self.old_datetime))
            if minute % 10 == 0:
                # Lancer process_backup dans un thread
                _thread.start_new_thread(self._thread_process_backup, (data_copy,))

        self.old_datetime = (year, month, day, hour, minute, second, microseconds)

    def _thread_process_daily(self, data_copy, process_datetime):
        """Version thread-safe de process_daily."""
        if not data_copy or not process_datetime:
            return

        process_year, process_month, process_day, process_hour, process_minute = process_datetime[:5]
        
        sum_v1 = sum_v2 = sum_v3 = sum_a1 = sum_a2 = sum_a3 = 0
        ws1 = ws2 = ws3 = 0
        length = 0
        prev_entry = None
        
        for entry in data_copy:
            year, month, day, hour, minute, second, microseconds, v1, a1, v2, a2, v3, a3 = entry
            if year == process_year and month == process_month and day == process_day and hour == process_hour and minute == process_minute:
                sum_v1 += v1
                sum_v2 += v2
                sum_v3 += v3
                sum_a1 += a1
                sum_a2 += a2
                sum_a3 += a3
                
                length += 1
                if prev_entry is not None:
                    delta_sec = (prev_entry[5] + prev_entry[6] / 1000000) - (second + microseconds / 1000000)
                    ws1 += (v1 * a1 + prev_entry[7] * prev_entry[8]) * (delta_sec) / 2
                    ws2 += (v2 * a2 + prev_entry[9] * prev_entry[10]) * (delta_sec) / 2
                    ws3 += (v3 * a3 + prev_entry[11] * prev_entry[12]) * (delta_sec) / 2
                prev_entry = entry
            elif length > 0:
                break 

        if length > 0:
            avg_v1 = sum_v1 / length
            avg_v2 = sum_v2 / length
            avg_v3 = sum_v3 / length
            avg_a1 = sum_a1 / length
            avg_a2 = sum_a2 / length
            avg_a3 = sum_a3 / length
            
            date_iso_str = datetime_to_iso_str(process_year, process_month, process_day, process_hour, process_minute, 0 )

            header = "date;avg_v1;avg_a1;ws1;avg_v2;avg_a2;ws2;avg_v3;avg_a3;ws3\n"
            line_to_save = f"{date_iso_str};{avg_v1:.3f};{avg_a1:.3f};{ws1:.4f};{avg_v2:.3f};{avg_a2:.3f};{ws2:.4f};{avg_v3:.3f};{avg_a3:.3f};{ws3:.4f}\n"
            
            file_name = f"{process_year:04d}-{process_month:02d}-{process_day:02d}_daily_1_minute_aggregate.txt"
            file_path = f"{self.dir_path}/{file_name}"

            file_exists = False
            try:
                with self.lock:  # Protéger l'accès au système de fichiers
                    all_files = os.listdir(self.dir_path)
                    file_exists = file_name in all_files
            except:
                file_exists = False
            
            try:
                with self.lock:  # Protéger l'écriture dans le fichier
                    with open(file_path, 'a') as f:
                        if not file_exists:
                            f.write(header)
                        f.write(line_to_save)
                log(f"✅ Sauvegardé {length} échantillons → {file_path}")
            except Exception as e:
                log(f"❌ Erreur sauvegarde dans thread daily: {e}")


    def load_backup(self):
        self.data = []
        
        now_year, now_month, now_day, _, now_hour, now_minute, now_second, now_microseconds = self.rtc.datetime()
        now_date = (now_year, now_month, now_day, now_hour, now_minute, now_second, now_microseconds)
        
        try:
            with open(self.backup_file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        fields = line.strip().split(';')
                        if len(fields) == 7:
                            datetime_str, v1, a1, v2, a2, v3, a3 = fields
                            data_date = parse_iso_date_str(datetime_str)
                
                            if is_date_after(now_date, data_date):
                                year, month, day, hour, minute, second, microseconds = data_date
                                v1, a1, v2, a2, v3, a3 = map(float, (v1, a1, v2, a2, v3, a3))
                                with self.lock:
                                    self.data.append((year, month, day, hour, minute, second, microseconds, v1, a1, v2, a2, v3, a3))
            log(f"✅ {len(self.data)} data chargées depuis {self.backup_file_path}")
        except OSError as e:
            log_err(f"Fichier backup_every_10_minutes.txt introuvable ou erreur d'accès : {e}")
        except Exception as e:
            log_err(f"Erreur lors du chargement du backup : {e}")
            

    def _thread_process_backup(self, data_copy):
        """Version thread-safe de process_backup."""
        with self.lock:  # Protéger l'écriture dans le fichier
            try:
                with open(self.backup_file_path, 'w') as f:
                    for entry in data_copy:
                        year, month, day, hour, minute, second, microseconds, v1, a1, v2, a2, v3, a3 = entry
                        date_iso_str = datetime_to_iso_str(year, month, day, hour, minute, second, microseconds )
                        f.write(f"{date_iso_str};{v1:.3f};{a1:.3f};{v2:.3f};{a2:.3f};{v3:.3f};{a3:.3f}\n")
                        
                log(f"✅ Sauvegarde backup effectuée dans thread")
            except Exception as e:
                log_err(f"❌ Erreur sauvegarde backup dans thread: {e}")



    def all_after(self, from_date):
        with self.lock:
            data = []
            for entry in self.data:
                if is_date_after(entry[:7], from_date):
                    data.append(self.json(entry))
                else:
                    break
        return data
    
    def all(self):
        with self.lock:
            data = []
            for entry in self.data:
                data.append(self.json(entry))
        return data
                    
    def json(self, entry=None):
        if entry is None:
            raise ValueError("entry should not be None")
        year, month, day, hour, minute, second, microseconds, v1, a1, v2, a2, v3, a3 = entry        
        date_iso_str = datetime_to_iso_str(year, month, day, hour, minute, second, microseconds )
        return {
            "date":  date_iso_str,
            "v1": v1,
            "a1": a1,
            "v2": v2,
            "a2": a2,
            "v3": v3,
            "a3": a3
        }