# Self-hosted Telephony Server

See https://docs.vocode.dev/open-source/telephony for setup steps!

My changes to setup steps:

Installed poetry and docker, used docker to run the server, etc,
and poetry to have source code that vscode can look at.

build (in same directory as this README) (after ngrok is up (see docs)):

docker build -t vocode-telephony-app . && docker-compose up


Debugging tips:

If twilio is not connecting to the server due to ngrok issues, try restarting
ngrok.