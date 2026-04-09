import httpx

# -------------------------
# CONFIGURATION
# -------------------------
BACKEND_URL = "https://pinnacle-ob2m.onrender.com"
EXPO_PUBLIC_API_KEY = "1856bc1b3dfb5fdc409f3e8802370dfc3a00f0beafd6b4cc2edb0e48577a5315"       # hardcode or from .env
FIREBASE_WEB_API_KEY = "AIzaSyDv3JB1AgnaRlNVfWDYYHozvo9ChZ4OtMk"     # hardcode or from .env

# Patient credentials
ID_TYPE = "PINK IC"
NRIC = "T1231231D"
MOBILE_CODE = "+65"
MOBILE_NUMBER = "89998745"
OTP = "555555"

HEADERS = {
    "Authorization": f"Bearer {EXPO_PUBLIC_API_KEY}",
    "Content-Type": "application/json"
}

# -------------------------
# STEP 1: Login → get session_id
# -------------------------
def login_backend():
    body = {
        "id_type": ID_TYPE,
        "id_number": NRIC,
        "mobile_code": MOBILE_CODE,
        "mobile_number": MOBILE_NUMBER
    }
    resp = httpx.post(f"{BACKEND_URL}/api/auth/login", json=body, headers=HEADERS, timeout=30.0)
    resp.raise_for_status()
    return resp.json()["session_id"]

# -------------------------
# STEP 2: Verify OTP → get Firebase custom token
# -------------------------
def verify_otp(session_id):
    body = {"session_id": session_id, "otp": OTP}
    resp = httpx.post(f"{BACKEND_URL}/api/auth/verify_otp", json=body, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["token"]

# -------------------------
# STEP 3: Firebase custom token → JWT idToken
# -------------------------
def firebase_to_jwt(custom_token):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_WEB_API_KEY}"
    body = {"token": custom_token, "returnSecureToken": True}
    resp = httpx.post(url, json=body)
    resp.raise_for_status()
    return resp.json()["idToken"]

# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    session_id = login_backend()
    print("✅ Session ID:", session_id)

    custom_token = verify_otp(session_id)
    print("✅ Firebase Custom Token:", custom_token)

    jwt_token = firebase_to_jwt(custom_token)
    print("\n✅ JWT Token (Use in Authorization header):\n")
    print(jwt_token)
