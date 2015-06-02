import asyncio
from datetime import datetime

from ika.classes import Command
from ika.enums import Permission
from ika.database import Nick, Account, Session


class ChangeName(Command):
    name = '계정명변경'
    aliases = (
        '계정명바꾸기',
        '이름변경',
        '이름바꾸기',
    )
    syntax = '<새 계정명>'
    regex = r'(?P<new_name>\S+)'
    permission = Permission.LOGIN_REQUIRED
    description = (
        '현재 오징어 IRC 네트워크에 로그인되어 있는 계정의 이름을 변경합니다.',
        ' ',
        '이 명령을 사용할 시 현재 로그인되어 있는 계정의 이름을 변경합니다.',
        '기존 계정에 이미 \x02그룹\x02 명령을 이용해 추가가 완료되어 있는 닉네임중 하나를 선택할 수 있습니다.',
        '계정 이름이 바뀐 후에는 기존 계정명이 보조 계정명(그룹)으로 자동으로 바뀌게 됩니다',
    )

    @asyncio.coroutine
    def execute(self, user, new_name):
        session = Session()
        nick = session.query(Nick).filter(Nick.name == new_name).first()
        if nick:
            if nick in user.account.aliases:
                old_name = user.account.name
                user.account.aliases.append(user.account.name)
                user.account.aliases.remove(nick)
                user.account.name = nick
                session.commit()
                self.service.msg(user, '\x02{}\x02 계정의 대표 닉네임이 \x02{}\x02 로 변경되었습니다.', old_name, new_name)
                return
        self.service.msg(user, '\x02{}\x02 계정에 \x02{}\x02 닉네임이 존재하지 않습니다. \x02/msg {} 그룹\x02 명령을 이용해 해당 닉네임을 계정에 추가해보세요.', user.account.name.name, new_name, self.service.name)