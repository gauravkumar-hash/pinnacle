import enum

from pydantic import BaseModel, Field

class ExceptionCode(enum.Enum):
    INVALID_LOGIN = 'invalid_login'
    USER_NOT_SUPPORTED = 'user_not_supported'
    OTP_RESEND_LIMIT = 'otp_resend_limit'
    OTP_SENT_FAILED = 'otp_sent_failed'
    INVALID_OTP = 'invalid_otp'
    EXPIRED_OTP = 'expired_otp'
    INVALID_DOB = 'invalid_dob'
    SERVER_ERROR = 'server_error'
    PREPAYMENT_RATE_CHANGE = 'prepayment_rate_change'
    INVALID = 'invalid'

    # Yuu Integration
    YUU_API_ERROR = 'yuu_api_error'
    YUU_AUTH_FAILED = 'yuu_auth_failed'
    YUU_ALREADY_LINKED = 'yuu_already_linked'
    YUU_NOT_LINKED = 'yuu_not_linked'
    YUU_ID_IN_USE = 'yuu_id_in_use'
    INVALID_YUU_CODE = 'invalid_yuu_code'
    INVALID_YUU_TOKEN = 'invalid_yuu_token'
    YUU_LINK_FAILED = 'yuu_link_failed'
    YUU_UNLINK_FAILED = 'yuu_unlink_failed'
    INVALID_STATE = 'invalid_state'

class HTTPJSONException(Exception):
    def __init__(self, title: str, message: str, status_code: int = 400, code: ExceptionCode = ExceptionCode.INVALID):
        self.status_code = status_code
        self.code = code
        self.title = title
        self.message = message

class SelectOption(BaseModel):
    value: str
    label: str

class RespStatus(str, enum.Enum):
    success = "success"
    failed = "failed"

class ErrorResponse(BaseModel):
    message: str = Field(default="API call failed")

class SuccessResp(BaseModel):
    success: bool

class CreateResp(BaseModel):
    id: str

default_resp = {
    400: {"model": ErrorResponse, "description": "Exception triggered on backend server"},
}
