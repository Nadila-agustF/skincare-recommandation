import mysql.connector
import streamlit as st
import os


class DatabaseConnection:
    def __init__(self):
        self.connection = None

    def connect(self):
        """Membuat koneksi ke database MySQL (Aiven)"""
        try:
            self.connection = mysql.connector.connect(
                host=st.secrets["mysql"]["host"],
                port=st.secrets["mysql"]["port"],
                database=st.secrets["mysql"]["database"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                ssl_ca=os.path.abspath(st.secrets["mysql"]["ssl_ca"]),
                ssl_verify_cert=True,
                use_pure=True,
                connection_timeout=5
            )
            return self.connection
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            self.connection = None
            return None

    def is_connected(self):
        return self.connection and self.connection.is_connected()

    # ===============================
    # SAVE USER HISTORY
    # ===============================
    def save_user_history(self, username, age, gender, skin_type, category):
        if not self.is_connected():
            return None

        try:
            cursor = self.connection.cursor()
            query = """
                INSERT INTO user_history (username, age, gender, skin_type, category)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (username, age, gender, skin_type, category))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"❌ Error saving user history: {e}")
            return None

    # ===============================
    # SAVE RECOMMENDATIONS
    # ===============================
    def save_recommendations(self, user_id, recommendations, product_urls=None):
        if not self.is_connected():
            return False

        try:
            cursor = self.connection.cursor()
            query = """
                INSERT INTO item_recommend (user_id, product_name, rank_position, product_urls)
                VALUES (%s, %s, %s, %s)
            """
            for i, product in enumerate(recommendations):
                url = product_urls[i] if product_urls else None
                cursor.execute(query, (user_id, product, url, i + 1))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"❌ Error saving recommendations: {e}")
            return False
