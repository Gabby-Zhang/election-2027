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

-- ── 候选人档案(首页总览大主页用)────────────────────────────────────────────
-- camp 取值:far-left / center-left / center-right / far-right(决定阵营分组与配色)
-- poll_name 必须等于 polls.candidate 里的姓氏(如 Mélenchon),首页据此实时算民调
create table if not exists candidates (
  id          bigint generated always as identity primary key,
  name        text not null unique,           -- 中文显示名,如 梅朗雄
  poll_name   text,                            -- = polls.candidate 姓氏,如 Mélenchon
  party       text,                            -- 党派显示文本,如 "LFI 不屈法国"
  camp        text not null
              check (camp in ('far-left','center-left','center-right','far-right')),
  declared    boolean not null default false,  -- 是否已正式宣布参选
  declared_on date,                            -- 宣布日期(declared 时填)
  bio         text,                            -- 一句话身份/政绩简介(背景,如 "马克龙首任总理…")
  issues      text[] default '{}',             -- 招牌议题 chips
  note        text,                            -- 一行当前动态点评(如 "数字城案" / "三个月窗口")
  avatar_url  text,                            -- 头像图 URL(维基头像);空则首页降级为姓名首字圆形
  sort_order  int not null default 0,          -- 同阵营内排序,大在前
  active      boolean not null default true,   -- 下架不删(战绩文化)
  created_at  timestamptz default now()
);
create index if not exists candidates_camp_idx on candidates (camp, sort_order desc);
-- 已建过表的库补列:
alter table candidates add column if not exists avatar_url text;
alter table candidates add column if not exists bio text;

-- ── Catalyst Events 催化事件(首页待观察事件时间线)──────────────────────────
create table if not exists timeline_events (
  id          bigint generated always as identity primary key,
  event_date  date not null,
  title       text not null,                   -- 如 "雷塔约 · 花卉公园首场大集会"
  candidate   text,                            -- 关联候选人中文名(可空)
  camp        text,                            -- 关联阵营(可空,决定日期色)
  description text,
  status      text not null default 'upcoming'
              check (status in ('upcoming','past')),
  created_at  timestamptz default now()
);
create index if not exists timeline_date_idx on timeline_events (event_date);

-- ── RLS:全部开启,anon 只读 ─────────────────────────────────────────────────
alter table polls           enable row level security;
alter table analysis_posts  enable row level security;
alter table predictions     enable row level security;
alter table site_config     enable row level security;
alter table candidates      enable row level security;
alter table timeline_events enable row level security;

drop policy if exists "anon read polls"           on polls;
drop policy if exists "anon read analysis_posts"  on analysis_posts;
drop policy if exists "anon read predictions"     on predictions;
drop policy if exists "anon read site_config"     on site_config;
drop policy if exists "anon read candidates"      on candidates;
drop policy if exists "anon read timeline_events" on timeline_events;

create policy "anon read polls"           on polls           for select using (true);
create policy "anon read analysis_posts"  on analysis_posts  for select using (true);
create policy "anon read predictions"     on predictions     for select using (true);
create policy "anon read site_config"     on site_config     for select using (true);
create policy "anon read candidates"      on candidates      for select using (true);
create policy "anon read timeline_events" on timeline_events for select using (true);
