from pydantic import BaseModel
import enum

from models.model_enums import PhoneCountryCode, SGiMedICType

class RedisAuthState(enum.Enum):
    VERIFY_OTP = 'verify_otp'
    VERIFY_DOB = 'verify_dob'
    REGISTER = 'register'
    LOGGED_IN = 'logged_in'
    CHANGE_MOBILE = 'change_mobile'

class RedisLoginState(BaseModel):
    id_type: SGiMedICType
    id_number: str
    mobile_code: PhoneCountryCode
    mobile_number: str
    otp_code: str
    otp_sent_at: float
    otp_expires_at: float
    state: RedisAuthState = RedisAuthState.VERIFY_OTP
