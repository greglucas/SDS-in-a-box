import os

import boto3
import psycopg2


def handler(event, context):
    """Lambda handler."""
    print("EVENT", event)

    HOST = os.environ["HOST"]  # "postgresmydb.123456789012.us-east-1.rds.amazonaws.com"
    PORT = os.environ["PORT"]  # 5432
    USER = "GregLambdaRole"  # os.environ["USER"] # "jane_doe"
    REGION = "us-east-1"  # os.environ["REGION"] # "us-west-2"
    DBNAME = os.environ["DBNAME"]  # "GregTestDB"

    # gets the credentials from .aws/credentials
    session = boto3.Session()  # profile_name='RDSCreds')
    client = session.client("rds")

    token = client.generate_db_auth_token(
        DBHostname=HOST, Port=PORT, DBUsername=USER, Region=REGION
    )

    try:
        conn = psycopg2.connect(
            host=HOST,
            port=PORT,
            database=DBNAME,
            user=USER,
            password=token,
            sslmode="require",
            sslrootcert="rds-combined-ca-bundle.pem",
        )
        print("CONNECTED")
        cur = conn.cursor()
        cur.execute("""SELECT now()""")
        query_results = cur.fetchall()
        print(query_results)
    except Exception as e:
        print(f"Database connection failed due to {e}")
        raise e
