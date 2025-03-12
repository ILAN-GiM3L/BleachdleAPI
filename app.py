import os
import mysql.connector
from flask import Flask, jsonify, request
import json
import urllib.parse
from datetime import datetime, timedelta
import pytz

# Initialize Flask app
app = Flask(__name__)

# Function to create a connection to the Cloud SQL database
def create_connection():
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        url = urllib.parse.urlparse(db_url)
        connection = mysql.connector.connect(
            user=url.username,
            password=url.password,
            host=url.hostname,
            database=url.path[1:]
        )
        return connection
    else:
        raise Exception("DATABASE_URL environment variable not set")

# Function to fetch the current character and its timestamp from the database
def get_current_character():
    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT character_data, last_updated FROM current_character LIMIT 1")
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return result

# Function to fetch the current bankai and its timestamp from the database
def get_current_bankai():
    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT chr_bankai, chr_id, last_updated FROM current_bankai LIMIT 1")
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return result

# Function to fetch the current schrift and its timestamp from the database
def get_current_schrift():
    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT chr_schrift, chr_id, last_updated FROM current_schrift LIMIT 1")
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return result

# Function to fetch a random character from the database
def get_random_character():
    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bleach_characters ORDER BY RAND() LIMIT 1")
    random_character = cursor.fetchone()
    cursor.close()
    connection.close()
    return random_character

# Function to fetch a random Bankai from the database
def get_random_bankai():
    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bleach_bankai ORDER BY RAND() LIMIT 1")
    random_bankai = cursor.fetchone()
    cursor.close()
    connection.close()
    return random_bankai

# Function to fetch a random Schrift from the database
def get_random_schrift():
    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bleach_schrift ORDER BY RAND() LIMIT 1")
    random_schrift = cursor.fetchone()
    cursor.close()
    connection.close()
    return random_schrift

# Function to refresh all (character, bankai, and schrift) at the same time
def refresh_all():
    # Fetch a random character, bankai, and schrift
    new_character = get_random_character()
    new_bankai = get_random_bankai()
    new_schrift = get_random_schrift()

    # Store the new data into their respective tables
    connection = create_connection()
    cursor = connection.cursor()

    # Insert or update the character in the current_character table
    cursor.execute("""
        REPLACE INTO current_character (id, character_data, last_updated)
        VALUES (1, %s, NOW())
    """, (json.dumps(new_character),))

    # Insert or update the bankai in the current_bankai table
    cursor.execute("""
        REPLACE INTO current_bankai (id, chr_bankai, chr_id, last_updated)
        VALUES (1, %s, %s, NOW())
    """, (new_bankai["chr_bankai"], new_bankai["chr_id"]))

    # Insert or update the schrift in the current_schrift table
    cursor.execute("""
        REPLACE INTO current_schrift (id, chr_schrift, chr_id, last_updated)
        VALUES (1, %s, %s, NOW())
    """, (new_schrift["chr_schrift"], new_schrift["chr_id"]))

    # Commit the transaction to the database
    connection.commit()
    cursor.close()
    connection.close()

    return new_character, new_bankai, new_schrift

# Function to check if the character, bankai, or schrift need to be refreshed (if it's midnight UTC)
def needs_refresh(character_last_updated, bankai_last_updated, schrift_last_updated):
    now = datetime.now(pytz.UTC)  # Ensure now is timezone-aware

    # If last_updated is None, it means no character exists, so refresh immediately
    if character_last_updated is None or bankai_last_updated is None or schrift_last_updated is None:
        return True

    # Ensure the last_updated timestamps are timezone-aware
    if character_last_updated.tzinfo is None:
        character_last_updated = pytz.UTC.localize(character_last_updated)

    if bankai_last_updated.tzinfo is None:
        bankai_last_updated = pytz.UTC.localize(bankai_last_updated)

    if schrift_last_updated.tzinfo is None:
        schrift_last_updated = pytz.UTC.localize(schrift_last_updated)

    # Calculate the next midnight time and make it timezone-aware
    next_midnight = max(
        character_last_updated.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        bankai_last_updated.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        schrift_last_updated.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
    )

    # Localize the next midnight if it doesn't already have timezone info
    if next_midnight.tzinfo is None:
        next_midnight = pytz.UTC.localize(next_midnight)

    # If current time is past the next midnight, refresh all three
    if now >= next_midnight:
        return True

    return False

# Initialize the character, bankai, and schrift only if they do not exist
def initialize_data():
    # Check if the current character, bankai, and schrift exist in the database
    current_character_data = get_current_character()
    current_bankai_data = get_current_bankai()
    current_schrift_data = get_current_schrift()

    if not current_character_data or not current_bankai_data or not current_schrift_data:
        # If any of them do not exist, initialize all of them
        refresh_all()

# Initialize the data before the app handles any requests
initialize_data()

# Endpoint to get the current data based on path parameter (e.g., /character, /bankai, /schrift)
@app.route('/<type>', methods=['GET'])
def get_data(type):
    type = type.lower()  # Convert the type to lowercase

    # Fetch the current character, bankai, and schrift, along with their timestamps
    current_character_data = get_current_character()
    current_bankai_data = get_current_bankai()
    current_schrift_data = get_current_schrift()

    if current_character_data and current_bankai_data and current_schrift_data:
        # Check if any data needs to be refreshed
        character_last_updated = current_character_data['last_updated']
        bankai_last_updated = current_bankai_data['last_updated']
        schrift_last_updated = current_schrift_data['last_updated']

        if needs_refresh(character_last_updated, bankai_last_updated, schrift_last_updated):
            # Refresh all if needed
            current_character_data, current_bankai_data, current_schrift_data = refresh_all()

        # Deserialize character_data from JSON string to Python dictionary
        character_data = json.loads(current_character_data['character_data'])

        # Return based on the 'type' path parameter
        if type == 'character':
            return jsonify({"character": character_data})
        elif type == 'bankai':
            return jsonify({
                "bankai": {
                    "chr_bankai": current_bankai_data["chr_bankai"],
                    "chr_id": current_bankai_data["chr_id"]  # No chr_name here; it's obtained through chr_id
                }
            })
        elif type == 'schrift':
            return jsonify({
                "schrift": {
                    "chr_schrift": current_schrift_data["chr_schrift"],
                    "chr_id": current_schrift_data["chr_id"]  # No chr_name here; it's obtained through chr_id
                }
            })
        else:
            # If an unknown type is passed, return 404
            return jsonify({"error": "Not found"}), 404

    else:
        return jsonify({"error": "No data available"}), 500

# Default endpoint to show only character data if no type is given
@app.route('/', methods=['GET'])
def get_default():
    return get_data('character')

# Ensuring the app runs on Google App Engine using the default host and port
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)



