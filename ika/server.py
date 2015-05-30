import asyncio
import inspect
import re
from importlib import import_module

from ika.classes import Channel, User
from ika.conf import settings
from ika.constants import Versions
from ika.event import EventHandler
from ika.logger import logger
from ika.utils import ircutils, timeutils


RE_SERVER = re.compile(r'^:(\w{3}) ')
RE_USER = re.compile(r'^:(\w{9}) ')


class Server:
    def __init__(self):
        self.name = settings.server.name
        self.description = settings.server.description
        self.sid = settings.server.sid
        self.link = settings.link
        self.ev = EventHandler()
        self.services = dict()
        self.services_instances = list()
        self.users = dict()
        self.channels = dict()

    @asyncio.coroutine
    def connect(self):
        self.reader, self.writer = yield from asyncio.open_connection(self.link.host, self.link.port)
        logger.debug('Connected')
        self.writeline('SERVER {} {} 0 {} :{}',
            self.name, self.link.password, self.sid, self.description
        )
        while 1:
            line = yield from self.readline()
            if not line:
                continue
            if RE_SERVER.match(line):
                server, command, *params = ircutils.parseline(line)
                sender = server
                if command == 'PING':
                    self.writeserverline('PONG {} {}', self.sid, self.link.sid)
                elif command == 'ENDBURST':
                    for service in self.services_instances:
                        service.register_modules()
                    if settings.admin_channel in self.channels:
                        timestamp = self.channels[settings.admin_channel].timestamp
                        modes = self.channels[settings.admin_channel].modes
                    else:
                        timestamp = timeutils.unixtime()
                        modes = ''
                    self.writeserverline('FJOIN {} {} +{} :{}', settings.admin_channel, timestamp, modes,
                        ' '.join(map(lambda x: 'o,{}'.format(x), self.services.keys())))
                elif command == 'UID':
                    self.users[params[0]] = User(*params)
                elif command == 'FJOIN':
                    channel = params[0]
                    if channel in self.channels:
                        self.channels[channel].fjoin(self.users, *params)
                    else:
                        self.channels[channel] = Channel(self.users, *params)
            elif RE_USER.match(line):
                uid, command, *params = ircutils.parseline(line)
                sender = uid
                user = self.users[uid]
                if command == 'PRIVMSG':
                    target = params[0]
                    if target.startswith(self.sid):
                        self.services[target].process_command(sender, *params[1:])
                elif command == 'NICK':
                    user.nick = params[0]
                elif command == 'PART':
                    channel = params[0]
                    if channel in self.channels:
                        self.channels[channel].remove_user(user)
                elif command == 'QUIT':
                    for _, channel in self.users[uid].channels.items():
                        channel.remove_user(user)
                        del self.users[uid]
            else:
                command, *params = ircutils.parseline(line)
                sender = None
                if command == 'SERVER':
                    try:
                        assert params[0] == self.link.name
                        assert params[1] == self.link.password
                    except AssertionError:
                        self.writeline('ERROR :Server information doesn\'t match.')
                        break
                    else:
                        self.link.sid = params[3]
                        self.writeserverline('BURST {}', timeutils.unixtime())
                        self.writeserverline('VERSION :{} {}', Versions.IKA, self.name)
                        idx = 621937810 # int('AAAAAA', 36)
                        for service in self.services_instances:
                            service.id = ircutils.base36encode(idx)
                            names = list(service.aliases)
                            names.insert(0, service.name)
                            for name in names:
                                uid = '{}{}'.format(self.sid, ircutils.base36encode(idx))
                                self.writeserverline('UID {uid} {timestamp} {nick} {host} {host} {ident} 0 {timestamp} + :{gecos}',
                                    uid=uid,
                                    nick=name,
                                    ident=service.ident,
                                    host=self.name,
                                    gecos=service.gecos,
                                    timestamp=timeutils.unixtime(),
                                )
                                self.writeuserline(uid, 'OPERTYPE Services')
                                self.services[uid] = service
                                idx += 1
                        self.writeserverline('ENDBURST')
            if hasattr(self.ev, command):
                getattr(self.ev, command).fire(sender, *params)
            # TODO: Implement each functions
        logger.debug('Disconnected')

    @asyncio.coroutine
    def readline(self):
        line = yield from self.reader.readline()
        if line == b'':
            raise RuntimeError('Disconnected')
        line = line.decode().rstrip('\r\n')
        logger.debug('>>> {}'.format(line))
        return line

    def writeline(self, line, *args, **kwargs):
        if isinstance(line, str):
            line = line.format(*args, **kwargs)
        self.writer.write(line.encode() + b'\r\n')
        logger.debug('<<< {}'.format(line))

    def writeserverline(self, line, *args, **kwargs):
        prefix = ':{} '.format(self.sid)
        self.writeline(prefix + line, *args, **kwargs)

    def writeuserline(self, uid, line, *args, **kwargs):
        prefix = ':{} '.format(uid)
        self.writeline(prefix + line, *args, **kwargs)

    def register_services(self):
        for modulename in settings.services:
            try:
                module = import_module('ika.services.{}'.format(modulename))
            except ImportError:
                logger.exception('Missing module!')
            else:
                _, cls = inspect.getmembers(module, lambda member: inspect.isclass(member)
                    and member.__module__ == 'ika.services.{}'.format(modulename))[0]
                instance = cls(self)
                self.services_instances.append(instance)
