import json
import os

import pandas as pd
from retriever import strava_api
from datalake import duckDB_utils as duckDB
from math_utils import power_utils
from models import model_physio
from visualisation import energy_plot

RESET_DB = True
MAX_ACTIVITY_TO_RETRIEVE = 3
RETRIEVE_ALL_RIDE = True
access_token = strava_api.get_access_token()


def retrieve_all():
    if RESET_DB:
        os.remove("./datalake/activities.db")
    duckDB.init_connection()
    # Save athletes
    with open("./datalake/athletes.json", "r") as f:
        all_athletes = json.load(f)
        all_athletes = pd.DataFrame(all_athletes)
        duckDB.create_all_athletes(all_athletes)
    all_rides = []
    all_stats = strava_api.get_stats(access_token=access_token)
    activities_count = all_stats['all_ride_totals']['count']
    i = 0
    j = 0
    if (RETRIEVE_ALL_RIDE):
        while i < activities_count / 100:
            all_activities_by_page = strava_api.get_activities(access_token=access_token, per_page=100, page=i)
            # Garder uniquement les éléments qui sont des dicts (les vraies activités)
            all_activities_by_page = [item for item in all_activities_by_page if isinstance(item, dict)]
            all_activities_by_page = [item for item in all_activities_by_page if item['sport_type'] == 'Ride']
            all_rides.extend(all_activities_by_page)
            i += 1

        with open("./datalake/all_activities.json", "w") as f:
            json.dump(all_rides, f, indent=2)
    else:
        with open("./datalake/all_activities.json", "r") as f:
            all_rides = json.load(f)

    # Construit les streams des activites
    while j < MAX_ACTIVITY_TO_RETRIEVE:
        all_rides[j]['name'] = all_rides[j]['name'].encode('utf-8', errors='replace').decode('utf-8').replace(' ', '_') + '_' + all_rides[j]['start_date_local'].split("T")[0]
        print('activity name', all_rides[j]['name'])
        activity_id = all_rides[j]['id']
        athlete_local_info = all_athletes[all_athletes['id'] == all_rides[j]['athlete']['id']].iloc[0]
        activity_stream = strava_api.get_activity_streams(access_token=access_token, activity_id=activity_id)
        # Compute power
        stream_power = []
        for i in range(len(activity_stream['speed'])):
            if i < len(activity_stream['distance']) - 1 and activity_stream['distance'][i + 1] - activity_stream['distance'][i] != 0.0:
                gradient = ((activity_stream['altitude'][i + 1] - activity_stream['altitude'][i]) /
                        (activity_stream['distance'][i + 1] - activity_stream['distance'][i])) * 100
            else:
                gradient = 0

            power_computed = power_utils.compute_power(
                speed_ms=activity_stream['speed'][i],
                gradient=gradient,
                mass_kg=athlete_local_info['weight'],
                altitude_m=activity_stream['altitude'][i],
                temp_celsius=activity_stream['temp'][i] if activity_stream['temp'] else 20,
            )
            stream_power.append(power_computed['power_total_w'])

        activity_stream['power'] = stream_power
        all_rides[j]['activity_stream'] = activity_stream

        # Generate energie calculation based on a physio model
        CTL = 50  # TODO Charge Chronique à déterminé
        FTP_WATTS = 250  # TODO à determiné ton FTP en watts
        df_streams = pd.DataFrame(activity_stream)
        df_streams['timestamp'] = range(len(df_streams)) #Ajout d'un timestamp pour chaque point TODO précision du timestamp ... ici 1 point = 1 seconde
        df_result = model_physio.run_energy_model(df_streams, athlete_local_info['weight'], FTP_WATTS, CTL)
        energy_plot.plot_energy_model(df_result,
                                      output_path="report/energy_report_{}.html".format(all_rides[j]['name']))
        j += 1
    all_rides = pd.DataFrame(all_rides)
    # Clean Data
    all_activities_stats = all_rides.loc[:, ['id', 'name', 'distance', 'moving_time']]
    all_activities_stats['athlete_id'] = pd.json_normalize(all_rides['athlete'])['id']
    duckDB.create_all_activities(all_activities_stats)
    # Create child table
    activity_stream_df = pd.json_normalize(all_rides['activity_stream'])
    activity_stream_df['activity_id'] = all_rides['id'].values

    duckDB.create_all_activity_streams(activity_stream_df)
    duckDB.close_con()

