create table track_segments (
    id bigserial primary key,
    account_id bigint not null references accounts(id) on delete cascade,
    title text not null,
    source_type text not null constraint track_segments_source_type_check check (source_type in ('flight', 'train', 'gps')),
    transport_type text not null check (transport_type in ('flight', 'train', 'walk', 'car', 'other')),
    external_code text,
    started_at timestamptz,
    ended_at timestamptz,
    summary text,
    is_approximate boolean not null default false,
    version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index track_segments_account_updated_idx
    on track_segments(account_id, updated_at desc);

create table track_points (
    id bigserial primary key,
    segment_id bigint not null references track_segments(id) on delete cascade,
    sequence integer not null,
    lat double precision not null,
    lng double precision not null,
    altitude double precision,
    speed double precision,
    recorded_at timestamptz,
    name text,
    raw jsonb,
    unique(segment_id, sequence)
);

create index track_points_segment_sequence_idx
    on track_points(segment_id, sequence);
