import requests
import urllib.parse

# --- PASTE YOUR KEYS HERE ---
CLIENT_ID = "77xglo1er8egl1"
CLIENT_SECRET = "WPL_AP1.qw2F0pe2mviztN8r.cVBC7g=="
# ----------------------------

REDIRECT_URI = "https://www.google.com" # We use a dummy URL to catch the code

def get_access_token():
    # 1. Build the Authorization URL
    auth_url = "https://www.linkedin.com/oauth/v2/authorization"
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile w_member_social email", # Standard permissions
    }
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"

    print("\n-------------------------------------------------------------")
    print("1. CLICK this URL to authorize your App:")
    print(url)
    print("-------------------------------------------------------------")
    print("2. Login and click 'Allow'.")
    print("3. You will be redirected to Google. Look at the URL bar.")
    print("4. Copy the code usually looks like: ...?code=AQUa...")
    
    auth_code = input("\n👇 PASTE THE CODE HERE: ").strip()

    # 2. Exchange Code for Token
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    
    response = requests.post(token_url, data=data)
    
    if response.status_code == 200:
        token = response.json().get("access_token")
        user_id = get_user_urn(token)
        print("\n✅ SUCCESS! Here is your info for .env:")
        print(f"LINKEDIN_ACCESS_TOKEN={token}")
        print(f"LINKEDIN_USER_URN={user_id}")
    else:
        print(f"\n❌ Error: {response.text}")

def get_user_urn(token):
    # Fetch your user ID (URN) needed for posting
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    if response.status_code == 200:
        return response.json().get("sub") # The 'sub' field is your URN
    return "UNKNOWN"

if __name__ == "__main__":
    get_access_token()