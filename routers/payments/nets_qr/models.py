from datetime import datetime
from enum import Enum
from typing import Annotated, Self
from pydantic import BaseModel, BeforeValidator, Field, model_validator

from .config import CALLBACK_URL, INSTITUTION_CODE, MID, TID

class NetsOrderReq(BaseModel):
    curr_time: Annotated[datetime, Field(datetime.now(), exclude=True)] 
    mti: str = "0200" # Fixed
    process_code: str = "990000" # Fixed
    # amount: str = Field(..., min_length=12, max_length=12)
    amount: Annotated[str, BeforeValidator(lambda x: f'{int(x * 100):012d}')]
    stan: Annotated[str, BeforeValidator(lambda x: f'{x:06d}')]
    transaction_date: str = Field('0000', min_length=4, max_length=4)
    transaction_time: str = Field('000000', min_length=6, max_length=6)
    entry_mode: str = "000" # Fixed
    condition_code: str = "85" # Online QR
    institution_code: str = INSTITUTION_CODE
    host_tid: str = TID
    host_mid: str = MID
    npx_data: dict = {}
    communication_data: list = []
    getQRCode: str = "Y"

    # @model_validator(mode="before")
    # def validate_time(self) -> Self:
    #     self['transaction_time'] = self['curr_time'].strftime('%H%M%S')
    #     self['transaction_date'] = self['curr_time'].strftime('%m%d')
    #     return self
    
    @model_validator(mode="after")
    def validate_time_2(self) -> Self:
        self.transaction_time = self.curr_time.strftime('%H%M%S')
        self.transaction_date = self.curr_time.strftime('%m%d')
        self.npx_data = {
                "E103": TID,
                "E201": self.amount,
                "E202": "SGD"
            }
        self.communication_data = [
            {
                "type": "https_proxy",
                "category": "URL",
                "destination": CALLBACK_URL,
                "addon": {
                    "external_API_keyID": "8bc63cde-2647-4a78-ac75-d5f534b56047"
                }
            },
        ]

        return self

class NetsOrderResp(BaseModel):
    mti: str
    txn_identifier: str
    process_code: str
    amount: str
    stan: str
    transaction_time: str
    transaction_date: str
    entry_mode: str
    condition_code: str
    institution_code: str
    response_code: str
    host_tid: str
    qr_code: str


class NetsOrderQueryReq(BaseModel):
    curr_time: Annotated[datetime, Field(datetime.now(), exclude=True)]
    mti: str = "0100" # Fixed
    process_code: str = "330000" # Fixed
    stan: Annotated[str, BeforeValidator(lambda x: f'{x:06d}')]
    transaction_date: str = Field('0000', min_length=4, max_length=4)
    transaction_time: str = Field('000000', min_length=6, max_length=6)
    entry_mode: str = "000" # Fixed
    condition_code: str = "85" # Online QR
    institution_code: str = INSTITUTION_CODE
    host_tid: str = TID
    host_mid: str = MID
    txn_identifier: str
    npx_data: dict = {}

    @model_validator(mode="after")
    def validate_time_2(self) -> Self:
        # TODO: Does this need to align with transaction time?
        self.transaction_time = self.curr_time.strftime('%H%M%S')
        self.transaction_date = self.curr_time.strftime('%m%d')
        self.npx_data = {
                "E103": TID
            }

        return self

class NetsOrderQueryResp(BaseModel):
    mti: str
    txn_identifier: str
    process_code: str
    stan: str
    transaction_time: str
    transaction_date: str
    response_code: str
    host_tid: str

class NetsResponseCode(str, Enum):
    # Success
    SUCCESS = "00"
    IN_PROGRESS = "09"
    # Failures
    NO_MATCHING_TRANSACTION = "12"
    SYSTEM_MAINTENANCE = "01"
    INVALID_EXPIRY_OR_INSTITUTION = "03"
    DO_NOT_HONOR = "05"
    ERROR = "06"
    INVALID_AMOUNT = "13"
    SOF_NOT_FOUND = "15"
    MESSAGE_FORMAT_ERROR = "30"
    INCORRECT_PIN = "55"
    SOF_NOT_ENABLED = "58"
    SCHEME_PAYLOAD_NOT_FOUND = "58"
    INVALID_SIGNATURE = "63"
    TRANSACTION_TIMED_OUT = "68"
    TRANSACTION_NOT_FOUND = "76"
    NO_ROUTE_FOUND_TO_BANK = "92"
    ORDER_ALREADY_EXISTS = "94"

class NetsOrderReversalReq(BaseModel):
    curr_time: Annotated[datetime, Field(datetime.now(), exclude=True)]
    mti: str = "0400" # Fixed
    process_code: str = "990000" # Fixed
    amount: Annotated[str, BeforeValidator(lambda x: f'{int(x * 100):012d}')]
    transmission_time: str = Field('0000000000', min_length=10, max_length=10)
    stan: Annotated[str, BeforeValidator(lambda x: f'{x:06d}')]
    transaction_date: str = Field('0000', min_length=4, max_length=4)
    transaction_time: str = Field('000000', min_length=6, max_length=6)
    entry_mode: str = "000" # Fixed
    condition_code: str = "85" # Online QR
    institution_code: str = INSTITUTION_CODE
    host_tid: str = TID
    host_mid: str = MID
    txn_identifier: str
    npx_data: dict = {}

    @model_validator(mode="after")
    def validate_time_2(self) -> Self:
        # TODO: Does this need to align with transaction time?
        self.transmission_time = self.curr_time.strftime('%m%d%H%M%S')
        self.transaction_time = self.curr_time.strftime('%H%M%S')
        self.transaction_date = self.curr_time.strftime('%m%d')
        self.npx_data = {
                "E103": TID
            }

        return self

class NetsOrderReversalResp(BaseModel):
    mti: str
    txn_identifier: str
    process_code: str
    amount: str
    stan: str
    transaction_time: str
    transaction_date: str
    entry_mode: str
    condition_code: str
    institution_code: str
    response_code: str
    host_tid: str
    host_mid: str
    transmission_time: str

class NetsWebhookPayload(BaseModel):
    mti: str
    txn_identifier: str
    process_code: str
    amount: str
    stan: str
    transaction_time: str
    transaction_date: str
    entry_mode: str
    condition_code: str
    institution_code: str
    response_code: str
    approval_code: str
    host_tid: str
    npx_data: dict
