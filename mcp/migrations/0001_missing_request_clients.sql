-- Migration number: 0001
-- Which client app asked for a measure the atlas lacks.
-- client is the first user-agent product token (max 80 characters).
-- No IP address and no full user-agent string is stored.
-- kind is "probe", "agent" or "unknown".
-- missing_requests is unchanged and is not created here.
CREATE TABLE IF NOT EXISTS missing_request_clients (
  day TEXT NOT NULL,
  term TEXT NOT NULL,
  client TEXT NOT NULL,
  kind TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (day, term, client)
);
