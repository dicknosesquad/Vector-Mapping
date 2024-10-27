import os

class Config:
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/regional_datacenter_db')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    AZURE_CREDENTIAL_KEY = os.getenv('AZURE_KEY')
    AZURE_ENDPOINT = os.getenv('AZURE_ENDPOINT')
