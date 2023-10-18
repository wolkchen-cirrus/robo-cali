from zaber_motion import Units
from zaber_motion.ascii import Connection
from zaber_motion import CommandFailedException
from . import config as conf
from os import environ as env
import asyncio


class CaliStage(object):
    def __init__(self):
        self.__axis_labels = conf.getval('axis_labels')
        self.__valid_ax = ['x', 'y', 'z']
        self.__port = None
        self.__axes = {}
        self.__connection = None

    def open(self, port):
        try:
            _ = env['PORTS']
            print(f"Device already detected at {port}, disconnect")
            return
        except KeyError:
            pass
        self.__port = port
        self.__connection = Connection.open_serial_port(port)
        self.__connection.enable_alerts()
        device_list = self.__connection.detect_devices()
        for k, sn in self.__axis_labels.items():
            for axis in device_list:
                if sn in axis.__repr__():
                    self.__axes[k] = axis
        env["PORTS"] = port

    def close(self):
        if self.__check_connection():
            self.__connection.close()
            self.__connection = None
            try:
                if self.__port in env["PORTS"]:
                    env.pop('PORTS')
            except KeyError:
                pass
            self.__port = None

    def __bool__(self):
        if self.__axes and self.__connection:
            return True
        else:
            return False

    async def move_axis(self, axis_label: str, dir_mm: int, abs=False):
        if self.__check_connection():
            if axis_label not in self.__valid_ax:
                raise ValueError(f'only {self.__valid_ax} can be axis labels')
            axis = self.axes[axis_label].get_axis(1)
            try:
                if abs:
                    axis.move_absolute(dir_mm, Units.LENGTH_MILLIMETRES)
                else:
                    axis.move_relative(dir_mm, Units.LENGTH_MILLIMETRES)
            except CommandFailedException:
                print(f"Distance {dir_mm} is out of range with abs={abs}")
                return

    def __check_connection(self):
        if bool(self):
            return True
        else:
            print("Zaber Stage Not Open")
            return False

    @property
    def axes(self):
        return self.__axes

    @property
    def port(self):
        return self.__port

