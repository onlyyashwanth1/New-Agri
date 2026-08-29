from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Regexp, ValidationError
from datetime import datetime, timedelta
import bcrypt
from flask_mysqldb import MySQL
import MySQLdb
import re

app = Flask(__name__, static_url_path='/static')
app.secret_key = 'your_secret_key'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = your_password
app.config['MYSQL_DB'] = 'AgriData'

mysql = MySQL(app)


def build_farmer_address(city, pincode, state):
    return ', '.join(part.strip() for part in (city, pincode, state) if part and part.strip())


def split_farmer_address(address):
    parts = [part.strip() for part in (address or '').split(',') if part.strip()]
    pincode_index = next((i for i, part in enumerate(parts) if re.fullmatch(r'\d{6}', part)), None)
    if pincode_index is not None:
        pincode = parts[pincode_index]
        remaining = parts[:pincode_index] + parts[pincode_index + 1:]
    else:
        pincode = ''
        remaining = parts
    city = remaining[0] if remaining else ''
    state = remaining[-1] if len(remaining) > 1 else ''
    if len(remaining) > 1:
        city = remaining[0]
        state = remaining[-1]
    return {'city': city, 'pincode': pincode, 'state': state}


class RegisterForm(FlaskForm):
    auth_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=100, message="Name must be between 2 and 100 characters.")])
    auth_email = StringField("Email", validators=[DataRequired(), Regexp(r'^[^@]+@agri\.com$', message="Please enter a valid email address with the correct domain.")])
    auth_phone_no = StringField("Phone Number", validators=[DataRequired(), Length(min=10, max=15), Regexp(r'^\d{10,15}$', message="Phone number must be 10-15 digits.")])
    auth_pass = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters long.")])
    submit = SubmitField("Register")

    def validate_field(self, field, column_name, message):
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(f"SELECT * FROM auths WHERE {column_name} = %s", (field.data,))
        exists = cursor.fetchone()
        cursor.close()
        if exists:
            raise ValidationError(message)

    def validate_auth_email(self, field):
        self.validate_field(field, 'auth_email', 'Email already exists')

    def validate_auth_phone_no(self, field):
        self.validate_field(field, 'auth_phone_no', 'Phone number already exists')

    def validate_auth_pass(self, field):
        if field.data != 'AgridataNexus@123':
            raise ValidationError(" Please enter the correct password.")


class LoginForm(FlaskForm):
    auth_email = StringField("Email", validators=[DataRequired()])
    auth_pass = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/auth_register', methods=['GET', 'POST'])
def auth_register():
    form = RegisterForm()
    if form.validate_on_submit():
        auth_name = form.auth_name.data
        auth_email = form.auth_email.data
        auth_pass = form.auth_pass.data
        auth_phone_no = form.auth_phone_no.data
        hashed_auth_pass = bcrypt.hashpw(auth_pass.encode('utf-8'), bcrypt.gensalt())
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("INSERT INTO auths (auth_name, auth_email, auth_pass, auth_phone_no) VALUES (%s, %s, %s, %s)", (auth_name, auth_email, hashed_auth_pass, auth_phone_no))
        mysql.connection.commit()
        cursor.close()
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth_login'))
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f' {error}', 'error')
    return render_template('auth_register.html', form=form)


@app.route('/auth_login', methods=['GET', 'POST'])
def auth_login():
    form = LoginForm()
    if form.validate_on_submit():
        auth_email = form.auth_email.data
        auth_pass = form.auth_pass.data
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM auths WHERE auth_email=%s", (auth_email,))
        auth = cursor.fetchone()
        cursor.close()
        if auth and bcrypt.checkpw(auth_pass.encode('utf-8'), auth['auth_pass'].encode('utf-8')):
            session['auth_id'] = auth['auth_id']
            session['auth_email'] = auth['auth_email']
            session['auth_name'] = auth['auth_name']
            flash('Login successful!', 'success')
            return redirect(url_for('existingfarmers'))
        flash('Invalid credentials, please try again.', 'error')
    return render_template('auth_login.html', form=form)


@app.route('/auth_logout')
def auth_logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth_login'))


import os
from dotenv import load_dotenv
load_dotenv()
from twilio.rest import Client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(username=account_sid, password=auth_token)


@app.route('/farmer_login', methods=['GET', 'POST'])
def farmer_login():
    if request.method == 'POST':
        aadhar_id = request.form.get('aadhar_id')
        phone_no = request.form.get('phone_no')
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s AND phone_no = %s", (aadhar_id, phone_no))
            farmer = cursor.fetchone()
            if farmer:
                session['aadhar_id'] = farmer['aadhar_id']
                session['farmer_name'] = farmer['farmer_name']
                if farmer['first_login']:
                    cursor.execute("INSERT INTO notifications (aadhar_id, notification_type, message, is_sent) VALUES (%s, %s, %s, %s)", (farmer['aadhar_id'], 'General', 'Welcome to AgriNexus! We are glad to have you.', False))
                    mysql.connection.commit()
                    try:
                        message = client.messages.create(body="Welcome to AgriNexus! We are glad to have you on board.", from_=os.getenv("TWILIO_PHONE_NUMBER"), to=f'+91{phone_no}')
                        cursor.execute("UPDATE notifications SET is_sent = TRUE WHERE aadhar_id = %s AND notification_type = 'General'", (farmer['aadhar_id'],))
                        mysql.connection.commit()
                    except Exception as e:
                        print(f"Failed to send SMS: {e}")
                        flash('Welcome message could not be sent, but login was successful.', 'warning')
                    cursor.execute("UPDATE farmers SET first_login = FALSE WHERE aadhar_id = %s", (aadhar_id,))
                    mysql.connection.commit()
                flash('Login successful!', 'success')
                return redirect(url_for('farmer_details'))
            flash('Invalid Aadhar ID or Phone Number.', 'error')
        except MySQLdb.Error:
            flash('An error occurred. Please try again.', 'error')
        finally:
            cursor.close()
    return render_template('farmer_login.html')


@app.route('/farmer_weather', methods=['GET', 'POST'])
def farmer_weather():
    if 'aadhar_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('farmer_login'))
    if request.method == 'GET':
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None, farmer=None, crop_context=None, error=None)
    aadhar_id = session['aadhar_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
        farmer = cursor.fetchone()
        cursor.execute("SELECT * FROM lands WHERE aadhar_id = %s AND deleted = FALSE", (aadhar_id,))
        lands = cursor.fetchall()
        cursor.execute("SELECT * FROM crops WHERE aadhar_id = %s AND crop_active = TRUE ORDER BY planting_date DESC", (aadhar_id,))
        active_crops = cursor.fetchall()
    finally:
        cursor.close()
    if not farmer:
        return redirect(url_for('farmer_login'))
    import requests
    import urllib.parse
    address = farmer.get('address') or ''
    if not address.strip():
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None, farmer=farmer, crop_context=None, error='A registered address is required to fetch weather information.')
    geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=1"
    try:
        geo_resp = requests.get(geo_url, headers={'User-Agent': 'AgriNexus-App/1.0'}, timeout=8)
        geo_resp.raise_for_status()
        geo_results = geo_resp.json()
        if not geo_results:
            raise ValueError('Address not located')
        lat = float(geo_results[0]['lat'])
        lon = float(geo_results[0]['lon'])
        resolved_location = geo_results[0].get('display_name', address)
    except Exception as e:
        print(f"Error geocoding farmer address: {e}")
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None, farmer=farmer, crop_context=None, error='We could not locate the registered address. Please ensure the farmer address is City, Pincode, State.')
    weather_url = ("https://api.open-meteo.com/v1/forecast" f"?latitude={lat}&longitude={lon}" "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m" "&hourly=precipitation_probability,precipitation,rain,reference_evapotranspiration,soil_moisture_0_to_1cm,soil_moisture_1_to_3cm" "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,reference_evapotranspiration_sum" "&forecast_days=5&timezone=auto")
    try:
        w_resp = requests.get(weather_url, timeout=12)
        w_resp.raise_for_status()
        w_data = w_resp.json()
        current = w_data['current']; hourly = w_data.get('hourly', {}); daily = w_data.get('daily', {})
    except Exception as e:
        print(f"Error fetching Open-Meteo data: {e}")
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None, farmer=farmer, crop_context=None, error='Live weather information is temporarily unavailable. Please try again.')
    crop_names = [c['crop_name'] for c in active_crops if c.get('crop_name')]
    crop_context = ", ".join(crop_names) if crop_names else "No active crop registered"
    rain_next_24 = sum(float(x or 0) for x in hourly.get('precipitation', [])[:24])
    rain_next_48 = sum(float(x or 0) for x in hourly.get('precipitation', [])[:48])
    et0_next_24 = sum(float(x or 0) for x in hourly.get('reference_evapotranspiration', [])[:24])
    soil_moisture = next((x for x in hourly.get('soil_moisture_0_to_1cm', []) if x is not None), None)
    temp = float(current['temperature_2m']); humidity = float(current['relative_humidity_2m']); current_rain = float(current.get('rain', 0) or 0)
    if rain_next_24 >= 8:
        irrigation_title = 'Irrigation: Wait'; irrigation_text = f'About {rain_next_24:.1f} mm precipitation is expected in the next 24 hours. Irrigation may be unnecessary unless field conditions indicate otherwise.'
    elif rain_next_24 >= 3:
        irrigation_title = 'Irrigation: Use caution'; irrigation_text = f'About {rain_next_24:.1f} mm precipitation is expected in the next 24 hours. Check field moisture before irrigating.'
    elif et0_next_24 >= 4 and (soil_moisture is None or soil_moisture < 0.30):
        irrigation_title = 'Irrigation: Consider irrigating'; irrigation_text = f'Rainfall is low while reference evapotranspiration is about {et0_next_24:.1f} mm over 24 hours. Check field moisture and irrigate according to crop needs.'
    else:
        irrigation_title = 'Irrigation: Monitor'; irrigation_text = 'No strong rainfall or atmospheric-demand signal was detected. Check field moisture and follow the crop-specific irrigation schedule.'
    suggestions = [{'category': 'irrigation', 'title': irrigation_title, 'text': irrigation_text, 'badge': 'bg-gray-100 text-gray-800 border border-gray-200'}]
    if rain_next_24 >= 5:
        suggestions.append({'category': 'field work', 'title': 'Rain expected', 'text': f'{rain_next_24:.1f} mm precipitation is forecast in the next 24 hours. Consider postponing fertilizer or spraying that could be washed off.', 'badge': 'bg-gray-100 text-gray-800 border border-gray-200'})
    if float(current.get('wind_speed_10m', 0) or 0) >= 8:
        suggestions.append({'category': 'spraying', 'title': 'High wind conditions', 'text': f"Current wind speed is {float(current['wind_speed_10m']):.1f} km/h. Avoid spraying when drift could affect application accuracy.", 'badge': 'bg-gray-100 text-gray-800 border border-gray-200'})
    gemini_text = None
    gemini_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if gemini_key:
        try:
            from google import genai
            ai_client = genai.Client(api_key=gemini_key)
            prompt = f"""You are an agricultural advisory assistant. Use only supplied facts and do not invent measurements. Active crops: {crop_context}. Current temperature: {temp:.1f} C. Current humidity: {humidity:.0f}%. Current rainfall: {current_rain:.1f} mm. Rain next 24h: {rain_next_24:.1f} mm. Rain next 48h: {rain_next_48:.1f} mm. Reference ET0 next 24h: {et0_next_24:.1f} mm. Soil moisture: {'unavailable' if soil_moisture is None else f'{soil_moisture:.3f} m3/m3'}. Give concise, cautious advice in 3 bullets focused on irrigation, field work, and crop-weather considerations. Do not claim a disease is present."""
            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            gemini_text = getattr(response, 'text', None)
        except Exception as e:
            print(f"Gemini advisory unavailable: {e}")
    forecast = []
    for i, day in enumerate(daily.get('time', [])):
        forecast.append({'date': day, 'min': daily.get('temperature_2m_min', [])[i], 'max': daily.get('temperature_2m_max', [])[i], 'rain': daily.get('precipitation_sum', [])[i], 'rain_probability': daily.get('precipitation_probability_max', [])[i], 'et0': daily.get('reference_evapotranspiration_sum', [])[i]})
    weather_data = {'address': resolved_location, 'temp': round(temp, 1), 'feels_like': round(float(current.get('apparent_temperature', temp)), 1), 'humidity': round(humidity), 'rain': round(current_rain, 2), 'wind_speed': round(float(current.get('wind_speed_10m', 0)), 1), 'desc': f"Weather code {current.get('weather_code', 'N/A')}", 'rain_next_24': round(rain_next_24, 1), 'et0_next_24': round(et0_next_24, 1), 'soil_moisture': None if soil_moisture is None else round(float(soil_moisture), 3)}
    return render_template('farmer_weather.html', farmer=farmer, weather=weather_data, forecast=forecast, suggestions=suggestions, crop_context=crop_context, gemini_text=gemini_text, error=None)


@app.route('/farmer_details')
def farmer_details():
    aadhar_id = session.get('aadhar_id')
    if not aadhar_id:
        flash("You need to log in first.", "error")
        return redirect(url_for('farmer_login'))
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone(); cursor.close()
    if not farmer:
        flash("Farmer not found.", 'error'); return redirect(url_for('farmer_login'))
    farmer['address_parts'] = split_farmer_address(farmer.get('address'))
    return render_template('farmer_details.html', farmer=farmer)

# Existing project routes continue below this point.
