import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time

# Fallback geocoder (geopy) for improved city lookup
from geopy.geocoders import Nominatim

st.set_page_config(page_title="MLB Game Weather", layout="wide")
st.title("🌦️ Today's MLB Game Weather Dashboard")

# Ballpark mapping: MLB venues and common alternates/spring training
MLB_BALLPARKS = {
    'Angel Stadium': 'Anaheim',
    'Chase Field': 'Phoenix',
    'Citi Field': 'Flushing',
    'Citizens Bank Park': 'Philadelphia',
    'Comerica Park': 'Detroit',
    'Coors Field': 'Denver',
    'Dodger Stadium': 'Los Angeles',
    'Fenway Park': 'Boston',
    'Globe Life Field': 'Arlington',
    'Great American Ball Park': 'Cincinnati',
    'Guaranteed Rate Field': 'Chicago',
    'Rate Field': 'Chicago',  # Sometimes abbreviated in API
    'Kauffman Stadium': 'Kansas City',
    'loanDepot park': 'Miami',
    'Minute Maid Park': 'Houston',
    'Nationals Park': 'Washington',
    'Oakland Coliseum': 'Oakland',
    'Oracle Park': 'San Francisco',
    'Oriole Park at Camden Yards': 'Baltimore',
    'Petco Park': 'San Diego',
    'PNC Park': 'Pittsburgh',
    'Progressive Field': 'Cleveland',
    'Rogers Centre': 'Toronto',
    'T-Mobile Park': 'Seattle',
    'Target Field': 'Minneapolis',
    'Tropicana Field': 'St. Petersburg',
    'Truist Park': 'Atlanta',
    'Wrigley Field': 'Chicago',
    'Yankee Stadium': 'New York',
    'American Family Field': 'Milwaukee',
    'Busch Stadium': 'St. Louis',
    # Spring training/neutral sites
    'George M. Steinbrenner Field': 'Tampa',
    'Sutter Health Park': 'Sacramento',
    # Add more venues as needed
}

# MLB Stats API for today's schedule
@st.cache_data(ttl=3600)
def get_today_mlb_games():
    today = datetime.now().strftime('%Y-%m-%d')
    url = f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}'
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        games = []
        for date in data.get('dates', []):
            for game in date.get('games', []):
                game_info = {
                    "home_name": game['teams']['home']['team']['name'],
                    "away_name": game['teams']['away']['team']['name'],
                    "venue": game['venue']['name'],
                    "game_time": game['gameDate'],
                    "link": f"https://www.mlb.com/gameday/{game['gamePk']}"
                }
                games.append(game_info)
        return games, data
    except Exception as e:
        return [], {"error": str(e)}

# Robust city geocoder: Try Open-Meteo, then geopy/Nominatim
@st.cache_data(ttl=86400)
def get_lat_lon(city):
    # First, try Open-Meteo geocoding API
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("results"):
            lat = data["results"][0]["latitude"]
            lon = data["results"][0]["longitude"]
            return lat, lon
    except Exception:
        pass
    # Fallback: geopy Nominatim
    try:
        geolocator = Nominatim(user_agent="mlb_weather_app")
        location = geolocator.geocode(city)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None

def get_weather(lat, lon, dt):
    date = pd.to_datetime(dt)
    date_str = date.strftime('%Y-%m-%d')
    hour = date.hour
    url = (f"https://api.open-meteo.com/v1/forecast?"
           f"latitude={lat}&longitude={lon}"
           f"&hourly=temperature_2m,precipitation_probability,weathercode,windspeed_10m"
           f"&start={date_str}T00:00"
           f"&end={date_str}T23:59"
           f"&timezone=auto")
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        temp = precip = wind = None
        if "hourly" in data and "time" in data["hourly"]:
            times = data["hourly"]["time"]
            idx = None
            for i, t in enumerate(times):
                if pd.to_datetime(t).hour == hour:
                    idx = i
                    break
            if idx is None:
                idx = 0  # Fallback: first hour
            temp = data["hourly"]["temperature_2m"][idx]
            precip = data["hourly"]["precipitation_probability"][idx]
            wind = data["hourly"]["windspeed_10m"][idx]
        return temp, precip, wind
    except Exception:
        return None, None, None

st.info("Fetching today's MLB games and weather data...")

games, raw_json = get_today_mlb_games()

if "error" in raw_json:
    st.error("Failed to load MLB schedule: " + raw_json["error"])
    st.stop()

st.write(f"Number of games scheduled for today: **{len(games)}**")
if len(games) == 0:
    st.warning("No MLB games scheduled for today (or failed to fetch the schedule).")
    st.json(raw_json)  # Show the actual data returned by MLB API for debugging
else:
    # Print all scheduled games for transparency
    st.write("Scheduled Games:")
    for g in games:
        st.write(f'- {g["away_name"]} @ {g["home_name"]} at {g["venue"]}, game time: {g["game_time"]}')

    game_data = []
    for g in games:
        ballpark = g["venue"]
        matchup = f'{g["away_name"]} @ {g["home_name"]}'
        game_time = pd.to_datetime(g["game_time"]).strftime("%Y-%m-%d %I:%M %p")
        city = MLB_BALLPARKS.get(ballpark)
        if not city:
            st.warning(f"Ballpark not mapped for weather lookup: {ballpark}")
            continue  # Skip unknown parks
        st.write(f"Looking up weather for {matchup} in {city}...")
        lat, lon = get_lat_lon(city)
        if not lat:
            st.warning(f"Failed to geocode city: {city}")
            continue
        temp, precip, wind = get_weather(lat, lon, g["game_time"])
        if temp is None:
            st.warning(f"Failed to fetch weather for {matchup} ({city})")
        game_data.append({
            "Matchup": matchup,
            "Ballpark": ballpark,
            "Location": city,
            "Game Time": game_time,
            "Temp (°C)": temp,
            "Precip (%)": precip,
            "Wind (km/h)": wind,
            "Link": g["link"]
        })
        time.sleep(0.3)  # Respect APIs

    df = pd.DataFrame(game_data)

    if df.empty:
        st.warning("Games scheduled, but failed to fetch weather data for all games. See above warnings.")
    else:
        st.dataframe(df)
        st.caption("Weather data from Open-Meteo (or geopy fallback). MLB games from MLB Stats API.")
