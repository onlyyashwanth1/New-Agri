import sys
import types
import sqlite3
import re
import os
import bcrypt
import requests as real_requests

# --- DUMMY MODULE INJECTIONS ---

# Mock MySQLdb
class DummyMySQLdb:
    Error = Exception
    MySQLError = Exception
    class cursors:
        class DictCursor:
            pass

mysqldb_mod = types.ModuleType("MySQLdb")
mysqldb_mod.Error = Exception
mysqldb_mod.MySQLError = Exception
mysqldb_mod.cursors = DummyMySQLdb.cursors
sys.modules["MySQLdb"] = mysqldb_mod

# Mock flask_mysqldb
class SQLiteMySQLBridgeCursor:
    def __init__(self, sqlite_cursor, dict_mode=False):
        self.cursor = sqlite_cursor
        self.dict_mode = dict_mode

    def execute(self, query, params=None):
        # Convert MySQL parameter markers %s to SQLite ?
        query = query.replace('%s', '?')
        # Translate MySQL AUTO_INCREMENT syntax
        query = query.replace('AUTO_INCREMENT', 'AUTOINCREMENT')
        
        if params is None:
            self.cursor.execute(query)
        else:
            if not isinstance(params, (tuple, list)):
                params = (params,)
            self.cursor.execute(query, params)
        return self

    def _process_row(self, row):
        if row is None:
            return None
        import datetime
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, str):
                if re.match(r'^\d{4}-\d{2}-\d{2}$', v):
                    try:
                        d[k] = datetime.datetime.strptime(v, '%Y-%m-%d').date()
                    except:
                        pass
                elif re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$', v):
                    try:
                        d[k] = datetime.datetime.strptime(v.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
        return d if self.dict_mode else tuple(d.values())

    def fetchone(self):
        row = self.cursor.fetchone()
        return self._process_row(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [self._process_row(r) for r in rows if r is not None]

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()

class SQLiteMySQLBridgeConnection:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def cursor(self, cursorclass=None):
        dict_mode = cursorclass is not None
        return SQLiteMySQLBridgeCursor(self._conn.cursor(), dict_mode=dict_mode)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

class MockMySQL:
    def __init__(self, app=None):
        self.app = app
        self._conn = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        pass

    @property
    def connection(self):
        if self._conn is None:
            self._conn = SQLiteMySQLBridgeConnection('agridata_preview.db')
        return self._conn

flask_mysqldb_mod = types.ModuleType("flask_mysqldb")
flask_mysqldb_mod.MySQL = MockMySQL
sys.modules["flask_mysqldb"] = flask_mysqldb_mod

# Mock joblib
class MockJoblib:
    @staticmethod
    def load(*args, **kwargs):
        class MockModel:
            def predict(self, *args, **kwargs):
                return ["Rice"]
        return MockModel()
        
joblib_mod = types.ModuleType("joblib")
joblib_mod.load = MockJoblib.load
sys.modules["joblib"] = joblib_mod

# Mock numpy
class MockNumpy:
    @staticmethod
    def array(*args, **kwargs):
        return list(*args)
        
numpy_mod = types.ModuleType("numpy")
numpy_mod.array = MockNumpy.array
sys.modules["numpy"] = numpy_mod

# Mock twilio
class MockTwilioMessages:
    def create(self, *args, **kwargs):
        print(f"\n--- [MOCK SMS SENT via Twilio] ---")
        print(f"To: {kwargs.get('to')}")
        print(f"Body: {kwargs.get('body')}")
        print(f"----------------------------------\n")
        class MockMessage:
            sid = "SMmock123456789"
        return MockMessage()

class MockTwilioClient:
    def __init__(self, *args, **kwargs):
        self.messages = MockTwilioMessages()

twilio_rest_mod = types.ModuleType("twilio.rest")
twilio_rest_mod.Client = MockTwilioClient
sys.modules["twilio.rest"] = twilio_rest_mod

twilio_mod = types.ModuleType("twilio")
sys.modules["twilio"] = twilio_mod

# Mock requests
class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
    def json(self):
        return self.json_data

class MockRequests:
    @staticmethod
    def get(url, *args, **kwargs):
        # The preview keeps MySQL mocked, but uses the real geocoder and Open-Meteo
        # so the Weather & Irrigation page shows genuine live data after Proceed.
        if "openstreetmap.org" in url or "api.open-meteo.com" in url:
            return real_requests.get(url, *args, **kwargs)
        if "api.openweathermap.org" in url:
            return MockResponse({
                "main": {"temp": 40.5, "humidity": 18.0},
                "rain": {"1h": 0.0},
                "wind": {"speed": 2.5},
                "weather": [{"description": "clear sky"}]
            })
        if "power.larc.nasa.gov" in url:
            return MockResponse({
                "properties": {
                    "parameter": {
                        "T2M": {"202601": 25.0},
                        "RH2M": {"202601": 60.0},
                        "PRECTOTCORR": {"202601": 0.05}
                    }
                }
            })
        return MockResponse({})

requests_mod = types.ModuleType("requests")
requests_mod.get = MockRequests.get
sys.modules["requests"] = requests_mod

# Bypassing the NameError at app.py:15
import builtins
builtins.your_password = "dummy_password"


# --- INITIALIZE SQLITE DATABASE ---

def init_db(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open('Agrinexus.sql', 'r') as f:
        sql_content = f.read()
        
    # Clean SQL for SQLite compatibility
    sql_content = re.sub(r'(?m)^#.*$', '', sql_content)
    sql_content = re.sub(r'(?i)CREATE\s+DATABASE\s+\w+;', '', sql_content)
    sql_content = re.sub(r'(?i)USE\s+\w+;', '', sql_content)
    sql_content = re.sub(r'(?i)INT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql_content)
    sql_content = re.sub(r'(?i)INT\s+PRIMARY\s+KEY\s+AUTO_INCREMENT', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql_content)
    sql_content = re.sub(r'(?i)ENUM\([^)]+\)', 'TEXT', sql_content)
    
    statements = sql_content.split(';')
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            try:
                cursor.execute(stmt)
            except Exception as e:
                # print(f"Ignoring statement: {e}")
                pass
                
    conn.commit()
    
    # Insert Mock Data
    hashed_pass = bcrypt.hashpw(b'AgridataNexus@123', bcrypt.gensalt()).decode('utf-8')
    
    try:
        # Default Authority
        cursor.execute(
            "INSERT INTO auths (auth_name, auth_email, auth_pass, auth_phone_no) VALUES (?, ?, ?, ?)",
            ("Demo Admin", "example@agri.com", hashed_pass, "1234567890")
        )
        # Default Farmer
        cursor.execute(
            "INSERT INTO farmers (farmer_name, date_of_birth, gender, phone_no, address, aadhar_id, first_login) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("John Doe", "1980-05-15", "Male", "9876543210", "Hyderabad, Telangana, India", "123412341234", 0)
        )
        # Default Land
        cursor.execute(
            "INSERT INTO lands (aadhar_id, location, soil_type, land_size, deleted) VALUES (?, ?, ?, ?, ?)",
            ("123412341234", "North Field", "Loamy", 5.5, 0)
        )
        # Default Crop
        cursor.execute(
            "INSERT INTO crops (land_id, aadhar_id, crop_name, crop_size, N_percent, P_percent, K_percent, soil_ph, planting_date, harvest_date, crop_suggestion, crop_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "123412341234", "Rice", 3.0, 40.0, 30.0, 30.0, 6.5, "2026-06-01", "2026-10-01", "Rice", 1)
        )
        # Default Loans
        cursor.execute(
            "INSERT INTO loans (loan_type, description, eligibility, deleted) VALUES (?, ?, ?, ?)",
            ("Kisan Credit Card (KCC)", "Short term credit for agricultural needs of farmers.", "All farmers", 0)
        )
        cursor.execute(
            "INSERT INTO loans (loan_type, description, eligibility, deleted) VALUES (?, ?, ?, ?)",
            ("Agricultural Term Loan", "Medium to long term credit for buying tractors, pumps, etc.", "All farmers owning land", 0)
        )
        # Default Subsidies
        cursor.execute(
            "INSERT INTO subsidies (subsidy_name, description, eligibility, last_date_apply, deleted) VALUES (?, ?, ?, ?, ?)",
            ("Fertilizer Subsidy", "Subsidized prices on urea and other fertilizers.", "Small and marginal farmers", "2026-12-31", 0)
        )
        cursor.execute(
            "INSERT INTO subsidies (subsidy_name, description, eligibility, last_date_apply, deleted) VALUES (?, ?, ?, ?, ?)",
            ("Solar Pump Subsidy", "90% subsidy for installation of solar water pumps.", "Farmers with functional wells", "2026-11-30", 0)
        )
        # Default Schemes
        cursor.execute(
            "INSERT INTO schemes (scheme_name, description, eligibility, last_date_apply, deleted) VALUES (?, ?, ?, ?, ?)",
            ("PM-KISAN", "Direct income support of Rs. 6000 per year to landholder farmer families.", "Landholding farmers", "2026-12-31", 0)
        )
        
        conn.commit()
        print("Mock Database initialized successfully with SQLite!")
    except Exception as e:
        print(f"Error inserting mock data: {e}")
        
    conn.close()


if __name__ == "__main__":
    init_db('agridata_preview.db')
    
    # Import the original Flask app and run it
    from app import app
    print("\n--- Starting Agrinexus Preview Mode ---")
    print("No MySQL database or external APIs required!")
    print("You can log in as:")
    print("  - Authority: email = example@agri.com  |  password = AgridataNexus@123")
    print("  - Farmer:    Aadhar ID = 123412341234  |  phone = 9876543210")
    print("----------------------------------------\n")
    app.run(debug=True)
