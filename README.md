# The Hindu Sales Intelligence

Web app for The Hindu calling campaigns. Backend is FastAPI; frontend is React.

## Bolna webhook

After the API is live, set the Bolna agent webhook to:

`https://<your-api-host>/api/webhooks/bolna`

Keep the API process always-on. A sleeping free host will drop background CSV jobs and inbound webhooks.
