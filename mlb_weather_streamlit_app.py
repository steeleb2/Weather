import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# Configuration
VC_API_KEY = os.getenv("VC_API_KEY")
MLB_SCHEDULE_URL = (
    "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}"
)

# Stadium coordinates mapping (add all MLB stadiums here)
# Stadium coordinates mapping (all 30 MLB parks)
STADIUM_COORDS = {
    "Oriole Park at Camden Yards": (39.2839, -76.6217),
    "Fenway Park": (42.3467, -71.0972),
    "Tropicana Field": (27.7687, -82.6534),
    "Yankee Stadium": (40.8296, -73.9262),
    "Citi Field": (40.7571, -73.8458),
    "Rogers Centre": (43.6414, -79.3894),
    "Citizens Bank Park": (39.9061, -75.1664),
    "Nationals Park": (38.8730, -77.0074),
    "Truist Park": (33.8903, -84.4678),
    "loanDepot Park": (25.7781, -80.2199),
    "PNC Park": (40.4468, -80.0059),
    "Guaranteed Rate Field": (41.8308, -87.6333),
    "Progressive Field": (41.4961, -81.6853),
    "Comerica Park": (42.3390, -83.0485),
    "Kauffman Stadium": (39.0510, -94.4803),
    "Target Field": (44.9817, -93.2775),
    "Wrigley Field": (41.9484, -87.6553),
    "Great American Ball Park": (39.0970, -84.5060),
    "American Family Field": (43.0286, -87.9711),
    "Busch Stadium": (38.6226, -90.1928),
    "T-Mobile Park": (47.5914, -122.3325),
    "Angel Stadium": (33.8003, -117.8827),
    "Dodger Stadium": (34.0739, -118.2400),
    "Globe Life Field": (32.7519, -97.0821),
    "Coors Field": (39.7562, -104.9942),
    "Chase Field": (33.4455, -112.0667),
    "Petco Park": (32.7073, -117.1567),
    "Oracle Park": (37.7786, -122.3893),
    "Oakland Coliseum": (37.7516, -122.2005),
    "Minute Maid Park": (29.7573, -95.3554),
}


def get_todays_schedule():
    today = datetime.now().strftime("%Y-%m-%d")
    url = MLB_SCHEDULE_URL.format(date=today)
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            home = game["teams"]["home"]["team"]["name"]
            away = game["teams"]["away"]["team"]["name"]
            game_time = game["gameDate"]
            venue_name = game.get("venue", {}).get("name")
            lat, lon = STADIUM_COORDS.get(venue_name, (None, None))

            games.append({
                "Home": home,
                "Away": away,
                "Game Time (UTC)": game_time,
                "Venue": venue_name,
                "Latitude": lat,
                "Longitude": lon,
            })

    return pd.DataFrame(games)


def get_weather(lat, lon):
    if lat is None or lon is None:
        return {"Temperature": None, "Humidity": None, "Conditions": None}

    # Use the Timeline endpoint for reliable current conditions
    vc_url = (
        f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/"
        f"timeline/{lat},{lon}?unitGroup=us&key={VC_API_KEY}&contentType=json"
    )
    resp = requests.get(vc_url)
    resp.raise_for_status()
    data = resp.json()

    # Extract current conditions
    current = data.get("currentConditions", {})

    return {
        "Temperature": current.get("temp"),
        "Humidity": current.get("humidity"),
        "Conditions": current.get("conditions"),
    }


def main():
    st.title("MLB Daily Games & Weather")

    st.markdown(
        "This app fetches today's MLB schedule and displays current weather at each stadium."
    )

    df_games = get_todays_schedule()
    weather_data = df_games.apply(
        lambda row: pd.Series(get_weather(row.Latitude, row.Longitude)), axis=1
    )

    df_display = pd.concat([df_games, weather_data], axis=1)
    st.dataframe(df_display)


if __name__ == "__main__":
    main()