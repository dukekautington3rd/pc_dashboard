import os
import psycopg2
from io import StringIO
from prismacloud.api import pc_api
from datetime import timedelta
from datetime import datetime
import pandas as pd
import sys
from direct_redis import DirectRedis


pc_settings = {
    "url":      os.environ['PC_URL'],
    "identity": os.environ['PC_IDENTITY'],
    "secret":   os.environ['PC_SECRET'],
}

db_settings = {
    "host":     os.environ['DB_SERVER'],
    "database": "prisma",
    "user":     os.environ['DB_USER'],
    "password": os.environ['DB_PASSWORD'],
}

pc_api.configure(pc_settings)
verbose = True
retention = 30

#
# Helpers
#


def db_connect(params_dict):
    conn = None
    try:
        conn = psycopg2.connect(**params_dict)
    except (Exception, psycopg2.DatabaseError) as msg:
        print("Error in db_connect function:")
        exit(msg)
    return conn


def db_write(conn, sql):
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
    except (Exception, psycopg2.DatabaseError) as msg:
        conn.rollback()
        cursor.close()
        print("Error in db_write function:")
        exit(msg)
    conn.commit()
    cursor.close()
    return True


def db_read(conn, sql):
    list = []
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
    except (Exception, psycopg2.DatabaseError) as msg:
        print("Error in db_read function:")
        exit(msg)
    list = cursor.fetchall()
    cursor.close()
    return (list)


def df_to_db(conn, df, table):
    buffer = StringIO()
    df.to_csv(buffer, header=False, index=False)
    buffer.seek(0)
    cursor = conn.cursor()
    cursor.execute("SET search_path TO reporting")
    try:
        cursor.copy_from(buffer, table, sep=",")
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as msg:
        conn.rollback()
        cursor.close()
        print("Error in df_to_db function:")
        sys.exit(msg)
    cursor.close()
    return True


#
# Main
#


def main():
    # Initate DB connection
    conn = db_connect(db_settings)

    # Create Defender DB table, if it doesn't exist
    sql = '''
    CREATE TABLE IF NOT EXISTS reporting.defenders (
        hostname varchar (128) NOT NULL,
        version varchar (9) NOT NULL,
        type varchar (24) NOT NULL,
        category varchar (24) NOT NULL,
        date_added DATE NOT NULL
    );
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA reporting TO prisma;
    '''
    db_write(conn, sql)

    # Build dataframe from defenders api endpoint
    df = pd.DataFrame(pc_api.defenders_list_read("connected=true"))

    # Obtain current time and add to column in dataframe
    current_time = datetime.now()
    date_column = [current_time.strftime(
        "%Y-%m-%d")] * len(df.index)
    date_column = ['2022-12-17'] * len(df.index)
    df['date_added'] = date_column

    # Purge old records from DB
    sql = ("DELETE FROM reporting.defenders * WHERE date_added::date < date \'" +
           ((current_time - timedelta(days=retention)).strftime('%Y-%m-%d')) + "\';")
    db_write(conn, sql)

    # Copy df columns to Write df_defenders and write to defenders table
    df_defenders = df[['hostname', 'version',
                       'type', 'category', 'date_added']].copy()
    df_to_db(conn, df_defenders, "defenders")

    # Pull all historical defender stats, store as dataframe
    sql = ("SELECT category, date_added, version FROM reporting.defenders")
    data_list = db_read(conn, sql)
    df_defenders = pd.DataFrame(
        data_list, columns=['category', 'date_added', 'version']).groupby(
            ['date_added', 'category', 'version'])['category'].count().reset_index(name='total')

    # Push defender dataframe to redis
    r = DirectRedis(host='localhost', port=6379)
    r.set('df_defenders', df_defenders)

    conn.close()


if __name__ == "__main__":
    main()
