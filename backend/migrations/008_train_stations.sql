create table train_stations (
    id bigserial primary key,
    name text not null unique,
    telecode text,
    pinyin text,
    short_pinyin text,
    sequence_no integer,
    city text,
    lat double precision,
    lng double precision,
    coordinate_source text,
    coordinate_status text not null default 'missing' check (coordinate_status in ('missing', 'verified', 'rejected')),
    coordinate_query text,
    coordinate_raw jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check ((lat is null and lng is null) or (lat is not null and lng is not null))
);

create index train_stations_coordinate_status_idx
    on train_stations(coordinate_status);

create index train_stations_telecode_idx
    on train_stations(telecode);
