from datetime import datetime
from time import time, sleep
from secrets import token_urlsafe
from json import dumps
from typing import Any, Callable
from decimal import Decimal
from enum import Enum

try:
    from numpy import (
        abs, zeros, arange, ones, convolve, isnan, ceil, array, repeat
    )
    from scipy.fftpack import rfft, irfft, fftfreq
    from pandas import DataFrame
except ImportError as ex:
    print("Numerical libraries are not installed")

import attr
from connexion import request
from statistics import median

from bathysphere.utils import interp1d, response
from bathysphere.datatypes import PostgresType, Field, Table, Query, Coordinates, Distance


@attr.s
class Actuators(object):
    """
    Actuators are devices that turn messages into physical effects
    """
    name: str = attr.ib(default=None)
    description: str = attr.ib(default=None)
    encodingType: str = attr.ib(default=None)  # metadata encoding
    metadata: Any = attr.ib(default=None)

    def startController(
        self,
        host: str,
        port: int,
        relay_id: int,
        banks: int,
        relays: int,
        refresh: int,
        file: str = None,
        verb: bool = False,
    ) -> bool:
        """
        Communicate with a single relay

        :param host: hostname
        :param port: port number
        :param relay_id: relay id on board, doesn't get registered with graph
        :param banks: number of replica banks
        :param relays: total number of relays
        :param refresh: fixed refresh rate, in seconds
        :param file: log file
        :param verb: log to console
        """
        # timer_id = relay_id + self.metadata["config"]["timer_id_offset"]
        # state = [[False] * banks] * (relays // banks)
        start = time()

        while True:
            response = 1  # TODO: wire up corrrectly
            # response = on(host, port, relay_id, timer_id, duration=None)
            if not response:
                print("breaking loop.")
            sleep(refresh - ((time() - start) % refresh))

        return True

@attr.s
class Assets(object):
    """
    Assets are references to data objects, which may or may not
    be accessible at the time of query.

    TODO: Assets is an ambiguous name when dealing with real-world systems
    """
    description: str = attr.ib(default=None)
    name: str = attr.ib(default=None)  # name of resource
    url: str = attr.ib(default=None)  # address of resource


@attr.s
class Collections(object):
    name: str = attr.ib(default=None)
    description: str = attr.ib(default=None) 
    extent: (float,) = attr.ib(default=None)


@attr.s
class DataStreams(object):
    """
    DataStreams are collections of Observations.
    """
    name: str = attr.ib(default=None)
    description: str = attr.ib(default=None)  
    unitOfMeasurement = attr.ib(default=None)
    observationType = attr.ib(default=None)
    observedArea: dict = attr.ib(default=None)  # boundary geometry, GeoJSON polygon
    phenomenonTime: (datetime, datetime) = attr.ib(default=None)  # time interval, ISO8601
    resultTime: (datetime, datetime) = attr.ib(default=None)  # result times interval, ISO8601


    @staticmethod
    def fourierTransform(dt=1, lowpass=None, highpass=None, fill=False, compress=True):
        """
        Perform frequency-domain filtering on regularly spaced time series
        
        Kwargs:
        
            tt, float[] :: time series
            yy, float[] :: reference series
            dt, float :: regular timestep
            lowpass, float :: lower cutoff
            highpass, float :: upper cutoff
        """
        series = tuple(item.value for item in request.json)
        spectrum: dict = DataStreams.frequencySpectrum(series, dt=dt, fill=fill, compress=compress)
        payload: dict = spectrum.get("payload")
        
        freq = payload["frequency"]
        ww = payload["index"]

        if highpass is not None:
            mask = (ww < highpass)
            freq[mask] = 0.0  # zero out low frequency

        if lowpass is not None:
            mask = (ww > lowpass)
            freq[mask] = 0.0  # zero out high-frequency
    
        filtered = irfft(freq)
       
        return response(
            200,
            payload=filtered
        )

    @staticmethod
    def frequencySpectrum(req, dt=1, fill=False, compress=True):

        series = array(tuple(item.value for item in req.json))
        
        if fill:
            series = series.ffill()  # forward-fill missing values

        index = fftfreq(len(series), d=dt)  # frequency indices
        freq = rfft(series)  # transform to frequency domain
        if compress:
            mask = (index < 0.0)
            freq[mask] = 0.0  # get rid of negative symmetry
        
        return response(
            status=200,
            payload={
                "frequency": freq,
                "index": index
            }
        )

    @staticmethod
    def smoothUsingConvolution(bandwidth, mode="same"):
        """
        Convolve

        :return:
        """
        series = tuple(item.value for item in request.json)
        filtered = convolve(series, ones((bandwidth,))/bandwidth, mode=mode)
        return response(200, payload=filtered)

    @staticmethod
    def resampleSparseSeries(method="forward", observations=None, start=None):
        """
        Generate filled regular time series of a variable from sparse observations
        using either backward/forward fill, or linear interpolation
        
        Kwargs:
            nobs, int :: number of observations
            start, datetime :: starting time index
            dates, datetime[] :: timestamps of observations
            series, float[] :: magnitude of observations
            method, str :: method if interpolation
            
        returns: array of filled values as single column
        """
        dates = tuple(item.time for item in request.json)
        series = tuple(item.value for item in request.json)

        if not observations:
            observations = (dates[-1] - dates[0]).hours + 1

        if not start:
            start = dates[0]

    
        new = zeros(observations, dtype=float)
        total = 0  # new observations created
        previous = None
        dtdt = None

        for ii in range(len(series)):
            time = dates[ii]
            signal = series[ii]
            if not isnan(signal):
                dt = time - start
                hours = dt.days * 24 + dt.seconds / 60 / 60  # hours elapsed since first sample
                if hours > 0:  # reference time is after start time
                    end = min(ceil(hours), observations)  # absolute end index
                    span = end - total  # width of subset

                    if method is "forward":
                        first = total
                        if ii == len(series) - 1:
                            span += observations - end

                        last = total + span  # not including self
                        new[first:last] = signal if previous is None else previous  # default to back-fill

                    elif method is "back":
                        first = total  # including self
                        last = total + span - 1
                        new[first:last] = signal

                    elif method is 'interp':
                        if dtdt is None:
                            fill = signal  # default to forward fill
                        else:
                            delta = end - dtdt  # get step between input obs
                            coefs = arange(delta) / delta  # inter-step interpolation coefficient
                            fill = interp1d(coefs, previous, signal)

                        first = max([total - 1, 0])
                        new[first:total + span - 1] = fill

                    dtdt = dt
                    total += span

                previous = signal
       
        return response(200, payload=new)

    def statisticalOutlierMask(
        self,
        assumeEvenSpacing: bool = False, 
        threshold: float = 3.5
    ):
        """
        Return array of logical values, with true indicating that the value or its 
        first derivative are outliers
        """
   
        dates = tuple(item.time for item in request.json)
        series = tuple(item.value for item in request.json)

        if assumeEvenSpacing:
            dydt = series
        else:
            dydt = [0.0]
            deltat = [0.0]
            
            for nn in range(1, len(series)):
                deltat.append(dates[nn] - dates[nn-1])
                dydt.append((series[nn] - series[nn-1])/deltat[nn])
            
        diff = abs(series - median(series))  # difference between series and median (anomaly)
        mad = median(diff)  # median of anomaly
        mod_z = 0.6745 * diff / mad 
        mask = mod_z > threshold

        return response(200, payload=mask)


    @staticmethod
    def outOfRangeMask(min, max):
        """
        Use backend to generate a mask. 
        """
        series = tuple(item.value for item in request.json)
        mask = map(lambda x: x.outOfRange(maximum=max, minimum=min), series)

        return response(200, payload=mask)

    def partition(
        self, 
        window: int, 
        horizon: int, 
        batch_size: int, 
        ratio: float, 
        periods: int
    ) -> (DataStreams, DataStreams):
        """

        :param window: moving average observations
        :param horizon: look ahead
        :param periods: number of observations
        :param batch_size: length of training segment
        :param ratio: approximate ratio of observations to use for training
    
        :return:
        """

        # reshaping functions
        def reshape3d(x):
            return x.values.reshape((x.shape[0], x.shape[1], 1))

        def reshape2d(y):
            return y.values.reshape((y.shape[0], 1))

        start = max(window - 1, horizon - 1)
        nn = int(periods * ratio)
        nn -= nn % batch_size
        expected = self.rolling(window=window, center=False).mean()  # set the target to moving average

        if horizon > 1:
            datastream = DataFrame(repeat(datastream.values, repeats=horizon, axis=1))
            for i, c in enumerate(datastream.columns):
                datastream[c] = datastream[c].shift(i)  # shift each by one more, "rolling window view" of data

        end = datastream.shape[0] % batch_size  # match with batch_size

        return {
            "training": {
                "x": reshape3d(datastream[start:start+nn]),
                "y": reshape2d(expected[start:start+nn])
            },
            "validation": {
                "x": reshape3d(datastream[start+nn:-1 * end] if end else datastream[start+nn:]),
                "y": reshape2d(expected[start+nn:-1 * end] if end else expected[start+nn:])
            }
        }

@attr.s
class FeaturesOfInterest(object):
    """
    FeaturesOfInterest are usually Locations.
    """
    name: str = attr.ib(default=None)
    description: str = attr.ib(default=None)
    encodingType: str = attr.ib(default=None)  # metadata encoding
    feature: Any = attr.ib(default=None)
    

@attr.s
class HistoricalLocations(object):
    """
    Private and automatic, should be added to sensor when new location is determined
    """
    time: str = attr.ib(default=None) # time when thing was at location (ISO-8601 string)


@attr.s
class Locations(object):
    """
    Last known location of a thing. May be a feature of interest, unless remote sensing.        
    """
    name: str = attr.ib(default=None)
    location = attr.ib(default=None)  # GeoJSON
    description: str = attr.ib(default=None)
    encodingType: str = attr.ib(default="application/vnd.geo+json")

    @staticmethod
    def nearestNeighborQuery(
        coordinates: Coordinates, 
        kNeighbors: int, 
        searchRadius: Distance,
    ) -> Query:
        """
        Format the query and parser required for making k nearest neighbor
        queries to a database running PostGIS, with the appropriate
        spatial indices already in place.
        """

        x, y = coordinates
        targetTable = "landsat_points"
        targetColumn, alias = "oyster_suitability_index", "osi"

        queryString = f"""
        SELECT AVG({alias}), COUNT({alias}) FROM (
            SELECT {alias} FROM (
                SELECT {targetColumn} as {alias}, geo
                FROM {targetTable}
                ORDER BY geo <-> 'POINT({x} {y})'
                LIMIT {kNeighbors}
            ) AS knn
            WHERE st_distance(geo, 'POINT({x} {y})') < {searchRadius}
        ) as points;
        """

        def parser(fetchAll):

            avg, count = fetchAll[0]
            return {
                "message": "Mean Oyster Suitability",
                "value": {
                    "mean": avg,
                    "distance": {
                        "value": searchRadius,
                        "units": "meters"
                    },
                    "observations": {
                        "requested": kNeighbors,
                        "found": count
                    }
                }
            }

        return Query(queryString, parser)

@attr.s
class Observations(object):
    """
    Observations are individual time-stamped members of Datastreams
    """
    phenomenonTime: datetime = attr.ib(default=None)  # timestamp, doesn't enforce specific format
    result: Any = attr.ib(default=None)  # value of the observation
    resultTime: datetime = attr.ib(default=None)
    resultQuality: Any = attr.ib(default=None)
    validTime: (datetime, datetime) = attr.ib(default=None)  # time period
    parameters: dict = attr.ib(default=None)

    @property
    def outOfRange(self, maximum, minimum=0.0):
        """
        True if value is outside the given range
        """
        return (self.result > maximum) | (self.result < minimum)


@attr.s
class ObservedProperties(object):
    """
    Create a property, but do not associate any data streams with it
    """
    name: str = attr.ib(default=None)
    description: str = attr.ib(default=None)
    definition: str = attr.ib(default=None)  #  URL to reference defining the property


@attr.s
class Providers(object):
    """
    Providers are generally organization or enterprise sub-units. This is used to
    route ingress and determine implicit permissions for data access, sharing, and
    attribution. 
    """
    name: str = attr.ib(default=None)
    domain: str = attr.ib(default=None)
    apiKey: str = attr.ib(default=attr.Factory(lambda: token_urlsafe(64)))
    secretKey: str = attr.ib(default=None)
    tokenDuration: int = attr.ib(default=600)


@attr.s
class Sensors(object):
    """
    Sensors are devices that observe processes
    """
    name: str = attr.ib(default=None)
    description: str = attr.ib(default=None)
    encodingType: str = attr.ib(default=None)  # metadata encoding
    metadata: Any = attr.ib(default=None)


@attr.s
class TaskingCapabilities(object):
    """
    Abstract tasking class mapping I/O and generating signal.
    """
    name: str = attr.ib(default=None)
    creationTime: float = attr.ib(default=attr.Factory(time))
    taskingParameters: dict = attr.ib(default=None)


@attr.s
class Tasks(object):
    """
    Tasks are pieces of work that are done asynchronously by humans or machines.
    """
    creationTime: float = attr.ib(default=attr.Factory(time))
    taskingParameters: dict = attr.ib(default=None)


@attr.s
class Things(object):
    """
    A thing is an object of the physical or information world that is capable of of being identified
    and integrated into communication networks.
    """
    name: str = attr.ib(default=None)
    description: str = attr.ib(default=None)
    properties: dict = attr.ib(default=None)


@attr.s
class User(object):
    """
    Create a user entity. Users contain authorization secrets, and do not enter/leave
    the system through the same routes as normal Entities
    """
    ip: str = attr.ib(default=None)
    __symbol: str = attr.ib(default="u")
    name: str = attr.ib(default=None)
    credential: str = attr.ib(default=None)
    validated: bool = attr.ib(default=True)
    description: str = attr.ib(default=None)
