import sqlite3, os
from flask import g

def connect_to_database():
    sql = sqlite3.connect("quizapp.db")
    sql.row_factory = sqlite3.Row
    return sql

def getDatabase():
    if not hasattr(g, "quizapp_db"):
        g.quizapp_db = connect_to_database()
    return g.quizapp_db
