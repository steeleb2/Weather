import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time
import pytz
from geopy.geocoders import Nominatim

st.set_page_config(page_title="MLB Game Weather", layout="wide")
st.title("🌦️ Today's MLB Game Weather Dashboard (Eastern Time & °F)")

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
    'Rate Field': 'Chicago',
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
    'George M. Steinbrenner Field': 'Tampa',
    'Sutter Health Park': 'Sacramento',
}

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

@st.cache_data(ttl=86400)
def get_lat_lon(city):
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
           f"&timezone=America/New_York")
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
                idx = 0
            temp = data["hourly"]["temperature_2m"][idx]
            precip = data["hourly"]["precipitation_probability"][idx]
            wind = data["hourly"]["windspeed_10m"][idx]
        return temp, precip, wind
    except Exception:
        return None, None, None

# Convert UTC to Eastern Time and nicely format
def format_to_eastern(dt_str):
    utc = pytz.utc
    eastern = pytz.timezone('US/Eastern')
    dt_utc = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utc)
    dt_eastern = dt_utc.astimezone(eastern)
    return dt_eastern.strftime("%Y-%m-%d %I:%M %p ET"), dt_eastern.hour

st.info("Fetching today's MLB games and weather data...")

games, raw_json = get_today_mlb_games()

if "error" in raw_json:
    st.error("Failed to load MLB schedule: " + raw_json["error"])
    st.stop()

st.write(f"Number of games scheduled for today: **{len(games)}**")
if len(games) == 0:
    st.warning("No MLB games scheduled for today (or failed to fetch the schedule).")
    st.json(raw_json)
else:
    st.write("Scheduled Games:")
    for g in games:
        local_time, _ = format_to_eastern(g["game_time"])
        st.write(f'- {g["away_name"]} @ {g["home_name"]} at {g["venue"]}, game time: {local_time}')

    game_data = []
    for g in games:
        ballpark = g["venue"]
        matchup = f'{g["away_name"]} @ {g["home_name"]}'
        game_time_str, game_hour_eastern = format_to_eastern(g["game_time"])
        city = MLB_BALLPARKS.get(ballpark)
        if not city:
            st.warning(f"Ballpark not mapped for weather lookup: {ballpark}")
            continue
        st.write(f"Looking up weather for {matchup} in {city}...")
        lat, lon = get_lat_lon(city)
        if not lat:
            st.warning(f"Failed to geocode city: {city}")
            continue
        # Pass the Eastern Time hour to get weather for correct local time
        # We'll adjust the dt to today's date and the ET hour for the forecast
        date = datetime.now(pytz.timezone("US/Eastern"))
        dt_for_weather = date.replace(hour=game_hour_eastern, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")
        temp_c, precip, wind_kmh = get_weather(lat, lon, dt_for_weather)
        if temp_c is None:
            st.warning(f"Failed to fetch weather for {matchup} ({city})")
        # Convert to Fahrenheit and mph
        temp_f = round(temp_c * 9/5 + 32, 1) if temp_c is not None else None
        wind_mph = round(wind_kmh * 0.621371, 1) if wind_kmh is not None else None
        game_data.append({
            "Matchup": matchup,
            "Ballpark": ballpark,
            "Location": city,
            "Game Time (ET)": game_time_str,
            "Temp (°F)": temp_f,
            "Precip (%)": precip,
            "Wind (mph)": wind_mph,
            "Link": g["link"]
        })
        time.sleep(0.3)

    df = pd.DataFrame(game_data)

    if df.empty:
        st.warning("Games scheduled, but failed to fetch weather data for all games. See above warnings.")
    else:
        st.dataframe(df)
        st.caption("Weather data from Open-Meteo (°F, mph). Game times shown in U.S. Eastern Time.")


