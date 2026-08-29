
CREATE DATABASE AgriData;
USE AgriData;
CREATE TABLE auths (
    auth_id INT AUTO_INCREMENT PRIMARY KEY,
    auth_name VARCHAR(100) NOT NULL,
    auth_email VARCHAR(255) NOT NULL UNIQUE,
    auth_pass VARCHAR(255) NOT NULL,
    auth_phone_no VARCHAR(15) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create table for farmers
CREATE TABLE farmers (
    farmer_id INT AUTO_INCREMENT PRIMARY KEY,  
    farmer_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    phone_no VARCHAR(15) NOT NULL UNIQUE,
    address VARCHAR(255) NOT NULL,
    aadhar_id VARCHAR(12) NOT NULL UNIQUE,
    first_login BOOLEAN DEFAULT TRUE
);

CREATE TABLE lands(
    land_id INT AUTO_INCREMENT PRIMARY KEY,
    aadhar_id VARCHAR(12),
    location VARCHAR(50) NOT NULL,
    soil_type VARCHAR(50) NOT NULL,
    land_size DECIMAL(10,4) NOT NULL,
    deleted BOOLEAN DEFAULT FALSE ,
    FOREIGN KEY (aadhar_id) REFERENCES farmers(aadhar_id)ON DELETE CASCADE ON UPDATE CASCADE  -- Cascades on both delete and update
    );
    
    -- Crops Grown on Land
CREATE TABLE crops (
    land_id INT,
    aadhar_id VARCHAR(12),
    crop_name VARCHAR(100) NOT NULL,
    crop_size DECIMAL(10,4) NOT NULL,
    N_percent DECIMAL(5, 2) NOT NULL,
    P_percent DECIMAL(5, 2) NOT NULL,
    K_percent DECIMAL(5, 2) NOT NULL,
    soil_ph DECIMAL(4, 2),
    planting_date DATE NOT NULL,
    harvest_date DATE NOT NULL,
    crop_suggestion VARCHAR(100),
    crop_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (land_id, crop_name, planting_date),
    FOREIGN KEY (land_id) REFERENCES lands(land_id) ON DELETE NO ACTION,
    FOREIGN KEY (aadhar_id) REFERENCES farmers(aadhar_id) ON DELETE CASCADE ON UPDATE CASCADE
);


CREATE TABLE loans (
    loan_id INT AUTO_INCREMENT PRIMARY KEY,
    loan_type VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    eligibility TEXT NOT NULL,
    deleted BOOLEAN DEFAULT FALSE  -- Added column to mark if the loan is deleted
);


CREATE TABLE loans_taken (
    loan_type VARCHAR(100),  -- Change from loan_id to loan_type
    aadhar_id VARCHAR(12),
    bank_name VARCHAR(100) NOT NULL, 
    sanction_date DATE NOT NULL,
    due_date DATE NOT NULL,
    amount_taken DECIMAL(10, 2) NOT NULL,
    status ENUM('paid', 'unpaid') NOT NULL DEFAULT 'unpaid',
    PRIMARY KEY (loan_type, aadhar_id, sanction_date),  -- Composite Primary Key
    FOREIGN KEY (loan_type) REFERENCES loans(loan_type) ON DELETE NO ACTION,  -- Reference by loan_type
    FOREIGN KEY (aadhar_id) REFERENCES farmers(aadhar_id) ON DELETE CASCADE ON UPDATE CASCADE  -- Cascades on both delete and update
);



CREATE TABLE subsidies (
    subsidy_id INT AUTO_INCREMENT PRIMARY KEY,
    subsidy_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    eligibility TEXT NOT NULL,
    last_date_apply DATE NOT NULL,
	deleted BOOLEAN DEFAULT FALSE 
);

CREATE TABLE subsidies_taken (
	subsidy_name VARCHAR(255),
    aadhar_id VARCHAR(12),
    sanction_date DATE NOT NULL,
     PRIMARY KEY (subsidy_name, aadhar_id, sanction_date),  -- Composite Primary Key
    FOREIGN KEY (subsidy_name) REFERENCES subsidies(subsidy_name) ON DELETE NO ACTION,  
    FOREIGN KEY (aadhar_id) REFERENCES farmers(aadhar_id) ON DELETE CASCADE ON UPDATE CASCADE  -- Cascades on both delete and update
);

CREATE TABLE schemes (
    scheme_id INT AUTO_INCREMENT PRIMARY KEY,
    scheme_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    eligibility TEXT NOT NULL,
    last_date_apply DATE NOT NULL,
    deleted BOOLEAN DEFAULT FALSE 
);

CREATE TABLE schemes_taken (
	scheme_name VARCHAR(255),
    aadhar_id VARCHAR(12),
    approval_date DATE NOT NULL,
	PRIMARY KEY (scheme_name, aadhar_id, approval_date),  -- Composite Primary Key
    FOREIGN KEY (scheme_name) REFERENCES schemes(scheme_name) ON DELETE NO ACTION,  
    FOREIGN KEY (aadhar_id) REFERENCES farmers(aadhar_id) ON DELETE CASCADE ON UPDATE CASCADE  -- Cascades on both delete and update
);

CREATE TABLE farmer_notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,  
    farmer_id INT NOT NULL,                         -- Reference to the farmer
    notification_type VARCHAR(100),                 -- Type of notification (e.g., 'Welcome Message')
    notification_message TEXT,                      -- The content of the notification
    sent BOOLEAN DEFAULT FALSE,                     -- Status to check if the notification has been sent
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,                  -- Timestamp when the notification was sent
    FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id) on DELETE CASCADE ON UPDATE CASCADE -- Link to the farmers table
);
#loan notifications
CREATE TABLE notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    aadhar_id VARCHAR(12) NOT NULL,
    notification_type VARCHAR(100) DEFAULT 'General',
    message VARCHAR(255) NOT NULL,   -- The notification message
    notification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Timestamp of notification creation
    is_sent BOOLEAN DEFAULT FALSE,  -- Indicates whether the notification is sent
    FOREIGN KEY (aadhar_id) REFERENCES farmers(aadhar_id) on DELETE CASCADE ON UPDATE CASCADE -- Cascade delete
);

CREATE TABLE applications (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    aadhar_id VARCHAR(12) NOT NULL,
    land_id INT, -- Optional land selection
    item_type VARCHAR(50) NOT NULL, -- 'scheme' or 'subsidy'
    item_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aadhar_id) REFERENCES farmers(aadhar_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (land_id) REFERENCES lands(land_id) ON DELETE SET NULL ON UPDATE CASCADE
);



DELIMITER //
CREATE EVENT update_crop_active_event
ON SCHEDULE EVERY 1 second   -- Adjust the interval as needed, e.g., '1 HOUR', '1 DAY', etc.
DO
BEGIN
    UPDATE crops
    SET crop_active = FALSE
    WHERE harvest_date IS NOT NULL
      AND harvest_date <= CURDATE();
      
    UPDATE crops
    SET crop_active = TRUE
    WHERE (harvest_date IS NULL OR harvest_date > CURDATE());
END;
//

DELIMITER ;
SET GLOBAL event_scheduler = ON;

DELIMITER $$
CREATE TRIGGER after_farmer_login
AFTER UPDATE ON farmers
FOR EACH ROW
BEGIN
    IF OLD.first_login = TRUE AND NEW.first_login = FALSE THEN
        -- Log or insert into a notifications table to indicate a welcome message should be sent
        INSERT INTO farmer_notifications (farmer_id, notification_type, notification_message, sent)
        VALUES (NEW.farmer_id, 'Welcome Message', 'Send a welcome message to the new farmer', FALSE);
    END IF;
END$$
DELIMITER ;




DELIMITER $$

CREATE TRIGGER due_date_notification
AFTER INSERT ON loans_taken
FOR EACH ROW
BEGIN
    -- Check if the loan's due date is within 30 days from today and status is 'unpaid'
    IF NEW.due_date <= CURDATE() + INTERVAL 30 DAY AND NEW.status = 'unpaid' THEN
        -- Avoid duplicates by checking if the notification already exists
        IF NOT EXISTS (
            SELECT 1 FROM notifications 
            WHERE aadhar_id = NEW.aadhar_id
              AND message = CONCAT('Reminder: Your loan with loan type ', NEW.loan_type, 
                                   ' is due on ', NEW.due_date, '. Please make necessary arrangements.')
        ) THEN
            -- Insert a notification into the notifications table
            INSERT INTO notifications (aadhar_id, message)
            VALUES (
                NEW.aadhar_id, 
                CONCAT('Reminder: Your loan with loan type ', NEW.loan_type, 
                       ' is due on ', NEW.due_date, '. Please make necessary arrangements.')
            );
        END IF;
    END IF;
END $$

DELIMITER ;

select * from notifications;
select * from farmer_notifications;
select * from auths;
select * from farmers;
select * from lands;
select * from crops;
select * from loans;
select * from loans_taken;
select * from subsidies;
select * from subsidies_taken;
select * from schemes;
select * from schemes_taken;
