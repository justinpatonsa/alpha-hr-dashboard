// Public settings for the browser. Nothing secret belongs in this file or anywhere in this repo.
//
// - Each viewer signs in on the sign-in page with their own Supabase login from the instructor.
// - The publishable key is designed to be public. On its own it reads nothing: every table
//   refuses the anonymous role, so a signed-in user is required.
// - Passwords never go in this repo (course rule). If you change the project URL, also update
//   connect-src in the Content-Security-Policy meta tag in index.html.
export const SUPABASE_URL = "https://qfqtowijmmceismaqzxw.supabase.co";
export const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_mWe1pU4wX-4YnnaaYqkJSw_5or3gdIM";
