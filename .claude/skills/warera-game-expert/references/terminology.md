# Terminology (Romanian source → English)

Prefer the official English UI term when known. Item codes are from the live config (`items.*`).

## Game objects

| Romanian (guide) | English (use this) | Code / note |
|---|---|---|
| Unitate Militară (UM) | Military Unit (MU) | |
| Sediu Central | Headquarters (HQ) | MU upgrade `headquarters` |
| Dormitoare | Dormitories | MU upgrade `dormitories` |
| Buncăr | Bunker | region upgrade `bunker` |
| Bază Militară | Military Base | region upgrade `base` |
| Centru de Pacificare | Pacification Center | region upgrade `pacificationCenter` |
| Motor Automat (AE) | Automated Engine (AE) | company upgrade `automatedEngine` |
| Magazie | Storage | company upgrade `storage` |
| (not in guide) | Break Room | company upgrade `breakRoom` (max workers; from v0.27 max employees, 1–3) |
| (v0.27) | Employee, candidate, trait, Training Potential, happiness, tool, toolbox | hired company workers (game characters) — see employees-and-wages.md |
| (v0.27) | Manager | player hired to run another player's company |
| (v0.27) | Government type — Provisional, Republic, Nationalist State, Homeland Front, Federation, Plutocracy, Autocracy, Mercenary State | replaces party ethics — see government-types.md |
| Hârtie | Paper | `paper` |
| Petrol | Oil | `oil` |
| Țiței | Petroleum (crude) | `petroleum` |
| Beton / Calcar | Concrete / Limestone | `concrete` / `limestone` |
| Oțel / Fier | Steel / Iron | `steel` / `iron` |
| Plumb | Lead | `lead` |
| Lemn | Wood | `wood` |
| Cereale / Pâine | Grain / Bread | `grain` / `bread` |
| Animale / Friptură | Livestock / Steak | `livestock` / `steak` |
| Pește / Pește prăjit | Fish / Cooked Fish | `fish` / `cookedFish` |
| Plantă Misterioasă | Mysterious Plant | `coca` |
| Pastilă | Pill | `cocain` (config spelling) |
| Muniție ușoară / Muniție / Muniție grea | Light Ammo / Ammo / Heavy Ammo | `lightAmmo` / `ammo` / `heavyAmmo` |
| Cutie / Cutie de elită | Case / Elite Case | `case1` / `case2` (mapping assumed) |
| Cutie de lemn | Wooden Case | `woodenCase` |
| Resturi | Scrap | `scraps` |
| Cuțit / Pistol / Pușcă | Knife / Gun / Rifle | `knife` / `gun` / `rifle`; also `sniper`, `tank`, `jet` |
| Cască / Vestă / Pantaloni / Mănuși / Cizme | Helmet / Chest (vest) / Pants / Gloves / Boots | `helmetN` … tier N = rarity |
| Bani | Money = **Coins** (in game sometimes "btc") | Gems = premium currency |
| Common / Uncommon / Rare / Epic | wiki tiers: Basic / Reinforced / Advanced / Elite (then Legendary, Mythic) | |

## Skills (Competențe)

| Romanian | English | Config key |
|---|---|---|
| Energie | Energy | `energy` |
| Antreprenoriat | Entrepreneurship (removed in v0.27) | `entrepreneurship` |
| (v0.27 → v0.27.2) | Leadership (merged into Management in v0.27.3) | `leadership` (assumed key) |
| Producție | Production | `production` |
| Limita de companii | Companies (company limit) | `companies` |
| Management | Management | `management` |
| Atac | Attack | `attack` |
| Precizie | Precision | `precision` |
| Șansă Critică | Critical Chance | `criticalChance` |
| Daune Critice | Critical Damage | `criticalDamages` |
| Armură | Armor | `armor` |
| Eschivă | Dodge | `dodge` |
| Viață | Health | `health` |
| Foame | Hunger | `hunger` |
| Șansă de Pradă / Noroc | Loot Chance (Luck) | `lootChance` |
| Stamina | Stamina | `stamina` |

## Battle and politics

| Romanian | English |
|---|---|
| Pradă | Loot |
| Recompensă (bounty) | Bounty (public damage fund) |
| Contract mercenar / licitație | Mercenary contract / reverse auction |
| Ordin de Țară / de UM | Country order / MU order |
| Prioritate Low/Medium/High (verde/galben/roșu) | Priority Low/Medium/High (green/yellow/red) |
| Rangul ordinului (#1, #2) | Order rank (display order) |
| Rundă / tick / teren | Round / tick / terrain (ground) |
| Bonus Patriotic | Patriotic bonus |
| Pact Defensiv | Defensive Pact |
| Inamic Principal | Main Enemy = **Sworn Enemy** (official/wiki term; config: "enemy") |
| Alianță | Alliance |
| Dezvoltare mondială | World Development (share) |
| Acord de neagresiune (NAP) | Non-Aggression Pact (NAP) — community agreement |
| Regiune core/centrală | Core region |
| Rezistență / revoltă | Resistance / revolt |
| Tensiune internă / război civil | Unrest / civil war |
| Etică (partid) | Ethic (party) — Diplomatic, Isolationist, Industrialist, Agrarian, Expansionist, Pacifist, Imperialist, Republican (+ Fanatic versions), Unethical — see parties-and-ethics.md; removed in v0.27 (→ government types) |
| Motiune de revoluție | Start Revolution (party motion) |
| Linie de aprovizionare | Supply line (capital link) |
| Președinte / Vicepreședinte | President / Vice President |
| MoFA / MoD / MoE / MoIA | Minister of Foreign Affairs / Defense / Economy (permission table: Finance) / Internal Affairs |
| Congres | Congress |
| Cetățenie | Citizenship |
| Reședință / Move home | Residence (home) / Move home |
| Grup de familie | Family Group |
| Reskill / respec | Skill reset (respec) |
| Build Eco / Fight | Economy build / Fight (war) build |
| Cod Galben/Portocaliu | Yellow/Orange alert code — Romanian policy, **definitions not in sources** |

## Abbreviations

PP production points · AE Automated Engine · MU Military Unit · WD World Development · EV expected value ·
NAP non-aggression pact · TheMachine = Romanian Discord bot · cost/1k = money per 1,000 damage.
