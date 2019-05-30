"""Constants for the prawcore package."""
import os

__version__ = '0.10.1'

ACCESS_TOKEN_PATH = '/api/v1/access_token'
AUTHORIZATION_PATH = '/api/v1/authorize'
REVOKE_TOKEN_PATH = '/api/v1/revoke_token'
TIMEOUT = float(os.environ.get('prawcore_timeout', 16))
