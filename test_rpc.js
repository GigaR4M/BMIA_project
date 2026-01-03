
require('dotenv').config({ path: '.env' });
const { createClient } = require('@supabase/supabase-js');

// Fallback to explicit read if needed, but try env first
// Note: User's env file might not be standard
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://your-project.supabase.co";
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || "your-key";

console.log(`URL: ${supabaseUrl ? 'Found' : 'Missing'}`);
console.log(`Key: ${supabaseServiceKey ? 'Found' : 'Missing'}`);

if (!supabaseUrl || !supabaseServiceKey || supabaseUrl.includes("your-project")) {
    console.error('Missing valid env vars. Please check .env file location.');
    // Python script had access, so .env exists in current dir.
    process.exit(1);
}

const supabaseAdmin = createClient(supabaseUrl, supabaseServiceKey);

async function testRpc() {
    const guildId = '1327836427915886643'; // String ID
    console.log(`Testing RPC for guild: ${guildId}`);

    // Test get_daily_message_stats
    console.log('\n--- Calling get_daily_message_stats ---');
    const { data: dailyData, error: dailyError } = await supabaseAdmin.rpc('get_daily_message_stats', {
        p_guild_id: guildId, // Passing string now supported
        p_days: 30,
        p_timezone: 'America/Sao_Paulo',
        p_start_date: null
    });

    if (dailyError) {
        console.error('Error:', dailyError);
    } else {
        console.log(`Returned ${dailyData ? dailyData.length : 0} rows`);
        if (dailyData && dailyData.length > 0) console.log(dailyData[0]);
    }

    // Test get_top_users_by_messages
    console.log('\n--- Calling get_top_users_by_messages ---');
    const { data: userData, error: userError } = await supabaseAdmin.rpc('get_top_users_by_messages', {
        p_guild_id: guildId,
        p_days: 30,
        p_limit: 10,
        p_start_date: null
    });

    if (userError) {
        console.error('Error:', userError);
    } else {
        console.log(`Returned ${userData ? userData.length : 0} rows`);
        if (userData && userData.length > 0) console.log(userData[0]);
    }
}

testRpc();
