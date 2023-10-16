from zaber_motion import Units
from zaber_motion.ascii import Connection
from . import config as conf
import click
import serial.tools.list_ports
from os import environ as env
from pynput.keyboard import Listener


def serial_ports(app_cls):
    ports = serial.tools.list_ports.comports()
    con_port = app_cls.cali_stage.port
    plist = []
    i=1
    for port, desc, _ in sorted(ports):
        slist = [i, port, desc]
        con = " "
        try:
            if con_port in port:
                con = "*"
        except TypeError:
            pass
        i = i+1
        slist.append(con)
        plist.append(slist)
    return plist


def key_control(cali):
    raise NotImplementedError
    #TODO: Just fuck with this til it works, something is up with the library.
    dist = 5
    x_axis = cali.axes['x'].get_axis(1)
    y_axis = cali.axes['y'].get_axis(1)
    z_axis = cali.axes['z'].get_axis(1)
    def on_press(key):
        print('{0} was entered'.format(key))
        #match str(key):
            #case 'w':
            #    move_axis(y_axis, dist)
            #case 's':
            #    move_axis(y_axis, -1*dist)
            #case 'a':
            #    move_axis(x_axis, -1*dist)
            #case 'd':
            #    move_axis(x_axis, -1*dist)
            #case 'q':
            #    move_axis(z_axis, -1*dist)
            #case 'e':
            #    move_axis(z_axis, -1*dist)
            #case _:
            #    click.echo('invalid input {}'.format(key))
    with Listener(on_press=on_press) as listener:
        print(1)
        listener.join()


def z_initiate(app, port):
    if port:
        pass
    elif 'Z_PORT' in env:
        port = env['Z_PORT']
    else:
        port = conf.getval('port')
    cali = app.cali_stage
    cali.open(port)
    env['Z_PORT'] = cali.port
    return cali


def move_axis(axis, dir_mm, abs=False):
    if abs:
        axis.move_absolute(dir_mm, Units.LENGTH_MILLIMETRES)
    else:
        axis.move_relative(dir_mm, Units.LENGTH_MILLIMETRES)


class CaliStage(object):
    def __init__(self):
        self.__axis_labels = conf.getval('axis_labels')
        self.__port = None
        self.__axes = {}
        self.__connection = None

    def open(self, port):
        self.__port = port
        self.__connection = Connection.open_serial_port(port)
        self.__connection.enable_alerts()
        device_list = self.__connection.detect_devices()
        for k, sn in self.__axis_labels.items():
            for axis in device_list:
                if sn in axis.__repr__():
                    self.__axes[k] = axis

    def close(self):
        self.__connection.close()
        self.__port = None

    def __bool__():
        if self.__axes and self.__connection:
            return True
        else:
            return False

    @property
    def axes(self):
        return self.__axes

    @property
    def port(self):
        return self.__port


class App(object):
    def __init__(self):
        self.__cali_stage = CaliStage()

    @property
    def cali_stage(self):
        return self.__cali_stage


pass_app = click.make_pass_decorator(App, ensure=True)
valid_ax = ['x', 'y', 'z']

@click.group
@click.option('--debug/--no-debug', default=False,
              envvar='CALI_DEBUG')
@click.pass_context
def cli(ctx, debug):
    ctx.obj = App()


@cli.command
@click.argument('port', default='')
@click.option('-k', '--key/--no-key', default=False)
@click.option('-h', '--home/--no-home', default=False)
@click.option('-a', '--axis', default='')
@click.option('-d', '--distance', default=0)
@click.option('--abs/--no-abs', default=False)
@pass_app
def move(app, port: str, key: bool, axis: str,
         distance: float, home: bool, abs: bool):
    cali = z_initiate(app, port)
    if key:
        key_control(cali)
    elif axis and home:
        axis_obj = cali.axes[axis].get_axis(1)
        axis_obj.home()
    elif home:
        [ax.get_axis(1).home() for ax in cali.axes.values()]
    elif axis:
        if axis not in valid_ax:
            raise IOError("axis can only be {} not {}".format(valid_ax, axis))
        elif distance == 0:
            raise IOError("specify distance with -d")
        axis_obj = cali.axes[axis].get_axis(1)
        move_axis(axis_obj, distance, abs=abs)


@cli.command
@click.argument('port', default='')
@pass_app
def disconnect(app, port: str):
    app.cali_stage.close()


@cli.command
@click.option('--list/--no-list', default=False)
@pass_app
def port(app, list):
    plist = serial_ports(app)
    if list:
        for num, port, desc, con in plist:
            click.echo("[{}] {}: {} [{}]".format(num, port,
                                                 desc, con))

