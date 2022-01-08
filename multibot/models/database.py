import pymongo

mongo_client = pymongo.MongoClient("localhost", 27017)
db = mongo_client.flanabot
