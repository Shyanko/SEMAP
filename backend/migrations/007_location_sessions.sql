create table location_sessions (
    id bigserial primary key,
    account_id bigint not null references accounts(id) on delete cascade,
    segment_id bigint not null references track_segments(id) on delete cascade,
    status text not null check (status in ('active', 'paused', 'finished')),
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index location_sessions_account_updated_idx
    on location_sessions(account_id, updated_at desc);
