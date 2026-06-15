import time
import psycopg2
import os
import sys

def main():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL env variable not set. Skipping DB check.")
        sys.exit(0)

    print("Waiting for database to be ready at host...")
    
    # Try up to 30 times (30 seconds)
    for i in range(30):
        try:
            # Connect using psycopg2
            conn = psycopg2.connect(db_url)
            conn.close()
            print("Database is ready and accepting connections!")
            sys.exit(0)
        except psycopg2.OperationalError as e:
            print(f"Database not ready yet (Attempt {i+1}/30)... waiting 1s.")
            time.sleep(1)
            
    print("Database connection timed out! Exiting.")
    sys.exit(1)

if __name__ == '__main__':
    main()
