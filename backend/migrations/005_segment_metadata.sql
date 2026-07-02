alter table track_segments
    add column if not exists metadata jsonb not null default '{}'::jsonb;
