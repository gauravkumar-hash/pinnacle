from fastapi import HTTPException
import httpx
import jwt
from config import PAYMENT_2C2P_ENDPOINT, PAYMENT_2C2P_MERCHANT_SHA_KEY

# Helper functions
def call_2c2p_api(endpoint: str, payload: dict):
    token = jwt_encode_payload(payload)
    jwt_payload = {'payload': token}

    response = httpx.post(
        f'{PAYMENT_2C2P_ENDPOINT}{endpoint}',
        headers={'Content-Type': 'application/json'},
        json=jwt_payload
    )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    
    return response.json()

def jwt_decode_payload(payload: str):
    return jwt.decode(payload, PAYMENT_2C2P_MERCHANT_SHA_KEY, algorithms=['HS256'])


def jwt_encode_payload(payload: dict):
    result =  jwt.encode(payload, PAYMENT_2C2P_MERCHANT_SHA_KEY, algorithm='HS256')
    return result
