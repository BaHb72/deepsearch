from enum import Enum


class BusName(str, Enum):
    INMEM = "inmem"
    REDIS = "redis"
    ZMQ = "zmq"
