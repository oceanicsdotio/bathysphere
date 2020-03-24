import pytest
from datetime import datetime
from json import dumps

from bathysphere import appConfig
from bathysphere.test.conftest import (
    getCredentials,
    CREDENTIALS,
    DARKSKY_API_KEY,
)
from bathysphere.graph.models import (
    Locations,
    Sensors,
    Things,
    Observations,
    ObservedProperties,
    FeaturesOfInterest,
    DataStreams,
    Collections,
    Entity,
    TaskingCapabilities,
    Tasks,
    Actuators,
)

YEAR = 2019
COLLECTION = "test-handlers-data-collection"
ASSET = "test-handlers-data-asset"
testAuth = ("testing@oceanics.io", "n0t_passw0rd", "something secret")
classes = [
    Locations,
    Sensors,
    Things,
    ObservedProperties,
    FeaturesOfInterest,
    Tasks,
    TaskingCapabilities,
    Actuators,
    Collections,
]

@pytest.mark.teardown
def test_graph_teardown(graph):
    """
    Destroy the graph.
    """
    # pylint: disable=no-value-for-parameter
    Entity.delete(
        db=graph("localhost", 7687, testAuth[1])
    )  


def test_graph_account_create_user(client):
    """
    Create the service account user
    """
    apiKeys = getCredentials()
    payload = {
        "username": testAuth[0],
        "password": testAuth[1],
        "secret": testAuth[2],
        "apiKey": apiKeys["Oceanicsdotio"],
    }
    response = client.post("api/auth", json=payload)
    assert response.status_code == 200, response.get_json()


def test_graph_account_get_token(token):
    """
    JWT Tokens are valid.
    """
    jwtToken = token(CREDENTIALS)
    btk = jwtToken.get("token")
    duration = jwtToken.get("duration")
    assert btk is not None and len(btk) >= 127
    assert duration is not None and duration > 30


def test_graph_account_update_user(client, token):
    """
    Give the user an alias.
    """
    jwtToken = token(CREDENTIALS).get("token")
    response = client.put(
        "api/auth",
        json={"alias": "By another name"},
        headers={"Authorization": ":" + jwtToken},
    )
    assert response.status_code == 204, response.get_json()


def test_graph_account_delete_user(client, token):
    """
    Delete a user, and then recreate it
    """
    jwtToken = token(CREDENTIALS).get("token")
    response = client.put(
        "api/auth", json={"delete": True}, headers={"Authorization": ":" + jwtToken},
    )
    assert response.status_code == 204, response.get_json()
    
    credentials = getCredentials()
    response = client.post(
        "api/auth",
        json={
            "username": testAuth[0],
            "password": testAuth[1],
            "secret": testAuth[2],
            "apiKey": credentials["Oceanicsdotio"],
        },
    )
    assert response.status_code == 200, response.get_json()
    _ = token(auth=CREDENTIALS, purge=True)


@pytest.mark.parametrize("cls", classes)
def test_graph_sensorthings_create(create_entity, cls):
    """
    Create the WellKnown Entities. 
    """
    results = []
    try:
        build = appConfig[cls.__name__]
    except KeyError:
        build = []
    for each in build:
        location = create_entity(cls.__name__, CREDENTIALS, each["spec"])
        results.append(location)


@pytest.mark.external_call
def test_graph_sensorthings_locations_weather_report(graph):

    locations = Locations(
        name="Upper Damariscotta Estuary"
    ).load(
        db=graph("localhost", 7687, testAuth[1])
    )

    if len(locations) != 1:
        for L in locations:
            print(dumps(L.serialize(db=None, service=None)))
        raise AssertionError

    response = (
        locations
        .pop()
        .reportWeather(
            ts=datetime(2016, 2, 1, 0, 0, 0),
            api_key=DARKSKY_API_KEY,
        )
    )
    assert response.ok, response.json()