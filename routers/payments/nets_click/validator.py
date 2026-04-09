from datetime import datetime
from typing import Annotated
from pydantic import AfterValidator, BaseModel, ValidationInfo, field_validator
from enum import Enum

class TransactionMode(Enum):
    GET_MERCHANT_TOKEN = 'gmt'
    PURCHASE = 'purchase'
    REFUND = 'refund'

def check_payload(tx_mode: TransactionMode, tx_datetime: datetime, data: dict):

    def check_value(val, actual: str, info: ValidationInfo):
        assert val == actual, f"{info.field_name} should be {actual}"
        return val
    def check_length(val, length: int, info: ValidationInfo):
        assert len(val) == length, f"{info.field_name} should have length {length}"
        return val

    value_validator = lambda actual: AfterValidator(lambda val, info: check_value(val, actual, info))
    length_validator = lambda length: AfterValidator(lambda val, info: check_length(val, length, info))
    
    # 4.3. Transaction Message Body Class (Page 10, 18)
    class MessageHeader(BaseModel):
        product_indicator: Annotated[str, value_validator('02')]
        release_number: Annotated[str, value_validator('50')]
        status: Annotated[str, value_validator('000')]
        originator_code: Annotated[str, value_validator('7')]
        responder_code: Annotated[str, value_validator('0')]
        mti: Annotated[str, value_validator('0200')]
        nets_tag_1: Annotated[str, value_validator('B238048008E00000')]
        
    class MesssageBody(BaseModel):
        nets_tag_2: Annotated[str, value_validator('0000000000000004')]
        processing_code: str
        trxn_amount: Annotated[str, length_validator(12)]
        xmit_datetime: Annotated[str, length_validator(10)] # TODO: Check hour is 8 hours behind SGT. UTC time
        stan:   Annotated[str, length_validator(6)]

        
        
        @field_validator("processing_code")
        @classmethod
        def processing_code_val(cls, v: str) -> str:
            ref = { TransactionMode.GET_MERCHANT_TOKEN: '31', TransactionMode.PURCHASE: '00', TransactionMode.REFUND: '20' }
            if v[:2] != ref[tx_mode]: raise ValueError(f'processing_code should start with {ref[tx_mode]}')
            if v[2:] != '0000': raise ValueError('processing_code should end with 0000')
            return v
            
    class TransactionMessage(BaseModel):
        header: MessageHeader
        body: MesssageBody

    a = TransactionMessage.model_validate(data)
    return a

data = {
    "header": {
        "product_indicator": "02",
        "release_number": "50",
        "status": "000",
        "originator_code": "7",
        "responder_code": "0",
        "mti": "0200",
        "nets_tag_1": "B238048008E00000"
    },
    "body": {
        "nets_tag_2": "0000000000000004",
        "processing_code": "310000",
        "trxn_amount": "000000000001",
        "xmit_datetime": "MMDDhhmmss",
        "stan": "000001",
        
    }
}
tx_datetime = datetime.now() # Not used in validation now
a = check_payload(TransactionMode.GET_MERCHANT_TOKEN, tx_datetime, data)


# a.model_validate()