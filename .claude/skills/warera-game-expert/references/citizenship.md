# Citizenship

## Rules `[RULE]`

- Citizenship change cooldown: **30 days** `[LIVE]` (5 days when introduced in v0.17.1). You can't change citizenship while an
  election candidate or a member of a government. Taking over an inactive country ignores the citizenship cooldown `[WIKI-ONLY]`.
- An approved application automatically drops the former citizenship.
- The country is chosen **on the sign-up screen**, before the account exists; the selector is pre-filled from your location and
  shows the chosen country's welcome article. The player is added to the country chat from the start (previously only after the
  welcome window `[DEPRECATED]`).
- Citizenship applications are managed only by the **President and Vice President**.
- Live: auto-approval enabled for countries with population ≤ 5 (`citizenshipApplication.autoApprovalMaxPopulation`); also automatic
  during the 7 open-border days after a successful revolution.
- Who manages applications: President and VP (guide); the wiki government page also lists the Minister of Defense `[CONFLICT]`.
- Voting requires ≥ 7 days since the last citizenship change `[LIVE]`. `[VERSIONED]` Since v0.27.4 (2026-11-02), during a **new
  country's first 14 days** its new citizens can vote right away (config `election.voteCitizenshipLockNewCountryMultiplier` 2,
  i.e. 2 × 7 days *[Derived]*). A "new country" is a brand-new country added to the game (U-V27-19); whether a country freed by a
  revolution counts isn't stated `[GAP]`. Registry: `election.vote_citizenship_lock`.
- `[OBS]` In presidential/congress elections, a player who moved country can vote in the new one only if they didn't already
  vote in the old one.
- A country needs ≥ 10 citizens to send/receive money (bounties/contracts excepted).
- New citizens joining during a revolt raise the resistance cap and lower the bonus `[OBS]`.

## Romanian policy `[POLICY-RO]`

- A recruit brought by the Romanian community must select **Romania before signing up**; otherwise they land elsewhere and face
  the 30-day cooldown. Send the link with this instruction in recruitment campaigns.
- Unexpected citizenship applications to a proxy are reported **before** acceptance (Scenario E).
- Don't change citizenship impulsively: it affects elections, bonuses and proxies.

Procedure detail for applications (UI flow, criteria) is `[GAP]`.
