# Add two levels up to the sys.path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from datetime import datetime
from routers.payments.nets_qr_utils import base64_to_image, send_request
from routers.payments.nets_qr_config import MID, NETS_ENDPOINT, TID
from routers.payments.nets_qr_models import NetsOrderQueryReq, NetsOrderQueryResp, NetsResponseCode, NetsOrderReq, NetsOrderResp, NetsOrderReversalReq, NetsOrderReversalResp

def nets_order(stan: int, amount: float):
    resp = send_request(
        '/qr/dynamic/v1/order/request', 
        NetsOrderReq(**{"amount": amount, "stan": stan}).model_dump()
        )
    return NetsOrderResp(**resp)


def nets_order_query(stan: int, txn_identifier: str):
    resp = send_request(
        '/qr/dynamic/v1/transaction/query', 
        NetsOrderQueryReq(**{"stan": stan, "txn_identifier": txn_identifier}).model_dump()
        )
    return NetsOrderQueryResp(**resp)

def nets_order_reversal(stan: int, amount: float, txn_identifier: str):
    url = f'{NETS_ENDPOINT}'
    resp = send_request(
        '/qr/dynamic/v1/transaction/reversal', 
        NetsOrderReversalReq(**{"stan": stan, "amount": amount, "txn_identifier": txn_identifier}).model_dump()
        )
    return NetsOrderReversalResp(**resp)


# 1. Nets Order
stan = int(datetime.now().strftime('%H%M%S'))
resp = nets_order(stan,13.00)
base64_to_image(resp.qr_code, "nets_order_qr.png")
txn_identifier = resp.txn_identifier
print(f"MID: {MID}")
print(f"TID: {TID}")
print(f"Stan: {stan}")
print(f"Datetime: {datetime.now()}")
print(f"Txn: {txn_identifier}")
exit()

# stan = 155037
# amount = 13
# txn_identifier = 'NETSQPAY037066801####11137066800155037380a60ce010000130000010d7804139TEST EZI TECHNOLOeb81'

# 6) After 5 minutes, if no callback message, use Transaction Query once.
# - Transaction Query is for exception handling only. Not for main flow. 
# 0100 /0110
# 7) if Transaction Query returns ‘09’/68, perform reversal just in-case to avoid duplicated payment.
# 0400 /0410

# 2. Nets Query
resp = nets_order_query(stan, txn_identifier)
response_code = resp.response_code
response_code = NetsResponseCode(response_code)

# 3. Perform Nets Reversal if after 5 minutes, no callbacks and NETS Query returns '09' or '68'
if response_code in [NetsResponseCode.IN_PROGRESS, NetsResponseCode.TRANSACTION_TIMED_OUT]:
    resp = nets_order_reversal(stan, amount, txn_identifier)
    response_code = NetsResponseCode(resp.response_code)
    print(NetsResponseCode(response_code))
