import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# Load the Official Keys
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
USER_URN = os.getenv("LINKEDIN_USER_URN")

def get_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

def register_upload():
    """
    Step 1: Ask LinkedIn for permission to upload an image.
    Returns: upload_url (where to send bytes) and asset_urn (the ID of the image).
    """
    url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    
    payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": f"urn:li:person:{USER_URN}",
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    
    response = requests.post(url, headers=get_headers(), json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Register Upload Failed: {response.text}")
    
    data = response.json()
    upload_url = data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
    asset = data['value']['asset']
    return upload_url, asset

def publish_to_linkedin(text, image_path=None):
    """
    The Official Way:
    1. If Image: Register -> Upload -> Post with Media
    2. If Text: Post Text Only
    """
    if not ACCESS_TOKEN or not USER_URN:
        return "❌ Error: Missing LINKEDIN_ACCESS_TOKEN or USER_URN in .env"

    try:
        media_category = "NONE"
        media_content = []

        # --- A. HANDLE IMAGE (3-Step Process) ---
        if image_path:
            print(f"📤 Starting Official Image Upload...")
            
            # 1. Register
            upload_url, asset_urn = register_upload()
            
            # 2. Upload Bytes
            with open(image_path, "rb") as f:
                # Note: We strip the content-type header for the binary upload to avoid errors
                headers_upload = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
                requests.put(upload_url, headers=headers_upload, data=f)
            
            # 3. Prepare Post Data
            media_category = "IMAGE"
            media_content = [{
                "media": asset_urn,
                "status": "READY",
                "title": {"attributes": [], "text": "Image"},
                "description": {"attributes": [], "text": "Uploaded via Linketron"}
            }]

        # --- B. CREATE POST (UGC API) ---
        post_url = "https://api.linkedin.com/v2/ugcPosts"
        
        payload = {
            "author": f"urn:li:person:{USER_URN}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": media_category,
                    "media": media_content
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC" 
            }
        }

        print("🚀 Sending Post to LinkedIn...")
        response = requests.post(post_url, headers=get_headers(), json=payload)
        
        if response.status_code == 201:
            post_id = response.json().get("id", "Unknown")
            return f"✅ **Published Successfully!**\nID: {post_id}"
        else:
            return f"❌ LinkedIn API Error: {response.text}"

    except Exception as e:
        return f"⚠️ Publish Failed: {str(e)}"