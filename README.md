# League of Legends Performance Analytics

## Project Overview
This project is a personal analytics tool designed to extract, transform, and visualize League of Legends performance metrics. It focuses on macro and micro-analytical trends, specifically tracking Damage Per Minute (DPM) and Creep Score per Minute (CS/Min) over time to benchmark personal progression against predefined ranked tiers.

## Technical Architecture
* **Backend:** Python (Flask framework)
* **Database:** SQLite (Local persistence for match history and timeline data)
* **Frontend:** HTML, CSS, JavaScript (Chart.js for data visualization)
* **Integration:** Direct consumption of Riot Games API via HTTP requests.

## Riot API Endpoints Utilized
The system currently implements the following endpoints to aggregate user and match data:
* `Account-V1`: /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
* `Summoner-V4`: /lol/summoner/v4/summoners/by-puuid/{puuid}
* `Match-V5 (List)`: /lol/match/v5/matches/by-puuid/{puuid}/ids
* `Match-V5 (Timeline)`: /lol/match/v5/matches/{matchId}/timeline
* `Match-V5 (Details)`: /lol/match/v5/matches/{matchId}

## Data Usage & Storage
Match data is extracted periodically and stored locally within an SQLite database (`matches` and `match_timeline` tables) to minimize API call volume and optimize rendering speeds. No personal identifiable information (PII) other than public Riot IDs is processed or stored.

## Legal Disclaimer
[League of Legends Performance Analytics] isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.