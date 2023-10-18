from zaber_motion import Units
from zaber_motion.ascii import Connection
from . import config as conf
from .CaliStage import CaliStage as CaliStage
import serial.tools.list_ports
from os import environ as env
import os.path
import asyncio

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import set_title
from prompt_toolkit.application import in_terminal, run_in_terminal
from prompt_toolkit.key_binding import KeyBindings


cs = None


def serial_ports():
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
        [ax.get_axis(1).home() for ax in cali.axes.values()]
    elif axis:
        if distance == 0:
            print("specify distance with -d")
            return
        try:
            await cali.move_axis(axis, distance, abs=abs)
        except ValueError:
            print(f"axis label {axis} is not valid")
            return


async def parse(input_: str):
    global cs
    input_ = input_.split(' ')
    if 'list' in input_:
        for num, port, desc, con in serial_ports():
            print("[{}] {}: {} [{}]".format(num, port, desc, con))
        return None
    elif 'exit' in input_:
        return 0
    elif 'connect' in input_:
        if len(input_) != 2:
            print("connect takes exactly one positional arguement")
            return 1
        port = input_[-1]
        cs.open(port)
    elif 'disconnect' in input_:
        cs.close()
    elif 'home' in input_:
        await move(home=True)
    elif 'move' in input_:
        axis = input_[input_.index('-a')+1]
        dist = float(input_[input_.index('-d')+1])
        try: 
            input_.index('--abs')
            await move(axis=axis, distance=dist, abs=True)
        except ValueError:
            await move(axis=axis, distance=dist, abs=False)
    else:
        print(f'Unrecognised command {input_}')


def main():
    bindings = KeyBindings()

    @bindings.add("c-w")
    async def _(event):
        try:
            await move(axis="y", distance=0.5)
        except asyncio.CancelledError:
            print("Prompt terminated before we completed.")

    @bindings.add("c-s")
    async def _(event):
        try:
            await move(axis="y", distance=-0.5)
        except asyncio.CancelledError:
            print("Prompt terminated before we completed.")

    @bindings.add("c-a")
    async def _(event):
        try:
            await move(axis="x", distance=0.5)
        except asyncio.CancelledError:
            print("Prompt terminated before we completed.")

    @bindings.add("c-d")
    async def _(event):
        try:
            await move(axis="x", distance=-0.5)
        except asyncio.CancelledError:
            print("Prompt terminated before we completed.")

    @bindings.add("c-q")
    async def _(event):
        try:
            await move(axis="z", distance=0.5)
        except asyncio.CancelledError:
            print("Prompt terminated before we completed.")

    @bindings.add("c-e")
    async def _(event):
        try:
            await move(axis="z", distance=-0.5)
        except asyncio.CancelledError:
            print("Prompt terminated before we completed.")

    global cs
    cs = CaliStage()
    set_title('Robo Cali')
    history = InMemoryHistory()
    session = PromptSession(history=history, enable_history_search=True)
    while True:
        with patch_stdout():
            arg = asyncio.run(parse(session.prompt("(rcali) $ ",
                                                   key_bindings=bindings)))
            if arg == 0:
                break


if __name__ == "__main__":
    main()

