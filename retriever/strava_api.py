import os
import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv('STRAVA_CLIENT_ID')
athlete_id = os.getenv('STRAVA_ATHLETE_ID')
refresh_token = os.getenv('STRAVA_REFRESH_TOKEN')
client_secret = os.getenv('STRAVA_CLIENT_SECRET')


def get_access_token():
    """Échange le refresh token contre un access token frais."""
    response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    tokens = response.json()

    if "access_token" not in tokens:
        raise Exception(f"Erreur lors du refresh token : {tokens}")

    # Mettre à jour le refresh token si Strava en retourne un nouveau
    new_refresh_token = tokens.get("refresh_token")
    if new_refresh_token and new_refresh_token != refresh_token:
        _update_env_refresh_token(new_refresh_token)

    return tokens["access_token"]


def _update_env_refresh_token(new_token):
    """Met à jour le refresh token dans le .env si besoin."""
    env_path = ".env"
    with open(env_path, "r") as f:
        lines = f.readlines()

    with open(env_path, "w") as f:
        for line in lines:
            if line.startswith("STRAVA_REFRESH_TOKEN"):
                f.write(f"STRAVA_REFRESH_TOKEN={new_token}\n")
            else:
                f.write(line)


def create_activity(access_token, payload):
    url = f"https://www.strava.com/api/v3/activities"
    headers = {"Authorization": "Bearer " + access_token}
    response = requests.request("POST", url=url, headers=headers, data=payload)
    data = response.json()
    return data


def get_activity_by_id(access_token, activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": "Bearer " + access_token}
    response = requests.request("GET", url=url, headers=headers)
    data = response.json()
    return data


def get_comments(access_token, activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}/comments?page=1&per_page=200"
    headers = {"Authorization": "Bearer " + access_token}
    response = requests.request("GET", url=url, headers=headers)
    data = response.json()
    return data


def get_kudos(access_token, activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}/kudos?page=1&per_page=200"
    headers = {"Authorization": "Bearer " + access_token}
    response = requests.request("GET", url=url, headers=headers)
    data = response.json()
    return data


def get_activities(access_token, per_page, page):
    url = f"https://www.strava.com/api/v3/athlete/activities?per_page={per_page}&page={page}"
    headers = {"Authorization": "Bearer " + access_token}
    response = requests.request("GET", url=url, headers=headers)
    data = response.json()
    return data


def get_activity_streams(access_token, activity_id):
    """Récupère les streams détaillés d'une activité."""
    keys = "heartrate,velocity_smooth,altitude,temp"
    url = f"https://www.strava.com/api/v3/activities/{activity_id}/streams"

    response = requests.get(url,
                            headers={"Authorization": f"Bearer {access_token}"},
                            params={
                                "keys": keys,
                                "key_by_type": True
                            })
    return parse_streams(response.json())


def parse_streams(streams):
    """Extrait les données utiles des streams."""
    return {
        "heartrate": streams.get("heartrate", {}).get("data", []),
        "speed": streams.get("velocity_smooth", {}).get("data", []),  # en m/s
        "altitude": streams.get("altitude", {}).get("data", []),  # en mètres
        "temp": streams.get("temp", {}).get("data", []), # en °C
        "distance": streams.get("distance", {}).get("data", []) # en mètres
    }


def update_activity(access_token, activity_id, payload):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": "Bearer " + access_token}
    response = requests.request("PUT", url=url, headers=headers, data=payload)
    data = response.json()
    return data


def profile(access_token):
    url = f"https://www.strava.com/api/v3/athlete?access_token={access_token}"
    response = requests.request("GET", url=url)
    data = response.json()
    return data


def get_stats(access_token, athlete_id=athlete_id):
    url = f"https://www.strava.com/api/v3/athletes/{athlete_id}/stats?access_token={access_token}"
    response = requests.request("GET", url)
    data = response.json()
    return data
