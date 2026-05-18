import duckdb


con = None

def init_connection():
    global con
    con = duckdb.connect("./datalake/activities.db")

def create_all_activities(df):
    con.execute("CREATE TABLE activities AS SELECT * FROM df")


def create_all_activity_streams(df):
    con.execute("CREATE TABLE activity_stream AS SELECT * FROM df")

def create_all_athletes(df):
    con.execute("CREATE TABLE athletes AS SELECT * FROM df")

def create_foreign_keys():
    con.execute("ALTER TABLE activities ADD CONSTRAINT fk_athlete FOREIGN KEY (athlete_id) REFERENCES athletes(id)")
    con.execute("ALTER TABLE activity_stream ADD CONSTRAINT fk_activity FOREIGN KEY (activity_id) REFERENCES activities(id)")


def close_con():
    con.commit()
    con.close()