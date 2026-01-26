from playwright.async_api import async_playwright

async def launch_browser_login():
    """
    Launches a visible browser for the user to login.
    Returns the 'li_at' cookie string if successful, else None.
    """
    print("🕵️ Auth Agent: Launching browser...")
    
    async with async_playwright() as p:
        # Launch visible browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Go to login page
            await page.goto("https://www.linkedin.com/login")
            
            # Wait for successful login (redirect to feed)
            # timeout=0 means we wait forever until they login
            await page.wait_for_url("**/feed/**", timeout=0) 
            
            # Extract cookies
            cookies = await context.cookies()
            li_at = next((c for c in cookies if c["name"] == "li_at"), None)
            
            if li_at:
                return li_at["value"]
            return None
            
        except Exception as e:
            print(f"❌ Auth Agent Error: {e}")
            return None
        finally:
            await browser.close()