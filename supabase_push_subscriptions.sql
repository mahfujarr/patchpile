-- Supabase Schema for Patchpile Web Push Notifications
-- Run this in your Supabase SQL Editor: https://supabase.com/dashboard/project/anikploodichlpgfymiq/sql

CREATE TABLE IF NOT EXISTS public.push_subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index on endpoint for fast lookup and deletion
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_endpoint ON public.push_subscriptions (endpoint);

-- Enable Row Level Security (RLS)
ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;

-- Allow anon and authenticated users to insert, update, and delete their own subscriptions
DROP POLICY IF EXISTS "Allow public access on push_subscriptions" ON public.push_subscriptions;
CREATE POLICY "Allow public access on push_subscriptions"
    ON public.push_subscriptions
    FOR ALL
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);

-- Grant permissions to public anon and authenticated roles
GRANT ALL ON TABLE public.push_subscriptions TO anon;
GRANT ALL ON TABLE public.push_subscriptions TO authenticated;
GRANT ALL ON TABLE public.push_subscriptions TO service_role;

