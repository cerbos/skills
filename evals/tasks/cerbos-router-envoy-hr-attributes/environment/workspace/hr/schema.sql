-- HR database (read replica available at hr-replica.internal:5432, database hr)
create table people (
  okta_user_id     text primary key,        -- matches the token's sub
  email            text not null unique,
  employment_type  text not null check (employment_type in ('employee', 'contractor', 'intern')),
  department       text not null,
  active           boolean not null default true,
  updated_at       timestamptz not null default now()
);
