from __future__ import print_function

import os
import io
import re

import csv
import httplib2
import argparse

from apiclient import discovery
from apiclient.http import MediaIoBaseDownload

import oauth2client
from oauth2client import client
from oauth2client import tools

from colorthief import ColorThief

parser = argparse.ArgumentParser(parents=[tools.argparser])
parser.add_argument('--folder',
                    help='ID of Google Drive folder')

flags = parser.parse_args()

SCOPES = 'https://www.googleapis.com/auth/drive.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Color Thief'


class GoogleDriveColorThief:
    def __init__(self, flags):
        self.flags = flags
        self.headers_set = False

        http = self._get_credentials().authorize(httplib2.Http())

        self.service = discovery.build('drive', 'v3', http=http)

    def _get_credentials(self):
        """Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.

        Returns:
            Credentials, the obtained credential.
        """
        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(home_dir, '.credentials')
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir,
                                       'drive-python-quickstart.json')

        store = oauth2client.file.Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
            flow.user_agent = APPLICATION_NAME
            if flags:
                credentials = tools.run_flow(flow, store, self.flags)

            print('Storing credentials to ' + credential_path)

        return credentials

    @staticmethod
    def _rgb_to_hex(rgb):
        return '#%02x%02x%02x' % rgb

    def grab_dominant_color(self, parent_folder):
        output_rows = []
        folders = self.grab_inner_folders(parent_folder)

        for folder in folders[46:]:
            print('Grab colors for images from folder %s' % folder['name'])
            images = self.grab_folder_images(folder['id'])
            output_rows = self.grab_colors(images)
            print('Writing to .csv file...', end=' ')
            self.write_csv(output_rows)
            print('Ok')

        print('Finished.')

    def grab_inner_folders(self, parent_folder_id):
        folders = []
        page_token = None
        query = "mimeType='application/vnd.google-apps.folder'"

        if parent_folder_id is not None:
            query += " and '" + parent_folder_id + "' in parents"

        response = self.service.files().list(
            q=query,
            spaces='drive',
            pageToken=page_token,
            fields="nextPageToken, files(id, name)").execute()

        while True:
            folders += response.get('files', [])

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

        if not folders:
            print('No folders found. Finished.')
            return

        # Sort folders by names
        folders.sort(key=lambda folder: folder['name'])

        return folders

    def grab_folder_images(self, folder_id):
        images = []
        page_token = None
        query = "mimeType='image/jpeg'"

        if folder_id is not None:
            query += " and '" + folder_id + "' in parents"

        response = self.service.files().list(
            q=query,
            spaces='drive',
            pageToken=page_token,
            fields="nextPageToken, files(id, name)").execute()

        #  Firstly, collect all files from folder
        while True:
            images += response.get('files', [])

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

        if not images:
            print('No images found. Finished.')
            return []

        # Sort images by number in the end of name
        images.sort(key=lambda image: int(re.split('_|\.', image['name'])[-2]))

        return images

    def grab_colors(self, images):
        seconds = 0
        rows = []

        for image in images:
            print(image['name'], end=' > ')

            try:
                request = self.service.files().get_media(
                    fileId=image['id'])

                fileBuffer = io.BytesIO()
                downloader = MediaIoBaseDownload(fileBuffer, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    downloaded = int(status.progress() * 100)

                    if downloaded < 100:
                        print('.', end='')
            except Exception:
                print('Can not download %s%' % image['name'])

            color_thief = ColorThief(fileBuffer)
            # get the dominant color
            dominant_color = color_thief.get_color(quality=1)
            hex_color = self._rgb_to_hex(dominant_color)

            rows.append({
                'fname': image['name'],
                'time_sec': seconds,
                'dominant_color': hex_color
            })

            print (hex_color)

            seconds = seconds + 5

        return rows

    def write_csv(self, rows):
        csvfile = open('pp_output.csv', 'a')
        fieldnames = ['fname', 'time_sec', 'dominant_color']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not self.headers_set:
            writer.writeheader()
            self.headers_set = True

        for row in rows:
            writer.writerow(row)

        csvfile.close()


if __name__ == '__main__':
    thief = GoogleDriveColorThief(flags)
    thief.grab_dominant_color(flags.folder)
