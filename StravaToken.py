from datetime import date, timedelta
import time
import csv
import sys
import argparse

import requests
import pandas as pd

class Credentials:
    """
    Class for API authentication
    
    Attributes: 
        client_id (str): Client ID for API authentication. 
        client_secret (str): Client secret for API authentication. 
        access_token (str): Access token for accessing API resources. 
        refresh_token (str): Refresh token used to obtain new access tokens. 
        club_id (str): Identifier for the associated club.
    """
    def __init__(self, credentials:dict):
        self.client_id = credentials.get("client_id")
        self.client_secret = credentials.get("client_secret")
        self.access_token = credentials.get("access_token")
        self.refresh_token = credentials.get("refresh_token")
        self.club_id = credentials.get("club_id")
        
    def replace_old_tokens(self, new_tokens:dict):
        self.access_token = new_tokens.get("access_token")
        self.refresh_token = new_tokens.get("refresh_token")
        self.expires_at = new_tokens.get("expires_at")
        self.expires_in = new_tokens.get("expires_in")

    ## Debug
    def __str__(self):
        return (f"client_id: {self.client_id}\n"
                f"client_secret: {self.client_secret}\n"
                f"access_token: {self.access_token}\n"
                f"refresh_token: {self.refresh_token}\n"
                f"club_id: {self.club_id}\n")
        

class StravaToken:
    def __init__(self, credentials: dict, output_file: str):
        self.credentials = Credentials(credentials=credentials)
        self.output_file = output_file
    
    # Post method to refresh the current access_token and refresh_token
    def refresh_access_token(self):
        response = requests.post('https://www.strava.com/oauth/token', 
                                data={
                                    'client_id': self.credentials.client_id,
                                    'client_secret': self.credentials.client_secret,
                                    'grant_type': "refresh_token",
                                    'refresh_token': self.credentials.refresh_token
                                },
                                timeout=5)
        
        if response.status_code is requests.codes.ok:
            cred_decoded:dict = response.json()

            self.credentials.replace_old_tokens(cred_decoded)
        else:
            raise ConnectionError(f"Request refresh tokens from Strava failed: {response.reason}\n",
                                  f" {response.text}\n")

    ###
    # Get method https://www.strava.com/api/v3/clubs/# for activity data of the 30 most recent public activities in the club.
    # Stored in the given output_file as a csv.
    #   Receives activities based on the most recent public activities visible in the club.
    #   i.e club type (sport_type) is of 'ride': Will receive public activities of members who have posted with activity type 'ride' within the club
    #       club type (sport_type) is of 'run: Will receive public activities of members who have posted with activity type 'run' within the club
    def club_data(self):
        """
        Get method https://www.strava.com/api/v3/clubs/# for activity data of the 30 most recent public activities in the club.\n
        Stored in the given output_file as a csv.\n
        Receives activities based on the most recent public activities visible in the club\n
        i.e club type (sport_type) is of 'ride': Will receive public activities of members who have posted with activity type 'ride' within the club\n
            club type (sport_type) is of 'run: Will receive public activities of members who have posted with activity type 'run' within the club 
        """
        response = requests.get(f'https://www.strava.com/api/v3/clubs/{self.credentials.club_id}/activities',
                                headers={'Authorization': f'Authorization: Bearer {self.credentials.access_token}'},
                                timeout=5)
        if response.status_code != requests.codes.ok:
            raise ConnectionError(f"Request club activities cannot be made to Strava: {response.reason}\n",
                                  f" {response.text}\n")
        
        df = pd.DataFrame
        headers = ["date","firstname","lastname","title","distance","moving_time","elapsed_time","total_elevation_gain","type","sport_type","workout_type"]
        try:
            df = pd.read_csv(self.output_file)
        except:
            df = pd.DataFrame(columns=headers)

        check_data = df[["firstname", "lastname", "title", "distance"]]
        new_activity = []

        for activity in response.json():
            test = check_data[(check_data["firstname"]==activity.get('athlete').get('firstname')) &
                            (check_data["lastname"]==activity.get('athlete').get('lastname')) &
                            (check_data["title"]==activity.get('name')) &
                            (check_data["distance"]==activity.get('distance'))]
            if test.empty:
                new_activity.append({
                    "date": "",
                    "firstname": activity.get('athlete').get('firstname'),
                    "lastname": activity.get('athlete').get('lastname'),
                    "title": activity.get('name'),
                    "distance": activity.get('distance'),
                    "moving_time": activity.get('moving_time'),
                    "elapsed_time": activity.get('elapsed_time'),
                    "total_elevation_gain": activity.get('total_elevation_gain'),
                    "type": activity.get('type'),
                    "sport_type": activity.get('sport_type'),
                    "workout_type": ""
                })

        if not df.empty:
            check_data = pd.concat([df, pd.DataFrame.from_records(new_activity)], ignore_index=True)
        else:
            check_data = pd.DataFrame.from_records(new_activity)
            
        check_data.to_csv(self.output_file, index=False, header=True)

    ###
    # Get method https://www.strava.com/api/v3/clubs/# for activity data of each member in the club 
    # Stored in the given output_file as a csv
    #   This function will repeat requests to Strava until the max_page_number is reached (set to 50)
    #   Receives activities based on the most recent public activity visible in the club
    #   i.e club type (sport_type) is of 'ride': Will receive public activities of members who have posted with activity type 'ride' within the club
    #       club type (sport_type) is of 'run: Will receive public activities of members who have posted with activity type 'run' within the club
    def club_data_repeat(self):
        '''
        Run this function only once
        '''
        headers = ["date", "firstname", "lastname", "title", "distance", "moving_time", "elapsed_time", "total_elevation_gain", "type", "sport_type", "workout_type"]
        response = None
        page_number = 1
        max_page_number = 50

        # To create a json file instead or with the csv file
        # with open(self.output_file, 'a') as file:
        with open(self.output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=",")
            writer.writerow(headers)

            while page_number < max_page_number:

                # Send a request to Strava for public activities in the specified club
                # Returns a json of the most recent 30 (default) public activities
                #   Also, depends on type (activity type) of the club
                response = requests.get(f'https://www.strava.com/api/v3/clubs/{self.credentials.club_id}/activities',
                                        params={'page': f'{page_number}', 'per_page': '30'},
                                        headers={'Authorization': f'Authorization: Bearer {self.credentials.access_token}'},
                                        timeout=5)
                
                for activity in response.json():
                    writer.writerow([
                        "",
                        activity.get('athlete').get('firstname'),
                        activity.get('athlete').get('lastname'),
                        activity.get('name'),
                        activity.get('distance'),
                        activity.get('moving_time'),
                        activity.get('elapsed_time'),
                        activity.get('total_elevation_gain'),
                        activity.get('type'),
                        activity.get('sport_type')
                    ])
                
                # Write to the json file being created
                # file.write(str(response.json()))
                print(f'Finished Page: {page_number} with Status code: {response.status_code}')
                
                page_number += 1
    
    def __str__(self):
        return str(self.credentials)

def main(args):
    strava_tokens = None

    try:
        with open("credentials.txt", 'r+') as file:  # Open the credentials.txt with read/write and closes once complete
            credentials_content = file.readlines()
            credentials = {}

            for line in credentials_content:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    credentials[key.strip()] = value.strip()

            strava_tokens = StravaToken(credentials=credentials, output_file=args)
            # print("\n\nPrinting old StravaTokens")
            # print(strava_tokens)

            # strava_tokens.refresh_access_token()

            # print("\n\nPrinting new StravaTokens")
            # print(strava_tokens)
            
            # file.seek(0)
            # for key, value in strava_tokens.credentials.__dict__.items():
            #     file.write(f"{key}={value}\n")
            print(strava_tokens)

        # Set a timer for completion
        starttime = time.perf_counter()
        # strava_tokens.club_data()
        # strava_tokens.club_data_repeat()
        duration = timedelta(seconds=time.perf_counter()-starttime)
        print("Club activity Retrieval and Formatting took: ", duration)

        print("\nFile opened successfully and credentials loaded into StravaTokens object!\n")

    except FileNotFoundError as e:
        with open(f"ErrorLogs/{date.today()}.txt", "a") as f:
            f.write(f"{time.ctime()}: ")
            f.write(f"Error: Could not open the file {e}. Please ensure the file exists in the current directory and contains the necessary credentials.\n")
    except Exception as e:
        with open(f"ErrorLogs/{date.today()}.txt", "a") as f:
            f.write(f"{time.ctime()}: ")
            f.write(f"{str(e)} \n")

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("filename", help="Outputs values to the given filename or name of csv", type=str)
        args = parser.parse_args()

        filename = args.filename if ".csv" in args.filename else args.filename + ".csv"

        main(filename)

    except:
        e = sys.exc_info()[0]
        print (e)