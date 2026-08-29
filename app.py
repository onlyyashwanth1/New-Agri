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
    """Store address consistently as City, Pincode, State."""
    return ', '.join(part.strip() for part in (city, pincode, state) if part and part.strip())


def split_farmer_address(address):
    """Parse stored City, Pincode, State addresses for display/edit forms."""
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
    return {'city': city, 'pincode': pincode, 'state': state}



class RegisterForm(FlaskForm):
    auth_name = StringField("Full Name", validators=[
        DataRequired(),
        Length(min=2, max=100, message="Name must be between 2 and 100 characters.")
    ])
   
    auth_email = StringField("Email", validators=[
        DataRequired(),
        Regexp(r'^[^@]+@agri\.com$', message="Please enter a valid email address with the correct domain.")
    ])

    auth_phone_no = StringField("Phone Number", validators=[
        DataRequired(), Length(min=10, max=15),
        Regexp(r'^\d{10,15}$', message="Phone number must be 10-15 digits.")
    ])
    
    auth_pass = PasswordField("Password", validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters long.")
    ])
    
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
    # Ensure the password matches the predefined one
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
        auth_pass = form.auth_pass.data  # This will be validated against the predefined password
        auth_phone_no = form.auth_phone_no.data

        # Hash the password (even though it's the same, we still hash it for consistency)
        hashed_auth_pass = bcrypt.hashpw(auth_pass.encode('utf-8'), bcrypt.gensalt())
        
        # Insert into database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("INSERT INTO auths (auth_name, auth_email, auth_pass, auth_phone_no) VALUES (%s, %s, %s, %s)",
                       (auth_name, auth_email, hashed_auth_pass, auth_phone_no))
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
            auth_name = auth['auth_name']
            flash('Login successful!', 'success')
            if 'auth_id' in session:
                return redirect(url_for('existingfarmers'))
        else:
            flash('Invalid credentials, please try again.', 'error')

    return render_template('auth_login.html', form=form)

@app.route('/auth_logout')
def auth_logout():
    session.clear()  # Clear the session
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth_login'))  # Redirect to the login page
#Farmer_login Page
import os
from dotenv import load_dotenv

load_dotenv() 
from twilio.rest import Client
from flask import Flask, request, redirect, url_for, render_template, flash, session
import MySQLdb

# Twilio credentials
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
            # Query for farmer details
            cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s AND phone_no = %s", (aadhar_id, phone_no))
            farmer = cursor.fetchone()

            if farmer:
                session['aadhar_id'] = farmer['aadhar_id']
                session['farmer_name'] = farmer['farmer_name']

                if farmer['first_login']:
                    # Insert welcome notification
                    cursor.execute("""
                        INSERT INTO notifications (aadhar_id, notification_type, message, is_sent)
                        VALUES (%s, %s, %s, %s)
                    """, (farmer['aadhar_id'], 'General', 'Welcome to AgriNexus! We are glad to have you.', False))
                    mysql.connection.commit()

                    # Send SMS
                    try:
                        message = client.messages.create(
                            body="Welcome to AgriNexus! We are glad to have you on board.",
                            from_=os.getenv("TWILIO_PHONE_NUMBER"),  #Twilio number
                            to=f'+91{phone_no}'    # Farmer's phone number
                        )

                        # Update notification status
                        cursor.execute("""
                            UPDATE notifications 
                            SET is_sent = TRUE 
                            WHERE aadhar_id = %s AND notification_type = 'General'
                        """, (farmer['aadhar_id'],))
                        mysql.connection.commit()
                    except Exception as e:
                        print(f"Failed to send SMS: {e}")
                        flash('Welcome message could not be sent, but login was successful.', 'warning')

                    # Update first login status
                    cursor.execute("UPDATE farmers SET first_login = FALSE WHERE aadhar_id = %s", (aadhar_id,))
                    mysql.connection.commit()

                flash('Login successful!', 'success')
                return redirect(url_for('farmer_details'))
            else:
                flash('Invalid Aadhar ID or Phone Number.', 'error')

        except MySQLdb.Error as e:
            flash('An error occurred. Please try again.', 'error')
        finally:
            cursor.close()

    return render_template('farmer_login.html')

@app.route('/farmer_weather', methods=['GET', 'POST'])
def farmer_weather():
    if 'aadhar_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('farmer_login'))

    # Opening the page does not fetch external data. Fetch only after Proceed.
    if request.method == 'GET':
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None,
                               farmer=None, crop_context=None, gemini_text=None, error=None)

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

    address = (farmer.get('address') or '').strip()
    if not address:
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None,
                               farmer=farmer, crop_context=None, gemini_text=None,
                               error='A registered City, Pincode, and State are required to fetch weather information.')

    import requests
    import urllib.parse
    geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=1&countrycodes=in"
    try:
        geo_resp = requests.get(geo_url, headers={'User-Agent': 'AgriNexus-App/1.0'}, timeout=10)
        geo_resp.raise_for_status()
        geo_results = geo_resp.json()
        if not geo_results:
            raise ValueError('Address not located')
        lat = float(geo_results[0]['lat'])
        lon = float(geo_results[0]['lon'])
        resolved_location = geo_results[0].get('display_name', address)
    except Exception as e:
        print(f"Error geocoding farmer address: {e}")
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None,
                               farmer=farmer, crop_context=None, gemini_text=None,
                               error='We could not locate the registered address. Please check City, Pincode, and State.')

    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m"
        "&hourly=precipitation_probability,precipitation,rain,reference_evapotranspiration,soil_moisture_0_to_1cm,soil_moisture_1_to_3cm"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,reference_evapotranspiration_sum"
        "&forecast_days=5&timezone=auto"
    )
    try:
        w_resp = requests.get(weather_url, timeout=12)
        w_resp.raise_for_status()
        w_data = w_resp.json()
        current = w_data['current']
        hourly = w_data.get('hourly', {})
        daily = w_data.get('daily', {})
    except Exception as e:
        print(f"Error fetching Open-Meteo data: {e}")
        return render_template('farmer_weather.html', weather=None, forecast=None, suggestions=None,
                               farmer=farmer, crop_context=None, gemini_text=None,
                               error='Live weather information is temporarily unavailable. Please try again.')

    crop_names = [c['crop_name'] for c in active_crops if c.get('crop_name')]
    crop_context = ", ".join(crop_names) if crop_names else "No active crop registered"
    rain_next_24 = sum(float(x or 0) for x in hourly.get('precipitation', [])[:24])
    rain_next_48 = sum(float(x or 0) for x in hourly.get('precipitation', [])[:48])
    et0_next_24 = sum(float(x or 0) for x in hourly.get('reference_evapotranspiration', [])[:24])
    soil_moisture = next((x for x in hourly.get('soil_moisture_0_to_1cm', []) if x is not None), None)
    temp = float(current['temperature_2m'])
    humidity = float(current['relative_humidity_2m'])
    current_rain = float(current.get('rain', 0) or 0)

    suggestions = []
    if rain_next_24 >= 8:
        title = 'Irrigation: Wait'
        text = f'About {rain_next_24:.1f} mm precipitation is expected in the next 24 hours. Irrigation may be unnecessary unless field conditions indicate otherwise.'
    elif rain_next_24 >= 3:
        title = 'Irrigation: Use caution'
        text = f'About {rain_next_24:.1f} mm precipitation is expected in the next 24 hours. Check field moisture before irrigating.'
    elif et0_next_24 >= 4 and (soil_moisture is None or soil_moisture < 0.30):
        title = 'Irrigation: Consider irrigating'
        text = f'Rainfall is low while reference evapotranspiration is about {et0_next_24:.1f} mm over 24 hours. Check field moisture and irrigate according to crop needs.'
    else:
        title = 'Irrigation: Monitor'
        text = 'No strong rainfall or atmospheric-demand signal was detected. Check field moisture and follow the crop-specific irrigation schedule.'
    suggestions.append({'category': 'irrigation', 'title': title, 'text': text,
                        'badge': 'bg-gray-100 text-gray-800 border border-gray-200'})

    if rain_next_24 >= 5:
        suggestions.append({'category': 'field work', 'title': 'Rain expected',
                            'text': f'{rain_next_24:.1f} mm precipitation is forecast in the next 24 hours. Consider postponing fertilizer or spraying that could be washed off.',
                            'badge': 'bg-gray-100 text-gray-800 border border-gray-200'})
    if float(current.get('wind_speed_10m', 0) or 0) >= 8:
        suggestions.append({'category': 'spraying', 'title': 'High wind conditions',
                            'text': f"Current wind speed is {float(current['wind_speed_10m']):.1f} km/h. Avoid spraying when drift could affect application accuracy.",
                            'badge': 'bg-gray-100 text-gray-800 border border-gray-200'})

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
    times = daily.get('time', [])
    for i, day in enumerate(times):
        forecast.append({
            'date': day,
            'min': daily.get('temperature_2m_min', [])[i],
            'max': daily.get('temperature_2m_max', [])[i],
            'rain': daily.get('precipitation_sum', [])[i],
            'rain_probability': daily.get('precipitation_probability_max', [])[i],
            'et0': daily.get('reference_evapotranspiration_sum', [])[i]
        })

    weather_data = {
        'address': resolved_location,
        'temp': round(temp, 1),
        'feels_like': round(float(current.get('apparent_temperature', temp)), 1),
        'humidity': round(humidity),
        'rain': round(current_rain, 2),
        'wind_speed': round(float(current.get('wind_speed_10m', 0)), 1),
        'desc': f"Weather code {current.get('weather_code', 'N/A')}",
        'rain_next_24': round(rain_next_24, 1),
        'et0_next_24': round(et0_next_24, 1),
        'soil_moisture': None if soil_moisture is None else round(float(soil_moisture), 3)
    }
    return render_template('farmer_weather.html', farmer=farmer, weather=weather_data,
                           forecast=forecast, suggestions=suggestions, crop_context=crop_context,
                           gemini_text=gemini_text, error=None)

@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    flash('You have been logged out.', 'success')
    return redirect(url_for('farmer_login'))  # Redirect to the login page

# Route for displaying farmer details
@app.route('/farmer_details')
def farmer_details():
    aadhar_id = session.get('aadhar_id')  # Get AADHAR ID from session
    if not aadhar_id:
        flash("You need to log in first.", "error")
        return redirect(url_for('farmer_login'))

    # Fetch farmer details from the database
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    cursor.close()

    if not farmer:
        flash("Farmer not found.", "error")
        return redirect(url_for('farmer_login'))

    farmer['address_parts'] = split_farmer_address(farmer.get('address'))
    return render_template('farmer_details.html', farmer=farmer)

@app.route('/farmer_lands')
def farmer_lands():
    aadhar_id = session.get('aadhar_id')  # Get AADHAR ID from session
    if not aadhar_id:
        flash("You need to log in first.", "error")
        return redirect(url_for('farmer_login'))

    search_avail_land = request.args.get('search_avail_land')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if search_avail_land:  # If there's a search query
        cursor.execute("SELECT * FROM lands WHERE aadhar_id = %s AND location LIKE %s AND deleted = FALSE", 
                       (aadhar_id, '%' + search_avail_land + '%'))
        lands = cursor.fetchall()
        if not lands:
            flash('No land found for this location.', 'error')

    else:
        cursor.execute("SELECT * FROM lands WHERE aadhar_id = %s AND deleted = FALSE", (aadhar_id,))  # Only present lands
        lands = cursor.fetchall()
    
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    cursor.close()

    # Render the farmer lands template
    return render_template('farmer_lands.html', lands=lands, farmer=farmer)


#Route to crops
@app.route('/farmer_crops')
def farmer_crops():
    aadhar_id = session.get('aadhar_id')  # Get AADHAR ID from session
    if not aadhar_id:
        flash("You need to log in first.", "error")
        return redirect(url_for('farmer_login'))

    search_avail_crop = request.args.get('search_avail_crop')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)


    # Search for specific crops if there's a search query
    if search_avail_crop:
        cursor.execute("""SELECT * FROM crops WHERE aadhar_id = %s AND crop_name LIKE %s """, 
                        (aadhar_id, '%' + search_avail_crop + '%'))
        crops = cursor.fetchall()
        if not crops:
            flash('No crop found for this type.', 'error')
    else:
        # Fetch present crops (deleted = 0)
        cursor.execute("""SELECT * FROM crops WHERE aadhar_id = %s """, (aadhar_id,))
        crops = cursor.fetchall()

    # Fetch farmer details
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    for crop in crops:
        crop['status'] = get_crop_status(crop['planting_date'], crop['harvest_date'])
    cursor.close()

    # Render the farmer crops template
    return render_template('farmer_crops.html', crops=crops,farmer=farmer)
#Farmer Loans
@app.route('/farmer_loans_taken')
def farmer_loans_taken():
    aadhar_id = session.get('aadhar_id')  # Get AADHAR ID from session
    if not aadhar_id:
        flash("You need to log in first.", "error")
        return redirect(url_for('farmer_login'))
    
    search_loan_taken = request.args.get('search_loan_taken')  # Get search query from request
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if search_loan_taken:  # If there's a search query
        # Fetch loans taken by the farmer based on the search query
        cursor.execute("SELECT * FROM loans_taken WHERE aadhar_id = %s AND loan_type LIKE %s", 
                       (aadhar_id, '%' + search_loan_taken + '%'))
        
        loans_taken = cursor.fetchall()
        if not loans_taken:
            flash('No loan taken found for this type.', 'error')

    else:
        # Fetch all loans taken by the farmer
        cursor.execute("SELECT * FROM loans_taken WHERE aadhar_id = %s", (aadhar_id,))

        loans_taken = cursor.fetchall()  # Get all loans taken by the farmer

    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    cursor.close()

    # Trigger notification sending for the farmer
    send_notifications(client)

    # Render the farmer loans taken template
    return render_template('farmer_loans_taken.html', loans_taken=loans_taken, farmer=farmer)


# Notification sending function
def send_notifications(client):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch unsent notifications
    cursor.execute("SELECT notification_id, aadhar_id, message FROM notifications WHERE is_sent = FALSE")
    notifications = cursor.fetchall()

    for notification in notifications:
        notification_id = notification['notification_id']
        aadhar_id = notification['aadhar_id']
        message_content = notification['message']

        # Fetch farmer's phone number
        cursor.execute("SELECT phone_no FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
        phone_no_data = cursor.fetchone()

        if phone_no_data:
            phone_no = phone_no_data['phone_no']
            try:
                # Send SMS
                sms = client.messages.create(
                    body=message_content,
                    from_='+14787968736',  # Replace with your Twilio phone number
                    to=f'+91{phone_no}'
                )
                print(f"Notification sent to {phone_no}")

                # Mark notification as sent
                cursor.execute(
                    "UPDATE notifications SET is_sent = TRUE WHERE notification_id = %s",
                    (notification_id,)
                )
                mysql.connection.commit()
            except Exception as e:
                print(f"Error sending SMS to {phone_no}: {e}")

    cursor.close() 

# Route for displaying subsidies taken by the logged-in farmer
@app.route('/farmer_subsidies_taken')
def farmer_subsidies_taken():
    aadhar_id = session.get('aadhar_id')  # Get AADHAR ID from session
    if not aadhar_id:
        flash("You need to log in first.", "error")
        return redirect(url_for('farmer_login'))
    
    search_subsidy_taken = request.args.get('search_subsidy_taken')  # Get search query from request
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if search_subsidy_taken:  # If there's a search query
        # Fetch subsidies taken by the farmer based on the search query
        cursor.execute("SELECT * FROM subsidies_taken WHERE aadhar_id = %s AND subsidy_name LIKE %s", 
                       (aadhar_id, '%' + search_subsidy_taken + '%'))
        subsidies_taken = cursor.fetchall()
        if not subsidies_taken:
            flash('No subsidy taken found for this type.', 'error')

    else:
        # Fetch all subsidies taken by the farmer
        cursor.execute("SELECT * FROM subsidies_taken WHERE aadhar_id = %s", (aadhar_id,))
        subsidies_taken = cursor.fetchall()

    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    cursor.close()

    # Render the farmer subsidies taken template
    return render_template('farmer_subsidies_taken.html', subsidies_taken=subsidies_taken, farmer=farmer)


# Route for displaying schemes taken by the logged-in farmer
@app.route('/farmer_schemes_taken')
def farmer_schemes_taken():
    aadhar_id = session.get('aadhar_id')  # Get AADHAR ID from session
    if not aadhar_id:
        flash("You need to log in first.", "error")
        return redirect(url_for('farmer_login'))
    
    search_scheme_taken = request.args.get('search_scheme_taken')  # Get search query from request
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if search_scheme_taken:  # If there's a search query
        # Fetch schemes taken by the farmer based on the search query
        cursor.execute("SELECT * FROM schemes_taken WHERE aadhar_id = %s AND scheme_name LIKE %s", 
                       (aadhar_id, '%' + search_scheme_taken + '%'))
        schemes_taken = cursor.fetchall()
        if not schemes_taken:
            flash('No scheme taken found for this type.', 'error')

    else:
        # Fetch all schemes taken by the farmer
        cursor.execute("SELECT * FROM schemes_taken WHERE aadhar_id = %s", (aadhar_id,))
        schemes_taken = cursor.fetchall()  # Get all schemes taken by the farmer

    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()

    cursor.close()
    return render_template('farmer_schemes_taken.html', schemes_taken=schemes_taken, farmer=farmer)


# Unified route to view and search available loans without requiring login
@app.route('/available_loans', methods=['GET'])
def available_loans():
    loan_type = request.args.get('loan_type', '')  # Get loan_type from query parameters
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    if loan_type:  # Fetch filtered loans if loan_type is provided
        cursor.execute("SELECT * FROM loans WHERE loan_type LIKE %s AND deleted = FALSE", ('%' + loan_type + '%',))
        loans = cursor.fetchall()
        if not loans:
            flash('No loans found for this type.', 'error')
    else:
        cursor.execute("SELECT * FROM loans WHERE deleted = FALSE")
        loans = cursor.fetchall()

    farmer_apps = {}
    if 'aadhar_id' in session:
        cursor.execute("SELECT item_name, status FROM applications WHERE aadhar_id = %s AND item_type = 'loan'", (session['aadhar_id'],))
        for app_rec in cursor.fetchall():
            farmer_apps[app_rec['item_name']] = app_rec['status']
    for loan in loans:
        loan['application_status'] = farmer_apps.get(loan['loan_type'])

    cursor.close()
    return render_template('available_loans.html', loans=loans)


# Unified route to view and search available subsidies without requiring login
@app.route('/available_subsidies', methods=['GET'])
def available_subsidies():
    subsidy_name = request.args.get('subsidy_name', '')  # Get subsidy_name from query parameters
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Query based on search term if provided, otherwise fetch all active subsidies
    if subsidy_name:
        cursor.execute(
            "SELECT * FROM subsidies WHERE subsidy_name LIKE %s AND deleted = FALSE",
            ('%' + subsidy_name + '%',)
        )
        subsidies = cursor.fetchall()
        if not subsidies:
            flash('No available subsidies found for this name.', 'error')
    else:
        cursor.execute("SELECT * FROM subsidies WHERE deleted = FALSE")
        subsidies = cursor.fetchall()
        
    # Get application status if logged in
    farmer_apps = {}
    if 'aadhar_id' in session:
        cursor.execute(
            "SELECT item_name, status FROM applications WHERE aadhar_id = %s AND item_type = 'subsidy'",
            (session['aadhar_id'],)
        )
        for app_rec in cursor.fetchall():
            farmer_apps[app_rec['item_name']] = app_rec['status']
            
    for subsidy in subsidies:
        subsidy['application_status'] = farmer_apps.get(subsidy['subsidy_name'], None)
    
    cursor.close()
    return render_template('available_subsidies.html', subsidies=subsidies)


# Unified route to view and search available schemes without requiring login
@app.route('/available_schemes', methods=['GET'])
def available_schemes():
    scheme_name = request.args.get('scheme_name', '')  # Get scheme_name from query parameters
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Query based on search term if provided, otherwise fetch all active schemes
    if scheme_name:
        cursor.execute(
            "SELECT * FROM schemes WHERE scheme_name LIKE %s AND deleted = FALSE",
            ('%' + scheme_name + '%',)
        )
        schemes = cursor.fetchall()
        if not schemes:
            flash('No available schemes found for this name.', 'error')
    else:
        cursor.execute("SELECT * FROM schemes WHERE deleted = FALSE")
        schemes = cursor.fetchall()
        
    # Get application status if logged in
    farmer_apps = {}
    if 'aadhar_id' in session:
        cursor.execute(
            "SELECT item_name, status FROM applications WHERE aadhar_id = %s AND item_type = 'scheme'",
            (session['aadhar_id'],)
        )
        for app_rec in cursor.fetchall():
            farmer_apps[app_rec['item_name']] = app_rec['status']
            
    for scheme in schemes:
        scheme['application_status'] = farmer_apps.get(scheme['scheme_name'], None)
    
    cursor.close()
    return render_template('available_schemes.html', schemes=schemes)


@app.route('/apply/<item_type>/<item_name>', methods=['GET'])
def apply_item(item_type, item_name):
    if 'aadhar_id' not in session:
        flash('You must log in as a farmer to apply.', 'error')
        return redirect(url_for('farmer_login'))
        
    aadhar_id = session['aadhar_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # 1. Fetch farmer details
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    
    # 2. Fetch and calculate total land size
    cursor.execute("SELECT land_id, location, land_size FROM lands WHERE aadhar_id = %s AND deleted = FALSE ORDER BY land_id", (aadhar_id,))
    lands = cursor.fetchall()
    total_land_size = sum(float(l['land_size']) for l in lands)
    
    # 3. Fetch last 2 crops grown in the recent past
    cursor.execute("""
        SELECT crop_name, planting_date 
        FROM crops 
        WHERE aadhar_id = %s 
        ORDER BY planting_date DESC 
        LIMIT 2
    """, (aadhar_id,))
    recent_crops = cursor.fetchall()
    
    # 4. Fetch item details (subsidy or scheme)
    item_details = None
    if item_type == 'subsidy':
        cursor.execute("SELECT description, eligibility, last_date_apply FROM subsidies WHERE subsidy_name = %s AND deleted = FALSE", (item_name,))
        item_details = cursor.fetchone()
    elif item_type == 'scheme':
        cursor.execute("SELECT description, eligibility, last_date_apply FROM schemes WHERE scheme_name = %s AND deleted = FALSE", (item_name,))
        item_details = cursor.fetchone()
    elif item_type == 'loan':
        cursor.execute("SELECT description, eligibility FROM loans WHERE loan_type = %s AND deleted = FALSE", (item_name,))
        item_details = cursor.fetchone()
        
    cursor.close()
    
    if not item_details:
        flash(f'Requested {item_type} not found.', 'error')
        return redirect(url_for('home'))
        
    return render_template(
        'apply_form.html',
        farmer=farmer,
        total_land_size=total_land_size,
        recent_crops=recent_crops,
        lands=lands,
        item_type=item_type,
        item_name=item_name,
        item_details=item_details
    )


@app.route('/submit_application', methods=['POST'])
def submit_application():
    if 'aadhar_id' not in session:
        flash('You must log in as a farmer to submit an application.', 'error')
        return redirect(url_for('farmer_login'))
        
    aadhar_id = session['aadhar_id']
    item_type = request.form.get('item_type')
    item_name = request.form.get('item_name')
    land_id = request.form.get('land_id') or None
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Check if already applied
    cursor.execute("""
        SELECT * FROM applications 
        WHERE aadhar_id = %s AND item_type = %s AND item_name = %s
    """, (aadhar_id, item_type, item_name))
    existing = cursor.fetchone()
    
    if existing:
        flash(f'You have already submitted an application for this {item_type}.', 'error')
        cursor.close()
        return redirect(url_for('farmer_applications'))
        
    try:
        if item_type not in ('scheme', 'subsidy', 'loan'):
            flash('Invalid application type.', 'error')
            cursor.close()
            return redirect(url_for('farmer_applications'))

        if land_id:
            cursor.execute("SELECT land_id FROM lands WHERE land_id = %s AND aadhar_id = %s AND deleted = FALSE", (land_id, aadhar_id))
            if not cursor.fetchone():
                flash('Selected land does not belong to this farmer.', 'error')
                cursor.close()
                return redirect(url_for('farmer_applications'))

        cursor.execute("""
            INSERT INTO applications (aadhar_id, land_id, item_type, item_name, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (aadhar_id, land_id, item_type, item_name))
        mysql.connection.commit()
        flash('Application submitted successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error submitting application: {str(e)}', 'error')
        
    cursor.close()
    return redirect(url_for('farmer_applications'))


@app.route('/farmer_applications')
def farmer_applications():
    if 'aadhar_id' not in session:
        flash('You need to log in as a farmer to access this page.', 'error')
        return redirect(url_for('farmer_login'))
        
    aadhar_id = session['aadhar_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get farmer details for sidebar
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    
    # Get applications, join with lands if present
    cursor.execute("""
        SELECT a.*, l.location as land_location 
        FROM applications a 
        LEFT JOIN lands l ON a.land_id = l.land_id 
        WHERE a.aadhar_id = %s 
        ORDER BY a.applied_date DESC
    """, (aadhar_id,))
    applications = cursor.fetchall()
    
    cursor.close()
    return render_template('farmer_applications.html', farmer=farmer, applications=applications)


@app.route('/addfarmer', methods=['GET', 'POST'])
def addfarmer():
    # Ensure user is authenticated before allowing access to this page
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    if request.method == 'POST':
        # Retrieve form data
        farmer_name = request.form.get('f_name')
        date_of_birth = request.form.get('f_dob')
        gender = request.form.get('f_gender')
        phone_no = request.form.get('f_phone')
        city = request.form.get('f_city', '').strip()
        pincode = request.form.get('f_pincode', '').strip()
        state = request.form.get('f_state', '').strip()
        address = build_farmer_address(city, pincode, state)
        if not city or not re.fullmatch(r'\d{6}', pincode) or not state:
            flash('Please provide a valid City, 6-digit Pincode, and State.', 'error')
            return render_template('addfarmer.html', auth_name=session.get('auth_name'))
        aadhar_id = request.form.get('f_aadharId')

        # Connect to MySQL database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Check if Aadhar ID already exists in the database
        cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
        existing_aadhar_id = cursor.fetchone()

        if existing_aadhar_id:
            flash('Aadhar ID already exists', 'error')
            cursor.close()
            return render_template('addfarmer.html', auth_name=session.get('auth_name'))

        # Check if Phone Number already exists in the database
        cursor.execute("SELECT * FROM farmers WHERE phone_no = %s", (phone_no,))
        existing_phone_no = cursor.fetchone()

        if existing_phone_no:
            flash('Phone number already exists', 'error')
            cursor.close()
            return render_template('addfarmer.html', auth_name=session.get('auth_name'))

        # Insert farmer details into the database
        try:
            cursor.execute(
                """INSERT INTO farmers (farmer_name, date_of_birth, gender, phone_no, address, aadhar_id) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (farmer_name, date_of_birth, gender, phone_no, address, aadhar_id)
            )
            mysql.connection.commit()
            flash('Farmer registered successfully!', 'success')
            return redirect(url_for('existingfarmers'))  # Redirect to the 'existingfarmers' page after registration
        except MySQLdb.Error as err:
            mysql.connection.rollback()
            flash(f'Error storing data: {err}', 'error')
        finally:
            cursor.close()

    return render_template('addfarmer.html', auth_name=session.get('auth_name'))


@app.route('/existingfarmers', methods=['GET'])
def existingfarmers():
    if 'auth_email' not in session:
        return redirect(url_for('auth_login'))

    search_aadhar_id = request.args.get('search_f_aadharId')  # Accessing search query from URL
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if search_aadhar_id:
        cursor.execute("SELECT aadhar_id, farmer_name FROM farmers WHERE aadhar_id LIKE %s", ('%' + search_aadhar_id + '%',))
        farmers = cursor.fetchall()


        if not farmers:
            flash('Farmer with this Aadhar ID does not exist.', 'error')
    else:
        cursor.execute("SELECT aadhar_id, farmer_name FROM farmers")
        farmers = cursor.fetchall()

    cursor.close()
    return render_template('existingfarmers.html', auth_name=session.get('auth_name'), farmers=farmers)


@app.route('/editfarmer/<aadhar_id>', methods=['GET', 'POST'])
def editfarmer(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch existing farmer details using Aadhar ID
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()

    if request.method == 'POST':
        farmer_name = request.form.get('f_name')
        date_of_birth = request.form.get('f_dob')
        gender = request.form.get('f_gender')
        phone_no = request.form.get('f_phone')
        city = request.form.get('f_city', '').strip()
        pincode = request.form.get('f_pincode', '').strip()
        state = request.form.get('f_state', '').strip()
        address = build_farmer_address(city, pincode, state)
        new_aadhar_id = request.form.get('f_aadharId')
        if not city or not re.fullmatch(r'\d{6}', pincode) or not state:
            flash('Please provide a valid City, 6-digit Pincode, and State.', 'error')
            farmer['address_parts'] = split_farmer_address(farmer.get('address'))
            return render_template('editfarmer.html', farmer=farmer)

        try:
            # Check if the new Aadhar ID exists for another farmer
            if new_aadhar_id != farmer['aadhar_id']:
                cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s AND aadhar_id != %s", (new_aadhar_id, aadhar_id))
                if cursor.fetchone():
                    flash('Aadhar ID already exists for another farmer.', 'error')
                    return render_template('editfarmer.html', farmer=farmer)

            # Check if the new Phone Number exists for another farmer
            if phone_no != farmer['phone_no']:
                cursor.execute("SELECT * FROM farmers WHERE phone_no = %s AND aadhar_id != %s", (phone_no, aadhar_id))
                if cursor.fetchone():
                    flash('Phone number already exists for another farmer.', 'error')
                    return render_template('editfarmer.html', farmer=farmer)

            # Update farmer details if no conflicts
            cursor.execute("""
                UPDATE farmers
                SET farmer_name = %s, date_of_birth = %s, gender = %s, phone_no = %s, address = %s, aadhar_id = %s
                WHERE aadhar_id = %s
            """, (farmer_name, date_of_birth, gender, phone_no, address, new_aadhar_id, aadhar_id))
            mysql.connection.commit()

            flash('Farmer details updated successfully!', 'success')
            return redirect(url_for('existingfarmers'))

        except MySQLdb.Error as err:
            mysql.connection.rollback()
            flash(f'Error updating data: {err}', 'error')

        finally:
            cursor.close()

    farmer['address_parts'] = split_farmer_address(farmer.get('address'))
    return render_template('editfarmer.html', farmer=farmer)

@app.route('/deletefarmer/<aadhar_id>', methods=['POST'])
def deletefarmer(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # Delete farmer based on Aadhar ID
        cursor.execute("DELETE FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
        mysql.connection.commit()

        flash('Farmer deleted successfully!', 'success')
    except MySQLdb.Error as e:
        mysql.connection.rollback()
        flash(f'Error deleting farmer: {str(e)}', 'error')
    finally:
        cursor.close()

    return redirect(url_for('existingfarmers'))

# Unified route to manage and search lands based on aadhar_id
@app.route('/manage_lands/<aadhar_id>', methods=['GET'])
def manage_lands(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if the farmer exists by aadhar_id
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    if not farmer:
        flash("Farmer not found.", 'error')
        return redirect(url_for('home'))

    # Check for search parameter in query string
    search_land = request.args.get('search_land', '')  # Get search_land query parameter

    if search_land:
        # Search lands based on location
        cursor.execute(
            "SELECT * FROM lands WHERE aadhar_id = %s AND location LIKE %s AND deleted = FALSE",
            (aadhar_id, '%' + search_land + '%')
        )
        lands = cursor.fetchall()
        if not lands:
            flash('No lands found for this location.', 'error')
    else:
        # Retrieve all lands for the farmer
        cursor.execute("SELECT * FROM lands WHERE aadhar_id = %s AND deleted = FALSE", (aadhar_id,))
        lands = cursor.fetchall()

    cursor.close()
    for land in lands:
        land['location_parts'] = split_farmer_address(land.get('location'))

    return render_template('manage_lands.html', farmer=farmer, lands=lands)


# Route to add a new land for a farmer
@app.route('/add_land/<aadhar_id>', methods=['POST'])
def add_land(aadhar_id):
    if 'auth_email' not in session:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor()

    city = request.form.get('land_city', '').strip()
    pincode = request.form.get('land_pincode', '').strip()
    state = request.form.get('land_state', '').strip()
    location = build_farmer_address(city, pincode, state)
    soil_type = request.form['soil_type']
    land_size = request.form['land_size']
    if not city or not re.fullmatch(r'\d{6}', pincode) or not state:
        flash('Please provide a valid land City, 6-digit Pincode, and State.', 'error')
        return redirect(url_for('manage_lands', aadhar_id=aadhar_id))

    try:
        cursor.execute("""
            INSERT INTO lands (aadhar_id, location, soil_type, land_size)
            VALUES (%s, %s, %s, %s)
        """, (aadhar_id, location, soil_type, land_size))
        mysql.connection.commit()
        flash("Land added successfully!", 'success')
    except MySQLdb.Error as err:
        mysql.connection.rollback()
        flash(f"Error adding land: {err}", 'error')
    
    cursor.close()
    print(request.form)  # This will show you what keys are present in the form data
    return redirect(url_for('manage_lands', aadhar_id=aadhar_id))


# Route to update land information
@app.route('/update_land/<aadhar_id>/<int:land_id>', methods=['POST'])
def update_land(aadhar_id, land_id):
    if 'auth_email' not in session :
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor()
    
    city = request.form.get('land_city', '').strip()
    pincode = request.form.get('land_pincode', '').strip()
    state = request.form.get('land_state', '').strip()
    location = build_farmer_address(city, pincode, state)
    soil_type = request.form.get('soil_type')
    land_size = request.form.get('land_size')
    if not city or not re.fullmatch(r'\d{6}', pincode) or not state:
        flash('Please provide a valid land City, 6-digit Pincode, and State.', 'error')
        return redirect(url_for('manage_lands', aadhar_id=aadhar_id))

    try:
        cursor.execute("""
            UPDATE lands 
            SET location = %s,soil_type=%s,land_size=%s
            WHERE aadhar_id = %s AND land_id = %s
        """, (location,soil_type,land_size ,aadhar_id, land_id))
        mysql.connection.commit()
        flash("Land information updated successfully!", 'success')
    except MySQLdb.Error as err:
        mysql.connection.rollback()
        flash(f"Error updating land information: {err}", 'error')

    cursor.close()
    return redirect(url_for('manage_lands', aadhar_id=aadhar_id))



# Route to delete a land record
@app.route('/delete_land/<aadhar_id>/<int:land_id>', methods=['POST'])
def delete_land(aadhar_id, land_id):
    if 'auth_email' not in session:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor()

    try:
        # Soft delete by setting the deleted flag to TRUE
        cursor.execute("""
            UPDATE lands 
            SET deleted = TRUE 
            WHERE aadhar_id = %s AND land_id = %s and deleted=False
        """, (aadhar_id, land_id))
        mysql.connection.commit()
        flash("Land deleted successfully!", 'success')
    except MySQLdb.Error as err:
        mysql.connection.rollback()  # Rollback in case of error
        flash(f"Error deleting land: {err}", 'error')
    finally:
        cursor.close()

    return redirect(url_for('manage_lands', aadhar_id=aadhar_id))

# Unified route to manage and search crops based on aadhar_id
@app.route('/manage_crops/<aadhar_id>', methods=['GET'])
def manage_crops(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if the farmer exists by aadhar_id
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    if not farmer:
        flash("Farmer not found.", 'error')
        return redirect(url_for('home'))

    # Retrieve lands owned by the farmer
    cursor.execute("SELECT land_id, land_size FROM lands WHERE aadhar_id = %s AND deleted = FALSE", (aadhar_id,))
    available_lands = cursor.fetchall()

    # Check for search parameter in query string
    search_crop = request.args.get('search_crop', '')  # Get search_crop query parameter
    if search_crop:
        # Search crops based on crop name
        cursor.execute(
            "SELECT * FROM crops WHERE aadhar_id = %s AND crop_name LIKE %s",
            (aadhar_id, '%' + search_crop + '%')
        )
        crops = cursor.fetchall()
        if not crops:
            flash('No crops found with this name.', 'error')
    else:
        # Retrieve all crops for the farmer
        cursor.execute("SELECT * FROM crops WHERE aadhar_id = %s", (aadhar_id,))
        crops = cursor.fetchall()

    cursor.close()

    for crop in crops:
        crop['status'] = get_crop_status(crop['planting_date'], crop['harvest_date'])

    return render_template('manage_crops.html', farmer=farmer, crops=crops, available_lands=available_lands, today_date=datetime.today().date())


# Crop lifecycle helpers
CROP_DURATIONS = {
    'rice': 120, 'maize': 90, 'chickpea': 100, 'kidneybeans': 90,
    'pigeonpeas': 150, 'mothbeans': 75, 'mungbean': 70, 'blackgram': 80,
    'lentil': 120, 'pomegranate': 180, 'banana': 300, 'mango': 100,
    'grapes': 120, 'watermelon': 90, 'muskmelon': 90, 'apple': 150,
    'orange': 200, 'papaya': 270, 'coconut': 365, 'cotton': 150,
    'jute': 120, 'coffee': 250, 'wheat': 120, 'sugarcane': 365
}

def estimate_harvest_date(crop_name, planting_date):
    normalized_name = crop_name.lower().strip().replace(" ", "")
    return planting_date + timedelta(days=CROP_DURATIONS.get(normalized_name, 120))

def get_crop_status(planting_date, harvest_date):
    today = datetime.today().date()
    if planting_date and planting_date > today:
        return 'Upcoming'
    if harvest_date and harvest_date <= today:
        return 'Harvested'
    return 'Ongoing'

# Route to add a new crop
import joblib
import requests
import numpy as np

model = joblib.load('./model.pkl')  # Path to your trai

@app.route('/add_crop/<aadhar_id>', methods=['POST'])
def add_crop(aadhar_id):
    if 'auth_email' not in session:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        land_id = request.form['land_id']
        crop_name = request.form['crop_name'].strip()
        crop_size = float(request.form['crop_size'])
        N_percent = float(request.form['N_percent'])
        P_percent = float(request.form['P_percent'])
        K_percent = float(request.form['K_percent'])
        soil_ph = float(request.form['soil_ph'])
        planting_date = request.form['planting_date']
        harvest_date = request.form.get('harvest_date') or None
        crop_status = request.form.get('crop_status', 'new')

        if not (0 <= N_percent <= 100) or not (0 <= P_percent <= 100) or not (0 <= K_percent <= 100):
            flash("N, P and K values must be between 0 and 100.", 'error')
            return redirect(url_for('manage_crops', aadhar_id=aadhar_id))
        if not (1 <= soil_ph <= 14):
            flash("Soil pH must be between 1 and 14.", 'error')
            return redirect(url_for('manage_crops', aadhar_id=aadhar_id))

        planting_date_obj = datetime.strptime(planting_date, '%Y-%m-%d').date()
        today = datetime.today().date()
        if crop_status == 'ongoing' and planting_date_obj > today:
            flash("An ongoing crop must have a planting date on or before today.", "error")
            return redirect(url_for('manage_crops', aadhar_id=aadhar_id))

        if harvest_date:
            harvest_date_obj = datetime.strptime(harvest_date, '%Y-%m-%d').date()
            if planting_date_obj >= harvest_date_obj:
                flash("Planting date must be earlier than harvest date.", "error")
                return redirect(url_for('manage_crops', aadhar_id=aadhar_id))
        else:
            harvest_date_obj = estimate_harvest_date(crop_name, planting_date_obj)
            harvest_date = harvest_date_obj.strftime('%Y-%m-%d')

        cursor.execute("SELECT land_size FROM lands WHERE land_id = %s AND aadhar_id = %s AND deleted = FALSE",
                       (land_id, aadhar_id))
        land = cursor.fetchone()
        if not land:
            flash("Selected land was not found.", 'error')
            return redirect(url_for('manage_crops', aadhar_id=aadhar_id))

        cursor.execute("""
            SELECT SUM(crop_size) AS total_crop_size
            FROM crops
            WHERE land_id = %s AND aadhar_id = %s AND crop_active = TRUE
        """, (land_id, aadhar_id))
        total_crop_size = cursor.fetchone()['total_crop_size'] or 0

        if float(total_crop_size) + crop_size > float(land['land_size']):
            flash(f"Cannot add crop. Total crop size exceeds land size ({land['land_size']} acres).", 'error')
            return redirect(url_for('manage_crops', aadhar_id=aadhar_id))

        cursor.execute("""
            SELECT 1 FROM crops
            WHERE land_id = %s AND crop_name = %s AND planting_date = %s AND aadhar_id = %s
        """, (land_id, crop_name, planting_date, aadhar_id))
        if cursor.fetchone():
            flash("A crop with this name and planting date already exists for this farmer.", 'error')
            return redirect(url_for('manage_crops', aadhar_id=aadhar_id))

        cursor.execute("""
            INSERT INTO crops
            (land_id, aadhar_id, crop_name, crop_size, N_percent, P_percent, K_percent,
             soil_ph, planting_date, harvest_date, crop_suggestion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (land_id, aadhar_id, crop_name, crop_size, N_percent, P_percent, K_percent,
              soil_ph, planting_date, harvest_date, None))
        mysql.connection.commit()

        # Keep the existing ML suggestion feature, but never let an external API
        # failure prevent the crop from being registered.
        try:
            cursor.execute("SELECT location FROM lands WHERE land_id = %s", (land_id,))
            land_location = cursor.fetchone()
            if land_location:
                api_key = "0b5f1c161935d39a4bd7dcfaa506791e"
                geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={land_location['location']}&limit=1&appid={api_key}"
                geo_response = requests.get(geo_url, timeout=5)
                if geo_response.status_code == 200 and geo_response.json():
                    geo_data = geo_response.json()[0]
                    power_url = (
                        f"https://power.larc.nasa.gov/api/temporal/climatology/point?"
                        f"parameters=T2M,PRECTOTCORR,RH2M&community=ag&longitude={geo_data['lon']}&latitude={geo_data['lat']}&start=1981&end=2010&format=JSON"
                    )
                    power_response = requests.get(power_url, timeout=5)
                    if power_response.status_code == 200:
                        power_data = power_response.json()
                        avg_temperature = power_data['properties']['parameter'].get('T2M', {}).get('ANN')
                        avg_humidity = power_data['properties']['parameter'].get('RH2M', {}).get('ANN')
                        avg_precipitation = power_data['properties']['parameter'].get('PRECTOTCORR', {}).get('ANN')
                        if all(v is not None for v in (avg_temperature, avg_humidity, avg_precipitation)):
                            input_data = np.array([[N_percent, P_percent, K_percent, avg_temperature,
                                                     avg_humidity, soil_ph, avg_precipitation * 100]])
                            predicted_class = model.predict(input_data)
                            crop_labels = [
                                'rice', 'maize', 'chickpea', 'kidneybeans', 'pigeonpeas', 'mothbeans',
                                'mungbean', 'blackgram', 'lentil', 'pomegranate', 'banana', 'mango',
                                'grapes', 'watermelon', 'muskmelon', 'apple', 'orange', 'papaya',
                                'coconut', 'cotton', 'jute', 'coffee'
                            ]
                            predicted_label = crop_labels[predicted_class[0]]
                            cursor.execute("""
                                UPDATE crops SET crop_suggestion = %s
                                WHERE land_id = %s AND aadhar_id = %s AND crop_name = %s AND planting_date = %s
                            """, (predicted_label, land_id, aadhar_id, crop_name, planting_date))
                            mysql.connection.commit()
        except Exception as prediction_error:
            print(f"Crop suggestion unavailable: {prediction_error}")

        flash(f"Crop added successfully. Harvest date: {harvest_date}.", 'success')
    except (ValueError, MySQLdb.MySQLError) as e:
        mysql.connection.rollback()
        flash(f'Error storing crop: {e}', 'error')
    finally:
        cursor.close()

    return redirect(url_for('manage_crops', aadhar_id=aadhar_id))


# Route to update a crop
@app.route('/update_crop/<aadhar_id>/<land_id>/<crop_name>/<planting_date>', methods=['POST'])
def update_crop(aadhar_id, land_id, crop_name, planting_date):
    if 'auth_email' not in session:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    harvest_date = request.form.get('harvest_date')
    crop_suggestion = request.form.get('crop_suggestion')

    cursor.execute("""
        UPDATE crops
        SET harvest_date = %s, crop_suggestion = %s
        WHERE land_id = %s AND crop_name = %s AND planting_date = %s
    """, (harvest_date, crop_suggestion, land_id, crop_name, planting_date))

    mysql.connection.commit()
    cursor.close()
    flash('Crop updated successfully.', 'success')

    return redirect(url_for('manage_crops', aadhar_id=aadhar_id))

# Route to delete a crop
@app.route('/delete_crop/<aadhar_id>/<land_id>/<crop_name>/<planting_date>', methods=['POST'])
def delete_crop(aadhar_id, land_id, crop_name, planting_date):
    if 'auth_email' not in session:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        DELETE FROM crops 
        WHERE land_id = %s AND crop_name = %s AND planting_date = %s
    """, (land_id, crop_name, planting_date))

    mysql.connection.commit()
    cursor.close()
    flash('Crop deleted successfully.', 'success')

    return redirect(url_for('manage_crops', aadhar_id=aadhar_id))

# Unified route to manage and search loans
@app.route('/manage_loans', methods=['GET'])
def manage_loans():
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    loan_type = request.args.get('loan_type', '')  # Get loan_type from query parameters
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if loan_type:
        # Search for loans matching the loan_type
        cursor.execute(
            "SELECT * FROM loans WHERE loan_type LIKE %s AND deleted = FALSE",  # Only active loans
            ('%' + loan_type + '%',)
        )
        loans = cursor.fetchall()

        if not loans:
            flash('No loans found for this type.', 'error')
    else:
        # If no search term is provided, retrieve all active loans
        cursor.execute("SELECT * FROM loans WHERE deleted = FALSE")  # Only active loans
        loans = cursor.fetchall()

    cursor.close()
    return render_template('manage_loans.html', loans=loans, auth_name=session.get('auth_name'))


# Route to add a new loan
@app.route('/add_loan', methods=['GET', 'POST'])
def add_loan():
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    if request.method == 'POST':
        loan_type = request.form.get('loan_type')
        description = request.form.get('description')
        eligibility = request.form.get('eligibility')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM loans WHERE loan_type = %s AND deleted = FALSE", (loan_type,))  # Check only active loans
        existing_loan = cursor.fetchone()

        if existing_loan:
            flash('Loan type already exists', 'error')
            cursor.close()
            return redirect(url_for('manage_loans'))

        try:
            cursor.execute(
                """INSERT INTO loans (loan_type, description, eligibility) 
                   VALUES (%s, %s, %s)""",
                (loan_type, description, eligibility)
            )
            mysql.connection.commit()
            flash('Loan added successfully!', 'success')
            return redirect(url_for('manage_loans'))
        except MySQLdb.Error as err:
            mysql.connection.rollback()
            flash(f'Error storing data: {err}', 'error')
        finally:
            cursor.close()

    return render_template('manage_loans.html', auth_name=session.get('auth_name'))

# Route to update an existing loan
@app.route('/update_loan/<int:id>', methods=['POST'])
def update_loan(id):
    description = request.form.get('description')
    eligibility = request.form.get('eligibility')

    if not description or not eligibility:
        flash('All fields must be filled!', 'error')
        return redirect(url_for('manage_loans'))

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(""" 
            UPDATE loans 
            SET description = %s, eligibility = %s 
            WHERE loan_id = %s
        """, (description, eligibility, id))
        mysql.connection.commit()
        flash('Loan updated successfully!', 'success')
    except Exception as e:
        flash('Error updating loan: {}'.format(e), 'danger')
    finally:
        cur.close()

    return redirect(url_for('manage_loans'))

# Route to logically delete a loan
@app.route('/delete_loan/<int:loan_id>', methods=['POST'])
def delete_loan(loan_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Logically delete the loan by setting the deleted flag to TRUE
        cur.execute("UPDATE loans SET deleted = TRUE WHERE loan_id = %s", (loan_id,))
        mysql.connection.commit()
        flash('Loan deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting loan: {}'.format(e), 'danger')
    finally:
        cur.close()
    return redirect(url_for('manage_loans'))


# Unified route to view and search loans taken by a farmer
@app.route('/manage_loans_taken/<aadhar_id>', methods=['GET'])
def manage_loans_taken(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if farmer exists by aadhar_id
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    if not farmer:
        flash("Farmer not found.", 'error')
        return redirect(url_for('home'))

    search_loan_taken = request.args.get('search_loan_taken', '')  # Accessing search query from URL
    
    # If search term is provided, filter loans taken by the farmer
    if search_loan_taken:
        cursor.execute("""SELECT lt.*, l.loan_type FROM loans_taken lt 
                          JOIN loans l ON lt.loan_type = l.loan_type 
                          WHERE lt.aadhar_id = %s AND l.loan_type LIKE %s""",
                          (aadhar_id, '%' + search_loan_taken + '%'))
    else:
        # If no search query is provided, fetch all loans taken by the farmer
        cursor.execute("""SELECT lt.*, l.loan_type FROM loans_taken lt 
                          JOIN loans l ON lt.loan_type = l.loan_type 
                          WHERE lt.aadhar_id = %s""", (aadhar_id,))

    loans_taken = cursor.fetchall()

    # Get active loan types (for selection when adding a new loan)
    cursor.execute("SELECT loan_type FROM loans WHERE deleted = FALSE")
    active_loans = cursor.fetchall()

    cursor.close()
    return render_template('manage_loans_taken.html', farmer=farmer, active_loans=active_loans, loans_taken=loans_taken)


# Route to add a loan taken by a farmer
@app.route('/add_loan_taken/<aadhar_id>', methods=['POST'])
def add_loan_taken(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor()

    loan_type = request.form['loan_type']
    bank_name = request.form['bank_name']
    sanction_date = request.form['sanction_date']
    due_date = request.form['due_date']
    amount_taken = request.form['amount_taken']
    status = request.form['status']

    # Validate dates
    if datetime.strptime(due_date, "%Y-%m-%d") <= datetime.strptime(sanction_date, "%Y-%m-%d"):
        flash("Due date must be later than the sanction date.", 'error')
        return redirect(url_for('manage_loans_taken', aadhar_id=aadhar_id))

    # Check if the loan with the same loan_type and sanction_date already exists
    cursor.execute("""SELECT * FROM loans_taken 
                      WHERE loan_type = %s AND sanction_date = %s AND aadhar_id = %s""",
                   (loan_type, sanction_date, aadhar_id))
    existing_loan = cursor.fetchone()

    if existing_loan:
        flash("A loan with this type and sanction date already exists for this farmer.", 'error')
        return redirect(url_for('manage_loans_taken', aadhar_id=aadhar_id))

    # Insert loan taken
    try:
        cursor.execute("""INSERT INTO loans_taken (loan_type, aadhar_id, bank_name, sanction_date, due_date, amount_taken, status)
                          VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                       (loan_type, aadhar_id, bank_name, sanction_date, due_date, amount_taken, status))
        mysql.connection.commit()
        flash("Loan taken added successfully!", 'success')
    except MySQLdb.Error as err:
        mysql.connection.rollback()
        flash(f'Error storing data: {err}', 'error')
    
    cursor.close()
    return redirect(url_for('manage_loans_taken', aadhar_id=aadhar_id))

# Route to update loan taken status
@app.route('/update_loan_taken/<aadhar_id>/<loan_type>/<sanction_date>', methods=['POST'])
def update_loan_taken(aadhar_id, loan_type, sanction_date):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    new_status = request.form.get('status') 
    
    if new_status not in ['paid', 'unpaid']:  # Adjust this list as needed
        flash('Invalid status provided.', 'error')
        return redirect(url_for('manage_loans_taken', aadhar_id=aadhar_id))
    
    cursor = mysql.connection.cursor()

    try:
        cursor.execute(""" 
            UPDATE loans_taken 
            SET status = %s 
            WHERE aadhar_id = %s AND loan_type = %s AND sanction_date = %s
        """, (new_status, aadhar_id, loan_type, sanction_date))
        mysql.connection.commit()
        flash("Loan status updated successfully!", 'success')
    except Exception as e:
        mysql.connection.rollback()  # Rollback in case of error
        flash(f'Error updating loan status: {e}', 'error')
    finally:
        cursor.close()
    
    return redirect(url_for('manage_loans_taken', aadhar_id=aadhar_id))

# Route to logically delete a loan taken
@app.route('/delete_loan_taken/<aadhar_id>/<loan_type>/<sanction_date>', methods=['POST'])
def delete_loan_taken(aadhar_id, loan_type, sanction_date):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(""" 
            DELETE FROM loans_taken 
            WHERE aadhar_id = %s AND loan_type = %s AND sanction_date = %s
        """, (aadhar_id, loan_type, sanction_date))
        mysql.connection.commit()
        flash("Loan taken deleted successfully!", 'success')
    except Exception as e:
        flash(f'Error deleting loan: {e}', 'error')
    finally:
        cursor.close()
    
    return redirect(url_for('manage_loans_taken', aadhar_id=aadhar_id))


@app.route('/manage_applications', methods=['GET'])
def manage_applications():
    if 'auth_email' not in session:
        flash('You need to log in as an authority to access this page.', 'error')
        return redirect(url_for('auth_login'))
        
    auth_name = session.get('auth_name', 'Authority')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch all applications joined with farmer details
    cursor.execute("""
        SELECT a.*, f.farmer_name
        FROM applications a
        JOIN farmers f ON a.aadhar_id = f.aadhar_id
        ORDER BY a.applied_date DESC
    """)
    applications = cursor.fetchall()
    
    # Dynamically fetch total land size and recent 2 crops for each application
    for app_rec in applications:
        aadhar_id = app_rec['aadhar_id']
        
        # 1. Calculate total land size
        cursor.execute("SELECT SUM(land_size) as total_size FROM lands WHERE aadhar_id = %s AND deleted = FALSE", (aadhar_id,))
        land_res = cursor.fetchone()
        app_rec['total_land_size'] = land_res['total_size'] if (land_res and land_res['total_size'] is not None) else 0.0
        
        # 2. Get last 2 crops
        cursor.execute("""
            SELECT crop_name, planting_date 
            FROM crops 
            WHERE aadhar_id = %s 
            ORDER BY planting_date DESC 
            LIMIT 2
        """, (aadhar_id,))
        app_rec['recent_crops'] = cursor.fetchall()
        
    cursor.close()
    return render_template('manage_applications.html', auth_name=auth_name, applications=applications)


@app.route('/respond_application/<int:application_id>/<action>', methods=['POST'])
def respond_application(application_id, action):
    if 'auth_email' not in session:
        flash('You must log in as an authority.', 'error')
        return redirect(url_for('auth_login'))
        
    if action not in ['approve', 'reject']:
        flash('Invalid action.', 'error')
        return redirect(url_for('manage_applications'))
        
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get application details
    cursor.execute("SELECT * FROM applications WHERE application_id = %s", (application_id,))
    app_record = cursor.fetchone()
    
    if not app_record:
        flash('Application not found.', 'error')
        cursor.close()
        return redirect(url_for('manage_applications'))
        
    aadhar_id = app_record['aadhar_id']
    item_name = app_record['item_name']
    item_type = app_record['item_type']
    
    if action == 'approve':
        try:
            # 1. Update application status
            cursor.execute("UPDATE applications SET status = 'approved' WHERE application_id = %s", (application_id,))
            
            # 2. Insert into schemes_taken or subsidies_taken
            today_str = datetime.today().strftime('%Y-%m-%d')
            if item_type == 'subsidy':
                # Check if already exists in subsidies_taken
                cursor.execute("""
                    SELECT * FROM subsidies_taken 
                    WHERE subsidy_name = %s AND aadhar_id = %s AND sanction_date = %s
                """, (item_name, aadhar_id, today_str))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO subsidies_taken (subsidy_name, aadhar_id, sanction_date)
                        VALUES (%s, %s, %s)
                    """, (item_name, aadhar_id, today_str))
            else:
                # Check if already exists in schemes_taken
                cursor.execute("""
                    SELECT * FROM schemes_taken 
                    WHERE scheme_name = %s AND aadhar_id = %s AND approval_date = %s
                """, (item_name, aadhar_id, today_str))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO schemes_taken (scheme_name, aadhar_id, approval_date)
                        VALUES (%s, %s, %s)
                    """, (item_name, aadhar_id, today_str))
            
            mysql.connection.commit()
            flash(f'Application approved! Farmer has been granted the {item_type}.', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error approving application: {str(e)}', 'error')
    else:
        try:
            cursor.execute("UPDATE applications SET status = 'rejected' WHERE application_id = %s", (application_id,))
            mysql.connection.commit()
            flash('Application rejected.', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error rejecting application: {str(e)}', 'error')
            
    cursor.close()
    return redirect(url_for('manage_applications'))


# Unified route to view and search subsidies
@app.route('/manage_subsidies', methods=['GET'])
def manage_subsidies():
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get the search query from URL (if any)
    subsidy_name = request.args.get('subsidy_name', '')

    # If a search term is provided, filter subsidies by subsidy_name
    if subsidy_name:
        cursor.execute(
            "SELECT * FROM subsidies WHERE subsidy_name LIKE %s AND deleted = FALSE",
            ('%' + subsidy_name + '%',)  # Using LIKE for partial matching
        )
    else:
        # If no search term is provided, retrieve all subsidies
        cursor.execute("SELECT * FROM subsidies WHERE deleted = FALSE")

    subsidies = cursor.fetchall()
    cursor.close()

    return render_template('manage_subsidies.html', subsidies=subsidies)


@app.route('/add_subsidy', methods=['GET', 'POST'])
def add_subsidy():
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    if request.method == 'POST':
        subsidy_name = request.form.get('subsidy_name')
        description = request.form.get('description')
        eligibility = request.form.get('eligibility')
        last_date_apply = request.form.get('last_date_apply')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cursor.execute("SELECT * FROM subsidies WHERE subsidy_name = %s AND deleted = FALSE", (subsidy_name,))
        existing_subsidy_type = cursor.fetchone()

        if existing_subsidy_type:
            flash('Subsidy name already exists', 'error')
            cursor.close()
            return redirect(url_for('manage_subsidies'))

        try:
            cursor.execute(
                """INSERT INTO subsidies (subsidy_name, description, eligibility, last_date_apply) 
                   VALUES (%s, %s, %s, %s)""",
                (subsidy_name, description, eligibility, last_date_apply)
            )
            mysql.connection.commit()
            flash('Subsidy added successfully!', 'success')
            return redirect(url_for('manage_subsidies'))
        except MySQLdb.Error as err:
            mysql.connection.rollback()
            flash(f'Error storing data: {err}', 'error')
        finally:
            cursor.close()

    return render_template('manage_subsidies.html', auth_name=session.get('auth_name'))


@app.route('/update_subsidy/<int:id>', methods=['POST'])
def update_subsidy(id):
    description = request.form.get('description')
    eligibility = request.form.get('eligibility')
    last_date_apply = request.form.get('last_date_apply')

    if not description or not eligibility or not last_date_apply:
        flash('All fields must be filled!', 'error')
        return redirect(url_for('manage_subsidies'))

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""
            UPDATE subsidies 
            SET description = %s, eligibility = %s, last_date_apply = %s 
            WHERE subsidy_id = %s
        """, (description, eligibility, last_date_apply, id))
        mysql.connection.commit()
        flash('Subsidy updated successfully!', 'success')
    except Exception as e:
        flash('Error updating subsidy: {}'.format(e), 'danger')
    finally:
        cur.close()

    return redirect(url_for('manage_subsidies'))


@app.route('/delete_subsidy/<int:subsidy_id>', methods=['POST'])
def delete_subsidy(subsidy_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Logically delete the subsidy by setting the deleted flag to TRUE
        cur.execute("UPDATE subsidies SET deleted = TRUE WHERE subsidy_id = %s", (subsidy_id,))
        mysql.connection.commit()
        flash('Subsidy deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting subsidy: {}'.format(e), 'danger')
    finally:
        cur.close()
    return redirect(url_for('manage_subsidies'))

# Unified route to view and search subsidies taken by farmers
@app.route('/manage_subsidies_taken/<aadhar_id>', methods=['GET'])
def manage_subsidies_taken(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if farmer exists by aadhar_id
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    if not farmer:
        flash("Farmer not found.", 'error')
        return redirect(url_for('home'))

    # Get active subsidy types
    cursor.execute("SELECT subsidy_name FROM subsidies WHERE deleted = FALSE")
    active_subsidies = cursor.fetchall()

    # Get the search query from URL (if any)
    search_subsidy_taken = request.args.get('search_subsidy_taken', '')

    # Search for subsidies taken if a search term is provided
    if search_subsidy_taken:
        cursor.execute("""SELECT sut.*, su.subsidy_name FROM subsidies_taken sut 
                          JOIN subsidies su ON sut.subsidy_name = su.subsidy_name 
                          WHERE sut.aadhar_id = %s AND su.subsidy_name LIKE %s""",
                       (aadhar_id, '%' + search_subsidy_taken + '%'))
    else:
        # If no search term is provided, retrieve all subsidies taken by the farmer
        cursor.execute("""SELECT sut.*, su.subsidy_name FROM subsidies_taken sut 
                          JOIN subsidies su ON sut.subsidy_name = su.subsidy_name 
                          WHERE sut.aadhar_id = %s""", (aadhar_id,))

    subsidies_taken = cursor.fetchall()
    cursor.close()

    return render_template('manage_subsidies_taken.html', farmer=farmer, active_subsidies=active_subsidies, subsidies_taken=subsidies_taken)


# Route to add a subsidy taken by a farmer
@app.route('/add_subsidy_taken/<aadhar_id>', methods=['POST'])
def add_subsidy_taken(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    subsidy_name = request.form['subsidy_name']
    sanction_date = request.form['sanction_date']

    # Check if the subsidy with the same subsidy_name and sanction_date already exists
    cursor.execute("""SELECT * FROM subsidies_taken 
                      WHERE subsidy_name = %s AND sanction_date = %s AND aadhar_id = %s""",
                   (subsidy_name, sanction_date, aadhar_id))
    existing_subsidy = cursor.fetchone()

    if existing_subsidy:
        flash("A subsidy with this name and sanction date already exists for this farmer.", 'error')
        return redirect(url_for('manage_subsidies_taken', aadhar_id=aadhar_id))
    
    # Retrieve last_date_apply and ensure it's a date object
    cursor.execute("SELECT last_date_apply FROM subsidies WHERE subsidy_name = %s", (subsidy_name,))
    last_date_apply = cursor.fetchone()

    if last_date_apply:
        last_date_apply = last_date_apply['last_date_apply']

        # Ensure both dates are datetime.date objects
        if isinstance(last_date_apply, str):
            last_date_apply = datetime.strptime(last_date_apply, "%Y-%m-%d").date()

        sanction_date_obj = datetime.strptime(sanction_date, "%Y-%m-%d").date()

        # Validate that the approval date is before the last date to apply
        if sanction_date_obj >= last_date_apply:
            flash("Sanction date must be before the last date to apply.", 'error')
            cursor.close()
            return redirect(url_for('manage_subsidies_taken', aadhar_id=aadhar_id))

    # Insert subsidy taken
    try:
        cursor.execute("""INSERT INTO subsidies_taken (subsidy_name, aadhar_id, sanction_date)
                          VALUES (%s, %s, %s)""",
                       (subsidy_name, aadhar_id, sanction_date))
        mysql.connection.commit()
        flash("Subsidy taken added successfully!", 'success')
    except MySQLdb.Error as err:
        mysql.connection.rollback()
        flash(f'Error storing data: {err}', 'error')
    
    cursor.close()
    return redirect(url_for('manage_subsidies_taken', aadhar_id=aadhar_id))

# Route to logically delete a subsidy taken
@app.route('/delete_subsidy_taken/<aadhar_id>/<subsidy_name>/<sanction_date>', methods=['POST'])
def delete_subsidy_taken(aadhar_id, subsidy_name, sanction_date):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute(""" 
            DELETE FROM subsidies_taken 
            WHERE aadhar_id = %s AND subsidy_name = %s AND sanction_date = %s
        """, (aadhar_id, subsidy_name, sanction_date))
        mysql.connection.commit()
        flash("Subsidy taken deleted successfully!", 'success')
    except Exception as e:
        flash(f'Error deleting subsidy: {e}', 'error')
    finally:
        cursor.close()
    
    return redirect(url_for('manage_subsidies_taken', aadhar_id=aadhar_id))

# Unified route to view and search schemes
@app.route('/manage_schemes', methods=['GET'])
def manage_schemes():
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    scheme_name = request.args.get('scheme_name', '')

    if scheme_name:
        # Search for schemes based on scheme_name if a search term is provided
        cursor.execute(
            "SELECT * FROM schemes WHERE scheme_name LIKE %s AND deleted = FALSE",
            ('%' + scheme_name + '%',)  
        )
    else:
        # If no search term is provided, retrieve all schemes
        cursor.execute("SELECT * FROM schemes WHERE deleted = FALSE")
    
    schemes = cursor.fetchall()
    cursor.close()

    return render_template('manage_schemes.html', schemes=schemes)


@app.route('/add_scheme', methods=['GET', 'POST'])
def add_scheme():
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    if request.method == 'POST':
        scheme_name = request.form.get('scheme_name')
        description = request.form.get('description')
        eligibility = request.form.get('eligibility')
        last_date_apply = request.form.get('last_date_apply')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cursor.execute("SELECT * FROM schemes WHERE scheme_name = %s AND deleted = FALSE", (scheme_name,))

        existing_scheme = cursor.fetchone()

        if existing_scheme:
            flash('Scheme name already exists', 'error')
            cursor.close()
            return redirect(url_for('manage_schemes'))

        try:
            cursor.execute(
                """INSERT INTO schemes (scheme_name, description, eligibility, last_date_apply) 
                   VALUES (%s, %s, %s, %s)""",
                (scheme_name, description, eligibility, last_date_apply)
            )
            mysql.connection.commit()
            flash('Scheme added successfully!', 'success')
            return redirect(url_for('manage_schemes'))
        except MySQLdb.Error as err:
            mysql.connection.rollback()
            flash(f'Error storing data: {err}', 'error')
        finally:
            cursor.close()

    return render_template('manage_schemes.html', auth_name=session.get('auth_name'))


@app.route('/update_scheme/<int:id>', methods=['POST'])
def update_scheme(id):
    description = request.form.get('description')
    eligibility = request.form.get('eligibility')
    last_date_apply = request.form.get('last_date_apply')

    if not description or not eligibility or not last_date_apply:
        flash('All fields must be filled!', 'error')
        return redirect(url_for('manage_schemes'))

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(""" 
            UPDATE schemes 
            SET description = %s, eligibility = %s, last_date_apply = %s 
            WHERE scheme_id = %s
        """, (description, eligibility, last_date_apply, id))
        mysql.connection.commit()
        flash('Scheme updated successfully!', 'success')
    except Exception as e:
        flash('Error updating scheme: {}'.format(e), 'danger')
    finally:
        cur.close()

    return redirect(url_for('manage_schemes'))


@app.route('/delete_scheme/<int:scheme_id>', methods=['POST'])
def delete_scheme(scheme_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Logically delete the scheme by setting the deleted flag to TRUE
        cur.execute("UPDATE schemes SET deleted = TRUE WHERE scheme_id = %s", (scheme_id,))
        mysql.connection.commit()
        flash('Scheme deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting scheme: {}'.format(e), 'danger')
    finally:
        cur.close()
    return redirect(url_for('manage_schemes'))


# Unified route to view and search schemes taken by farmers
@app.route('/manage_schemes_taken/<aadhar_id>', methods=['GET'])
def manage_schemes_taken(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Check if farmer exists by aadhar_id
    cursor.execute("SELECT * FROM farmers WHERE aadhar_id = %s", (aadhar_id,))
    farmer = cursor.fetchone()
    if not farmer:
        flash("Farmer not found.", 'error')
        return redirect(url_for('home'))

    # Get active scheme types
    cursor.execute("SELECT scheme_name FROM schemes WHERE deleted = FALSE")
    active_schemes = cursor.fetchall()

    search_scheme_taken = request.args.get('search_scheme_taken', '')

    if search_scheme_taken:
        # Search for schemes taken by the farmer based on scheme name
        cursor.execute("""SELECT sct.*, sc.scheme_name FROM schemes_taken sct 
                          JOIN schemes sc ON sct.scheme_name = sc.scheme_name 
                          WHERE sct.aadhar_id = %s AND sc.scheme_name LIKE %s""", 
                          (aadhar_id, '%' + search_scheme_taken + '%'))
    else:
        # If no search query, fetch all schemes taken by the farmer
        cursor.execute("""SELECT sct.*, sc.scheme_name FROM schemes_taken sct 
                          JOIN schemes sc ON sct.scheme_name = sc.scheme_name 
                          WHERE sct.aadhar_id = %s""", (aadhar_id,))

    schemes_taken = cursor.fetchall()
    cursor.close()

    return render_template('manage_schemes_taken.html', farmer=farmer, active_schemes=active_schemes, schemes_taken=schemes_taken)



@app.route('/add_scheme_taken/<aadhar_id>', methods=['POST'])
def add_scheme_taken(aadhar_id):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    scheme_name = request.form['scheme_name']
    approval_date = request.form['approval_date']

    # Check if the scheme with the same scheme_name and approval_date already exists
    cursor.execute("""SELECT * FROM schemes_taken 
                      WHERE scheme_name = %s AND approval_date = %s AND aadhar_id = %s""",
                   (scheme_name, approval_date, aadhar_id))
    existing_scheme = cursor.fetchone()

    if existing_scheme:
        flash("A scheme with this name and approval date already exists for this farmer.", 'error')
        cursor.close()
        return redirect(url_for('manage_schemes_taken', aadhar_id=aadhar_id))
    
     # Retrieve last_date_apply and ensure it's a date object
    cursor.execute("SELECT last_date_apply FROM schemes WHERE scheme_name = %s", (scheme_name,))
    last_date_apply = cursor.fetchone()

    if last_date_apply:
        last_date_apply = last_date_apply['last_date_apply']

        # Ensure both dates are datetime.date objects
        if isinstance(last_date_apply, str):
            last_date_apply = datetime.strptime(last_date_apply, "%Y-%m-%d").date()

        approval_date_obj = datetime.strptime(approval_date, "%Y-%m-%d").date()

        # Validate that the approval date is before the last date to apply
        if approval_date_obj >= last_date_apply:
            flash("Approval date must be before the last date to apply.", 'error')
            cursor.close()
            return redirect(url_for('manage_schemes_taken', aadhar_id=aadhar_id))

    # Insert scheme taken
    try:
        cursor.execute("""INSERT INTO schemes_taken (scheme_name, aadhar_id, approval_date)
                          VALUES (%s, %s, %s)""",
                       (scheme_name, aadhar_id, approval_date))
        mysql.connection.commit()
        flash("Scheme taken added successfully!", 'success')
    except MySQLdb.Error as err:
        mysql.connection.rollback()
        flash(f'Error storing data: {err}', 'error')
    
    cursor.close()
    return redirect(url_for('manage_schemes_taken', aadhar_id=aadhar_id))


# Route to logically delete a scheme taken
@app.route('/delete_scheme_taken/<aadhar_id>/<scheme_name>/<approval_date>', methods=['POST'])
def delete_scheme_taken(aadhar_id, scheme_name, approval_date):
    if 'auth_email' not in session:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth_login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute(""" 
            DELETE FROM schemes_taken 
            WHERE aadhar_id = %s AND scheme_name = %s AND approval_date = %s
        """, (aadhar_id, scheme_name, approval_date))
        mysql.connection.commit()
        flash("Scheme taken deleted successfully!", 'success')
    except Exception as e:
        flash(f'Error deleting scheme: {e}', 'error')
    finally:
        cursor.close()
    
    return redirect(url_for('manage_schemes_taken', aadhar_id=aadhar_id))

if __name__ == '__main__':
    with app.app_context():
       send_notifications(client)
    app.run(debug=True)
    