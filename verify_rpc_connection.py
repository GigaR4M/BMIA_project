
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: Missing env vars in python load")
    exit(1)

js_code = f"""
const {{ createClient }} = require('@supabase/supabase-js');

const supabase = createClient('{url}', '{key}');

async function run() {{
    console.log("Testing get_daily_message_stats for guild 1327836427915886643...");
    const {{ data, error }} = await supabase.rpc('get_daily_message_stats', {{
        p_guild_id: '1327836427915886643',
        p_days: 30,
        p_timezone: 'America/Sao_Paulo',
        p_start_date: null
    }});

    if (error) {{
        console.error("RPC Error:", error);
    }} else {{
        console.log("Success! Row count:", data ? data.length : 0);
        if (data && data.length > 0) console.log("Sample:", data[0]);
    }}

    console.log("Testing get_top_users_by_messages...");
    const {{ data: userData, error: userError }} = await supabase.rpc('get_top_users_by_messages', {{
        p_guild_id: '1327836427915886643',
        p_days: 30,
        p_limit: 5,
        p_start_date: null
    }});

    if (userError) {{
        console.error("User RPC Error:", userError);
    }} else {{
        console.log("Success! User Row count:", userData ? userData.length : 0);
        if (userData && userData.length > 0) console.log("User Sample:", userData[0]);
    }}
}}

run();
"""

with open("temp_test_rpc.js", "w") as f:
    f.write(js_code)

print("Running temp_test_rpc.js...")
subprocess.run(["node", "temp_test_rpc.js"])
