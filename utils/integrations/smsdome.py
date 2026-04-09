
# https://www.smsdome.com/api/http/sendsms.aspx?appid=5818&appsecret=af24c9c8-ba6e-4e6e-905d-103f196a4075&receivers=6581611147&content=This%20is%20a%20test%20message.&responseformat=JSON

# {"result":{"status":"OK","error":"","testmode":false},"content":{"value":"This is a test message.","encoding":"GSM 7 bit","chars":23,"parts":1},"receivers":[{"id":"1","value":"6581611147","credits":1,"messageid":"327987049"}],"credit":{"balance":20,"required":1}}

import requests
from config import SMSDOME_URL, SMSDOME_APPID, SMSDOME_APPSECRET

class SMSDomeException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

def send_sms(phone: str, text: str):
    response = requests.get(SMSDOME_URL, params={
        "appid": SMSDOME_APPID,
        "appsecret": SMSDOME_APPSECRET,
        "receivers": phone,
        "content": text,
        "responseformat": "JSON"
    })

    if response.status_code != 200:
        raise SMSDomeException(f"Failed to send OTP. {response.status_code}: {response.text}")
    
    data = response.json()
    if data["result"]["status"] != "OK":
        raise SMSDomeException(f"Failed to send OTP. {data['result']['error']}")
    
    return True

if __name__ == "__main__":
    send_sms("+6581611234", "This is a test message.")