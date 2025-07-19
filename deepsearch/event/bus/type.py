from enum import Enum
from typing import Literal

BusName = Literal['inmemory', 'zmq', 'timeseries', 'composite']

class BusName(str, Enum):
    INMEM = "inmem"
    REDIS = "redis"
    ZMQ = "zmq"
    TIMESERIES = "timeseries"
