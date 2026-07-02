create table accounts (
    id bigserial primary key,
    username text not null unique check (length(username) between 3 and 64),
    password_hash text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
