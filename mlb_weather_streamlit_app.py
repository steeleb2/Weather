import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

st.set_page_config(page_title="MLB Game Weather", layout="wide")
st.title("🌦️ Today's MLB Game Weather Dashboard")

# Helper: Get today's MLB games from Baseball-Reference
@st.cache_data(ttl=3600)
def get_today_mlb_games():
    url = "https://www.baseball-reference.com/boxes/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')

    # Find all links to today's games
    today = datetime.now().strftime("%Y-%m-%d")
    games = []
    for link in soup.select("a[href^='/boxes/']"):
        href = link.get('href')
        if href.endswith('.shtml') and today in href:
            games.append("https://www.baseball-reference.com" + href)
    return games

# Helper: Scrape city/stadium from a game's Baseball-Reference page
@st.cache_data(ttl=3600)
def get_game_location(game_url):
    r = requests.get(game_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    # Stadium info
    stadium = soup.find('div', {'itemtype': 'https://schema.org/Stadium'})
    if not stadium:
        return None, None
    location = stadium.find('span', {'itemprop': 'addressLocality'})
    state = stadium.find('span', {'itemprop': 'addressRegion'})
    ballpark = stadium.find('strong')
    if not location or not state or not ballpark:
        return None, None
    city_state = f"{location.text}, {state.text}"
    ballpark = ballpark.text
    return city_state, ballpark

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
def get_weather(lat, lon):
    now = datetime.now()
    url = (f"https://api.open-meteo.com/v1/forecast?"
           f"latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation,weathercode,windspeed_10m"
           f"&start={now.strftime('%Y-%m-%dT00:00')}&end={now.strftime('%Y-%m-%dT23:59')}&timezone=America/New_York")
    r = requests.get(url)
    data = r.json()
    # Use the next game-time hour (approximate as 7pm)
    idx = 19  # 7pm = index 19 (start at 0)
    temp = data["hourly"]["temperature_2m"][idx]
    precip = data["hourly"]["precipitation"][idx]
    wind = data["hourly"]["windspeed_10m"][idx]
    return temp, precip, wind

st.info("Fetching today's MLB games and weather data...")

games = get_today_mlb_games()

game_data = []

for game_url in games:
    city_state, ballpark = get_game_location(game_url)
    if not city_state:
        continue
    lat, lon = get_lat_lon(city_state)
    if not lat:
        continue
    try:
        temp, precip, wind = get_weather(lat, lon)
    except Exception:
        temp, precip, wind = None, None, None
    # Extract team matchup from URL
    matchup = game_url.split("/")[-1].replace(".shtml", "")
    away_team = matchup[:3].upper()
    home_team = matchup[4:7].upper()
    game_data.append({
        "Matchup": f"{away_team} @ {home_team}",
        "Ballpark": ballpark,
        "Location": city_state,
        "Temp (°F)": temp,
        "Precip (%)": precip,
        "Wind (mph)": wind,
        "Link": game_url
    })
    time.sleep(1)  # Be polite to APIs

df = pd.DataFrame(game_data)

if df.empty:
    st.warning("No games found or failed to fetch weather data.")
else:
    st.dataframe(df)

    st.caption("Weather data from Open-Meteo. MLB games from Baseball-Reference.")
