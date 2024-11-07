import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector

# Get the password from an environment variable
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Database connection configuration (DON'T PUSH PASSWORD TO DOCKERHUB)
db_config = {
    'user': 'root',
    'password': 'dbuserdbuser',
    'host': 'localhost',
    'database': 'roulette',
}

# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)

# Function to get a database connection
def get_db_connection():
    return mysql.connector.connect(**db_config)

# Endpoint to get wins and losses by username
@app.get("/get_records/")
def get_scores(username: str = Query(...)):
    # Establish database connection
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Query the database for the user's scores
        query = "SELECT wins, losses FROM records WHERE username = %s"
        cursor.execute(query, (username,))
        result = cursor.fetchone()

        if result:
            wins, losses = result
            return {"username": username, "wins": wins, "losses": losses}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    finally:
        cursor.close()
        conn.close()
