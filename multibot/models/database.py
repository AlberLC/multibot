import os

import pymongo

mongo_client = pymongo.MongoClient(
    host=os.environ.get('MONGO_HOST'),
    port=int(port) if (port := os.environ.get('MONGO_PORT')) else None,
    username=os.environ.get('MONGO_USER'),
    password=os.environ.get('MONGO_PASSWORD'),
    tz_aware=True
)

db = getattr(mongo_client, os.environ['DATABASE_NAME'])
