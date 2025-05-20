import asyncio
import json
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import aiodns
import aiohttp
from fastapi import FastAPI, Body, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi_mqtt import FastMQTT, MQTTConfig
from gmqtt import Client as MQTTClient
import os
import models

try:
    filename = eval(os.environ.get('PERSISTENT_CONFIG_FILENAME'))
except:
    filename = 'config.std'

print(f'Persistent Config File: {filename}')
env_file_path = Path(f"config/{filename}")
# Create the file if it does not exist.
env_file_path.touch(mode=0o600, exist_ok=True)


def read_config(file_path: Path):
    with file_path.open('r') as file:
        try:
            return json.loads(file.read())
        except json.decoder.JSONDecodeError:
            return dict()


config = read_config(env_file_path)
print(f'Configuration {config}')
description = """
## 🚀🚀 API-MQTT Gateway 🚀🚀
### MQTT-Broker Credentials
* **Set credentials and connect** (_implemented_)\n
* **Get credentials information and connection state** (_implemented_)\n
### MQTT-Communication
* **Publish message** (_implemented_)\n
* **Publish message and wait for reply** (_implemented_)\n
* **Read message** (_implemented_)\n
* **Flush  messages** (_implemented_)\n
### API-Buffer
* **Write into buffer** (_implemented_)\n
* **Read from buffer** (_implemented_)\n
* **Flush buffer** (_implemented_)\n
"""

mqtt_config = MQTTConfig(
    host=config.get("HOST", "test.mosquitto.org"),
    port=int(config.get("PORT", "1883")),
    keepalive=60,
    username=config.get("USERNAME", str()),
    password=config.get("PASSWORD", str()),
    reconnect_delay=10,
    reconnect_retries=200000,
    ssl=bool(int(config.get("SSL", "0"))),
)

fast_mqtt = FastMQTT(config=mqtt_config)
messages = dict()
buffer = dict()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        await asyncio.wait_for(fast_mqtt.mqtt_startup(), 2)
    except Exception as e:
        print('Startup failed', e)
    yield
    await fast_mqtt.mqtt_shutdown()


app = FastAPI(lifespan=_lifespan,
              title="API-MQTT Gateway for IoT",
              version="1.0.0",
              contact={"name": "Franz Krenn",
                       "email": "office@fkrenn.at"},
              summary="Shoot up MQTT communication possibilities",
              description=description)


@fast_mqtt.on_connect()
def connect(client: MQTTClient, flags: int, rc: int, properties: Any):
    # client.subscribe(f"{ROOT_TOPIC}/#")  # subscribing mqtt topic
    username = client._username.decode() if type(client._username) is bytes else client._username
    password = client._password.decode() if type(client._password) is bytes else client._password
    host = client._host.decode() if type(client._host) is bytes else client._host
    print(
        f"Connected to: {host}:{client._port} {username} flags {flags}, rc {rc}, properties {properties}")

    with env_file_path.open('w') as env_file:
        env_file.write(json.dumps({"HOST": host,
                                   "PORT": client._port,
                                   "USERNAME": username,
                                   "PASSWORD": password,
                                   "SSL": str(int(client._ssl)),
                                   "LAST_CONNECTION_TIME": time.strftime("%Y-%m-%dT%H:%M:%S",
                                                                         time.localtime(time.time()))}))


@fast_mqtt.subscribe("back-to-api/#", "+/back-to-api/#", "+/+/back-to-api/#", "+/+/+/back-to-api/#", qos=1)
async def reply_message(client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any):
    print("reply_message: ", topic, payload.decode(), qos, properties)
    try:
        payload = json.loads(payload.decode())
    except:
        payload = payload.decode()

    # print(f'Type {type(payload)} {payload}')
    try:
        messages[topic] = (payload, time.time())
    except Exception as e:
        print(f'home_message {e}')


async def handle_and_reply_response(response_topic: str, response: aiohttp.ClientResponse):
    print("Status:", response.status)
    print('headers', response.headers)
    body = await response.text()
    print("Body:", body[:50], end='')
    line_termination = ' ...' if len(body) > 50 else '\n'
    print(line_termination)
    fast_mqtt.publish(response_topic,
                      {"http-status": response.status, "response": json.loads(body)})  # publishing mqtt topic


@fast_mqtt.subscribe("http-get", "+/http-get", "+/+/http-get", "+/+/+/http-get", "+/+/+/+/http-get", qos=1)
async def http_get(client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any):
    print("request: ", topic, payload.decode(), qos, properties)
    try:
        payload = json.loads(payload.decode())
        path = payload.get("path", str())
        if path and not path.startswith("/"):
            path = f"/{path}"
        host = payload.get("host", str())
        params = payload.get("params", dict())
        headers = payload.get("headers", {"accept": "application/json"})
        url = f'{host}{path}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                response_topic = topic.replace("http-get", "http-get-response")
                await handle_and_reply_response(response_topic, response)
    except Exception as e:
        print(f'home_message {e}')


@fast_mqtt.subscribe("http-post", "+/http-post", "+/+/http-post", "+/+/+/http-post", "+/+/+/+/http-post", qos=1)
async def http_post(client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any):
    print("post: ", topic, payload.decode(), qos, properties)
    try:
        payload = json.loads(payload.decode())
        host = payload.get("host", str())
        path = payload.get("path", str())
        if path and not path.startswith("/"):
            path = f"/{path}"
        params = payload.get("params", dict())
        _json = payload.get("json", dict())
        body = payload.get("body", str())
        headers = payload.get("headers", dict())
        url = f'{host}{path}'
        async with aiohttp.ClientSession() as session:
            if _json:
                async with session.post(url=url, params=params, json=_json, headers=headers) as response:
                    response_topic = topic.replace("http-post", "http-post-response")
                    await handle_and_reply_response(response_topic, response)
            else:
                async with session.post(url=url, params=params, data=body, headers=headers) as response:
                    response_topic = topic.replace("http-post", "http-post-response")
                    await handle_and_reply_response(response_topic, response)
    except Exception as e:
        print(f'http-post {e}')


@fast_mqtt.subscribe("api-buffer-get", "+/api-buffer-get", "+/+/api-buffer-get", "+/+/+/api-buffer-get",
                     "+/+/+/+/api-buffer-read", qos=1)
async def api_buffer_get(client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any):
    global buffer
    print("api_buffer_get: ", topic, payload.decode(), qos, properties)
    response_topic = topic.replace("api-buffer-get", "api-buffer-response")
    result = False
    value = "Missing value"
    buffer_id = str()
    timestamp = 0
    try:
        payload = json.loads(payload.decode())
        autoflush = payload.get("autoflush", 1)
        buffer_id = payload.get("id", str())
        if buffer_id:
            value, timestamp = buffer.get(buffer_id, ("{}", 0))
            try:
                value = json.loads(value)
            except:
                value = value
            result = bool(timestamp)
            if autoflush:
                try:
                    del buffer[buffer_id]
                except:
                    pass
    except Exception as e:
        print(f'api_buffer_get {e}')
    finally:
        datetime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp))
        try:
            response = json.dumps({"result": result, "id": buffer_id, "value": value, "datetime": datetime})
        except Exception as e:
            response = json.dumps({"result": False, "id": buffer_id})
        fast_mqtt.publish(response_topic, payload=response, qos=1)


@fast_mqtt.on_message()
async def message(client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any):
    print("Received message: ", topic, payload.decode(), qos, properties)


@fast_mqtt.on_disconnect()
def disconnect(client: MQTTClient, packet, exc=None):
    print("Disconnected")


@fast_mqtt.on_subscribe()
def subscribe(client: MQTTClient, mid: int, qos: int, properties: Any):
    pass
    # print("subscribed", client, mid, qos, properties)


@app.post("/mqtt-broker-connect",
          response_description='Result is true if successfully connected.\nReason gives an indication of failure.',
          description='Use credential settings of mqtt broker to connect',
          tags=['Broker'])
async def mqtt_broker_set_credentials_and_connect(credentials: models.BrokerCredentials =
                                                  Body(default=models.default_brokercredentials)) -> Any:
    _config = read_config(env_file_path)
    host = credentials.host if credentials.host else _config.get("HOST", str())
    port = credentials.port if credentials.port else _config.get("PORT", 1883)
    username = credentials.username if credentials.username is not None else _config.get("USERNAME", str())
    password = credentials.password if credentials.password is not None else _config.get("PASSWORD", str())
    ssl = credentials.ssl if credentials.ssl is not None else _config.get("SSL", 0)
    try:
        resolver = aiodns.DNSResolver(loop=asyncio.get_event_loop())
        await resolver.gethostbyname(host, socket.AF_INET)
        if fast_mqtt.client.is_connected:
            await fast_mqtt.client.disconnect()
            await asyncio.sleep(1)
        print('broker credentials and connecting', host, port, username, password, bool(ssl))
        fast_mqtt.client.set_auth_credentials(username, password)
        await asyncio.wait_for(fast_mqtt.client.connect(host=host, port=port, ssl=bool(ssl)), 5)
        return models.Response(connected=True).model_dump(exclude={"reason"})
    except Exception as e:
        return models.Response(connected=False, reason=str(e)).model_dump()


@app.get("/mqtt-broker-information",
         response_description='Credentials and status of connection',
         description='Information about actual broker connection state',
         tags=['Broker'])
async def mqtt_broker_information() -> Any:
    _config = read_config(env_file_path)
    try:
        if fast_mqtt.client.is_connected:
            return models.ResponseBrokerCredentials(connected=True,
                                                    host=_config.get("HOST"),
                                                    port=_config.get("PORT"),
                                                    username=_config.get("USERNAME"),
                                                    password=_config.get("PASSWORD"),
                                                    ssl=_config.get("SSL"),
                                                    last_connection_time=_config.get(
                                                        "LAST_CONNECTION_TIME")).model_dump(exclude={"password"})

        else:
            return models.ResponseBrokerCredentials(connected=False).model_dump(include={"connected"})

    except Exception as e:
        return models.Response(connected=False, reason=str(e)).model_dump()


@app.post("/mqtt-publish",
          response_description='',
          description="Publishing topic / payload",
          tags=['Communication'])
async def publish(payload=Body(default={"topic": f"from-api", "payload": {'item': 1.23}})) -> Any:
    topic = payload.get("topic", None)
    try:
        payload = json.dumps(payload.get("payload", dict()))
        if topic is None or topic == str():
            raise Exception("Missing topic")
        fast_mqtt.publish(topic, payload, qos=1)  # publishing mqtt topic
        return models.PublishResponse(success=True).model_dump(exclude={"reason"})
    except Exception as e:
        return models.PublishResponse(success=False, reason=str(e)).model_dump()


@app.post("/mqtt-publish-and-wait-for-reply",
          response_description='Publishing topic to broker',
          description="Publish and wait timed out for replied message."
                      "To use this feature, it is necessary to use following conventions:\n"
                      "Publish topic must contain 'from-api' and must be replaced with 'back-to-api' from replier",
          tags=['Communication'])
async def publish_and_wait_for_message_reply(
        payload=Body(default={"topic": f"from-api", "payload": {"item": 1.23}, "timeout_seconds": 2})) -> Any:
    topic = payload.get("topic", None)
    timeout = payload.get("timeout_seconds", 2) * 10
    payload = json.dumps(payload.get("payload", dict()))
    timestamp = None
    if topic is None:
        return models.PublishResponse(success=False, reason="Missing topic").model_dump()

    receive_topic = topic.replace("from-api", "back-to-api")
    print(receive_topic)
    try:
        del messages[receive_topic]
    except KeyError:
        pass
    fast_mqtt.publish(topic, payload)
    await asyncio.sleep(0.2)  # give chance for reply
    while timeout:
        payload, timestamp = messages.get(receive_topic, (None, None))
        if payload is not None and timestamp is not None:
            break
        await asyncio.sleep(0.1)
        timeout -= 1
    try:
        del messages[receive_topic]
    except KeyError:
        pass
    if payload is not None and timestamp is not None:
        _datetime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp))
        return models.PublishAndWaitReplyResponse(success=True,
                                                  topic=receive_topic,
                                                  payload=payload,
                                                  timestamp=timestamp,
                                                  datetime=_datetime).model_dump(exclude={"key", "value", "reason"})
    return models.PublishAndWaitReplyResponse(success=False,
                                              topic=receive_topic,
                                              reason=f"No message for topic '{receive_topic}' available").model_dump(
        include={"success", "topic", "reason"})


@app.get("/mqtt-read",
         description="Read buffered message from specific topic",
         tags=['Communication'])
async def read_message(topic=Query(default="back-to-api",
                                   description="must contain 'back-to-api'")) -> Any:
    payload, timestamp = messages.get(topic, (None, None))
    print(topic, payload, timestamp)
    try:
        del messages[topic]
    except KeyError:
        pass
    _datetime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp))
    if payload is not None and timestamp is not None:
        return models.PublishAndWaitReplyResponse(success=True,
                                                  topic=topic,
                                                  payload=payload,
                                                  timestamp=timestamp,
                                                  datetime=_datetime).model_dump(exclude={"key", "value", "reason"})

    return models.PublishAndWaitReplyResponse(success=False,
                                              topic=topic,
                                              reason=f"No message for topic '{topic}' available").model_dump(
        include={"success", "topic", "reason"})


@app.get("/mqtt-flush",
         description='Flush input buffer',
         tags=['Communication'])
async def mqtt_flush_message(topic: str = Query(default=str(),
                                                description='empty for all messages or '
                                                            'topic which should be flushed')) -> Any:
    global messages
    try:
        if topic is None or topic == str():
            messages = dict()
        else:
            try:
                del messages[topic]
            except KeyError:
                raise Exception(f"Topic '{topic}' not found")
    except Exception as e:
        return models.PublishResponse(success=False, reason=str(e)).model_dump()
    return models.PublishResponse(success=True).model_dump(exclude={"reason"})


@app.post("/buffer-write",
          description="Write value into buffer",
          tags=['Buffer'])
async def write_buffer(payload=Body(default={"key": "#abc1234", "json": {}, "text": ""})) -> Any:
    global buffer
    try:
        key = payload.get("key", None)
    except Exception as e:
        return models.PublishResponse(success=False, reason=str(e)).model_dump()

    try:
        _json = payload.get("json", None)
        if _json:
            _json = json.dumps(_json)
            _json = None if _json == dict() else _json
    except json.JSONDecodeError as e:
        return models.PublishResponse(success=False, reason=str(e)).model_dump()

    text = payload.get("text", None)
    timestamp = time.time()
    if key is None:
        return models.PublishResponse(success=False, reason='Missing key').model_dump()
    if _json and text:
        return models.PublishResponse(success=False,
                                      reason="Only one source allowed - json OR text, not both").model_dump()
    if _json:
        buffer[key] = (_json, timestamp)
    elif text:
        buffer[key] = (text, timestamp)
    else:
        return models.PublishResponse(success=False, reason='Missing value').model_dump()
    print(buffer)
    return models.PublishResponse(success=True).model_dump(exclude={"reason"})


@app.get("/buffer-read",
         description="Read previously stored value from buffer",
         tags=['Buffer'])
async def read_buffer(autoflush: int = Query(default=0, ge=0, le=1,
                                             description='0: leave value in buffer 1: Value will be flushed after reading'),
                      key=Query(default="#abc1234",
                                description="This is the identifier key of the previously stored value")) -> Any:
    global buffer
    value, timestamp = buffer.get(key, (None, None))
    print(key, value, timestamp)
    try:
        if autoflush:
            del buffer[key]
    except KeyError:
        pass
    _datetime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(timestamp))
    if value is not None and timestamp is not None:
        return models.PublishAndWaitReplyResponse(success=True,
                                                  value=value,
                                                  key=key,
                                                  timestamp=timestamp,
                                                  datetime=_datetime).model_dump(exclude={"topic", "payload", "reason"})
    return models.PublishResponse(success=False, reason="No value available").model_dump()


@app.get("/buffer-flush",
         description='Flush buffer',
         tags=['Buffer'])
async def flush_buffer(key: str = Query(default="#abc1234",
                                        description='Let it empty for all key/values or '
                                                    'enter specific key which will be flushed')) -> Any:
    global buffer
    try:
        if key is None or key == str():
            buffer = dict()
        else:
            try:
                del buffer[key]
            except KeyError:
                raise Exception(f"Id '{key}' not found")
    except Exception as e:
        return models.PublishResponse(success=False, reason=str(e)).model_dump()
    return models.PublishResponse(success=True).model_dump(exclude={"reason"})
