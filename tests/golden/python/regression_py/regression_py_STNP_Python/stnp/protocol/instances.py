from stnp.core import InstanceDefinition
from .modules import *

LinkMain = InstanceDefinition(name='LinkMain', id=1, module=Link)
SensorFront = InstanceDefinition(name='SensorFront', id=2, module=Sensor)
SensorRear = InstanceDefinition(name='SensorRear', id=3, module=Sensor)

INSTANCES = {
    'LinkMain': LinkMain,
    'SensorFront': SensorFront,
    'SensorRear': SensorRear,
}
