from pymongo import MongoClient


def get_mongo_empresa(empresa):
    """
    Retorna la base MongoDB asociada a una empresa
    """
    client = MongoClient(empresa.mongo_uri)
    return client[empresa.mongo_db]
