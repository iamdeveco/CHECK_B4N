import datetime
from flask import Flask, request, Response, render_template_string
import requests
import json
import os
import urllib3
import concurrent.futures
from functools import lru_cache

# ❌ SSL Warning বন্ধ করা
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ✅ Cache for player info (reduces API calls)
@lru_cache(maxsize=100)
def get_player_info_cached(player_id, server="BD"):
    """Cached version of player info fetching"""
    return get_player_info(player_id, server)

# ✅ Updated function to parse the new API response structure
def get_player_info(player_id, server="BD"):
    url = f"https://info-api-ecru-ten.vercel.app/get?uid={player_id}"
    
    try:
        res = requests.get(url, timeout=5, verify=False)
        if res.status_code != 200:
            print(f"[INFO ERROR] UID={player_id} | STATUS={res.status_code}")
            return {
                "nickname": "❌ Fetch failed",
                "region": server,
                "lastLoginAt": "0",
                "lastLoginReadable": "❌ Unknown",
                "createAt": "0",
                "createAtReadable": "❌ Unknown",
                "level": "0",
                "experience": "0",
                "rank": "Unknown",
                "guild": "None"
            }

        data = res.json()
        
        # Parse AccountInfo section
        account_info = data.get("AccountInfo", {})
        nickname = account_info.get("AccountName", "❌ Not available")
        region = account_info.get("AccountRegion", server)
        level = str(account_info.get("AccountLevel", "0"))
        experience = str(account_info.get("AccountEXP", "0"))
        
        # Parse dates from string format "2025-02-10 20:27:51 BDT"
        last_login_str = account_info.get("AccountLastLogin", "")
        create_time_str = account_info.get("AccountCreateTime", "")
        
        # Parse AccountProfileInfo for rank
        account_profile = data.get("AccountProfileInfo", {})
        rank_point = account_profile.get("BrRankPoint", "0")
        
        # Parse GuildInfo
        guild_info = data.get("GuildInfo", {})
        guild_name = guild_info.get("GuildName", "No Guild")
        
        # Parse SocialInfo for signature
        social_info = data.get("SocialInfo", {})
        signature = social_info.get("signature", "")
        
        # Function to parse date string with timezone
        def parse_date_string(date_str):
            if not date_str:
                return "❌ Unknown"
            try:
                # Remove timezone part (BDT, IST, etc.)
                date_part = date_str.split(" ")[:2]
                if len(date_part) >= 2:
                    return " ".join(date_part)
                return date_str
            except:
                return date_str

        last_login_readable = parse_date_string(last_login_str)
        create_time_readable = parse_date_string(create_time_str)

        return {
            "nickname": nickname,
            "region": region,
            "lastLoginAt": "0",  # Keep as 0 since we don't have timestamp
            "lastLoginReadable": last_login_readable,
            "createAt": "0",  # Keep as 0 since we don't have timestamp
            "createAtReadable": create_time_readable,
            "level": level,
            "experience": experience,
            "rank": f"BR: {rank_point}",
            "guild": guild_name,
            "signature": signature[:50] + "..." if len(signature) > 50 else signature
        }

    except requests.Timeout:
        print(f"[TIMEOUT ERROR] UID={player_id}")
        return {
            "nickname": "❌ Timeout",
            "region": server,
            "lastLoginAt": "0",
            "lastLoginReadable": "❌ Unknown",
            "createAt": "0",
            "createAtReadable": "❌ Unknown",
            "level": "0",
            "experience": "0",
            "rank": "Unknown",
            "guild": "None"
        }
    except Exception as e:
        print(f"[PLAYER INFO ERROR] UID={player_id} | ERROR={str(e)[:100]}")
        return {
            "nickname": "❌ Error",
            "region": server,
            "lastLoginAt": "0",
            "lastLoginReadable": "❌ Unknown",
            "createAt": "0",
            "createAtReadable": "❌ Unknown",
            "level": "0",
            "experience": "0",
            "rank": "Unknown",
            "guild": "None"
        }

# ✅ Fast ban checking function
def check_ban_status(player_id):
    """Check ban status from Garena API"""
    url = f"https://ff.garena.com/api/antihack/check_banned?lang=en&uid={player_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://ff.garena.com/en/support/",
        "X-Requested-With": "B6FksShzIgjfrYImLpTsadjS86sddhFH"
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=3)
        if response.status_code == 200:
            data = response.json().get("data", {})
            return {
                "is_banned": data.get("is_banned", 0),
                "period": data.get("period", 0),
                "success": True
            }
        return {"is_banned": 0, "period": 0, "success": False}
    except:
        return {"is_banned": 0, "period": 0, "success": False}

# ✅ Enhanced parallel processing with more info
def check_banned_fast(player_id, server="BD"):
    """Parallel execution for faster response with enhanced info"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks in parallel
        player_info_future = executor.submit(get_player_info_cached, player_id, server)
        ban_info_future = executor.submit(check_ban_status, player_id)
        
        # Get results
        player_info = player_info_future.result()
        ban_info = ban_info_future.result()
    
    # Prepare enhanced response
    is_banned = ban_info["is_banned"]
    
    result = {
        "✅ Status": "Account checked successfully" if ban_info["success"] else "Partial data fetched",
        "🆔 UID": player_id,
        "🏷️ Nickname": player_info["nickname"],
        "🌍 Region": player_info["region"],
        "⭐ Level": player_info["level"],
        "⚡ Experience": player_info["experience"],
        "📊 Rank": player_info["rank"],
        "👥 Guild": player_info["guild"],
        "🕒 Last Login": player_info["lastLoginReadable"],
        "🆕 Created At": player_info["createAtReadable"],
        "🔒 Account": "🚫 BANNED" if is_banned else "✅ NOT BANNED",
        "⏳ Duration": f"{ban_info['period']} month(s)" if is_banned else "No ban",
        "📊 Banned?": bool(is_banned),
        "💎 Powered by": "@dev_eco",
        "📡 Channel": "https://discord.gg/Mba5bNbdCP"
    }
    
    # Add signature if available
    if player_info.get("signature"):
        result["✏️ BIO"] = player_info["signature"]
    
    return result

@app.route("/check", methods=["GET"])
def check():
    player_id = request.args.get("uid", "")
    server = request.args.get("server", "BD")
    
    if not player_id:
        return Response(
            json.dumps({
                "⚠️ error": "Player ID (uid) is required!",
                "status_code": 400
            }, indent=2),
            mimetype="application/json",
            status=400
        )
    
    # Validate UID format
    if not player_id.isdigit():
        return Response(
            json.dumps({
                "⚠️ error": "Invalid UID format. Must be numeric!",
                "status_code": 400
            }, indent=2),
            mimetype="application/json",
            status=400
        )
    
    try:
        result = check_banned_fast(player_id, server)
        return Response(
            json.dumps(result, indent=2, ensure_ascii=False),
            mimetype="application/json",
            status=200
        )
    except Exception as e:
        print(f"[ROUTE ERROR] UID={player_id} | ERROR={e}")
        return Response(
            json.dumps({
                "💥 exception": "Internal server error",
                "status_code": 500
            }, indent=2),
            mimetype="application/json",
            status=500
        )

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return Response(
        json.dumps({
            "status": "✅ OK",
            "service": "Free Fire Ban Check API",
            "version": "2.0",
            "uptime": datetime.datetime.now().isoformat(),
            "features": ["Ban Check", "Account Info", "Guild Info", "Rank Info"]
        }, indent=2),
        mimetype="application/json"
    )

@app.route("/info/<uid>", methods=["GET"])
def get_full_info(uid):
    """Get full account information from the API"""
    try:
        url = f"https://info-api-ecru-ten.vercel.app/get?uid={uid}"
        response = requests.get(url, timeout=5, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            return Response(
                json.dumps(data, indent=2, ensure_ascii=False),
                mimetype="application/json",
                status=200
            )
        else:
            return Response(
                json.dumps({
                    "⚠️ error": "Failed to fetch account info",
                    "status_code": response.status_code
                }, indent=2),
                mimetype="application/json",
                status=response.status_code
            )
    except Exception as e:
        print(f"[FULL INFO ERROR] UID={uid} | ERROR={e}")
        return Response(
            json.dumps({
                "💥 exception": "Internal server error",
                "status_code": 500
            }, indent=2),
            mimetype="application/json",
            status=500
        )

# Premium HTML Template with CSS - UPDATED for new fields
PREMIUM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 Free Fire Ban Check - Premium API</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            /* Color Palette - Dark & Premium */
            --bg-core: #050505;
            --bg-surface: #0f0f0f;
            --bg-surface-hover: #1a1a1a;
            --bg-glass: rgba(20, 20, 20, 0.7);
            --bg-gradient: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);

            --primary-hue: 16;
            --primary: hsl(var(--primary-hue), 100%, 50%);
            --primary-dim: hsl(var(--primary-hue), 100%, 30%);
            --primary-glow: hsla(var(--primary-hue), 100%, 50%, 0.3);

            --accent-cyan: #00f2ff;
            --accent-purple: #bd00ff;
            --accent-gradient: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));

            --text-main: #ffffff;
            --text-muted: #a0a0a0;
            --text-dim: #505050;

            --border-light: rgba(255, 255, 255, 0.1);
            --border-active: rgba(255, 69, 0, 0.5);

            --success: #00ff9d;
            --error: #ff2a6d;
            --warning: #ffb300;

            /* Spacing & Layout */
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 16px;
            --radius-xl: 24px;
            --radius-full: 9999px;

            --space-xs: 0.5rem;
            --space-sm: 1rem;
            --space-md: 2rem;
            --space-lg: 4rem;
            --space-xl: 6rem;

            /* Typography */
            --font-ui: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-display: 'Outfit', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;

            /* Shadows & Effects */
            --shadow-sm: 0 4px 6px rgba(0, 0, 0, 0.1);
            --shadow-md: 0 10px 20px rgba(0, 0, 0, 0.25);
            --shadow-lg: 0 20px 40px rgba(0, 0, 0, 0.3);
            --shadow-glow: 0 0 30px var(--primary-glow);

            /* Animation */
            --ease-out: cubic-bezier(0.215, 0.61, 0.355, 1);
            --ease-in-out: cubic-bezier(0.645, 0.045, 0.355, 1);
            --transition-fast: 0.2s var(--ease-out);
            --transition-normal: 0.3s var(--ease-in-out);
        }

        /* Reset & Base */
        *,
        *::before,
        *::after {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-core);
            color: var(--text-main);
            font-family: var(--font-ui);
            line-height: 1.6;
            overflow-x: hidden;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 20% 30%, rgba(255, 69, 0, 0.05) 0%, transparent 20%),
                radial-gradient(circle at 80% 70%, rgba(0, 242, 255, 0.05) 0%, transparent 20%);
        }

        /* Glass Effect */
        .glass {
            background: var(--bg-glass);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border-light);
        }

        /* Container */
        .container {
            width: 100%;
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 var(--space-md);
        }

        /* Header */
        .header {
            padding: var(--space-md) 0;
            position: relative;
            overflow: hidden;
        }

        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at center, var(--primary-glow) 0%, transparent 70%);
            opacity: 0.1;
            z-index: -1;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            margin-bottom: var(--space-sm);
        }

        .logo-icon {
            width: 48px;
            height: 48px;
            background: var(--accent-gradient);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: white;
        }

        .logo-text {
            font-family: var(--font-display);
            font-size: 2rem;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }

        .tagline {
            font-size: 1.1rem;
            color: var(--text-muted);
            margin-bottom: var(--space-md);
            max-width: 600px;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: var(--space-sm);
            margin-bottom: var(--space-xl);
        }

        .stat-card {
            padding: var(--space-md);
            border-radius: var(--radius-lg);
            background: var(--bg-surface);
            border: 1px solid var(--border-light);
            transition: var(--transition-normal);
        }

        .stat-card:hover {
            transform: translateY(-4px);
            border-color: var(--primary);
            box-shadow: var(--shadow-glow);
        }

        .stat-icon {
            width: 48px;
            height: 48px;
            border-radius: var(--radius-md);
            background: var(--bg-surface-hover);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: var(--space-sm);
            font-size: 1.5rem;
            color: var(--primary);
        }

        .stat-value {
            font-family: var(--font-display);
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: var(--space-xs);
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        /* Main Content */
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1.2fr;
            gap: var(--space-lg);
            margin-bottom: var(--space-xl);
        }

        @media (max-width: 1024px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }

        /* Check Panel */
        .check-panel {
            padding: var(--space-lg);
            border-radius: var(--radius-xl);
            background: var(--bg-gradient);
            border: 1px solid var(--border-light);
        }

        .panel-header {
            margin-bottom: var(--space-md);
        }

        .panel-title {
            font-family: var(--font-display);
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: var(--space-xs);
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }

        .panel-title i {
            color: var(--primary);
        }

        .panel-subtitle {
            color: var(--text-muted);
            font-size: 1rem;
        }

        /* Form */
        .form-group {
            margin-bottom: var(--space-md);
        }

        .form-label {
            display: block;
            margin-bottom: var(--space-xs);
            color: var(--text-main);
            font-weight: 500;
        }

        .form-input {
            width: 100%;
            padding: var(--space-sm) var(--space-md);
            background: var(--bg-surface);
            border: 1px solid var(--border-light);
            border-radius: var(--radius-md);
            color: var(--text-main);
            font-family: var(--font-ui);
            font-size: 1rem;
            transition: var(--transition-fast);
        }

        .form-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        .form-input::placeholder {
            color: var(--text-dim);
        }

        .server-select {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
            gap: var(--space-sm);
            margin-top: var(--space-xs);
        }

        .server-option {
            padding: var(--space-sm);
            background: var(--bg-surface);
            border: 1px solid var(--border-light);
            border-radius: var(--radius-md);
            text-align: center;
            cursor: pointer;
            transition: var(--transition-fast);
        }

        .server-option:hover {
            background: var(--bg-surface-hover);
        }

        .server-option.active {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }

        .submit-btn {
            width: 100%;
            padding: var(--space-sm) var(--space-md);
            background: var(--accent-gradient);
            border: none;
            border-radius: var(--radius-md);
            color: white;
            font-family: var(--font-display);
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition-normal);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: var(--space-sm);
        }

        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-glow);
        }

        .submit-btn:active {
            transform: translateY(0);
        }

        /* Result Panel */
        .result-panel {
            padding: var(--space-lg);
            border-radius: var(--radius-xl);
            background: var(--bg-gradient);
            border: 1px solid var(--border-light);
            opacity: 0;
            transform: translateY(20px);
            transition: var(--transition-normal);
        }

        .result-panel.show {
            opacity: 1;
            transform: translateY(0);
        }

        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-md);
            padding-bottom: var(--space-sm);
            border-bottom: 1px solid var(--border-light);
        }

        .result-title {
            font-family: var(--font-display);
            font-size: 1.5rem;
            font-weight: 600;
        }

        .result-status {
            padding: var(--space-xs) var(--space-sm);
            border-radius: var(--radius-full);
            font-size: 0.9rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .result-status.banned {
            background: rgba(255, 42, 109, 0.2);
            color: var(--error);
            border: 1px solid var(--error);
        }

        .result-status.clean {
            background: rgba(0, 255, 157, 0.2);
            color: var(--success);
            border: 1px solid var(--success);
        }

        .result-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: var(--space-sm);
        }

        .result-card {
            padding: var(--space-sm);
            background: var(--bg-surface);
            border-radius: var(--radius-md);
            border: 1px solid var(--border-light);
        }

        .result-card-header {
            display: flex;
            align-items: center;
            gap: var(--space-xs);
            margin-bottom: var(--space-xs);
        }

        .result-card-icon {
            color: var(--primary);
            font-size: 0.9rem;
        }

        .result-card-label {
            color: var(--text-muted);
            font-size: 0.9rem;
            font-weight: 500;
        }

        .result-card-value {
            font-family: var(--font-mono);
            font-weight: 500;
            word-break: break-word;
        }

        .result-card-value.banned {
            color: var(--error);
            font-weight: 600;
        }

        .result-card-value.clean {
            color: var(--success);
            font-weight: 600;
        }

        /* API Docs */
        .docs-panel {
            margin-top: var(--space-xl);
            padding: var(--space-lg);
            border-radius: var(--radius-xl);
            background: var(--bg-gradient);
            border: 1px solid var(--border-light);
        }

        .docs-header {
            margin-bottom: var(--space-md);
        }

        .docs-title {
            font-family: var(--font-display);
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: var(--space-xs);
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }

        .docs-title i {
            color: var(--accent-cyan);
        }

        .endpoint-list {
            display: flex;
            flex-direction: column;
            gap: var(--space-md);
        }

        .endpoint-item {
            padding: var(--space-md);
            background: var(--bg-surface);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-light);
        }

        .endpoint-method {
            display: inline-block;
            padding: var(--space-xs) var(--space-sm);
            background: var(--primary);
            color: white;
            border-radius: var(--radius-sm);
            font-family: var(--font-mono);
            font-size: 0.9rem;
            font-weight: 600;
            margin-right: var(--space-sm);
        }

        .endpoint-path {
            font-family: var(--font-mono);
            color: var(--accent-cyan);
            font-size: 1.1rem;
        }

        .endpoint-desc {
            color: var(--text-muted);
            margin-top: var(--space-xs);
            font-size: 0.95rem;
        }

        /* Footer */
        .footer {
            margin-top: var(--space-xl);
            padding: var(--space-lg) 0;
            border-top: 1px solid var(--border-light);
            text-align: center;
        }

        .footer-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: var(--space-md);
        }

        .social-links {
            display: flex;
            gap: var(--space-md);
        }

        .social-link {
            width: 40px;
            height: 40px;
            border-radius: var(--radius-full);
            background: var(--bg-surface);
            border: 1px solid var(--border-light);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-main);
            text-decoration: none;
            transition: var(--transition-fast);
        }

        .social-link:hover {
            background: var(--primary);
            transform: translateY(-2px);
            border-color: var(--primary);
        }

        .copyright {
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        .powered-by {
            color: var(--text-dim);
            font-size: 0.8rem;
            margin-top: var(--space-xs);
        }

        /* Loading Animation */
        .loading {
            display: none;
            text-align: center;
            padding: var(--space-md);
        }

        .loading.show {
            display: block;
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border-light);
            border-top-color: var(--primary);
            border-radius: 50%;
            margin: 0 auto var(--space-sm);
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Responsive */
        @media (max-width: 768px) {
            .container {
                padding: 0 var(--space-sm);
            }
            
            .header, .main-content, .docs-panel {
                padding: var(--space-md);
            }
            
            .logo-text {
                font-size: 1.5rem;
            }
            
            .panel-title {
                font-size: 1.5rem;
            }
            
            .result-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .animate-in {
            animation: fadeIn 0.5s var(--ease-out) forwards;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="logo">
                <div class="logo-icon">
                    <i class="fas fa-fire"></i>
                </div>
                <div class="logo-text">CHECK BAN API v2.0</div>
            </div>
            <p class="tagline">
                Enhanced Free Fire account analyzer with detailed stats, ban checking, 
                guild information, and real-time account analysis.
            </p>
            
            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card glass">
                    <div class="stat-icon">
                        <i class="fas fa-shield-alt"></i>
                    </div>
                    <div class="stat-value">15K+</div>
                    <div class="stat-label">Checks Today</div>
                </div>
                <div class="stat-card glass">
                    <div class="stat-icon">
                        <i class="fas fa-bolt"></i>
                    </div>
                    <div class="stat-value">99.9%</div>
                    <div class="stat-label">Uptime</div>
                </div>
                <div class="stat-card glass">
                    <div class="stat-icon">
                        <i class="fas fa-globe"></i>
                    </div>
                    <div class="stat-value">20+</div>
                    <div class="stat-label">Data Points</div>
                </div>
                <div class="stat-card glass">
                    <div class="stat-icon">
                        <i class="fas fa-rocket"></i>
                    </div>
                    <div class="stat-value">0.4s</div>
                    <div class="stat-label">Avg Response</div>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Left Panel - Check Form -->
            <section class="check-panel glass">
                <div class="panel-header">
                    <h2 class="panel-title">
                        <i class="fas fa-search"></i>
                        Check Account Status
                    </h2>
                    <p class="panel-subtitle">
                        Enter Player UID to get comprehensive account analysis including ban status, level, rank, and more
                    </p>
                </div>

                <form id="checkForm">
                    <div class="form-group">
                        <label class="form-label" for="uid">
                            <i class="fas fa-id-card"></i>
                            Player UID
                        </label>
                        <input 
                            type="text" 
                            id="uid" 
                            class="form-input" 
                            placeholder="Enter 9-10 digit UID" 
                            required
                            pattern="\\d{9,10}"
                        >
                        <small style="color: var(--text-muted); display: block; margin-top: 4px;">
                            Example: 1234567890
                        </small>
                    </div>

                    <div class="form-group">
                        <label class="form-label">
                            <i class="fas fa-server"></i>
                            Default Region
                        </label>
                        <div class="server-select">
                            <div class="server-option active" data-value="BD">
                                <i class="fas fa-flag"></i> BD
                            </div>
                            <div class="server-option" data-value="IN">
                                <i class="fas fa-flag"></i> IN
                            </div>
                            <div class="server-option" data-value="ID">
                                <i class="fas fa-flag"></i> ID
                            </div>
                            <div class="server-option" data-value="TH">
                                <i class="fas fa-flag"></i> TH
                            </div>
                            <div class="server-option" data-value="BR">
                                <i class="fas fa-flag"></i> BR
                            </div>
                        </div>
                    </div>

                    <div class="form-group">
                        <button type="submit" class="submit-btn">
                            <i class="fas fa-bolt"></i>
                            ANALYZE ACCOUNT
                        </button>
                    </div>
                </form>

                <!-- Loading Indicator -->
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>Fetching account data...</p>
                </div>
            </section>

            <!-- Right Panel - Results -->
            <section class="result-panel glass" id="resultPanel">
                <div class="result-header">
                    <h3 class="result-title">Account Analysis</h3>
                    <div class="result-status clean" id="statusBadge">✅ CLEAN</div>
                </div>

                <div class="result-grid" id="resultGrid">
                    <!-- Results will be populated here by JavaScript -->
                </div>
            </section>
        </main>

        <!-- API Documentation -->
        <section class="docs-panel glass">
            <div class="docs-header">
                <h2 class="docs-title">
                    <i class="fas fa-code"></i>
                    API Documentation v2.0
                </h2>
                <p class="panel-subtitle">
                    Enhanced API endpoints for comprehensive Free Fire account analysis
                </p>
            </div>

            <div class="endpoint-list">
                <div class="endpoint-item">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/check?uid=PLAYER_ID&server=REGION</span>
                    <p class="endpoint-desc">
                        Enhanced account analysis with ban status, level, experience, rank, guild info, and more.
                        Returns detailed JSON response with comprehensive account data.
                    </p>
                </div>
                <div class="endpoint-item">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/info/PLAYER_ID</span>
                    <p class="endpoint-desc">
                        Get full raw account information from the source API.
                        Returns complete account data including equipped items, pet info, and social info.
                    </p>
                </div>
                <div class="endpoint-item">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/health</span>
                    <p class="endpoint-desc">
                        Health check endpoint to verify API status and uptime.
                        Returns service status, version, and available features.
                    </p>
                </div>
            </div>
        </section>

        <!-- Footer -->
        <footer class="footer">
            <div class="footer-content">
                <div class="social-links">
                    <a href="https://discord.gg/Mba5bNbdCP" class="social-link" target="_blank">
                        <i class="fab fa-discord"></i>
                    </a>
                    <a href="https://github.com" class="social-link" target="_blank">
                        <i class="fab fa-github"></i>
                    </a>
                    <a href="#" class="social-link">
                        <i class="fas fa-envelope"></i>
                    </a>
                </div>
                <div class="copyright">
                    © 2024 CHECK BAN API v2.0. All rights reserved.
                </div>
                <div class="powered-by">
                    Powered by @dev_eco • Enhanced with new API integration
                </div>
            </div>
        </footer>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Server selection
            const serverOptions = document.querySelectorAll('.server-option');
            let selectedServer = 'BD';
            
            serverOptions.forEach(option => {
                option.addEventListener('click', function() {
                    serverOptions.forEach(opt => opt.classList.remove('active'));
                    this.classList.add('active');
                    selectedServer = this.dataset.value;
                });
            });

            // Form submission
            const form = document.getElementById('checkForm');
            const resultPanel = document.getElementById('resultPanel');
            const resultGrid = document.getElementById('resultGrid');
            const loading = document.getElementById('loading');
            
            // Template for result cards
            const resultCardTemplate = (icon, label, value, className = '') => `
                <div class="result-card">
                    <div class="result-card-header">
                        <i class="fas ${icon} result-card-icon"></i>
                        <span class="result-card-label">${label}</span>
                    </div>
                    <div class="result-card-value ${className}">${value}</div>
                </div>
            `;
            
            form.addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const uidInput = document.getElementById('uid');
                const uid = uidInput.value.trim();
                
                if (!uid.match(/^\d{9,10}$/)) {
                    alert('Please enter a valid 9-10 digit UID');
                    return;
                }
                
                // Show loading
                loading.classList.add('show');
                resultPanel.classList.remove('show');
                resultGrid.innerHTML = '';
                
                try {
                    // Make API request
                    const response = await fetch(`/check?uid=${uid}&server=${selectedServer}`);
                    const data = await response.json();
                    
                    // Update UI with results
                    updateResults(data);
                    
                    // Show results
                    resultPanel.classList.add('show');
                } catch (error) {
                    console.error('Error:', error);
                    alert('Failed to check account. Please try again.');
                } finally {
                    // Hide loading
                    loading.classList.remove('show');
                }
            });

            // Update results function
            function updateResults(data) {
                // Get status badge
                const statusBadge = document.getElementById('statusBadge');
                
                // Clear previous results
                resultGrid.innerHTML = '';
                
                // Add all data fields
                const fields = [
                    { key: '🆔 UID', icon: 'fa-id-badge', label: 'UID' },
                    { key: '🏷️ Nickname', icon: 'fa-user', label: 'Nickname' },
                    { key: '🌍 Region', icon: 'fa-globe', label: 'Region' },
                    { key: '⭐ Level', icon: 'fa-star', label: 'Level' },
                    { key: '⚡ Experience', icon: 'fa-bolt', label: 'Experience' },
                    { key: '📊 Rank', icon: 'fa-chart-line', label: 'Rank Points' },
                    { key: '👥 Guild', icon: 'fa-users', label: 'Guild' },
                    { key: '🕒 Last Login', icon: 'fa-sign-in-alt', label: 'Last Login' },
                    { key: '🆕 Created At', icon: 'fa-calendar-plus', label: 'Created At' },
                    { key: '🔒 Account', icon: 'fa-shield-alt', label: 'Ban Status', className: () => data['📊 Banned?'] ? 'banned' : 'clean' },
                    { key: '⏳ Duration', icon: 'fa-clock', label: 'Ban Duration' }
                ];
                
                // Check for signature
                if (data['✏️ BIO']) {
                    fields.push({ key: '✏️ BIO', icon: 'fa-quote-left', label: 'BIO' });
                }
                
                // Add powered by
                fields.push({ key: '💎 Powered by', icon: 'fa-gem', label: 'Powered By' });
                fields.push({ key: '📡 Channel', icon: 'fa-broadcast-tower', label: 'Community' });
                
                // Create cards for each field
                fields.forEach(field => {
                    if (data[field.key]) {
                        const className = typeof field.className === 'function' ? field.className() : '';
                        const cardHtml = resultCardTemplate(
                            field.icon,
                            field.label,
                            data[field.key],
                            className
                        );
                        resultGrid.innerHTML += cardHtml;
                    }
                });
                
                // Update badge
                const isBanned = data['📊 Banned?'];
                if (isBanned) {
                    statusBadge.textContent = '🚫 BANNED';
                    statusBadge.className = 'result-status banned';
                } else {
                    statusBadge.textContent = '✅ CLEAN';
                    statusBadge.className = 'result-status clean';
                }
                
                // Add animation
                resultPanel.classList.remove('animate-in');
                void resultPanel.offsetWidth; // Trigger reflow
                resultPanel.classList.add('animate-in');
            }

            // Example UID input
            document.getElementById('uid').addEventListener('click', function() {
                if (this.value === '') {
                    this.value = '1234567890';
                    setTimeout(() => this.select(), 100);
                }
            });

            // Animate elements on load
            const elements = document.querySelectorAll('.stat-card, .check-panel, .docs-panel');
            elements.forEach((el, index) => {
                setTimeout(() => {
                    el.classList.add('animate-in');
                }, index * 100);
            });
        });
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    """Premium UI index page"""
    return render_template_string(PREMIUM_HTML)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Production settings for better performance
    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,  # Enable threading for concurrent requests
        debug=False  # Disable debug in production
    )
