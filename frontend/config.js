// Isolated on purpose: this is the one file to change between local dev
// and a deployed backend (e.g. Render). Everything else in app.js reads
// from window.CITADEL_CONFIG.

window.CITADEL_CONFIG = {
  SUPABASE_URL: "https://qxsyscrbnbrzzvctozht.supabase.co",
  SUPABASE_ANON_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF4c3lzY3JibmJyenp2Y3Rvemh0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ0MDA2MDAsImV4cCI6MjA5OTk3NjYwMH0.PEfXTGNi1CXsAu_dZiYsixo0hb3urzh-s6a8haGX8LA",

  // Local dev default. Change to your Render URL once deployed,
  // e.g. "https://citadel-ai-backend.onrender.com/api/v1"
  API_BASE_URL: "http://localhost:8000/api/v1"
};