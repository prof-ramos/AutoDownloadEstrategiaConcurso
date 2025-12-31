import os
import pickle
import mimetypes
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# Se modificar estes escopos, delete o arquivo token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveManager:
    def __init__(self, client_secret_path='client_secret.json', token_path='token.json'):
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        """Faz a autenticação e retorna o serviço da API do Drive."""
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                try:
                    creds = pickle.load(token)
                except Exception:
                    creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds or not creds.valid:
                if not os.path.exists(self.client_secret_path):
                    raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {self.client_secret_path}")
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_path, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        return build('drive', 'v3', credentials=creds)

    def get_or_create_folder(self, folder_name, parent_id=None):
        """Busca uma pasta pelo nome ou cria se não existir."""
        # Escapar aspas simples no nome da pasta
        safe_name = folder_name.replace("'", "\\'")
        query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        try:
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get('files', [])

            if items:
                return items[0]['id']

            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]

            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')
        except HttpError as error:
            print(f"Erro ao gerenciar pasta Drive: {error}")
            return None

    def upload_file(self, file_path, drive_folder_id):
        """Faz o upload de um arquivo para uma pasta específica do Drive com suporte a resumo."""
        file_name = os.path.basename(file_path)

        # Escapar aspas simples no nome do arquivo
        safe_name = file_name.replace("'", "\\'")
        query = f"name = '{safe_name}' and '{drive_folder_id}' in parents and trashed = false"
        try:
            results = self.service.files().list(q=query, fields="files(id)").execute()
            if results.get('files'):
                return results.get('files')[0]['id']
        except HttpError:
            pass

        file_metadata = {
            'name': file_name,
            'parents': [drive_folder_id]
        }

        # Tentar adivinhar o MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        try:
            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            )

            response = None
            retries = 0
            max_retries = 5

            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        # Opcional: print de progresso aqui se necessário (ou deixar para o DownloadManager)
                        pass
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        retries += 1
                        if retries > max_retries:
                            raise
                        time.sleep(2 ** retries)
                    else:
                        raise

            return response.get('id')
        except Exception as e:
            print(f"Erro no upload para o Drive: {e}")
            return None
