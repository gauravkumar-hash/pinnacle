import base64
import enum

from pydantic import BaseModel
from .config import NETS_CLICK_API_KEY, NETS_CLICK_API_STATUS_DOMAIN_NAME, NETS_CLICK_DOMAIN_NAME, NETS_CLICK_RID, NETS_CLICK_SECRET, NETS_CLICK_TID
import requests
import json
import hashlib
from enum import Enum

from .utils import split_0102, split_0205
from datetime import datetime, timezone
import pytz
sgtz = pytz.timezone("Asia/Singapore") 

# APIs Purpose Description Message
# Health Check
# Get Merchant Token (GMT) # Page 4 of NETSClick Merchant Host Specification Interface Specification
# Purchase # Page 6 of NETSClick Merchant Host Specification Interface Specification

# TODO: Not the best approach to get the unique 6 digit number
def get_unique_ref_num():
    return datetime.now().strftime("%H%M%S")

def nof_health_status():
    response = requests.get(f'{NETS_CLICK_API_STATUS_DOMAIN_NAME}/nof/admin/v1/health', timeout=45)
    print(response.status_code)
    print(response.json())

class MessageType(Enum):
    REGISTER = "register"
    PURCHASE = "purchase"
    REVERSAL = "reversal"

def message_header(mtype: MessageType):
    # Page 9 - 4.1. Message Header Class
    headers = {
        "product_indicator": "02", # Fixed
        "release_number": "50",  # Fixed
        "status": "000",  # Fixed
        "originator_code": "7",  # Fixed
        "responder_code": "0", # Fixed
        # May need to change
        "mti": "0200",
        "nets_tag_1": "B238048008E00000"
    }

    if mtype == MessageType.REVERSAL:
        headers["mti"] = "0420"
        headers["nets_tag_1"] = "B23A04800AE00000"
    
    return headers

class MessageFunction(enum.Enum):
    GMT = { "nets_tag_2": "0000004000000004", "processing_code": "310000", "condition_code": "01" }
    Purchase = { "nets_tag_2": "0000000000000004", "processing_code": "000000", "condition_code": "00" }
    REVERSAL = { "nets_tag_2": "0000004000000004", "processing_code": "000000", "condition_code": "00"  }

# TODO: Reversal here
def message_body(
        txn_specific_data: list, 
        msg: MessageFunction, 
        ret_ref_num: str, 
        trxn_amount: str = '0', 
        now_gmt = datetime.now(timezone.utc), 
        now_sg = datetime.now(sgtz),
        reversal_dict: dict = {}
    ):
    nets_tag_2 = msg.value["nets_tag_2"]
    processing_code = msg.value["processing_code"]
    condition_code = msg.value["condition_code"]
    
    retailer_info = "PINNACLE SG"
    
    # Reversal - From Request
    # - processing_code
    # - trxn_amount
    # - xmit_datetime
    # - [x] trxn_time
    # - [x] trxn_date
    
    # Echo from purchase response?? What does it even mean
    # - settlement_date
    # - response_code
    
    trxn_time = now_sg.strftime("%H%M%S") # hhmmss
    trxn_date = now_sg.strftime("%m%d") # MMDD

    # Page 10 - 4.3. Transaction Message Body Class
    data = {
        "nets_tag_2": nets_tag_2,
        "processing_code": processing_code, # 31 - GMT, 00 - Purchase. 0000 = account type default 00
        "trxn_amount": trxn_amount.zfill(12), # In cents
        "xmit_datetime": now_gmt.strftime("%m%d%H%M%S"), # MMDDhhmmss, GMT+0
        "stan": ret_ref_num.zfill(6), # System trace audit number. Unique per message.
        "trxn_time": trxn_time,
        "trxn_date": trxn_date,
        "entry_mode": "100", # Fixed 
        "condition_code": condition_code, # 01 - GMT, 00 - Purchase
        "ret_ref_num": ret_ref_num.zfill(12), # (12) sequence number assigned by merchant to identify a transaction. First 2 digits always 00xxxxxxxxxx
        "terminal_id": NETS_CLICK_TID, # TID
        "retailer_id": NETS_CLICK_RID, # RID
        "retailer_info": retailer_info, # Retailer Name
        "txn_specific_data": txn_specific_data
    }
    
    if msg == MessageFunction.REVERSAL:
        data.update(reversal_dict)
        # mti = '0200'
        # data['original_data_elements'] =  f'{mti}{ret_ref_num}{trxn_date}{trxn_time}00' + (' ' * 14)
    
    return data

def post(url, body):
    # Compute payload signature
    payload = json.dumps(body) + NETS_CLICK_SECRET
    sha256_hash = hashlib.sha256()
    sha256_hash.update(payload.encode('utf-8'))
    signature = base64.b64encode(sha256_hash.digest()).decode('utf-8')

    # Page 48 - 6. Security
    headers = {
        'Content-Type': 'application/json',
        'keyId': NETS_CLICK_API_KEY,
        'sign': signature,
    }

    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=4)}")
    print(f"Payload: {payload}")
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=45)
        if response.status_code != 200:
            raise Exception(f"Error: {response.status_code}. {response.text}")
        return response.json()
    except requests.exceptions.Timeout:
        raise Exception("The request has timed out")
        # TODO: Retries to handle
        # In case of request timeout after 45 seconds,
        # - Merchant Host shall initiate reversal for purchase transaction. Purchase transaction shall only
        # be reversed with in the transaction life cycle (i.e, 45 seconds after original purchase timed out).
        # - Merchant Host shall initiate reversal for refund/merchandise return transaction.
        # - Merchant Host shall initiate reversal for refund/merchandise return transaction.
        #     Refund/merchandise return transaction shall only be reversed with in the transaction life cycle
        #     (i.e, 45 seconds after original refund/merchandise return timed out).
        # - In case of no response for reversal, merchant host shall retry 3 times. Even after the failure
        #     occurs, merchant host shall invoke operational recovery procedure.

def nof_gmt_reg(result_string: str, ret_ref_num: str):
    # Call Register/GMT API to register your card and obtain merchant token 
    # General Message Request Body Class
    # Original Transaction Information Sub-Class
    # Additional Merchant and Cardholder Information Sub-Class
    
    # hex_values = "30313039303331303030303339303235303031202020202020202030303030303134333234353330383238313032363535303030303030303030303030373935323735202020202020202020202020202020202020202020202020202020203032313530475332333244443143333842414337423145364639334339353934344142363444323533413042334239476f6f676c652073646b5f6770686f6e6536345f61726d36202020202020202020202020202020202020202020203230332e3131372e3133332e3130362020202020202020202020202020202020202020202020202020202020202020202020202020202020202020202020"
    # result_string = ''.join([chr(int(nof_hex_str[i:i+2], 16)) for i in range(0, len(nof_hex_str), 2)])
    
    d01, d02 = split_0102(result_string)

    body = {
        "header": message_header(MessageType.REGISTER),
        "body": message_body(
            ret_ref_num=ret_ref_num,
            msg=MessageFunction.GMT, 
            txn_specific_data=[
                # Page 17 - SDK data tbl 0102 returned during register/GMT
                #     "(01)(090)31000080000102000000000001092121580200000000000012345602150GSC8C985D03512E4E100CFAE24F2D57CF7FB38E395XIAOMI POCOPHONEF1 1.35996806103.8373553210.10.7.172 "
                # - Split data into sub id 01 and 02
                #     {
                #         "sub_id": "01",
                #         "sub_length": "090",
                #         "sub_data": "310000800001020000000000010921215802000000000000123456 "
                #     },
                #     {
                #         "sub_id": "02",
                #         "sub_length": "150",
                #         "sub_data":"GSC8C985D03512E4E100CFAE24F2D57CF7FB38E395XIAOMI POCOPHONE F11.35996806 103.8373553210.10.7.172"
                #     }                                           
                {
                    "sub_id": "01",
                    "sub_length": f'{len(d01)}'.zfill(3),
                    "sub_data": d01
                },
                {
                    "sub_id": "02",
                    "sub_length": f'{len(d02)}'.zfill(3),
                    "sub_data": d02
                }
            ]
        )  
    }

    # url = f'{NETS_CLICK_DOMAIN_NAME}/nof/v2/merchantservices/token/register'
    url = f'{NETS_CLICK_DOMAIN_NAME}/nof/tls/v2/merchantservices/token/register'
    resp = post(url, body)

    if resp:
        with open(f'http_gmt_reg_{datetime.now().strftime("%H%M%S")}.json', 'a') as fw:
            fw.write(f"POST {url}\n\n{json.dumps(body, indent=4)}\n\n{json.dumps(resp, indent=4)}\n\n==================\n")
        print(json.dumps(resp))
        print(f"Response Code: {resp['body']['response_code']}")
        print(f"txn_specific_data: {json.dumps(resp['body']['txn_specific_data'])}")
        with open('gmt_reg.json', 'w') as f:
            json.dump(resp['body']['txn_specific_data'], f)
        # print(f"Merchant Token: {resp['body']['txn_specific_data'][0]['merchant_token']}")


# {
#     "muid": "null",
#     "t0205": "02150PS232DD1C38BAC7B1E6F93C95944AB64D253A0B3B9Google sdk_gphone64_arm60.000000   0.000000   203.117.133.106                                               05100D7AFFECE34354256000124082810140000000000000000000000000000002CD54D12265BAC660000                    ",
#     "amt": "000000000200",
#     "muuid": "null",
#     "authCode": "000000"
# }

class GmtReg(BaseModel):
    rfu: str
    response_code: str
    first_8_muid_hash: str
    mtoken_expiry_date: str
    current_trxn_time: str
    mtoken_status: str
    sub_id: str
    current_trxn_rrn: str
    mtoken_index: str
    sub_length: str
    bank_fiid: str
    issuer_short_name: str
    merchant_token: str
    last_4_digits_fpan: str
    current_trxn_date: str

class NofPurchaseApi(BaseModel):
    muid: str
    t0205: str
    amt: str
    muuid: str
    authCode: str

class PurchaseRespHeader(BaseModel):
    release_number: str
    mti: str
    nets_tag_1: str
    originator_code: str
    responder_code: str
    product_indicator: str
    status: str

class TxnSpecificData(BaseModel):
    sub_length: str
    sub_id: str
    sub_data: str | None = None

class PurchaseRespBody(BaseModel):
    # approval_code: str
    trxn_time: str
    response_code: str
    settlement_date: str
    entry_mode: str
    retailer_id: str
    processing_code: str
    trxn_date: str
    xmit_datetime: str
    ret_ref_num: str
    nets_tag_2: str
    txn_specific_data: list[TxnSpecificData]
    trxn_amount: str
    stan: str
    terminal_id: str

class PurchaseResp(BaseModel):
    header: PurchaseRespHeader
    body: PurchaseRespBody

def nof_purchase(gmt_reg: GmtReg, nof_api: NofPurchaseApi, muid: str, trxn_ref_number: str, amt: str):
    
    def muid_hash(muid: str):
        sha256_hash = hashlib.sha256()
        sha256_hash.update(muid.encode('utf-8'))
        return sha256_hash.digest().hex().upper()
    
    now_gmt = datetime.now(timezone.utc)
    now_sg = datetime.now(sgtz)
    d02, d05 = split_0205(nof_api.t0205)

    url = f'{NETS_CLICK_DOMAIN_NAME}/nof/tls/v2/paymentservices/purchase'
    body = {
        "header": message_header(MessageType.PURCHASE),
        "body": message_body(
                msg=MessageFunction.Purchase,
                trxn_amount=amt,
                ret_ref_num=trxn_ref_number,
                now_gmt=now_gmt,
                now_sg=now_sg,
                txn_specific_data=[
                    {
                        "sub_id": "02",
                        "sub_length": f'{len(d02)}'.zfill(3),
                        # "sub_data": "GSC8C985D03512E4E100CFAE24F2D57CF7FB38E395XIAOMI POCOPHONE F11.35996806 103.8373553210.10.7.172"
                        "sub_data": d02
                    },
                    # Page 19 - 4.3.2.3. NETSClick/NOF Data
                    {
                        "sub_id": "03",
                        "sub_length": "200",
                        "merchant_token": gmt_reg.merchant_token, # Merchant Token from GMT
                        "mtoken_expiry_date": gmt_reg.mtoken_expiry_date,
                        "mtoken_index": gmt_reg.mtoken_index,
                        "hash_value_of_muid": muid_hash(muid),
                        "nof_reg_merchant_id": NETS_CLICK_RID.ljust(15),
                        "current_trxn_date": now_sg.strftime("%m%d"), # MMDD
                        "current_trxn_time": now_sg.strftime("%H%M%S"), # hhmmss
                        # Page 34: current_trxn_rrn under sub_id ‘03’ should match with body ret_ref_num (end trip/purchase preceded by CFA ret_ref_num).
                        "current_trxn_rrn": trxn_ref_number.zfill(12),
                        "cfa_auth_code": nof_api.authCode,
                        "rfu": "000000000000000000000000000000000000000"
                    },
                    # Page 19 - 4.3.2.4. Merchant Specific Information
                    {
                        "sub_id": "04",
                        "sub_length": "150",
                        # This field need to only contains alphanumeric and space. Left justified with trailing spaces. (20)
                        "merchant_name": "PINNACLE SG".ljust(20),
                        "merchant_discretionary_data": " " * 100, # Fixed 100 bytes
                        "trxn_ref_number": trxn_ref_number.zfill(16),
                        "rfu": " " * 8,
                        # 0000 is the default, no fee
                        "fee_info": "000000"
                    },
                    # Page 21 - 4.3.2.5. Transaction Cryptogram from SDK to NETS Host
                    {
                        "sub_id": "05", # Fixed
                        "sub_length": f'{len(d05)}'.zfill(3),
                        # Cryptogram from SDK (16), Returned by SDK (64), RFU spaces (20)
                        "sub_data": d05
                    }
                ]
        )
    }
    resp = post(url, body)
    if resp:
        with open(f'http_gmt_purchase_{datetime.now().strftime("%H%M%S")}.json', 'a') as fw:
            fw.write(f"POST {url}\n\n{json.dumps(body, indent=4)}\n\n{json.dumps(resp, indent=4)}\n\n==================\n")
        print()
        print(f"Response: {json.dumps(resp, indent=2)}")
        return PurchaseResp(**resp)

    return None
    # return body

def nof_purchase_reversal(purchase_req, purchase_resp):
    '''
    - Most of values are echoed from nof_purchase request fields except: mti, nets_tag_1, nets_tag_2 and stan.
    - settlement_date & response_code are echoed from response; or new value in case of reversal for no response.
    - original_data_elements (contains request data).
    '''

    now_gmt = datetime.strptime(purchase_req['body']['xmit_datetime'], "%m%d%H%M%S")
    now_sg = datetime.strptime(purchase_req['body']['trxn_date'] + purchase_req['body']['trxn_time'], "%m%d%H%M%S")
    
    # Page 13: 4.3.1.3. Transaction Reversal Messages
    url = f'{NETS_CLICK_DOMAIN_NAME}/nof/tls/v2/paymentservices/purchase/reversal'
    
    resp_body = purchase_resp['body'] if purchase_resp else {}
    body = {
        "header": message_header(MessageType.REVERSAL),
        "body": message_body(
                msg=MessageFunction.REVERSAL,
                trxn_amount=purchase_req['body']['trxn_amount'].lstrip('0'),
                ret_ref_num=purchase_req['body']['ret_ref_num'].lstrip('0'),
                now_gmt=now_gmt,
                now_sg=now_sg,
                txn_specific_data=purchase_req['body']['txn_specific_data'],
                reversal_dict={
                    'settlement_date': resp_body.get('settlement_date', datetime.now().strftime("%m%d")),
                    'response_code': resp_body.get('response_code', '00'),
                    'original_data_elements': "".join(
                        [
                            purchase_req['header']['mti'], 
                            purchase_req['body']['ret_ref_num'].lstrip('0'), 
                            purchase_req['body']['trxn_date'], 
                            purchase_req['body']['trxn_time'],
                            '00' + (' ' * 14)
                        ]
                    )
                }
        )
    }

    # print(json.dumps(body, indent=4))
    # exit()

    resp = post(url, body)
    if resp:
        with open(f'http_reversal_{datetime.now().strftime("%H%M%S")}.json', 'a') as fw:
            fw.write(f"POST {url}\n\n{json.dumps(body, indent=4)}\n\n{json.dumps(resp, indent=4)}\n\n==================\n")
        print()
        print(f"Response: {json.dumps(resp, indent=2)}")

## Register
    
# nof_hex_str = '30313039303331303030303339303235303031202020202020202030303030303134333235343630383330313630383336303030303030303030303030343638323239202020202020202020202020202020202020202020202020202020203032313530475344423432413033394332303945323632303436313739324430343138353237453430423439414533476f6f676c652073646b5f6770686f6e6536345f61726d36202020202020202020202020202020202020202020203231302e31302e37362e35382020202020202020202020202020202020202020202020202020202020202020202020202020202020202020202020202020'
# ret_ref_num = '150'
# nof_gmt_reg(nof_hex_str, ret_ref_num=ret_ref_num)
# exit()

## Purchase
# From nof_gmt_reg
# muid = "88281231234"
# gmt_reg = {"rfu": "000000000000000", "response_code": "00", "first_8_muid_hash": "EDE14A92", "mtoken_expiry_date": "2712", "current_trxn_time": "160849", "mtoken_status": "0", "sub_id": "51", "current_trxn_rrn": "000000000150", "mtoken_index": "00", "sub_length": "120", "bank_fiid": "NCLC", "issuer_short_name": "TEST      ", "merchant_token": "EBA14C67FD79CECBAF937D51FAA330B257D721519140A800", "last_4_digits_fpan": "5511", "current_trxn_date": "0830"}

# # From Android SDK when Purchase is issued
# nof_api = {"muid":"null","t0205":"02150PSDB42A039C209E2620461792D0418527E40B49AE3Google sdk_gphone64_arm60.000000   0.000000   210.10.76.58                                                  05100010E392B901102BF00022408301608350000000000000000000000000000E458418573A2431D0000                    ","amt":"000000000200","muuid":"null", "authCode" : "000000"}


# trxn_ref_number = "112"
# amt = '200'

# purchase_body = nof_purchase(gmt_reg, nof_api, muid, trxn_ref_number, amt)
# exit()



## Reversal
# purchase_req = {
#     "header": {
#         "product_indicator": "02",
#         "release_number": "50",
#         "status": "000",
#         "originator_code": "7",
#         "responder_code": "0",
#         "mti": "0200",
#         "nets_tag_1": "B238048008E00000"
#     },
#     "body": {
#         "nets_tag_2": "0000004000000004",
#         "processing_code": "000000",
#         "trxn_amount": "000000000200",
#         "xmit_datetime": "0830041316",
#         "stan": "000151",
#         "trxn_time": "121316",
#         "trxn_date": "0830",
#         "entry_mode": "100",
#         "condition_code": "00",
#         "ret_ref_num": "000000000151",
#         "terminal_id": "36198901",
#         "retailer_id": "11136198900",
#         "retailer_info": "PINNACLE SG",
#         "txn_specific_data": [
#             {
#                 "sub_id": "02",
#                 "sub_length": "150",
#                 "sub_data": "PS754AAF42487480DEEC1E2358FB27E78408E0AC30Google sdk_gphone64_arm60.000000   0.000000   0.0.0.0                                                       "
#             },
#             {
#                 "sub_id": "03",
#                 "sub_length": "200",
#                 "merchant_token": "C8F5A88C489ADA35DAF8DB5E8EA9E9F56DF55DED5F06D800",
#                 "mtoken_expiry_date": "2712",
#                 "mtoken_index": "00",
#                 "hash_value_of_muid": "ede14a9295343bca871f98ad378ea249d7299bb3aeb95d671229ac36d8a24d66",
#                 "nof_reg_merchant_id": "11136198900    ",
#                 "current_trxn_date": "0830",
#                 "current_trxn_time": "121316",
#                 "current_trxn_rrn": "000000000151",
#                 "cfa_auth_code": "000000",
#                 "rfu": "000000000000000000000000000000000000000"
#             },
#             {
#                 "sub_id": "04",
#                 "sub_length": "150",
#                 "merchant_name": "PINNACLE SG         ",
#                 "merchant_discretionary_data": "                                                                                                    ",
#                 "trxn_ref_number": "0000000000000151",
#                 "rfu": "        ",
#                 "fee_info": "000000"
#             },
#             {
#                 "sub_id": "05",
#                 "sub_length": "100",
#                 "sub_data": "5720AD311984AA60000124083012102900000000000000000000000000001072239D9343BE0F0000                    "
#             }
#         ],
#         "original_data_elements": "0200151083012131600              "
#     }
# }
# purchase_resp = {
#     "header": {
#         "release_number": "50",
#         "mti": "0210",
#         "nets_tag_1": "B23A04000EC00000",
#         "originator_code": "7",
#         "responder_code": "5",
#         "product_indicator": "02",
#         "status": "000"
#     },
#     "body": {
#         "approval_code": "217098",
#         "trxn_time": "121316",
#         "response_code": "00",
#         "settlement_date": "0830",
#         "entry_mode": "102",
#         "retailer_id": "11136198900",
#         "processing_code": "000000",
#         "trxn_date": "0830",
#         "xmit_datetime": "0830041317",
#         "ret_ref_num": "000000000151",
#         "nets_tag_2": "0000000000000004",
#         "txn_specific_data": [
#             {
#                 "rfu": "                                          ",
#                 "sub_length": "070",
#                 "bank_fiid": "NCLC",
#                 "sub_id": "52",
#                 "mtoken_status": "3",
#                 "issuer_auth_flag": "Y",
#                 "issuer_name": "TEST                  "
#             }
#         ],
#         "trxn_amount": "000000000200",
#         "stan": "000151",
#         "terminal_id": "36198901"
#     }
# }

if __name__ == '__main__':
    with open('refund.json', 'r') as f:
        data = json.load(f) 
        purchase_req = data['request']
        purchase_resp = data['response']
    nof_purchase_reversal(purchase_req, purchase_resp)