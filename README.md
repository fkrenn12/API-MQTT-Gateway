# API-MQTT Gateway
## API -> MQTT 
## Publishing mqtt message from http 
Prerequisist: Running MQTT-Broker / you can use public broker for first use and testing

Topic<br>
wei/http-post<br>
Payload(json)<br>
{"host":"https://posttestserver.dev/p/9krr5xfxo3g5m8nu/post", "params":{"model":"audi"},"json":{"data":12.66}, "path":""}
auch mit "body":"Plain Text" möglich, aber json und body gleichzeitig geht nicht
# httpget via mqtt
Topic<br>
wei/http-get<br>apimqtt
Payload(json)<br>
{"host":"https://api.clever-together.at","path":"/v1/info"}

## MQTT -> API -> MQTT 