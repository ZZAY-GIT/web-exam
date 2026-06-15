#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for PostgreSQL database to be online
python wait_for_db.py

# Initialize database schema and insert default credentials/genres
python seed.py

# Launch the Flask application
python app.py
