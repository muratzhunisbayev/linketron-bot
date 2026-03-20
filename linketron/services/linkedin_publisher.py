import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# REMOVED: Global ACCESS_TOKEN and USER_URN variables as they are now user-specific

def get_headers(token):
    """Generates headers using the specific user's token."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

def register_upload(token, urn):
    """
    Step 1: Ask LinkedIn for permission to upload an image using user-specific credentials.
    Returns: upload_url (where to send bytes) and asset_urn (the ID of the image).
    """
    url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    
    payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": f"urn:li:person:{urn}",
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    
    response = requests.post(url, headers=get_headers(token), json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Register Upload Failed: {response.text}")
    
    data = response.json()
    upload_url = data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
    asset = data['value']['asset']
    return upload_url, asset

def publish_to_linkedin(text, image_paths, token, urn):
    """
    The Official Way:
    1. If Images: Register -> Upload -> Append to Media array for each file.
    2. If Text: Post Text Only
    Uses token and urn provided for the specific user.
    """
    if not token or not urn:
        return "❌ Error: Missing authentication for this user."

    try:
        media_category = "NONE"
        media_content = []

        # --- A. HANDLE IMAGES (Multi-File Process) ---
        if image_paths:
            # Normalize single strings (from Web/AI) into a list
            if isinstance(image_paths, str):
                image_paths = [image_paths]

            print(f"📤 Starting Official Image Upload for {len(image_paths)} file(s)...")
            media_category = "IMAGE"

            for path in image_paths:
                if not os.path.exists(path):
                    continue
                
                # 1. Register with user credentials
                upload_url, asset_urn = register_upload(token, urn)
                
                # 2. Upload Bytes
                with open(path, "rb") as f:
                    headers_upload = {"Authorization": f"Bearer {token}"}
                    requests.put(upload_url, headers=headers_upload, data=f)
                
                # 3. Append to Media Array
                media_content.append({
                    "media": asset_urn,
                    "status": "READY",
                    "title": {"attributes": [], "text": "Image"},
                    "description": {"attributes": [], "text": "Uploaded via Linketron"}
                })

        # --- B. CREATE POST (UGC API) ---
        post_url = "https://api.linkedin.com/v2/ugcPosts"
        
        payload = {
            "author": f"urn:li:person:{urn}",
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
        response = requests.post(post_url, headers=get_headers(token), json=payload)
        
        if response.status_code == 201:
            post_id = response.json().get("id", "Unknown")
            return f"✅ **Published Successfully!**\nID: {post_id}"
        else:
            return f"❌ LinkedIn API Error: {response.text}"

    except Exception as e:
        return f"⚠️ Publish Failed: {str(e)}"