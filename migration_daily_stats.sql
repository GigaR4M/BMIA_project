-- Create daily_user_stats table
CREATE TABLE IF NOT EXISTS daily_user_stats (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    date DATE NOT NULL,
    voice_seconds INTEGER DEFAULT 0,
    messages_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(guild_id, user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_guild_date ON daily_user_stats(guild_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_stats_user ON daily_user_stats(user_id);

-- Function to handle message inserts
CREATE OR REPLACE FUNCTION update_daily_stats_message()
RETURNS TRIGGER AS $$
DECLARE
    msg_date DATE;
BEGIN
    -- Calculate date based on Brazil time
    msg_date := DATE(NEW.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo');
    
    INSERT INTO daily_user_stats (guild_id, user_id, date, messages_count, updated_at)
    VALUES (NEW.guild_id, NEW.user_id, msg_date, 1, NOW())
    ON CONFLICT (guild_id, user_id, date)
    DO UPDATE SET 
        messages_count = daily_user_stats.messages_count + 1,
        updated_at = NOW();
        
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for messages
DROP TRIGGER IF EXISTS trigger_update_daily_stats_message ON messages;
CREATE TRIGGER trigger_update_daily_stats_message
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION update_daily_stats_message();

-- Function to handle voice activity updates
CREATE OR REPLACE FUNCTION update_daily_stats_voice()
RETURNS TRIGGER AS $$
DECLARE
    voice_date DATE;
    duration_diff INTEGER;
BEGIN
    -- We only care if duration_seconds changed or is set
    IF (TG_OP = 'UPDATE' AND NEW.duration_seconds IS DISTINCT FROM OLD.duration_seconds) OR (TG_OP = 'INSERT' AND NEW.duration_seconds > 0) THEN
        
        -- Use joined_at as the reference date for the session (simplification for "daily" assignment)
        voice_date := DATE(NEW.joined_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo');
        
        IF TG_OP = 'INSERT' THEN
            duration_diff := NEW.duration_seconds;
        ELSE
            -- Handle potential nulls in OLD (though unlikely for an update on duration)
            duration_diff := COALESCE(NEW.duration_seconds, 0) - COALESCE(OLD.duration_seconds, 0);
        END IF;

        IF duration_diff > 0 THEN
            INSERT INTO daily_user_stats (guild_id, user_id, date, voice_seconds, updated_at)
            VALUES (NEW.guild_id, NEW.user_id, voice_date, duration_diff, NOW())
            ON CONFLICT (guild_id, user_id, date)
            DO UPDATE SET 
                voice_seconds = daily_user_stats.voice_seconds + duration_diff,
                updated_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for voice_activity
DROP TRIGGER IF EXISTS trigger_update_daily_stats_voice ON voice_activity;
CREATE TRIGGER trigger_update_daily_stats_voice
AFTER INSERT OR UPDATE ON voice_activity
FOR EACH ROW
EXECUTE FUNCTION update_daily_stats_voice();
