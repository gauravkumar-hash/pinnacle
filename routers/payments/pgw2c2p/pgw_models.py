from pydantic import BaseModel

# Webhook PGW Payloads
#     tokenization_payload = {'accountNo': '55555555XXXX4444', 'customerToken': '08012508394183718333', 'customerTokenExpiry': None, 'loyaltyPoints': None, 'uniqueAccountReference': None, 'childMerchantID': None, 'processBy': 'MA', 'paymentID': 'ccpp_11181411', 'schemePaymentID': '', 'merchantID': '702702000003702', 'invoiceNo': '20250108093927', 'amount': 0.0, 'monthlyPayment': None, 'userDefined1': '', 'userDefined2': '', 'userDefined3': '', 'userDefined4': '', 'userDefined5': '', 'currencyCode': 'SGD', 'recurringUniqueID': '', 'tranRef': '11181411', 'referenceNo': '', 'approvalCode': None, 'eci': '02', 'transactionDateTime': '20250108093941', 'agentCode': 'UOBT', 'channelCode': 'MA', 'issuerCountry': 'BR', 'issuerBank': '', 'installmentMerchantAbsorbRate': None, 'cardType': 'CREDIT', 'paymentScheme': 'MA', 'displayProcessingAmount': False, 'respCode': '4200', 'respDesc': 'Tokenization Successful.'}
#     payment_payload = {'accountNo': '411111XXXXXX1111', 'customerToken': '15102407152611252518', 'customerTokenExpiry': None, 'merchantID': '702702000003702', 'invoiceNo': '20241118123914', 'amount': 2.0, 'currencyCode': 'SGD', 'transactionDateTime': '20241118123928', 'agentCode': 'UOBT', 'respCode': '0000', 'respDesc': 'Success'}

class PGWPaymentInquiryResponse(BaseModel):
    accountNo: str
    customerToken: str
    customerTokenExpiry: str | None = None
    merchantID: str
    invoiceNo: str
    transactionDateTime: str
    agentCode: str
    channelCode: str
    issuerCountry: str
    issuerBank: str
    cardType: str
    respCode: str
    respDesc: str


class PGWPaymentTokenResponse(BaseModel):
    webPaymentUrl: str    
    paymentToken: str
    respCode: str
    respDesc: str


class PGWWebhookResp(BaseModel):
    accountNo: str
    customerToken: str
    invoiceNo: str
    amount: float
    cardType: str
    currencyCode: str
    transactionDateTime: str
    respCode: str
