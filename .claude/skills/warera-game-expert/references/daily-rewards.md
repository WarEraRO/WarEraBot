# Daily login, streak and comeback rewards

## 7-day calendar `[RULE]` (`rewards.daily_login_calendar`)

| Day | XP | Money | Cases | Extra |
|---|---|---|---|---|
| 1 | 10 | 5 | 1 | |
| 2 | 10 | 10 | 1 | |
| 3 | 10 | 15 | 1 | |
| 4 | 10 | 20 | 2 | |
| 5 | 10 | 25 | 2 | |
| 6 | 10 | 30 | 2 | |
| 7 | 10 | 35 → **50** from v0.27 | 3 | 10 gems (jackpot) |

Week total: 70 XP, 140 money (**155** from v0.27, 2026-10-26), 12 cases, 10 gems. The claim window opens automatically at login and shows how many players
claimed that day. After day 7 the calendar restarts at day 1.

`[CONFLICT]` Live config has `user.dailyReward = {xp: 50, money: 10, case1: 1}`; its relationship to the calendar is unknown.
Do not use it to override the calendar.

## Streak `[RULE]`

Consecutive login days. The rewards page shows calendar position, current streak and best streak. The streak keeps
counting after the calendar restarts. `[STRAT-RO]` On a busy day, a short login keeps the streak and lets you claim already
completed missions.

## Comeback rewards `[RULE]` (`rewards.comeback`)

| Absence | XP | Money | Cases |
|---|---|---|---|
| ≥ 3 days | 150 | 50 | 2 |
| ≥ 7 days | 400 | 150 | 3 |
| ≥ 30 days | 800 | 400 | 5 |

At most once every 14 days. They soften but never compensate lost mission XP (a missed week alone loses up to
200×7 + 1,000 mission XP).
