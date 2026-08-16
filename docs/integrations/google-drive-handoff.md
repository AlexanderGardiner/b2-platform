# Google Drive handoff

Accepted death-certificate cases are uploaded to GiveLight as two files with a
shared filename stem: the JSON verification payload and the original image (or
PDF). The destination should be a folder in a Google Shared Drive.

## Google Cloud and GiveLight setup

1. Enable the Google Drive API in the Google Cloud project that runs the B2
   WhatsApp adapter.
2. Use the Cloud Run runtime service account through Application Default
   Credentials (ADC). Do not create or send a service-account JSON key.
3. Ask GiveLight to share the destination Shared Drive folder with the runtime
   service-account email and grant it permission to add files.
4. Copy the folder ID from its Drive URL and set it on the service as
   `GOOGLE_DRIVE_FOLDER_ID`.
5. Deploy a revision and verify that one accepted case creates both the JSON
   payload and original document in the destination folder.

The uploader requests only the
`https://www.googleapis.com/auth/drive.file` OAuth scope. Store configuration in
the deployment platform; never commit credentials or secret values.

## WhatsApp configuration

The current repository requires:

- `WHATSAPP_TOKEN`: a production system-user access token with
  `whatsapp_business_messaging`, used to retrieve incoming media.
- `WHATSAPP_GRAPH_VERSION`: an optional, non-secret Graph API version override.
- `WEBHOOK_SECRET`: the internal shared secret between the central B2 webhook
  and this service.

If this service later integrates directly with Meta, it will additionally need
the Meta App ID and App Secret, WhatsApp Business Account (WABA) ID, Phone
Number ID, and a separately generated webhook verification token. Grant
`whatsapp_business_management` when account or template administration is
needed. Share secret values only through the approved secret-management
channel; do not send them in chat or commit them to the repository.
