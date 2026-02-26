
import base64
import hashlib
import json
import requests
from routers.payments.nets_qr_config import KEY_ID, NETS_ENDPOINT, SECRET_KEY

def send_request(path: str, body: dict):
    print("= Request =")
    print(f"POST {path}")
    print(f"{json.dumps(body, indent=4)}")
    url = f'{NETS_ENDPOINT}{path}'
    hashed_body = json.dumps(body, separators=(',', ':')) + SECRET_KEY
    hashed_body = base64.b64encode(hashlib.sha256(hashed_body.encode('utf-8')).digest())
    signature = hashed_body.decode()

    headers={
            "KeyId": KEY_ID,
            "Sign": signature,
            "Content-Type": "application/json"
        }

    resp = requests.post(
        url=url,
        data=json.dumps(body, separators=(',', ':')),
        headers={
            "KeyId": KEY_ID,
            "Sign": signature,
            "Content-Type": "application/json"
        }
    )
    print("= Response =")
    json_resp = resp.json()
    if resp.status_code != 200:
        raise Exception(f"Error: {json_resp}")
    
    print(json.dumps(json_resp, indent=4))
    return json_resp

def base64_to_image(base64_string: str, output_file: str):
    # Decode the base64 string
    image_data = base64.b64decode(base64_string)
    
    # Write the decoded bytes to an image file
    with open(output_file, 'wb') as file:
        file.write(image_data)