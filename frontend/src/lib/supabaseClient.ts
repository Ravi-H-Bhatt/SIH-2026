/**
 * Supabase Auth client — used ONLY to run the Google OAuth redirect and read the
 * resulting session. All application data still goes through the FastAPI backend.
 *
 * The token this returns is a *Supabase* token, not an application token. It is
 * posted to `POST /api/v1/auth/google`, verified server-side, and exchanged for
 * the application JWT. It is never used to talk to the backend directly.
 *
 * Only the anon (publishable) key belongs here. The service-role key must never
 * appear in frontend code.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const isSupabaseAuthConfigured = Boolean(url && anonKey);

let client: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient | null {
  if (!isSupabaseAuthConfigured) return null;
  if (!client) {
    client = createClient(url as string, anonKey as string, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return client;
}
