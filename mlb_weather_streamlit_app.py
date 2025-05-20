import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time

st.set_page_config(page_title="MLB Game Weather", layout="wide")
st.title("🌦️ Today's MLB Game Weather Dashboard")

# MLB ballpark locations (city, state) mapping
MLB_BALLPARKS = {
    'Angel Stadium': 'Anaheim, CA',
    'Chase Field': 'Phoenix, AZ',
    'Citi Field': 'Flushing, NY',
    'Citizens Bank Park': 'Philadelphia, PA',
    'Comerica Park': 'Detroit, MI',
    'Coors Field': 'Denver, CO',
    'Dodger Stadium': 'Los Angeles, CA',
    'Fenway Park': 'Boston, MA',
    'Globe Life Field': 'Arlington, TX',
    'Great American Ball Park': 'Cincinnati, OH',
    'Guaranteed Rate Field': 'Chicago, IL',
    'Kauffman Stadium': 'Kansas City, MO',
    'loanDepot park': 'Miami, FL',
    'Minute Maid Park': 'Houston, TX',
    'Nationals Park': 'Washington, DC',
    'Oakland Coliseum': 'Oakland, CA',
    'Oracle Park': 'San Francisco, CA',
    'Oriole Park at Camden Yards': 'Baltimore, MD',
    'Petco Park': 'San Diego, CA',
    'PNC Park': 'Pittsburgh, PA',
    'Progressive Field': 'Cleveland, OH',
    'Rogers Centre': 'Toronto, ON',
    'T-Mobile Park': 'Seattle, WA',
    'Target Field': 'Minneapolis, MN',
    'Tropicana Field': 'St. Petersburg, FL',
    'Truist Park': 'Atlanta, GA',
    'Wrigley Field': 'Chicago, IL',
    'Yankee Stadium': 'Bronx, NY',
    'American Family Field': 'Milwaukee, WI',
    'Busch Stadium': 'St. Louis, MO'
}

# Helper: MLB Stats API for today's schedule
@st.cache_data(ttl=3600)
def get_today_mlb_games():
    today = datetime.now().strftime('%Y-%m-%d')
    url = f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}'
    r = requests.get(url)
    games = []
    try:
        data = r.json()
        for date in data['dates']:
            for game in date['games']:
                game_info = {
                    "home_name": game['teams']['home']['team']['name'],
                    "away_name": game['teams']['away']['team']['name'],
                    "venue": game['venue']['name'],
                    "game_time": game['gameDate'],
                    "link": f"https://www.mlb.com/gameday/{game['gamePk']}"
                }
                games.append(game_info)
    except Exception as e:
        st.warning("Error fetching MLB games: " + str(e))
    return games

# Helper: Geocode city/stadium to lat/lon (Open-Meteo geocoding, free and public)
@st.cache_data(ttl=86400)
def get_lat_lon(city):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
    r = requests.get(url)
    try:
        data = r.json()
        if data.get("results"):
            lat = data["results"][0]["latitude"]
            lon = data["results"][0]["longitude"]
            return lat, lon
    except Exception:
        return None, None
    return None, None

# Helper: Fetch weather forecast from Open-Meteo
def get_weather(lat, lon, dt):
    # dt is ISO8601 UTC (from MLB API), use hour in stadium's local time for forecast
    # For simplicity, use the next available hour if out of range
    date = pd.to_datetime(dt)
    date_str = date.strftime('%Y-%m-%d')
    hour = date.hour
    url = (f"https://api.open-meteo.com/v1/forecast?"
           f"latitude={lat}&longitude={lon}"
           f"&hourly=temperature_2m,precipitation_probability,weathercode,windspeed_10m"
           f"&start={date_str}T00:00"
           f"&end={date_str}T23:59"
           f"&timezone=auto")
    r = requests.get(url)
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
            idx = 0  # fallback
        temp = data["hourly"]["temperature_2m"][idx]
        precip = data["hourly"]["precipitation_probability"][idx]
        wind = data["hourly"]["windspeed_10m"][idx]
    return temp, precip, wind

st.info("Fetching today's MLB games and weather data...")

games = get_today_mlb_games()

game_data = []

for g in games:
    ballpark = g["venue"]
    matchup = f'{g["away_name"]} @ {g["home_name"]}'
    game_time = pd.to_datetime(g["game_time"]).strftime("%Y-%m-%d %I:%M %p")
    city = MLB_BALLPARKS.get(ballpark)
    if not city:
        continue  # Skip unknown parks
    lat, lon = get_lat_lon(city)
    if not lat:
        continue
    try:
        temp, precip, wind = get_weather(lat, lon, g["game_time"])
    except Exception:
        temp, precip, wind = None, None, None
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
    time.sleep(0.5)  # Nice to API

df = pd.DataFrame(game_data)

if df.empty:
    st.warning("No games found or failed to fetch weather data.")
else:
    st.dataframe(df)
    st.caption("Weather data from Open-Meteo. MLB games from MLB Stats API.")

