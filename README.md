# Agrinexus-DBMS-Minor-Project
  
Agriculture plays a vital role in many economies, but farmers often face challenges accessing the information they need to improve their livelihoods. Simultaneously, governments and agricultural researchers require accurate, centralized data to make informed decisions.

However, the absence of a unified system to manage crop details, government subsidies, and loans creates a significant gap hindering effective planning and support.

To bridge this gap, we developed Agrinexus: a comprehensive Database Management System with a user-friendly interface that consolidates all essential agricultural information into a single platform.

📌 This project was developed as part of our Database Management Systems (DBMS) Minor Project coursework.
## Table of Contents
- [Key Features](#key-features)
- [Installation](#installation)
- [Twilio Integration](#twilio-integration)
- [Run the Project](#run-the-project)
- [Login Instructions](login-instructions)
- [Contributors](#contributors)
## Key Features
#### 1. **Loan & Scheme Awareness**:
- Farmers can view available government loans, schemes, and subsidies relevant to their profiles.
#### 2. **Farmer & Crop Management**:
- Authorities can register farmers and add details about their crops, lands, loans, schemes and subsidies.
- Authorities will add or update available loans, schemes, subsidies.
 #### 3. **AI-Powered Crop Recommendation**:
- A Machine Learning model suggests optimal crops for the upcoming year based on soil profile and geographic conditions (e.g., temperature, humidity, and average rainfall), retrieved via external APIs.
#### 4. **SMS Notifications via Twilio**:
  - Sends a welcome message to the farmer upon first login.
  - Sends loan repayment reminders to ensure timely payments.
#### 5. **Centralized Farmer Dashboard**: Farmers can access a personalized dashboard showing:
  - Crops grown each year.
  - Land details.
  - Details of loans, subsidies, and schemes availed.
## Installation
#### 1.Clone the Repository
```bash
git@github.com:PavithraNelluri/Agrinexus-DBMS-Minor-Project-.git
```
#### 2.Set Up the DataBase
-  Create a MySQL account if you don’t have one. 
-  Log in to MySQL and create a new database and paste the code given in the Agrinexus.sql file.
-  Create a .env file in your project directory and add the following:

```bash
MYSQL_HOST="your host name"   # usually "localhost"
MYSQL_USER="your user name"  # e.g., "root"
MYSQL_PASSWORD="your password"
MYSQL_DB="your "AgriData"
```
#### 3.Create a Virtual Environment
```bash
python -m venv venv
```
#### 4.Activate the virtual environment
- On Windows
```bash
venv/Scripts/activate
```
- On macOS/Linux:
```bash
  source venv/bin/activate
```
#### 5.Install Dependencies
```bash
pip install -r requirements.txt
```
##  Twilio Integration
We use Twilio API to send a welcome message to farmers upon their first login.
### 🔑 Setup Instructions:
#### 1.Sign up for a free or paid Twilio account.
#### 2.Get your:
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_PHONE_NUMBER
#### 3.Create a .env file in the root directory and add your credentials:
```ini
ACCOUNT_SID=your_account_sid
AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_twilio_number
```
## Run the Project
Once setup is complete, start the application with: 
```bash
python app.py
```
## Login Instructions:
#### 1. To Register/Log in as Authority:
- Use an email in the following format: example@agri.com
- Use the default password: AgridataNexus@123
#### 2. To Log in as Farmer:
- Farmers must be registered by an authority before logging in.
- Use the Aadhar ID and Mobile Number exactly as registered by the authority.
## Contributors
- [Jayanthi-21](https://github.com/Jayanthi-21)
- [onlyyashwanth1](https://github.com/onlyyashwanth1)
- [prudhvi-machana](https://github.com/prudhvi-machana)
- [PavithraNelluri](https://github.com/PavithraNelluri)

