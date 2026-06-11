-- 2027 大选站建表脚本
-- 在 Supabase Dashboard → SQL Editor 里整段执行一次即可。
-- 权限模型与 sa-archive 一致:RLS 开启,anon 只读,写操作一律走 service key。

-- ── 民调表 ────────────────────────────────────────────────────────────────
create table if not exists polls (
  id              bigint generated always as identity primary key,
  source          text not null,            -- 民调机构 Ipsos / Ifop / ...
  poll_date       date not null,            -- = fieldwork_end,排序与去重用
  fieldwork_start date,
  fieldwork_end   date,
  sample_size     int,
  candidate       text not null,            -- 候选人姓氏,如 Attal
  party           text,                     -- 政党缩写,如 RE
  score           numeric(5,2) not null,
  round           smallint not null default 1,
  scenario        text not null,            -- 精确场景:该行全部参选人
  scenario_group  text,                     -- 简化分组,如 "Attal × Bardella"
  source_url      text,
  created_at      timestamptz default now(),
  unique (source, poll_date, candidate, round, scenario)
);
create index if not exists polls_group_idx on polls (round, scenario_group, poll_date);

-- ── 研判文章表 ─────────────────────────────────────────────────────────────
create table if not exists analysis_posts (
  id         bigint generated always as identity primary key,
  date       date not null default current_date,
  title      text not null,
  body_md    text not null,
  tags       text[] default '{}',
  author     text not null default '匿名',
  evidence   jsonb default '[]',            -- [{"type":"url","value":"...","note":".."}]
  created_at timestamptz default now()
);

-- ── 预测表(落空的预测永不删除——战绩文化)──────────────────────────────────
create table if not exists predictions (
  id              bigint generated always as identity primary key,
  statement       text not null,
  author          text not null default '匿名',
  confidence      smallint check (confidence between 0 and 100),
  made_on         date not null default current_date,
  deadline        date,
  status          text not null default 'open'
                  check (status in ('open', 'correct', 'wrong', 'partial')),
  resolution_note text,
  resolved_on     date,
  created_at      timestamptz default now()
);

-- ── 站点配置(本周形势速览等)────────────────────────────────────────────────
create table if not exists site_config (
  key        text primary key,
  value      text,
  updated_at timestamptz default now()
);

-- ── RLS:全部开启,anon 只读 ─────────────────────────────────────────────────
alter table polls          enable row level security;
alter table analysis_posts enable row level security;
alter table predictions    enable row level security;
alter table site_config    enable row level security;

drop policy if exists "anon read polls"          on polls;
drop policy if exists "anon read analysis_posts" on analysis_posts;
drop policy if exists "anon read predictions"    on predictions;
drop policy if exists "anon read site_config"    on site_config;

create policy "anon read polls"          on polls          for select using (true);
create policy "anon read analysis_posts" on analysis_posts for select using (true);
create policy "anon read predictions"    on predictions    for select using (true);
create policy "anon read site_config"    on site_config    for select using (true);
