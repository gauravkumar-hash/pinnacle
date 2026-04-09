from enum import Enum
import logging
import uuid
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from pydantic import BaseModel

from config import YUU_CLIENT_ID, YUU_CLIENT_SECRET, YUU_API_URL, YUU_REDIRECT_URI
from utils.integrations.yuu_crypto import decrypt_id_token, load_keys

logger = logging.getLogger(__name__)


class GetTokenResp(BaseModel):
    # {
    #     "https://tomoloyalty.io/application_metadata": {
    #         "brand_code": "sg-pfc"
    #     },
    #     "iss": "https://auth.uat.yuu.sg/",
    #     "sub": "FNoNgXEoXtodpf2Puts42elcfo1pjAhH@clients",
    #     "aud": "https://partner-api-uat/",
    #     "iat": 1747282330,
    #     "exp": 1749874330,
    #     "gty": "client-credentials",
    #     "azp": "FNoNgXEoXtodpf2Puts42elcfo1pjAhH"
    # }
    accessToken: str
    expiresIn: int
    tokenType: str

class PayloadType(Enum):
    HEADER = 'header'
    JSON = 'json'
    FORM = 'form'

class YuuClient:
    def __init__(self):
        self.url = YUU_API_URL
        self._access_token = None
        self._token_expiry = None
        self.yuu_public_key, self.pinnacle_private_key = load_keys()

    def _should_refresh_token(self) -> bool:
        """Check if token should be refreshed (1 day before expiry)"""
        if not self._token_expiry:
            return True
        
        one_day_before = self._token_expiry - timedelta(days=1)
        return datetime.now() >= one_day_before

    def get_token(self):
        '''
        Get an access token for the Yuu API
        NOTE: Each client id have a limit 350 times within a day
        The authentication token has an expiry of 30 days.
        '''
        return self.get_access_token()
    
    def get_access_token(self) -> str:
        """Get access token, refresh if needed (1 day before expiry)"""
        if self._access_token and not self._should_refresh_token():
            return self._access_token
        
        # Refresh token
        new_token, expiry = self._refresh_access_token()
        self._access_token = new_token
        self._token_expiry = expiry
        
        logger.info(f"Yuu access token refreshed, expires at: {self._token_expiry}")
        return self._access_token
    
    def _refresh_access_token(self) -> tuple[str, datetime]:
        """Get new access token from Yuu using client credentials flow"""
        # OAuth2 client credentials grant
        request_id = str(uuid.uuid4())
        headers = {
            "Content-Type": 'application/json',
            "RequestID": request_id,
            "Accept": "application/json"
        }
        url = f"{self.url}/oauth/token"
        payload = {
            'clientId': YUU_CLIENT_ID,
            'clientSecret': YUU_CLIENT_SECRET,
        }
        
        response = requests.post(url, json=payload, headers=headers, allow_redirects=False)    
        if response.status_code == 200:
            data = response.json()
            access_token = data['accessToken']
            
            # Decode JWT to get expiry time from 'exp' claim
            payload_data = jwt.decode(access_token, options={"verify_signature": False})
            
            # Extract expiry timestamp
            exp_timestamp = payload_data.get('exp')
            if not exp_timestamp:
                raise Exception("No 'exp' field in JWT token")
            
            expiry_datetime = datetime.fromtimestamp(exp_timestamp)
            return access_token, expiry_datetime
        else:
            raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")
    

    def post(self, path, payload, payload_type: PayloadType):
        url = f"{self.url}{path}"
        request_id = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/x-www-form-urlencoded" if payload_type == PayloadType.FORM else "application/json",
            "RequestID": request_id,
            "Accept": "application/json"
        }
        logging.debug(f"Request ID: {request_id}, Payload: {payload}")
        if payload_type == PayloadType.FORM:
            response = requests.post(url, data=payload, headers=headers, allow_redirects=False)
        elif payload_type == PayloadType.HEADER:
            headers.update(payload)
            response = requests.post(url, headers=headers, allow_redirects=False)
        elif payload_type == PayloadType.JSON:
            response = requests.post(url, json=payload, headers=headers, allow_redirects=False)
        else:
            raise Exception(f"Invalid payload type: {payload_type}")
        # logging.debug(f"Response: {response.json()}")
        return response
        # return response.json()

    def get(self, path, payload=None):
        url = f"{self.url}{path}"
        request_id = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {self.get_token()}",
            "RequestID": request_id,
            "Accept": "application/json",
            "Host": "partner-api.uat.tomoloyalty.io"
        }
        logging.debug(f"Request ID: {request_id}, Payload: {payload}")
        if payload:
            headers.update(payload)
        response = requests.get(url, headers=headers, allow_redirects=False)
        return response
        # logging.debug(f"Response: {response.json()}")
        # return response.json()
    
    def get_preauth_url(self, state: str) -> str:
        """Get Yuu OAuth URL for account linking"""
        resp = self.get(
            f'/account-linking/webpage?redirect_uri={YUU_REDIRECT_URI}&state={state}'
        )
        if resp.status_code == 302:
            location = resp.headers.get('Location', '')
            if not location:
                raise Exception(f"Invalid Response: {resp.status_code}")
            return location
        raise Exception(f"Invalid Response: {resp.status_code}")
    
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange OAuth code for tokens"""
        resp = self.post('/account-linking/token', {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': YUU_REDIRECT_URI
        }, PayloadType.FORM)
        
        if resp.status_code == 200:
            return resp.json()
        raise Exception(f"Invalid Response: {resp.status_code}")
    
    def decrypt_and_link(self, id_token: str) -> Dict[str, str]:
        """Decrypt ID token and extract user details"""
        decrypted = decrypt_id_token(id_token, self.yuu_public_key, self.pinnacle_private_key)
        return {
            'tomo_id': decrypted['tomo_id'],
            'user_identifier': decrypted['user_identifier']
        }
    
    def link_account(self, tomo_id: str, user_identifier: str) -> bool:
        """Link Yuu account with Pinnacle"""
        payload_type = PayloadType.HEADER
        headers = {
            'TomoId': tomo_id,
            'UserIdentifier': user_identifier
        }
        resp = self.post('/account-linking/link', headers, payload_type)
        if resp.status_code != 204:
            raise Exception(f"Invalid Response: {resp.status_code}")
        return resp.status_code == 204
    
    def unlink_account(self, tomo_id: str, user_identifier: str) -> bool:
        """Unlink Yuu account from Pinnacle"""
        payload_type = PayloadType.HEADER
        headers = {
            'TomoId': tomo_id,
            'UserIdentifier': user_identifier
        }
        resp = self.post('/account-linking/unlink', headers, payload_type)
        if resp.status_code != 204:
            raise Exception(f"Invalid Response: {resp.status_code}")
        return resp.status_code == 204
    
    def verify_membership(self, tomo_id: str, user_identifier: str) -> Optional[Dict[str, Any]]:
        """Verify active Yuu membership status"""
        headers = {
            'TomoId': tomo_id,
            'UserIdentifier': user_identifier
        }
        resp = self.get('/in-app/consumers/verification', headers)
        if resp.status_code != 200:
            raise Exception(f"Invalid Response: {resp.status_code}")
        return resp.json()

    def send_transaction_log(self, payload: dict):
        """Send transaction log to Yuu"""
        resp = self.post('/transactions', payload, PayloadType.JSON)
        if resp.status_code != 204:
            raise Exception(f"Invalid Response: {resp.status_code}, {resp.json()}")
        return resp.status_code == 204

# Create singleton instance
yuu_client = YuuClient()