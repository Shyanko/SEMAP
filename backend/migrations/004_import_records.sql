create table import_records (
    id bigserial primary key,
    account_id bigint not null references accounts(id) on delete cascade,
    segment_id bigint not null references track_segments(id) on delete cascade,
    source_type text not null check (source_type in ('flight', 'train')),
    external_code text not null,
    request_payload jsonb not null,
    response_payload jsonb not null,
    status text not null,
    created_at timestamptz not null default now()
);

create index import_records_account_created_idx
    on import_records(account_id, created_at desc);
