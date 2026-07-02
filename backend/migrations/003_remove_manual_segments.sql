do $$
declare
    constraint_name text;
begin
    for constraint_name in
        select conname
        from pg_constraint
        where conrelid = 'track_segments'::regclass
          and contype = 'c'
          and pg_get_constraintdef(oid) like '%source_type%'
    loop
        execute format('alter table track_segments drop constraint %I', constraint_name);
    end loop;

    alter table track_segments
        add constraint track_segments_source_type_check
        check (source_type in ('flight', 'train', 'gps'));
end $$;
