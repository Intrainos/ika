import asyncio
from datetime import datetime

from ika.classes import Command
from ika.database import Nick, Account, Session


class Register(Command):
    name = '로그아웃'
    aliases = (
        '인증해제',
    )
    description = (
        '오징어 IRC 네트워크에서 로그아웃합니다.',
        ' ',
        '이 명령을 사용할 시 오징어 IRC 네트워크에서 로그아웃합니다.',
    )

    @asyncio.coroutine
    def execute(self, uid, *params):
        user = self.service.server.users[uid]
        if 'accountname' in user.metadata:
            self.service.server.writeserverline('METADATA {} accountname :', uid)
            del user.metadata['accountname']
            self.service.msg(uid, '로그아웃했습니다.')
