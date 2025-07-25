import os
import json
import mysql.connector

# ==== Konfigurasi DB ====
DB_NAME = "seleksi_lab_basdat_warehouse_new"
DB_USER = "root"
DB_PASSWORD = "4L1y42003"
DB_HOST = "localhost"
DB_PORT = 3306

def load_json(filename):
    path = os.path.join("Data Scraping", "data", "preprocessed", filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_int(val):
    try:
        if val is None or val == "":
            return None
        return int(val)
    except:
        return None

def create_tables():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
    )
    cursor = conn.cursor()

    cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
    cursor.execute(f"CREATE DATABASE {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")

    commands = [
        # dim_date
        """
        CREATE TABLE dim_date (
            date DATE PRIMARY KEY,
            day INT,
            month INT,
            quarter INT,
            semester INT,
            year INT
        );
        """,
        # dim_country
        """
        CREATE TABLE dim_country (
            country_id INT PRIMARY KEY,
            country VARCHAR(100)
        );
        """,
        # dim_community
        """
        CREATE TABLE dim_community (
            community_id INT PRIMARY KEY,
            community_name VARCHAR(255),
            member INT
        );
        """,
        # dim_game
        """
        CREATE TABLE dim_game (
            game_id BIGINT PRIMARY KEY,
            title VARCHAR(255),
            date_created DATE,
            last_updated DATE,
            genre_id INT,
            url TEXT,
            community_id INT,
            country_id INT,
            FOREIGN KEY (community_id) REFERENCES dim_community(community_id),
            FOREIGN KEY (country_id) REFERENCES dim_country(country_id)
        );
        """,
        # dim_game_per_country
        """
        CREATE TABLE dim_game_per_country (
            country_id INT,
            game_id BIGINT,
            PRIMARY KEY (country_id, game_id),
            FOREIGN KEY (country_id) REFERENCES dim_country(country_id),
            FOREIGN KEY (game_id) REFERENCES dim_game(game_id)
        );
        """,
        # fact_game_stats
        """
        CREATE TABLE fact_game_stats (
            stats_id INT AUTO_INCREMENT PRIMARY KEY,
            active_users INT,
            favorites INT,
            total_visits BIGINT,
            thumbs_up INT,
            thumbs_down INT,
            RBM INT,
            game_id BIGINT,
            date DATE,
            FOREIGN KEY (game_id) REFERENCES dim_game(game_id),
            FOREIGN KEY (date) REFERENCES dim_date(date),
            UNIQUE KEY unique_game_date (game_id, date)
        );
        """
    ]

    for command in commands:
        cursor.execute(command)

    conn.commit()
    return conn, cursor

def insert_data(cursor, conn):
    cursor.execute(f"USE {DB_NAME}")

    # Insert communities
    communities = load_json("community_preprocessed.json")
    for comm in communities:
        cursor.execute("""
            INSERT IGNORE INTO dim_community (community_id, community_name, member)
            VALUES (%s, %s, %s)
        """, (
            comm.get("communityID"),
            comm.get("Community Name", None),
            comm.get("Members", None)
        ))

    # Insert games and facts
    games = load_json("game_preprocessed.json")
    for g in games:
        # Validate game_id
        try:
            game_id = int(g["gameID"])
            if game_id <= 0:
                print(f"Skipping invalid game_id: {g['gameID']}")
                continue
        except (ValueError, TypeError):
            print(f"Skipping non-integer game_id: {g['gameID']}")
            continue

        date_val = g.get("Date")
        community_id = g.get("communityID")

        # Insert into dim_date (auto derive attributes)
        cursor.execute("""
            INSERT IGNORE INTO dim_date (date, day, month, quarter, semester, year)
            VALUES (%s, DAY(%s), MONTH(%s), QUARTER(%s),
                    IF(MONTH(%s)<=6,1,2), YEAR(%s))
        """, (date_val, date_val, date_val, date_val, date_val, date_val))

        # Insert dim_game
        try:
            cursor.execute("""
                INSERT IGNORE INTO dim_game (
                    game_id, title, date_created, last_updated,
                    genre_id, url, community_id, country_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,NULL)
            """, (
                game_id,
                g.get("Title"),
                g.get("Date Created"),
                g.get("Last Updated"),
                g.get("genreID"),
                g.get("URL"),
                community_id
            ))
        except mysql.connector.Error as e:
            print(f"Error inserting dim_game for game_id={game_id}: {e}")
            continue

        # Insert fact_game_stats
        cursor.execute("""
            INSERT IGNORE INTO fact_game_stats
            (active_users, favorites, total_visits, thumbs_up, thumbs_down, RBM, game_id, date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            parse_int(g.get("Active Users", 0)) or 0,
            parse_int(g.get("Favorites", 0)) or 0,
            parse_int(g.get("Total Visits", 0)) or 0,
            parse_int(g.get("Thumbs Up", 0)) or 0,
            parse_int(g.get("Thumbs Down", 0)) or 0,
            parse_int(g.get("RBM", 0)) or 0,
            game_id,
            date_val
        ))


if __name__ == "__main__":
    conn, cursor = create_tables()
    insert_data(cursor, conn)
    conn.commit()
    cursor.close()
    conn.close()
    print("Data warehouse berhasil dibuat dan diisi.")
