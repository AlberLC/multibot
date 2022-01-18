import os

import pymongo

mongo_client = pymongo.MongoClient("localhost", 27017, username=os.environ.get('MONGO_USER'), password=os.environ.get('MONGO_PASSWORD'))

db = mongo_client.flanabot
