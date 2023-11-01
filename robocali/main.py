from zaber_motion import Units, Library, LogOutputMode
from . import config as conf
from .CaliStage import CaliStage as CaliStage
import serial.tools.list_ports
from os import environ as env
import os.path
import asyncio
import numpy as np

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import set_title
from prompt_toolkit.key_binding import KeyBindings


cs = None

def serial_ports():
    """Retrieves a list of active"""
    ports = serial.tools.list_ports.comports()
    try:
        con_ports = env["PORTS"].split(',')
    except KeyError:
        con_ports = []
    plist = []
    i=1
    for port, desc, _ in sorted(ports):
        slist = [i, port, desc]
        con = " "
        try:
            for con_port in con_ports:
                if con_port in port:
                    con = "*"
                    break
        except TypeError:
            pass
        i = i+1
        slist.append(con)
        plist.append(slist)
    return plist


async def move(axis: str = "", distance: float = 0, home: bool = False,
         abs: bool = False):
    global cs
    cali = cs
    if axis and home:
        axis_obj = cali.axes[axis].get_axis(1).home()
    elif home:
        [asyncio.create_task(cali.home_axis(ax))
         for ax in cali.axis_labels.keys()]
    elif axis:
        if distance == 0:
            print("specify distance with -d")
            return
        try:
            mtask = asyncio.create_task(cali.move_axis(axis, distance,
                                                       abs=abs))
        except ValueError:
            print(f"axis label {axis} is not valid")
            return

def format_scope(val, units=None):
    if isinstance(val, list):
        pass
    else:
        val = [val]
    if units:
        data = [i.get_data(units) for i in val]
    else:
        data = [i.get_data() for i in val]
    data = np.array(data).T
    time = np.array([list(j) for j in zip([val[0].get_sample_time(i) for i in
                     range(data.shape[0])])])
    data = np.hstack([time, data])
    return data


async def calibrate(axis_label, up_mm, low_mm, step_mm, zlim1, zlim2):
    global cs
    low_mm = float(low_mm)
    up_mm = float(up_mm)
    step_mm = float(step_mm)
    zlim1 = float(zlim1)
    zlim2 = float(zlim2)
    coords = np.arange(up_mm, low_mm, step_mm)
    await cs.home_axis('z')
    await cs.move_axis('z', zlim1)
    print('Calibration Starting in ...')
    for i in reversed(range(5)):
        print(i)
        await asyncio.sleep(1)
    for coord in coords:
        await cs.move_axis(axis_label, coord, abs=True)
        await cs.move_axis('z', zlim2, abs=True)
        await cs.move_axis('z', zlim1, abs=True)


async def read(axis: str, param: str, units=None):
    global cs
    cali = cs
    val = await cali.getval(axis, param)
    data = format_scope(val, units=units)
    return data


def soft_error(msg: str):
    print(msg)
    return 1


async def parse(input_: str):
    global cs
    input_ = input_.split(' ')
    if 'list' in input_:
        for num, port, desc, con in serial_ports():
            print("[{}] {}: {} [{}]".format(num, port, desc, con))
    elif 'exit' in input_:
        return 0
    elif 'connect' in input_:
        if len(input_) != 2:
            return soft_error("connect takes exactly one positional arguement")
        port = input_[-1]
        cs.open(port)
    elif 'disconnect' in input_:
        cs.close()
    elif 'home' in input_:
        try:
            await move(home=True)
        except RuntimeError:
            return soft_error("Zaber Stage Not Open")
    elif 'move' in input_:
        try:
            axis = input_[input_.index('-a')+1]
            dist = float(input_[input_.index('-d')+1])
        except (ValueError, IndexError):
            return soft_error("Specify axis with -a and distance with -d")
        except RuntimeError:
            return soft_error("Zaber Stage Not Open")
        try:
            input_.index('--abs')
            await move(axis=axis, distance=dist, abs=True)
        except ValueError:
            await move(axis=axis, distance=dist, abs=False)
        except RuntimeError:
            return soft_error("Zaber Stage Not Open")
    elif 'read' in input_:
        try:
            axis = input_[input_.index('-a')+1]
            param = input_[input_.index('-p')+1]
            rtask = asyncio.create_task(read(axis, param))
            data = await rtask
            print(data[0,1])
        except (ValueError, IndexError):
            return soft_error("Specify axis with -a and param with -p")
        except RuntimeError:
            return soft_error("Zaber Stage Not Open")
    elif 'cali' in input_:
        input_ = input_[input_.index('cali')+1:]
        if 'set' in input_:
            try:
                axis = input_[input_.index('-a')+1]
                if axis == 'z':
                    return soft_error('only x and y are valid'\
                                      'calibration targets')
                elif axis not in list(conf.getval('axis_labels').keys()):
                    return soft_error(f'{axis} is not a valid input')
                env['CALI_AXIS'] = axis
            except (ValueError, IndexError):
                pass
            try:
                step = input_[input_.index('-s')+1]
                try:
                    float(step)
                except ValueError:
                    return soft_error("step must be numeric")
                env['CALI_STEP'] = step
            except (ValueError, IndexError):
                pass
            try:
                zlims = input_[input_.index('-z')+1].split(',')
                if len(zlims) != 2:
                    return soft_error("z limts must be specified as \'l1,l2\'")
                for val in zlims:
                    try:
                        float(val)
                    except ValueError:
                        return soft_error("z lim must be numeric")
                env['CALI_ZLIM1'] = zlims[0]
                env['CALI_ZLIM2'] = zlims[1]
            except (ValueError, IndexError):
                pass
            try:
                if '-u' in input_:
                    try:
                        axis = env['CALI_AXIS']
                    except KeyError:
                        return soft_error("Calibration axis not set")
                    var_name = 'CALI_UPPER'
                elif '-l' in input_:
                    try:
                        axis = env['CALI_AXIS']
                    except KeyError:
                        return soft_error("Calibration axis not set")
                    var_name = 'CALI_LOWER'
                else:
                    raise ValueError
                rtask = asyncio.create_task(read(axis, 'pos',
                                            units=Units.LENGTH_MILLIMETRES))
                data = await rtask
                env[var_name] = str(data[0,1])
            except (ValueError, IndexError):
                pass
            except RuntimeError:
                return soft_error("Zaber Stage Not Open")
        elif 'get' in input_:
            try:
                print('Axis = {}'.format(env['CALI_AXIS']))
                print('Step = {}mm'.format(env['CALI_STEP']))
                print('Upper Limit = {}mm'.format(env['CALI_UPPER']))
                print('Lower Limit = {}mm'.format(env['CALI_LOWER']))
                print('Lower Z Limit = {}mm'.format(env['CALI_ZLIM1']))
                print('Upper Z Limit = {}mm'.format(env['CALI_ZLIM2']))
            except KeyError:
                return soft_error("One or more calibration env vars not set,"\
                                  " run \'cali set\' for info")
        elif 'save' in input_:
            try:
                axis = env['CALI_AXIS']
                step = env['CALI_STEP']
                u_lim = env['CALI_UPPER']
                l_lim = env['CALI_LOWER']
                zlim1 = env['CALI_ZLIM1']
                zlim2 = env['CALI_ZLIM2']
                conf.change_config_val('cali_axis', axis)
                conf.change_config_val('axis_limits', [l_lim, u_lim, step])
                conf.change_config_val('z_limit', [zlim1, zlim2])
            except KeyError:
                return soft_error("One or more calibration env vars not set,"\
                                  " run \'cali set\' for info")
        elif 'load' in input_:
            env['CALI_AXIS'] = conf.getval('cali_axis')
            env['CALI_STEP'] = conf.getval('axis_limits')[2]
            env['CALI_UPPER'] = conf.getval('axis_limits')[1]
            env['CALI_LOWER'] = conf.getval('axis_limits')[0]
            env['CALI_ZLIM1'] = conf.getval('z_limit')[0]
            env['CALI_ZLIM2'] = conf.getval('z_limit')[1]
        elif 'run' in input_:
            try:
                ctask = asyncio.create_task(calibrate(env['CALI_AXIS'],
                                                      env['CALI_UPPER'],
                                                      env['CALI_LOWER'],
                                                      env['CALI_STEP'],
                                                      env['CALI_ZLIM1'],
                                                      env['CALI_ZLIM2']
                                                     )
                                           )
                await ctask
            except KeyError:
                return soft_error("One or more calibration env vars not set, "\
                                  "run \'cali set\' for info")
            except RuntimeError:
                return soft_error("Zaber Stage Not Open")
    else:
        if (len(input_) == 1) and (input_[0] == ''):
            pass
        else:
            return soft_error(f'Unrecognised command {input_}')


async def start_prompt():
    bindings = KeyBindings()
    big_dist = conf.getval("big_move")
    small_dist = conf.getval("small_move")

    @bindings.add("c-i")
    async def _(event):
        asyncio.create_task(event_move("y", small_dist))
    @bindings.add("c-k")
    async def _(event):
        asyncio.create_task(event_move("y", -small_dist))
    @bindings.add("c-j")
    async def _(event):
        asyncio.create_task(event_move("x", small_dist))
    @bindings.add("c-l")
    async def _(event):
        asyncio.create_task(event_move("x", -small_dist))
    @bindings.add("c-u")
    async def _(event):
        asyncio.create_task(event_move("z", small_dist))
    @bindings.add("c-o")
    async def _(event):
        asyncio.create_task(event_move("z", -small_dist))
    @bindings.add("c-w")
    async def _(event):
        asyncio.create_task(event_move("y", big_dist))
    @bindings.add("c-s")
    async def _(event):
        asyncio.create_task(event_move("y", -big_dist))
    @bindings.add("c-a")
    async def _(event):
        asyncio.create_task(event_move("x", big_dist))
    @bindings.add("c-d")
    async def _(event):
        asyncio.create_task(event_move("x", -big_dist))
    @bindings.add("c-q")
    async def _(event):
        asyncio.create_task(event_move("z", big_dist))
    @bindings.add("c-e")
    async def _(event):
        asyncio.create_task(event_move("z", -big_dist))

    history = InMemoryHistory()
    session = PromptSession(history=history, enable_history_search=True)
    while True:
        with patch_stdout():
            try:
                _input = await session.prompt_async("(rcali) $ ",
                                                    key_bindings=bindings)
                arg = await parse(_input)
                if arg == 0:
                    break
            except (EOFError, KeyboardInterrupt):
                return

async def event_move(axis, distance):
    try:
        mtask = asyncio.create_task(move(axis=axis, distance=distance))
    except asyncio.CancelledError:
        print("Prompt terminated before we completed.")


def main():
    global cs
    cs = CaliStage()
    set_title('Robo Cali')
    asyncio.run(start_prompt())


if __name__ == "__main__":
    main()

