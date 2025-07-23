# API-MQTT Gateway
# How do get it running
## Local Windows 
cd api   
uvicorn --reload main:app --port 5600 --log-level debug  
## Local Docker on Windows  
execute script: rebuild_and_start.local.development.ps1  
## Production on Linux
execute script: rebuild_and_start.prod.sh
## API -> MQTT 
## Publishing mqtt message from http 
Prerequisist: Running MQTT-Broker / you can use public broker for first use and testing

Topic<br>
http-post<br>
Payload(json)<br>
{"host":"https://posttestserver.dev/p/9krr5xfxo3g5m8nu/post", "params":{"model":"audi"},"json":{"data":12.66}, "path":""}
auch mit "body":"Plain Text" möglich, aber json und body gleichzeitig geht nicht
# httpget via mqtt
Topic<br>
http-get<br>apimqtt
Payload(json)<br>
{"host":"https://api.clever-together.at","path":"/v1/info"}

## MQTT -> API -> MQTT 